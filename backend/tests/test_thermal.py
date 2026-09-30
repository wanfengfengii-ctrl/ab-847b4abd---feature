"""温控审计引擎测试。"""
from __future__ import annotations

import math

import pytest

from app.thermal import ThermalValidationError, audit

from .reference import make_records_from_sim, rk4_simulate

TAU_CLOSED = 300.0
TAU_OPEN = 90.0
LIMIT = 8.0
EXPOSURE = 600.0


def params(**over):
    base = {
        "tau_closed": TAU_CLOSED,
        "tau_open": TAU_OPEN,
        "box_temp_limit": LIMIT,
        "exposure_limit_seconds": EXPOSURE,
    }
    base.update(over)
    return base


def run(records, **over):
    return audit({"records": records, "parameters": params(**over)})


def iso_records(times, boxes, ambs, lids):
    from datetime import datetime, timezone

    def iso(t):
        return datetime.fromtimestamp(1_700_000_000 + t, tz=timezone.utc).isoformat()

    return [
        {"time": iso(t), "box_temp": b, "ambient_temp": a, "lid_open": l}
        for t, b, a, l in zip(times, boxes, ambs, lids)
    ]


# ---------- 解析解交叉验证 ----------

def test_closed_form_matches_independent_rk4():
    times = list(range(0, 3601, 600))
    ambs = [25.0, 26.0, 24.5, 27.0, 23.0, 26.5, 24.0]
    lids = [False, True, False, False, True, False, False]
    recs = make_records_from_sim(times, ambs, lids, 20.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)

    sim = rk4_simulate(recs, TAU_CLOSED, TAU_OPEN, dt=0.25)
    # 取闭式曲线采样点与独立 RK4 积分逐点比较
    for pt in res["curve"][::37]:
        u = pt["elapsed_seconds"]
        # 在 sim 中线性插值
        for (ta, va), (tb, vb) in zip(sim, sim[1:]):
            if ta - 1e-9 <= u <= tb + 1e-9:
                ref = va + (vb - va) * (u - ta) / (tb - ta)
                assert abs(pt["box_temp"] - ref) < 1e-6, (u, pt["box_temp"], ref)
                break
        else:
            raise AssertionError(f"仿真未覆盖 t={u}")

    # 各段末端与下一实测读数（RK4 自洽数据）一致
    for seg in res["segments"]:
        assert abs(seg["model_record_gap"]) < 1e-8


# ---------- 场景：采样点全部合格、途中超温必须被捕获 ----------

def test_mid_segment_excursion_caught_though_samples_pass():
    # 核心业务场景：质控员录入的全部读数均未超限（4.0/7.81/7.25/3.21/3.01℃，
    # 全部 < 8℃），且数据与一阶模型完全自洽（model_record_gap≈1e-12）。
    # 第 2 段环境温由 25℃ 线性降到 3℃：箱温先追热冲高到闭式内部极大值
    # 约 18℃（t≈537s），再被冷环境拉回。只按离散采样点裁决必然误放行；
    # 解析解给出上穿 63.4s、下穿 1507.3s，连续超温约 1444s。
    times = [0, 60, 1560, 2460, 3360]
    ambs = [25.0, 25.0, 3.0, 3.0, 3.0]
    lids = [False] * 5
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    assert all(r["box_temp"] < LIMIT for r in recs)
    res = run(recs, exposure_limit_seconds=300)
    assert res["status"] == "reject"
    assert res["first_failure_time"] is not None
    hot = [
        s
        for s in res["segments"]
        if s["max_temp"]["value"] > LIMIT and s["max_temp"]["kind"] == "interior"
    ]
    assert len(hot) == 1
    spike = hot[0]["max_temp"]
    assert spike["value"] > 15.0
    # 超温峰严格位于段内部，而非任一记录时刻
    assert spike["elapsed_seconds"] not in times
    # 自洽数据：各段末模型值与下一读数一致
    assert all(abs(s["model_record_gap"]) < 1e-9 for s in res["segments"])
    # 连续超温区间证据完整
    iv = res["exceedance_intervals"][0]
    assert iv["reaches_limit"] is True
    assert iv["duration_seconds"] == pytest.approx(1443.9, abs=1.0)
    assert res["first_failure_time"]["elapsed_seconds"] == pytest.approx(
        iv["elapsed_start_seconds"] + 300, abs=1e-6
    )


