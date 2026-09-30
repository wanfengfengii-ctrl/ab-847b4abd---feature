"""温控审计 API 冒烟脚本（verify 服务内运行）。

校验：健康检查、参数约定接口、拒收裁决（含连续超温区间证据与最早失效时刻）、
数据不合法 (422)。任何断言失败即以非零退出码结束容器。
"""
from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("AUDIT_BASE_URL", "http://app:8000").rstrip("/")

REJECT_PAYLOAD = {
    "records": [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 25.0, "lid_open": False},
        {"time": 60, "box_temp": 7.806654, "ambient_temp": 25.0, "lid_open": False},
        {"time": 1560, "box_temp": 7.254505, "ambient_temp": 3.0, "lid_open": False},
        {"time": 2460, "box_temp": 3.211819, "ambient_temp": 3.0, "lid_open": False},
        {"time": 3360, "box_temp": 3.010546, "ambient_temp": 3.0, "lid_open": False},
    ],
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600,
    },
}

PASS_PAYLOAD = {
    "records": [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 3.0, "lid_open": False},
        {"time": 300, "box_temp": 3.551819, "ambient_temp": 3.5, "lid_open": False},
        {"time": 600, "box_temp": 3.703003, "ambient_temp": 4.0, "lid_open": False},
        {"time": 900, "box_temp": 3.817165, "ambient_temp": 3.8, "lid_open": False},
    ],
    "parameters": {
        "tau_closed": 300,
        "tau_open": 90,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600,
    },
}

# 复冷记忆场景（tau=300，限温 8℃，复冷阈值 5℃，限额 400s）：
# 热相 137.1s → 连续 <=5℃ 约 650.3s → 热相 325.6s。
# 旧口径两段各自不足 400s 本应放行；复冷记忆开启后：
#   确认 600s → 复冷有效清零，仍放行（新口径的清零分支）；
#   确认 700s → 复冷不足（650.3<700），累计 137.1+… 达 400s 在后段拒收。
def _make_records(times, ambs, lids, t0_box, tau_closed, tau_open):
    """与后端测试参考实现一致的自洽记录生成（冒烟脚本独立内联，不依赖 backend 包）。"""
    def env(a, c, ts, dur):
        return lambda tt: a + (c - a) * (tt - ts) / dur

    def rk4(T, t, h, f, tau):
        k1 = (f(t) - T) / tau
        k2 = (f(t + h / 2) - (T + h * k1 / 2)) / tau
        k3 = (f(t + h / 2) - (T + h * k2 / 2)) / tau
        k4 = (f(t + h) - (T + h * k3)) / tau
        return T + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6

    out = [{"time": times[0], "box_temp": t0_box, "ambient_temp": ambs[0], "lid_open": lids[0]}]
    T, t, dt = t0_box, float(times[0]), 0.1
    for i in range(len(times) - 1):
        dur = float(times[i + 1] - times[i])
        f = env(ambs[i], ambs[i + 1], t, dur)
        tau = float(tau_open if lids[i] else tau_closed)
        for _ in range(int(round(dur / dt))):
            T = rk4(T, t, dt, f, tau)
            t += dt
        out.append(
            {"time": times[i + 1], "box_temp": T, "ambient_temp": ambs[i + 1], "lid_open": lids[i + 1]}
        )
    return out


RECOOL_RECORDS = _make_records(
    [0, 100, 101, 1100, 1101, 1500],
    [25.0, 25.0, 3.0, 3.0, 25.0, 25.0],
    [False] * 6,
    4.0,
    300.0,
    90.0,
)
RECOOL_PARAMS = {
    "tau_closed": 300,
    "tau_open": 90,
    "box_temp_limit": 8.0,
    "exposure_limit_seconds": 400,
}



def check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"SMOKE FAIL: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ {msg}")


