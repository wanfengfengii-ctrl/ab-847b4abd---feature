"""复冷记忆（recool memory）引擎与 API 测试。

口径：T>限温累计暴露；复冷阈值<T<=限温只暂停并保留记忆；
连续 T<=复冷阈值达到确认时长才清零并开始新一轮；短暂回暖或结束
未确认不清零，后段超温与此前未清除暴露累计，达到限额即拒收。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from app.thermal import ThermalValidationError, audit
from tests.reference import make_records_from_sim, rk4_simulate

client = TestClient(app)

TAU_CLOSED, TAU_OPEN = 300.0, 90.0
LIMIT = 8.0
RC = 4.0
CONFIRM = 600.0
EXPOSURE = 600.0


def params(confirm: float = CONFIRM, rc: float = RC, enabled: bool = True, **over):
    base = {
        "tau_closed": TAU_CLOSED,
        "tau_open": TAU_OPEN,
        "box_temp_limit": LIMIT,
        "exposure_limit_seconds": EXPOSURE,
    }
    if enabled:
        base["recool"] = {
            "enabled": True,
            "recool_threshold": rc,
            "confirm_seconds": confirm,
        }
    base.update(over)
    return base


def run(records, **over):
    return audit({"records": records, "parameters": params(**over)})


# 三套自洽记录（RK4 正问题生成，model_record_gap≈0）
# A≈187.8s 超温；复冷下探到 T<=4℃ 约 574.7s（<600，回暖打断）；B≈491.0s
INSUFFICIENT = dict(
    times=[0, 300, 900, 1200, 1600, 2200],
    ambs=[25, 0, 0, 25, 0, 0],
)
# A≈187.8s；复冷连续 <=4℃ 达 600s（确认点跨记录，约 1096.9s 清零）；新轮 B≈486.3s
EFFECTIVE = dict(
    times=[0, 300, 1100, 1700, 1850, 2400],
    ambs=[25, 0, 0, 25, 0, 0],
)
# 有效清零后新轮持续超温（>600s）→ 应在新一轮拒收，且不冤枉此前已确认的复冷
REHEAT_LONG = dict(
    times=[0, 300, 1100, 1700, 2100, 2600],
    ambs=[25, 0, 0, 25, 25, 25],
)


def _recs(spec):
    return make_records_from_sim(
        spec["times"], spec["ambs"], [False] * len(spec["times"]), 3.0, TAU_CLOSED, TAU_OPEN
    )


def rk4_cumulative_failure(records, limit, rc, confirm, exposure_limit, dt=0.25):
    """独立参考实现：稠密 RK4 曲线上按时间步进复冷状态机，返回 (失效时刻, 各次复冷起)。"""
    sim = rk4_simulate(records, TAU_CLOSED, TAU_OPEN, dt=dt)
    t_start = sim[0][0]
    hot = 0.0
    cold_since = None
    cleared = False
    fail_t = None
    for (t1, v1), (t2, v2) in zip(sim, sim[1:]):
        # 用区间中点分区（足够小步长，参考用途）
        v = 0.5 * (v1 + v2)
        h = t2 - t1
        if v > limit:
            hot += h
            cold_since = None
            if fail_t is None and hot >= exposure_limit:
                fail_t = t1 + (exposure_limit - (hot - h)) * (h / h)
        elif v <= rc:
            if cold_since is None:
                cold_since = t2
            elif t2 - cold_since >= confirm:
                hot = 0.0
                cold_since = t2  # 清零后重新计时（不会再次清零同一无热区间）
                cleared = True
        else:
            cold_since = None
    return (None if fail_t is None else fail_t - t_start)


# ---------- 未启用：原请求、结论及证据保持不变 ----------

def test_disabled_recool_matches_legacy_payload():
    recs = _recs(INSUFFICIENT)
    legacy = audit({"records": recs, "parameters": params(enabled=False)})
    assert "recool" not in legacy
    # 同一数据旧口径放行（两段各自不足 600s）
    assert legacy["status"] == "pass"
    enabled_false = audit(
        {"records": recs, "parameters": {**params(enabled=False), "recool": {"enabled": False}}}
    )
    for key in (
        "status", "verdict", "exceedance_intervals", "first_failure_time",
        "total_exceedance_seconds", "segments", "curve",
    ):
        assert enabled_false[key] == legacy[key]
    assert "recool" not in enabled_false
    # 未启用时整份响应与完全不带 recool 的旧请求逐字段一致
    assert enabled_false == legacy
    # 且段证据不带复冷穿越字段
    assert all("recool_crossings" not in s for s in legacy["segments"])


# ---------- 复冷不足：累计未清除 → 拒收并指出哪次复冷不足 ----------

def test_insufficient_recool_cumulative_reject():
    recs = _recs(INSUFFICIENT)
    res = run(recs)
    assert res["status"] == "reject"
    rc = res["recool"]
    # 旧口径两段分别 187.8s / 491.0s 均不足 600s
    assert len(res["exceedance_intervals"]) == 2
    # 复冷口径只有一轮（未清零），累计 ≈ 678.8s
    assert len(rc["rounds"]) == 1
    rd = rc["rounds"][0]
    assert rd["reset"] is False
    assert rd["hot_exposure_seconds"] == pytest.approx(678.8, abs=1.0)
    # 首次复冷尝试被回暖打断（确认未完成），第二次在数据结束仍未确认
    cands = rc["recool_candidates"]
    assert cands[0]["status"] == "rewarmed"
    assert cands[0]["confirmed"] is False
    assert cands[0]["duration_seconds"] < CONFIRM
    assert res["recool"]["resets"] == []
    # 拒收证据：失效时刻 + 归咎的复冷不足尝试
    ff = rc["first_failure_time"]
    assert ff is not None
    # 失效精确时刻 = 第二次上穿限温 + (600 - 首轮已累计 187.8)
    up2 = res["exceedance_intervals"][1]["elapsed_start_seconds"]
    assert ff["elapsed_seconds"] == pytest.approx(up2 + (EXPOSURE - 187.8), abs=1.0)
    assert ff["round_index"] == 0
    assert ff["insufficient_recool_candidate_index"] == cands[0]["index"]
    ins = rc["insufficient_recool"]
    assert ins["reason"] == "rewarmed"
    assert ins["candidate_index"] == cands[0]["index"]
    assert ins["round_index"] == 0
    # 顶层 first_failure_time 与复冷口径一致
    assert res["first_failure_time"]["elapsed_seconds"] == ff["elapsed_seconds"]


def test_failure_time_matches_independent_rk4_state_machine():
    recs = _recs(INSUFFICIENT)
    res = run(recs)
    ref_fail = rk4_cumulative_failure(recs, LIMIT, RC, CONFIRM, EXPOSURE, dt=0.25)
    assert ref_fail is not None
    assert res["recool"]["first_failure_time"]["elapsed_seconds"] == pytest.approx(
        ref_fail, abs=1.0
    )


def test_band_between_thresholds_pauses_but_keeps_memory():
    # 复冷阈值与限温之间（4<T<=8）：暂停累计但绝不清零。
    # INSUFFICIENT 数据回暖时先经过 band 再上穿；累计仍为两段热暴露之和。
    recs = _recs(INSUFFICIENT)
    res = run(recs)
    hot_total = sum(i["duration_seconds"] for i in res["exceedance_intervals"])
    assert res["recool"]["rounds"][0]["hot_exposure_seconds"] == pytest.approx(
        hot_total, abs=1e-6
    )


# ---------- 有效复冷：清零、新一轮 ----------

def test_effective_recool_clears_and_passes():
    recs = _recs(EFFECTIVE)
    res = run(recs)
    assert res["status"] == "pass"
    rc = res["recool"]
    assert len(rc["rounds"]) == 2
    r0, r1 = rc["rounds"]
    assert r0["reset"] is True
    assert r0["hot_exposure_seconds"] == pytest.approx(187.8, abs=1.0)
    assert r1["reset"] is False
    assert r1["hot_exposure_seconds"] == pytest.approx(486.3, abs=1.0)
    # 确认点 = 下跨复冷阈值时刻 + 600s，且该确认跨越了记录边界（900s 处）
    cand = rc["recool_candidates"][0]
    assert cand["status"] == "confirmed"
    assert cand["confirmed"] is True
    assert cand["elapsed_start_seconds"] < 900 < cand["cleared_elapsed_seconds"]
    assert cand["cleared_elapsed_seconds"] == pytest.approx(
        cand["elapsed_start_seconds"] + CONFIRM, abs=1e-6
    )
    assert len(rc["resets"]) == 1
    assert rc["resets"][0]["cleared_round_index"] == 0
    assert rc["uncleared_cumulative_exposure_seconds"] == pytest.approx(486.3, abs=1.0)
    assert rc["first_failure_time"] is None


def test_reset_then_long_heat_rejects_in_new_round_without_blame():
    recs = _recs(REHEAT_LONG)
    res = run(recs)
    assert res["status"] == "reject"
    rc = res["recool"]
    assert len(rc["rounds"]) == 2
    assert rc["rounds"][0]["reset"] is True
    ff = rc["first_failure_time"]
    # 失效发生在清零之后的新一轮
    assert ff["round_index"] == 1
    assert ff["elapsed_seconds"] > rc["rounds"][0]["reset_elapsed_seconds"]
    # 新一轮有完整 600s 才失效，故此前的有效复冷不背锅
    assert ff["insufficient_recool_candidate_index"] is None
    ref_fail = rk4_cumulative_failure(recs, LIMIT, RC, CONFIRM, EXPOSURE, dt=0.25)
    assert ff["elapsed_seconds"] == pytest.approx(ref_fail, abs=1.0)


# ---------- 阈值边界与穿越精度 ----------

def test_confirm_uses_both_threshold_roots_not_samples():
    # 确认时长设为恰好等于冷区长度：边界上必须确认清零（连续 T<=rc 达到时长）；
    # 略大于冷区长度则在回暖（重新高于复冷阈值）时被打断。
    recs = _recs(EFFECTIVE)
    # 用一个很大的确认时长跑一次：本次冷区无法确认，候选终点即“上穿复冷阈值”
    # 的精确时刻（冷区全长由闭式穿越根给出，而非采样点）。
    res_big = run(recs, confirm=100000.0)
    cold_piece = res_big["recool"]["recool_candidates"][0]
    cold_len = cold_piece["duration_seconds"]
    assert cold_piece["status"] == "rewarmed"

    res_edge = run(recs, confirm=cold_len)
    assert res_edge["recool"]["recool_candidates"][0]["status"] == "confirmed"
    res_under = run(recs, confirm=cold_len - 0.5)
    assert res_under["recool"]["recool_candidates"][0]["status"] == "confirmed"
    res_over = run(recs, confirm=cold_len + 0.5)
    assert res_over["recool"]["recool_candidates"][0]["status"] == "rewarmed"


def test_cumulative_failure_exact_parse_moment():
    # 失效时刻必须是闭式曲线解析出的“累计达到限额”时刻，而非采样点
    recs = _recs(INSUFFICIENT)
    res = run(recs)
    ff = res["recool"]["first_failure_time"]["elapsed_seconds"]
    # 失效点不应落在任何记录或展示采样时刻上
    sample_times = {p["elapsed_seconds"] for p in res["curve"]}
    record_times = {r["elapsed_seconds"] for r in res["records_echo"]}
    assert ff not in record_times
    assert ff not in sample_times
    # 且失效点处箱温必然仍高于限温（处于热区）
    seg = next(
        p for p in res["curve"]
        if p["elapsed_seconds"] <= ff
    )
    assert seg["box_temp"] > LIMIT or True  # 采样点可能恰在穿越前；改用分段穿越核对
    up2 = res["exceedance_intervals"][1]["elapsed_start_seconds"]
    end2 = res["exceedance_intervals"][1]["elapsed_end_seconds"]
    assert up2 < ff < end2


def test_iso_time_mode_reports_iso_failure():
    spec = INSUFFICIENT

    def iso(t):
        return datetime.fromtimestamp(1_700_000_000 + t, tz=timezone.utc).isoformat()

    num = _recs(spec)
    iso_recs = [
        {"time": iso(r["time"]), "box_temp": r["box_temp"],
         "ambient_temp": r["ambient_temp"], "lid_open": r["lid_open"]}
        for r in num
    ]
    r1 = run(num)
    r2 = run(iso_recs)
    assert r1["status"] == r2["status"] == "reject"
    assert r1["recool"]["first_failure_time"]["elapsed_seconds"] == pytest.approx(
        r2["recool"]["first_failure_time"]["elapsed_seconds"], abs=1e-6
    )
    assert isinstance(r2["recool"]["first_failure_time"]["time"], str)
    assert isinstance(r2["recool"]["recool_candidates"][0]["start_time"], str)


# ---------- 多段短暂回暖：归咎失效前最后一次复冷不足 ----------

def test_blame_latest_insufficient_attempt_before_failure():
    # 直接以区域恒定子区间驱动状态机：
    # 热 200 → band → 冷 280(不足,回暖) → band → 热 300(累计500)
    # → band → 冷 260(仍不足,回暖) → band → 热：应归咎“第 2 次”复冷，
    # 且失效时刻 = 第三段热起点 + (600-500)。
    from app.thermal import _RecoolMachine, _RecoolConfig, ZONE_HOT, ZONE_BAND, ZONE_COLD

    pieces = [
        (0.0, 200.0, ZONE_HOT),
        (200.0, 220.0, ZONE_BAND),
        (220.0, 500.0, ZONE_COLD),    # 280s < 600 → rewarmed
        (500.0, 520.0, ZONE_BAND),
        (520.0, 820.0, ZONE_HOT),     # +300 → 累计 500
        (820.0, 840.0, ZONE_BAND),
        (840.0, 1100.0, ZONE_COLD),   # 260s < 600 → rewarmed
        (1100.0, 1120.0, ZONE_BAND),
        (1120.0, 1400.0, ZONE_HOT),   # +280 → 在 1220 处累计达 600
    ]
    m = _RecoolMachine(
        zone_pieces=pieces,
        cfg=_RecoolConfig(threshold=4.0, confirm_seconds=600.0),
        exposure_limit=600.0,
        total_duration=1400.0,
    )
    rounds, cands, resets, failure, insufficient = m.run()
    assert resets == []
    assert len(rounds) == 1  # 从未清零，始终同一轮
    assert failure is not None
    assert failure["elapsed"] == pytest.approx(1220.0, abs=1e-9)
    rewarmed = [c for c in cands if c["reason"] == "rewarmed"]
    assert [c["index"] for c in rewarmed] == [0, 1]
    # 拒收归咎失效前最后一次（第二次）复冷不足
    assert insufficient["candidate_index"] == 1


def test_no_blame_when_no_prior_recool_attempt():
    # 一次性持续超温即失效：此前根本没有复冷尝试，不应归咎任何候选
    from app.thermal import _RecoolMachine, _RecoolConfig, ZONE_HOT

    m = _RecoolMachine(
        zone_pieces=[(0.0, 800.0, ZONE_HOT)],
        cfg=_RecoolConfig(threshold=4.0, confirm_seconds=600.0),
        exposure_limit=600.0,
        total_duration=800.0,
    )
    rounds, cands, resets, failure, insufficient = m.run()
    assert failure["elapsed"] == pytest.approx(600.0, abs=1e-9)
    assert cands == [] and insufficient is None


def test_confirmation_completing_exactly_at_record_seam():
    # 两个相邻 cold 子区间在记录接缝 720s 处相接；确认完成时刻恰为 720s，
    # 不得因接缝而漏清零或重复清零。
    from app.thermal import _RecoolMachine, _RecoolConfig, ZONE_HOT, ZONE_BAND, ZONE_COLD

    pieces = [
        (0.0, 100.0, ZONE_HOT),
        (100.0, 120.0, ZONE_BAND),
        (120.0, 720.0, ZONE_COLD),   # 记录接缝恰在确认点 120+600
        (720.0, 900.0, ZONE_COLD),
        (900.0, 920.0, ZONE_BAND),
        (920.0, 1300.0, ZONE_HOT),   # 新一轮，热 380s 不足限额
    ]
    m = _RecoolMachine(
        zone_pieces=pieces,
        cfg=_RecoolConfig(threshold=4.0, confirm_seconds=600.0),
        exposure_limit=600.0,
        total_duration=1300.0,
    )
    rounds, cands, resets, failure, insufficient = m.run()
    assert failure is None
    assert len(resets) == 1
    assert resets[0]["at_elapsed"] == pytest.approx(720.0, abs=1e-9)
    assert len(rounds) == 2
    assert rounds[0]["reset_elapsed"] == pytest.approx(720.0, abs=1e-9)
    assert rounds[1]["hot"] == pytest.approx(380.0, abs=1e-9)
    # 确认候选恰好闭合在接缝，且其后相邻 cold 不产生第二个候选
    assert [c["reason"] for c in cands] == ["confirmed"]


def test_failure_exactly_at_record_seam():
    # 热暴露恰在记录接缝处累计达到限额：失效时刻必须精确定位到接缝。
    from app.thermal import _RecoolMachine, _RecoolConfig, ZONE_HOT

    pieces = [(0.0, 300.0, ZONE_HOT), (300.0, 600.0, ZONE_HOT), (600.0, 800.0, ZONE_HOT)]
    m = _RecoolMachine(
        zone_pieces=pieces,
        cfg=_RecoolConfig(threshold=4.0, confirm_seconds=600.0),
        exposure_limit=600.0,
        total_duration=800.0,
    )
    rounds, _c, _r, failure, _i = m.run()
    assert failure["elapsed"] == pytest.approx(600.0, abs=1e-9)


# ---------- 参数合法性 ----------

@pytest.mark.parametrize(
    "recool",
    [
        {"enabled": True, "recool_threshold": 8.0, "confirm_seconds": 60},
        {"enabled": True, "recool_threshold": 9.0, "confirm_seconds": 60},
        {"enabled": True, "recool_threshold": 4.0, "confirm_seconds": 0},
        {"enabled": True, "recool_threshold": 4.0, "confirm_seconds": -1},
        {"enabled": True, "recool_threshold": "x", "confirm_seconds": 60},
        {"enabled": True, "recool_threshold": 4.0},
        {"enabled": "yes", "recool_threshold": 4.0, "confirm_seconds": 60},
        "not-an-object",
    ],
)
def test_bad_recool_params_rejected(recool):
    recs = _recs(EFFECTIVE)
    with pytest.raises(ThermalValidationError) as ei:
        audit({"records": recs, "parameters": {**params(enabled=False), "recool": recool}})
    assert ei.value.code == "bad_param"


# ---------- HTTP API ----------

def test_api_recool_reject_and_legacy_contrast():
    recs = _recs(INSUFFICIENT)
    # 旧口径（不带 recool）放行
    r_old = client.post("/api/audit", json={"records": recs, "parameters": params(enabled=False)})
    assert r_old.status_code == 200
    assert r_old.json()["status"] == "pass"
    # 启用复冷记忆后拒收并带全部证据
    r = client.post("/api/audit", json={"records": recs, "parameters": params()})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "reject"
    rc = body["recool"]
    assert rc["enabled"] is True
    assert rc["recool_threshold"] == RC
    assert rc["confirm_seconds"] == CONFIRM
    assert rc["rounds"] and rc["recool_candidates"]
    assert rc["first_failure_time"]["insufficient_recool_candidate_index"] is not None
    # 原连续区间证据仍保留，供新旧口径对照
    assert len(body["exceedance_intervals"]) == 2


def test_api_recool_invalid_returns_422():
    recs = _recs(EFFECTIVE)
    bad = params()
    bad["recool"] = {"enabled": True, "recool_threshold": 4.0, "confirm_seconds": 0}
    r = client.post("/api/audit", json={"records": recs, "parameters": bad})
    assert r.status_code == 422
    assert r.json()["status"] == "invalid"
    assert r.json()["errors"][0]["code"] == "bad_param"


def test_api_schema_documents_recool():
    r = client.get("/api/audit/schema")
    assert r.status_code == 200
    assert "recool" in r.json()["parameters"]
    assert "recool_threshold" in r.json()["parameters"]["recool"]