def test_pass_when_always_below_limit():
    times = list(range(0, 2401, 300))
    ambs = [3.0, 3.5, 4.0, 3.8, 3.2, 3.0, 2.8, 2.5, 2.0]
    lids = [False] * 9
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    assert res["status"] == "pass"
    assert res["exceedance_intervals"] == []
    assert res["first_failure_time"] is None
    assert res["total_exceedance_seconds"] == 0


# ---------- 跨记录延续 ----------

def test_exposure_accumulates_across_records():
    # 每段超温时间不足限额，但相邻段超温区间在记录点相接 → 合并后超限
    times = [0, 400, 800, 1200, 1600]
    ambs = [20.0, 20.0, 20.0, 20.0, 20.0]
    lids = [False, False, False, False, False]
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    assert res["status"] == "reject"
    interval = res["exceedance_intervals"][0]
    # 首个失效时刻 = 区间起点 + 允许暴露时长
    ff = res["first_failure_time"]
    assert ff["elapsed_seconds"] == pytest.approx(
        interval["elapsed_start_seconds"] + EXPOSURE, abs=1e-6
    )
    assert ff["elapsed_seconds"] <= interval["elapsed_end_seconds"] + 1e-9
    # 各段内部的超温碎片数 >= 2，证明做了跨段合并
    pieces = sum(len(s["exceedance_intervals"]) for s in res["segments"])
    assert pieces >= 2
    assert len(res["exceedance_intervals"]) == 1


def test_short_excursion_below_limit_passes():
    # 超温但持续时间不足限额（暴露 10 分钟，限额 1 小时）
    times = [0, 600, 1200, 1800]
    ambs = [4.0, 25.0, 25.0, 4.0]
    lids = [False, False, False, False]
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, exposure_limit_seconds=3600)
    assert res["status"] == "pass"
    assert res["exceedance_intervals"]
    assert res["exceedance_intervals"][0]["duration_seconds"] < 3600


def test_gap_below_limit_breaks_continuity():
    # 两段超温之间有明确低于阈值的间隙 → 两个独立区间，各自时长不足
    times = [0, 500, 1000, 1500, 2000, 2500]
    ambs = [20.0, 20.0, 2.0, 2.0, 20.0, 20.0]
    lids = [False] * 6
    recs = make_records_from_sim(times, ambs, lids, 6.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, exposure_limit_seconds=10_000)
    assert len(res["exceedance_intervals"]) == 2
    assert res["status"] == "pass"


# ---------- 箱盖热惯性切换 ----------

def test_lid_open_switches_tau():
    times = [0, 600, 1200, 1800]
    ambs = [25.0, 25.0, 25.0, 25.0]
    lids = [False, True, False, False]
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    taus = [s["tau_seconds"] for s in res["segments"]]
    assert taus == [TAU_CLOSED, TAU_OPEN, TAU_CLOSED]
    assert res["segments"][1]["lid_open"] is True
    # 开启段响应更快：比较"本段闭合的温差占初始温差比例"（公平指标，
    # 与起点高度无关），tau_open < tau_closed ⇒ 开启段比例应更高
    seg0, seg1 = res["segments"][0], res["segments"][1]
    gap0 = 25.0 - seg0["box_temp_start"]
    gap1 = 25.0 - seg1["box_temp_start"]
    frac0 = (seg0["box_temp_end_model"] - seg0["box_temp_start"]) / gap0
    frac1 = (seg1["box_temp_end_model"] - seg1["box_temp_start"]) / gap1
    assert frac1 > frac0
    # 与闭式恒温解 1-exp(-Δ/τ) 核对
    assert frac0 == pytest.approx(1 - math.exp(-600 / TAU_CLOSED), abs=1e-9)
    assert frac1 == pytest.approx(1 - math.exp(-600 / TAU_OPEN), abs=1e-9)


# ---------- 解析极值与穿越点 ----------