def main() -> None:
    print(f"目标审计服务：{BASE}")
    with httpx.Client(base_url=BASE, timeout=10) as c:
        r = c.get("/healthz")
        check(r.status_code == 200 and r.json().get("status") == "ok", "GET /healthz 返回 200/ok")

        r = c.get("/api/audit/schema")
        check(r.status_code == 200 and "tau_closed" in r.json()["parameters"], "GET /api/audit/schema 含模型参数约定")

        r = c.post("/api/audit", json=REJECT_PAYLOAD)
        check(r.status_code == 200, f"拒收场景 HTTP 200（实际 {r.status_code}）")
        body = r.json()
        check(body["status"] == "reject", "拒收场景裁决为 reject/拒收")
        intervals = body["exceedance_intervals"]
        check(len(intervals) >= 1, "至少报告 1 个连续超温区间")
        iv = intervals[0]
        check(iv["start_time"] < iv["end_time"], "超温区间起点早于终点")
        check(iv["duration_seconds"] >= 600, "超温区间持续时长达到允许连续暴露时长")
        ff = body.get("first_failure_time")
        check(ff is not None, "给出最早失效时刻")
        check(
            abs(ff["elapsed_seconds"] - (iv["elapsed_start_seconds"] + 600)) < 1e-6,
            "最早失效时刻 = 区间起点 + 允许暴露时长",
        )
        check(len(body["curve"]) > len(REJECT_PAYLOAD["records"]), "返回稠密箱温连续曲线（非仅离散读数）")
        check(any(s["max_temp"]["kind"] == "interior" for s in body["segments"]), "存在段内解析极值证据")

        r = c.post("/api/audit", json=PASS_PAYLOAD)
        body = r.json()
        check(r.status_code == 200 and body["status"] == "pass", "放行场景裁决为 pass/放行")
        check(body["first_failure_time"] is None, "放行场景无失效时刻")

        r = c.post("/api/audit", json={"records": [], "parameters": {}})
        check(r.status_code == 422 and r.json()["status"] == "invalid", "空记录判为数据不合法 (422)")

        bad = {
            "records": [
                {"time": 0, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 0, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 1, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
                {"time": 2, "box_temp": 4, "ambient_temp": 5, "lid_open": False},
            ],
            "parameters": {
                "tau_closed": 300,
                "tau_open": 90,
                "box_temp_limit": 8,
                "exposure_limit_seconds": 600,
            },
        }
        r = c.post("/api/audit", json=bad)
        check(
            r.status_code == 422 and r.json()["errors"][0]["code"] == "time_not_strict",
            "时间非严格递增判为 time_not_strict",
        )

        # ---------- 复冷记忆：新旧口径冒烟对照 ----------
        r = c.post("/api/audit", json={"records": RECOOL_RECORDS, "parameters": RECOOL_PARAMS})
        legacy = r.json()
        check(r.status_code == 200, "复冷场景未启用时 HTTP 200")
        check(legacy["status"] == "pass", "复冷场景旧口径放行（两段各自不足限额）")
        check("recooling" not in legacy, "未启用复冷时响应不含 recooling 字段（旧证据不变）")

        r = c.get("/api/audit/schema")
        check("recooling" in r.json(), "schema 含复冷记忆字段约定")

        reset_payload = {
            "records": RECOOL_RECORDS,
            "parameters": RECOOL_PARAMS,
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 600.0},
        }
        r = c.post("/api/audit", json=reset_payload)
        ok = r.json()
        check(r.status_code == 200 and ok["status"] == "pass", "连续复冷达确认时长清零后放行")
        check(ok["first_failure_time"] is None, "有效复冷后无失效时刻")
        reasons = {rd["end_reason"] for rd in ok["recooling"]["rounds"]}
        check("recool_confirmed" in reasons, "报告清零轮次（recool_confirmed）")
        confirmed = [ct for ct in ok["recooling"]["candidates"] if ct["outcome"] == "recool_confirmed"]
        check(len(confirmed) == 1 and confirmed[0]["shortfall_seconds"] == 0, "复冷候选达确认时长、缺口为 0")

        bad_recool_payload = {
            "records": RECOOL_RECORDS,
            "parameters": RECOOL_PARAMS,
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 700.0},
        }
        r = c.post("/api/audit", json=bad_recool_payload)
        rej = r.json()
        check(r.status_code == 200 and rej["status"] == "reject", "复冷不足导致后段超温后拒收")
        ff2 = rej["first_failure_time"]
        check(ff2 is not None, "复冷不足场景给出首个失效时刻")
        check(ff2["segment_index"] == 4, "失效定位到后段（第 5 段，0 基）")
        cited = rej["recooling"]["insufficient_recool_at_failure"]
        check(cited is not None and cited["outcome"] == "rewarm_above_recool", "指出此前哪次复冷不足")
        check(ff2["elapsed_seconds"] > cited["elapsed_end_seconds"], "失效时刻晚于不足复冷结束时刻")

        bad_cfg = {
            "records": RECOOL_RECORDS,
            "parameters": RECOOL_PARAMS,
            "recooling": {"enabled": True, "recool_temp": 9.0, "confirm_seconds": 600},
        }
        r = c.post("/api/audit", json=bad_cfg)
        check(r.status_code == 422, "复冷阈值不低于限温判 422")
        check(r.json()["errors"][0]["code"] == "bad_recooling", "错误码 bad_recooling")

    print("冒烟全部通过。")


if __name__ == "__main__":
    main()
