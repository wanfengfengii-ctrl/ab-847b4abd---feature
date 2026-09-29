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

# 两段超温各自不足 600s（约 187.8s / 491.0s），中间回落：
# * 旧口径（不启用复冷记忆）→ 放行；
# * 启用复冷记忆（复冷阈值 4℃ / 确认 600s）后，首次复冷仅约 574.8s 即被回暖
#   打断（不足），两轮暴露同轮累计达 600s → 拒收，并须指明第 1 次复冷不足。
_RECOOL_RECORDS = [
    {"time": 0, "box_temp": 3.0, "ambient_temp": 25.0, "lid_open": False},
    {"time": 300, "box_temp": 7.709666, "ambient_temp": 0.0, "lid_open": False},
    {"time": 900, "box_temp": 1.04339, "ambient_temp": 0.0, "lid_open": False},
    {"time": 1200, "box_temp": 9.580828, "ambient_temp": 25.0, "lid_open": False},
    {"time": 1600, "box_temp": 9.743104, "ambient_temp": 0.0, "lid_open": False},
    {"time": 2200, "box_temp": 1.318586, "ambient_temp": 0.0, "lid_open": False},
]
_RECOOL_PARAMS = {
    "tau_closed": 300,
    "tau_open": 90,
    "box_temp_limit": 8.0,
    "exposure_limit_seconds": 600,
}
RECOOL_INSUFFICIENT_OLD = {"records": _RECOOL_RECORDS, "parameters": dict(_RECOOL_PARAMS)}
RECOOL_INSUFFICIENT_NEW = {
    "records": _RECOOL_RECORDS,
    "parameters": {
        **_RECOOL_PARAMS,
        "recool": {"enabled": True, "recool_threshold": 4.0, "confirm_seconds": 600.0},
    },
}

# 首次复冷连续不高于 4℃ 达到 600s（确认点跨记录，约 1096.9s）→ 清零，
# 后段约 486s 超温作为新一轮（不足限额）→ 放行。
_RECOOL_RESET_RECORDS = [
    {"time": 0, "box_temp": 3.0, "ambient_temp": 25.0, "lid_open": False},
    {"time": 300, "box_temp": 7.709666, "ambient_temp": 0.0, "lid_open": False},
    {"time": 1100, "box_temp": 0.535694, "ambient_temp": 0.0, "lid_open": False},
    {"time": 1700, "box_temp": 14.264189, "ambient_temp": 25.0, "lid_open": False},
    {"time": 1850, "box_temp": 13.161869, "ambient_temp": 0.0, "lid_open": False},
    {"time": 2400, "box_temp": 2.104316, "ambient_temp": 0.0, "lid_open": False},
]
RECOOL_RESET_NEW = {
    "records": _RECOOL_RESET_RECORDS,
    "parameters": {
        **_RECOOL_PARAMS,
        "recool": {"enabled": True, "recool_threshold": 4.0, "confirm_seconds": 600.0},
    },
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

        r = c.post("/api/audit", json=RECOOL_INSUFFICIENT_OLD)
        check(r.status_code == 200, "复冷场景（旧口径）HTTP 200")
        old_body = r.json()
        check(old_body["status"] == "pass", "旧口径：两段各自不足限额 → pass/放行")
        check("recool" not in old_body, "未启用复冷记忆时响应不含 recool 证据（旧响应不变）")

        r = c.post("/api/audit", json=RECOOL_INSUFFICIENT_NEW)
        check(r.status_code == 200, "复冷场景（新口径）HTTP 200")
        body = r.json()
        check(body["status"] == "reject", "新口径：复冷不足、累计暴露达限 → reject/拒收")
        rc = body["recool"]
        check(rc is not None and rc["enabled"] is True, "返回 recool 复冷记忆证据块")
        check(len(rc["rounds"]) == 1 and not rc["rounds"][0]["reset"], "复冷不足时始终同一轮且未清零")
        check(
            rc["rounds"][0]["hot_exposure_seconds"] >= 600,
            "该轮累计热暴露（跨多段，含暂停带）达到限额 600s",
        )
        check(len(rc["resets"]) == 0, "复冷不足 → 无清零事件")
        cands = rc["recool_candidates"]
        check(any(x["status"] == "rewarmed" for x in cands), "存在被回暖打断的复冷候选区间")
        ins = rc["insufficient_recool"]
        check(ins is not None and ins["reason"] == "rewarmed", "指出具体哪次复冷不足（回暖打断）")
        ff = rc["first_failure_time"]
        check(
            ff is not None
            and ff["insufficient_recool_candidate_index"] == ins["candidate_index"],
            "首个失效时刻绑定到那次不足的复冷尝试",
        )
        # 失效发生在第二段超温内部（首个解析失效时刻），且早于该段结束
        second_iv = body["exceedance_intervals"][1]
        check(
            second_iv["elapsed_start_seconds"]
            < ff["elapsed_seconds"]
            < second_iv["elapsed_end_seconds"],
            "首个失效时刻位于后段超温内部（累计达标解析时刻，非采样点）",
        )
        # 原口径证据仍保留，可与新口径对照
        check(len(body["exceedance_intervals"]) == 2, "原连续超温区间证据保留供新旧口径对照")

        r = c.post("/api/audit", json=RECOOL_RESET_NEW)
        body = r.json()
        check(r.status_code == 200 and body["status"] == "pass", "有效复冷清零后新一轮不足限额 → pass/放行")
        rc = body["recool"]
        check(len(rc["resets"]) == 1, "有效复冷产生 1 个清零事件")
        check(len(rc["rounds"]) == 2, "清零后开始新一轮（共 2 轮）")
        check(rc["first_failure_time"] is None, "有效复冷口径无失效时刻")

        r = c.post(
            "/api/audit",
            json={
                "records": _RECOOL_RECORDS,
                "parameters": {
                    **_RECOOL_PARAMS,
                    "recool": {"enabled": True, "recool_threshold": 9.0, "confirm_seconds": 600.0},
                },
            },
        )
        check(
            r.status_code == 422 and r.json()["errors"][0]["code"] == "bad_param",
            "复冷阈值不低于原限温判为 bad_param (422)",
        )

    print("冒烟全部通过。")


if __name__ == "__main__":
    main()