def test_interior_extremum_is_reported():
    # 降温段：箱温先升后降，存在内部极大值
    times = [0, 900, 1800, 2700]
    ambs = [25.0, 10.0, 2.0, 2.0]
    lids = [False, False, False, False]
    recs = make_records_from_sim(times, ambs, lids, 7.5, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    seg = res["segments"][0]
    assert seg["max_temp"]["kind"] == "interior"
    # 与独立稠密 RK4 积分（dt=0.05s）的段内最大值核对
    sim = rk4_simulate(recs, TAU_CLOSED, TAU_OPEN, dt=0.05)
    ref_max = max(v for t, v in sim if 0 <= t <= 900)
    assert abs(seg["max_temp"]["value"] - ref_max) < 1e-4
    # 驻点时刻导数为零（由闭式导数核验）
    import math as _m

    s_star = seg["max_temp"]["elapsed_seconds"]
    b = seg["ambient_slope_per_second"]
    deriv = b - (recs[0]["box_temp"] - 25.0 + b * TAU_CLOSED) / TAU_CLOSED * _m.exp(
        -s_star / TAU_CLOSED
    )
    assert abs(deriv) < 1e-9


def test_crossings_are_up_down_paired():
    times = [0, 900, 1800, 2700, 3600]
    ambs = [20.0, 20.0, 20.0, 3.0, 3.0]
    lids = [False] * 5
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    dirs = [d for s in res["segments"] for d in [c["direction"] for c in s["crossings"]]]
    assert "up" in dirs and "down" in dirs
    assert dirs.index("up") < dirs.index("down")


def test_crossing_root_is_accurate():
    # 恒温环境下可手工求穿越时刻并比对二分根
    T0, Tenv, tau, lim = 4.0, 20.0, 300.0, 8.0
    times = [0, 1000]
    recs = [
        {"time": 0, "box_temp": T0, "ambient_temp": Tenv, "lid_open": False},
        {"time": 1000, "box_temp": 9.9, "ambient_temp": Tenv, "lid_open": False},
    ]
    while len(recs) < 4:
        recs.append(
            {"time": 1000 + len(recs) * 1000, "box_temp": 9.9, "ambient_temp": Tenv, "lid_open": False}
        )
    res = run(recs)
    root_elapsed = res["segments"][0]["crossings"][0]["elapsed_seconds"]
    # T(s)=Tenv+(T0-Tenv)e^{-s/tau}=lim  →  s=-tau ln((lim-Tenv)/(T0-Tenv))
    expect = -tau * math.log((lim - Tenv) / (T0 - Tenv))
    assert abs(root_elapsed - expect) < 1e-6


# ---------- 时间格式 ----------

def test_iso_times_and_numeric_times_equivalent():
    times = [0, 600, 1200, 1800]
    ambs = [20.0, 20.0, 20.0, 20.0]
    lids = [False] * 4
    num = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    iso = iso_records(
        times, [r["box_temp"] for r in num], ambs, lids
    )
    r1 = run(num)
    r2 = run(iso)
    assert r1["status"] == r2["status"]
    assert (
        r1["first_failure_time"]["elapsed_seconds"]
        == r2["first_failure_time"]["elapsed_seconds"]
    )
    assert isinstance(r2["first_failure_time"]["time"], str)


# ---------- 数据合法性 ----------

@pytest.mark.parametrize(
    "mutate",
    [
        lambda rs: rs[:3],  # 少于 4 条
        lambda rs: rs + [rs[-1]] * 27,  # 31 条
    ],
)
def test_record_count_bounds(mutate):
    times = list(range(0, 5))
    base = [
        {"time": t, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False}
        for t in times
    ]
    with pytest.raises(ThermalValidationError) as ei:
        run(mutate(base))
    assert ei.value.code == "bad_records"


def test_time_must_be_strictly_increasing():
    recs = [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": 600, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": 600, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": 900, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
    ]
    with pytest.raises(ThermalValidationError) as ei:
        run(recs)
    assert ei.value.code == "time_not_strict"


def test_mixed_time_formats_rejected():
    recs = [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": "2023-11-14T22:10:00+00:00", "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": 1200, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
        {"time": 1800, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False},
    ]
    with pytest.raises(ThermalValidationError) as ei:
        run(recs)
    assert ei.value.code == "mixed_time"


def test_bad_values_and_params():
    good = [
        {"time": t, "box_temp": 4.0, "ambient_temp": 5.0, "lid_open": False}
        for t in range(0, 4)
    ]
    bad = [dict(r, box_temp=float("nan")) for r in good]
    with pytest.raises(ThermalValidationError):
        run(bad)
    bad_lid = [dict(r) for r in good]
    bad_lid[0]["lid_open"] = "yes"
    with pytest.raises(ThermalValidationError) as ei:
        run(bad_lid)
    assert ei.value.code == "bad_lid"
    with pytest.raises(ThermalValidationError):
        run(good, tau_closed=0)
    with pytest.raises(ThermalValidationError):
        run(good, exposure_limit_seconds=-1)


# ---------- 证据完整性 ----------

def test_interval_report_contains_required_evidence():
    times = list(range(0, 3001, 600))
    ambs = [20.0] * 6
    lids = [False] * 6
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs)
    assert res["status"] == "reject"
    iv = res["exceedance_intervals"][0]
    for key in (
        "start_time",
        "end_time",
        "duration_seconds",
        "reaches_limit",
        "elapsed_start_seconds",
        "elapsed_end_seconds",
    ):
        assert key in iv
    assert iv["start_time"] < iv["end_time"]
    assert iv["duration_seconds"] > 0
    ff = res["first_failure_time"]
    assert ff["time"] >= iv["start_time"]
    assert ff["interval_index"] == iv["index"]


def test_tangent_at_limit_is_not_exceedance():
    # 边界：段内内部极大值恰好等于阈值（相切而非严格穿越），
    # T 始终 <= limit，不得产生超温区间。
    # 在 T0=4、b<0、tau=300 上对起点环境温 a 二分，使闭式极大值恰为 8.0。
    import math as _m

    tau, dur, b, T0, target = 300.0, 1500.0, -20.0 / 1500.0, 4.0, 8.0

    def max_value(a):
        ratio = (T0 - a + b * tau) / (b * tau)
        s_star = tau * _m.log(ratio)
        return a + b * (s_star - tau) + (T0 - a + b * tau) * _m.exp(-s_star / tau), s_star

    lo, hi = 8.0, 40.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        v, _ = max_value(mid)
        if v < target:
            lo = mid
        else:
            hi = mid
    a = 0.5 * (lo + hi)
    vmax, s_star = max_value(a)
    assert abs(vmax - target) < 1e-9
    assert 0 < s_star < dur
    recs = [
        {"time": 0, "box_temp": T0, "ambient_temp": a, "lid_open": False},
        {"time": dur, "box_temp": 3.0, "ambient_temp": a + b * dur, "lid_open": False},
        {"time": dur + 900, "box_temp": 3.0, "ambient_temp": 3.0, "lid_open": False},
        {"time": dur + 1800, "box_temp": 3.0, "ambient_temp": 3.0, "lid_open": False},
    ]
    res = run(recs)
    assert res["status"] == "pass"
    assert res["exceedance_intervals"] == []


def test_curve_covers_entire_timeline():
    times = [0, 300, 900, 1500]
    recs = [
        {"time": t, "box_temp": 4.0, "ambient_temp": 6.0, "lid_open": False}
        for t in times
    ]
    res = run(recs)
    assert res["curve"][0]["elapsed_seconds"] == 0
    assert res["curve"][-1]["elapsed_seconds"] == 1500


# ---------- 复冷记忆 ----------

# 恒温相位场景（相邻同温记录 + 1 秒过渡，tau=300, limit=8, recool=5）：
#   H1（T>8）        ≈ 63.4–200.5 ，热暴露 137.1s
#   C1（T<=5）       ≈ 475.4–1125.7，连续 650.3s
#   H2               ≈ 1174.4–1500 ，热暴露 325.6s
# 旧口径：两个超温区间各自 <400s → 放行。
RECOOL_TIMES = [0, 100, 101, 1100, 1101, 1500]
RECOOL_AMBS = [25.0, 25.0, 3.0, 3.0, 25.0, 25.0]


def recool_records():
    return make_records_from_sim(RECOOL_TIMES, RECOOL_AMBS, [False] * 6, 4.0, TAU_CLOSED, TAU_OPEN)


def test_disabled_recooling_keeps_legacy_shape():
    res = run(recool_records(), exposure_limit_seconds=400)
    assert res["status"] == "pass"  # 旧口径：两段各自不足
    assert "recooling" not in res  # 未启用时请求、结论及证据保持不变


def test_recooling_default_when_key_absent_equals_legacy():
    payload = {"records": recool_records(), "parameters": params(exposure_limit_seconds=400)}
    assert audit(payload)["status"] == "pass"


def test_effective_recool_clears_memory_and_passes():
    res = audit(
        {
            "records": recool_records(),
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 600.0},
        }
    )
    assert res["status"] == "pass"
    assert res["first_failure_time"] is None
    blk = res["recooling"]
    assert blk["enabled"] is True
    # 第 0 轮：137.1s 暴露，在连续复冷确认完成时清零
    r0, r1 = blk["rounds"]
    assert r0["end_reason"] == "recool_confirmed"
    assert r0["reset"] is True
    assert r0["heat_exposure_seconds"] == pytest.approx(137.1, abs=0.5)
    assert r1["end_reason"] == "timeline_end"
    assert r1["heat_exposure_seconds"] == pytest.approx(325.6, abs=0.5)
    # 唯一候选达到确认：完成时刻 = 候选起点 + 600
    cand = blk["candidates"][0]
    assert cand["outcome"] == "recool_confirmed"
    assert cand["reset"] is True
    assert cand["shortfall_seconds"] == 0
    assert cand["elapsed_end_seconds"] - cand["elapsed_start_seconds"] == pytest.approx(600, abs=1e-6)


def test_insufficient_recool_accumulates_and_rejects_later():
    res = audit(
        {
            "records": recool_records(),
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 700.0},
        }
    )
    # 复冷只有 650.3s（<700），未清零：137.1 + 325.6 累计达 400 → 后段拒收
    assert res["status"] == "reject"
    ff = res["first_failure_time"]
    # 失效时刻 = H2 起点 1174.4 + (400-137.1)
    assert ff["elapsed_seconds"] == pytest.approx(1174.4 + 262.9, abs=1.0)
    assert ff["round_index"] == 0  # 同一轮延续到后段
    assert ff["segment_index"] == 4  # 失效发生在第 5 段（H2 所在段，0 基）
    cand = res["recooling"]["insufficient_recool_at_failure"]
    assert cand is not None
    assert cand["index"] == 0
    assert cand["reset"] is False
    assert cand["outcome"] == "rewarm_above_recool"
    assert cand["shortfall_seconds"] == pytest.approx(49.7, abs=1.0)
    assert cand["continuous_below_recool_seconds"] == pytest.approx(650.3, abs=1.0)
    # 轮次：仅有一轮，以 failure 收尾，热暴露精确为限额
    assert len(res["recooling"]["rounds"]) == 1
    rd = res["recooling"]["rounds"][0]
    assert rd["end_reason"] == "failure"
    assert rd["heat_exposure_seconds"] == pytest.approx(400, abs=1e-6)


def test_interrupted_confirm_by_middle_band_does_not_reset():
    # 冷区被一次停留在 (5,8] 复冷阈值与限温之间的回暖打断：
    # 即使两段冷区之和超过确认时长，也不能清零。
    times = [0, 100, 101, 1100, 1101, 1141, 1142, 1900]
    ambs = [25.0, 25.0, 3.0, 3.0, 25.0, 25.0, 3.0, 3.0]
    recs = make_records_from_sim(times, ambs, [False] * 8, 4.0, TAU_CLOSED, TAU_OPEN)
    res = audit(
        {
            "records": recs,
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 700.0},
        }
    )
    cands = res["recooling"]["candidates"]
    assert len(cands) == 2
    assert all(c["reset"] is False for c in cands)
    assert cands[0]["outcome"] == "rewarm_above_recool"
    assert cands[1]["outcome"] == "timeline_end"
    # 每段单独不足 700；不存在清零轮
    assert all(r["end_reason"] != "recool_confirmed" for r in res["recooling"]["rounds"])
    # 回暖期间 T 未超过限温：不产生新的超温区间
    assert len(res["exceedance_intervals"]) == 1


def test_recool_crossing_roots_are_accurate():
    from app.thermal import _box_temperature

    res = audit(
        {
            "records": recool_records(),
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 600.0},
        }
    )
    crosses = [c for s in res["segments"] for c in s["recool_crossings"]]
    assert {c["direction"] for c in crosses} == {"up", "down"}
    # 在每个穿越根上以闭式解复核：箱温恰为复冷阈值
    for seg in res["segments"]:
        for c in seg["recool_crossings"]:
            s = c["elapsed_seconds"] - seg["elapsed_start_seconds"]
            val = _box_temperature(
                s,
                seg["box_temp_start"],
                seg["ambient_start"],
                seg["ambient_slope_per_second"],
                seg["tau_seconds"],
            )
            assert abs(val - 5.0) < 1e-7


def test_recooling_with_iso_times_matches_numeric():
    from datetime import datetime, timezone

    num = recool_records()
    iso = [
        {
            **r,
            "time": datetime.fromtimestamp(1_700_000_000 + r["time"], tz=timezone.utc).isoformat(),
        }
        for r in num
    ]
    cfg = {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 700.0}
    r1 = audit({"records": num, "parameters": params(exposure_limit_seconds=400), "recooling": cfg})
    r2 = audit({"records": iso, "parameters": params(exposure_limit_seconds=400), "recooling": cfg})
    assert r1["status"] == r2["status"] == "reject"
    assert (
        r1["first_failure_time"]["elapsed_seconds"]
        == r2["first_failure_time"]["elapsed_seconds"]
    )
    assert isinstance(r2["recooling"]["candidates"][0]["start_time"], str)


@pytest.mark.parametrize(
    "cfg,field",
    [
        ({"enabled": "yes", "recool_temp": 5.0, "confirm_seconds": 600}, "recooling.enabled"),
        ({"enabled": True, "recool_temp": 8.0, "confirm_seconds": 600}, "recooling.recool_temp"),
        ({"enabled": True, "recool_temp": 9.0, "confirm_seconds": 600}, "recooling.recool_temp"),
        ({"enabled": True, "recool_temp": 5.0, "confirm_seconds": 0}, "recooling.confirm_seconds"),
        ({"enabled": True, "recool_temp": 5.0}, "recooling.confirm_seconds"),
        ({"enabled": True, "confirm_seconds": 600}, "recooling.recool_temp"),
    ],
)
def test_bad_recooling_config_rejected(cfg, field):
    with pytest.raises(ThermalValidationError) as ei:
        audit(
            {
                "records": recool_records(),
                "parameters": params(exposure_limit_seconds=400),
                "recooling": cfg,
            }
        )
    assert ei.value.code == "bad_recooling"
    assert ei.value.field == field


def test_recooling_must_be_object():
    with pytest.raises(ThermalValidationError) as ei:
        audit(
            {
                "records": recool_records(),
                "parameters": params(exposure_limit_seconds=400),
                "recooling": [],
            }
        )
    assert ei.value.code == "bad_recooling"


def test_confirm_longer_than_cold_period_candidate_open_at_end():
    # 末段仍在复冷阈值以下且时长不足：候选以 timeline_end 收尾且不判清零
    times = [0, 100, 101, 1100]
    ambs = [25.0, 25.0, 3.0, 3.0]
    recs = make_records_from_sim(times, ambs, [False] * 4, 4.0, TAU_CLOSED, TAU_OPEN)
    res = audit(
        {
            "records": recs,
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 10000.0},
        }
    )
    assert res["status"] == "pass"
    cand = res["recooling"]["candidates"][-1]
    assert cand["outcome"] == "timeline_end"
    assert cand["reset"] is False
    assert cand["shortfall_seconds"] > 0


def test_cold_before_first_exposure_does_not_start_candidate():
    # 全程低温（无任何超温）：即使长时间 <=复冷阈值，也不应有轮次或候选
    times = list(range(0, 2401, 300))
    ambs = [3.0, 3.5, 4.0, 3.8, 3.2, 3.0, 2.8, 2.5, 2.0]
    recs = make_records_from_sim(times, ambs, [False] * 9, 4.0, TAU_CLOSED, TAU_OPEN)
    res = audit(
        {
            "records": recs,
            "parameters": params(),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 100.0},
        }
    )
    assert res["status"] == "pass"
    assert res["recooling"]["rounds"] == []
    assert res["recooling"]["candidates"] == []


def test_reanchor_jump_accumulates_same_round_across_records():
    # 非自洽记录：段末重锚使两个热分量被记录点处的短暂停隔开，
    # 累计不得被割裂成两轮。
    recs = [
        {"time": 0, "box_temp": 4.0, "ambient_temp": 25.0, "lid_open": False},
        {"time": 500, "box_temp": 6.0, "ambient_temp": 3.0, "lid_open": False},
        {"time": 520, "box_temp": 12.0, "ambient_temp": 25.0, "lid_open": False},
        {"time": 1000, "box_temp": 20.0, "ambient_temp": 25.0, "lid_open": False},
    ]
    res = audit(
        {
            "records": recs,
            "parameters": params(exposure_limit_seconds=400),
            "recooling": {"enabled": True, "recool_temp": 5.0, "confirm_seconds": 600.0},
        }
    )
    assert res["status"] == "reject"
    # 两个超温连通分量（中间记录点有 20s 间隙）却同属一轮
    assert len(res["exceedance_intervals"]) == 2
    assert len(res["recooling"]["rounds"]) == 1
    ff = res["first_failure_time"]
    assert ff["round_index"] == 0
    assert ff["elapsed_seconds"] < 520  # 第一段（430.8s）内即达 400s 限额


