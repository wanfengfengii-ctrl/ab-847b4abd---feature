"""一阶热响应模型解析求解引擎。

模型（每段记录区间内）：

    dT/dt = (T_env(t) - T(t)) / τ

* T 为箱温，T_env(t) 在相邻两条记录之间按约定做线性插值；
* τ 为箱体热惯性（时间常数），箱盖开启/关闭取不同常数，
  在箱盖状态对应的整段区间内保持该常数，跨记录点无缝延续；
* 不使用欧拉/龙格-库塔等数值步进，也不按离散采样点裁决：
  每段均给出闭式解，阈值穿越点在由解析驻点切分出的单调区间上
  以二分求根（收敛容差 1e-12 s）精确定位。

区间 [t_i, t_{i+1}]，令 s = t - t_i，Δ = t_{i+1} - t_i，
T_env(s) = a + b·s（a 为起点环境温，b 为线性斜率），则：

    T(s) = a + b·(s - τ) + (T_i - a + b·τ)·exp(-s/τ)

    T'(s) = b - (T_i - a + b·τ)/τ · exp(-s/τ)

默认裁决口径：严格超限 T > T_limit；相邻超温子区间在全局取并集后，
任一连续超温区间持续达到允许连续暴露时长即判拒收，首个失效时刻
为该区间起点 + 允许暴露时长。

复冷记忆（recool，质控员在审计页可选启用）：
启用后另给一道更低的复冷阈值与确认时长，按全程事件顺序推进：

* 箱温高于原限温（T > T_limit）时累计热暴露；
* 处于复冷阈值与限温之间（rc < T <= limit）时只暂停累计并保留本轮记忆；
* 只有连续不高于复冷阈值（T <= rc）达到确认时长才清零并开始新一轮；
* 短暂回落（复冷不足：被回暖打断、或数据结束时仍未确认）不清零，
  后续超温继续累加同一轮暴露，累计达到限额即拒收。

实现上，每段先由解析驻点切出单调子区间，在其上对“限温/复冷”两道
阈值分别二分求根，把整段时间切成区域恒定（hot/band/cold）的子区间；
状态机直接沿这些子区间（含跨记录拼接处）按时间推进，确认完成时刻
也是精确定位的事件，故不按展示采样点裁决，也不会割裂跨记录或短暂
回暖的同一轮暴露。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

# 时间求根容差（秒）与连续区间合并容差
ROOT_TOL = 1e-12
MERGE_TOL = 1e-9
BISECT_ITER = 200
# 仅用于画图的每段采样密度（不参与任何裁决）
DISPLAY_SAMPLES_PER_SEGMENT = 48

ZONE_HOT = "hot"    # T > T_limit：累计热暴露
ZONE_BAND = "band"  # rc < T <= T_limit：暂停累计、保留记忆
ZONE_COLD = "cold"  # T <= rc：复冷确认计时


class ThermalValidationError(ValueError):
    """输入数据不合法。"""

    def __init__(self, code: str, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def parse_time(value: Any) -> tuple[float, bool]:
    """返回 (epoch 秒, 是否 ISO 文本)。ISO 与数值两种格式各自必须统一。"""
    if isinstance(value, str):
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ThermalValidationError(
                "bad_time", f"时间 {value!r} 不是合法的 ISO 8601 日期时间", "time"
            ) from exc
        if dt.tzinfo is not None:
            return dt.timestamp(), True
        # 朴素时间按 UTC 解释，保证可计算
        return dt.replace(tzinfo=timezone.utc).timestamp(), True
    if _is_finite_number(value):
        return float(value), False
    raise ThermalValidationError(
        "bad_time", f"时间 {value!r} 必须是 ISO 8601 字符串或数值型纪元秒", "time"
    )


def _box_temperature(s: float, t_i: float, a: float, b: float, tau: float) -> float:
    """段内闭式箱温，s 为距段起点的秒数。"""
    return a + b * (s - tau) + (t_i - a + b * tau) * math.exp(-s / tau)


def _stationary_point(t_i: float, a: float, b: float, tau: float, duration: float) -> Optional[float]:
    """解析驻点 s*（段内局部极值），不存在则返回 None。b == 0 时箱温单调。"""
    if b == 0.0:
        return None
    ratio = (t_i - a + b * tau) / (b * tau)
    if ratio <= 0.0:
        return None
    s_star = tau * math.log(ratio)
    if 0.0 < s_star < duration:
        return s_star
    return None


def _bisect_root(f, lo: float, hi: float, f_lo: float) -> float:
    """在已知单调且端点异号的区间上二分求 f(s)=0。"""
    for _ in range(BISECT_ITER):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if hi - lo <= ROOT_TOL:
            return mid
        if (f_lo > 0.0) == (f_mid > 0.0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _exceedance_on_piece(f, lo: float, hi: float, limit: float) -> Optional[tuple[float, float]]:
    """在单调子区间上求严格超限 {s : f(s) > limit} 的起止。

    单调函数仅需比较端点；端点异号时二分求根。
    """
    v_lo = f(lo) - limit
    v_hi = f(hi) - limit
    above_lo = v_lo > 0.0
    above_hi = v_hi > 0.0
    if above_lo and above_hi:
        return (lo, hi)
    if not above_lo and not above_hi:
        return None
    root = _bisect_root(lambda s: f(s) - limit, lo, hi, v_lo)
    return (lo, root) if above_lo else (root, hi)


def _root_on_piece(f, lo: float, hi: float, level: float) -> Optional[float]:
    """单调子区间内部穿越 level 的根（严格异号才有），否则 None。"""
    v_lo = f(lo) - level
    v_hi = f(hi) - level
    if v_lo * v_hi < 0.0:
        return _bisect_root(lambda s: f(s) - level, lo, hi, v_lo)
    return None


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged: list[list[float]] = [[intervals[0][0], intervals[0][1]]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1] + MERGE_TOL:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def _classify(value: float, limit: float, rc: float) -> str:
    if value > limit:
        return ZONE_HOT
    if value > rc:
        return ZONE_BAND
    return ZONE_COLD


@dataclass
class _RecoolConfig:
    threshold: float
    confirm_seconds: float


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    """执行完整温控审计，返回可直接序列化的结果字典。"""
    records = payload.get("records")
    if not isinstance(records, list):
        raise ThermalValidationError("bad_records", "records 必须是数组", "records")
    if not 4 <= len(records) <= 30:
        raise ThermalValidationError(
            "bad_records", f"记录数必须在 4 至 30 条之间，当前为 {len(records)} 条", "records"
        )

    params = payload.get("parameters")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ThermalValidationError(
            "bad_params", "parameters 必须是对象", "parameters"
        )

    def _require_positive(name: str, label: str) -> float:
        value = params.get(name)
        if not _is_finite_number(value):
            raise ThermalValidationError("bad_param", f"{label}必须是有限数值", name)
        if float(value) <= 0:
            raise ThermalValidationError("bad_param", f"{label}必须大于 0", name)
        return float(value)

    tau_closed = _require_positive("tau_closed", "箱盖关闭热惯性")
    tau_open = _require_positive("tau_open", "箱盖开启热惯性")
    exposure_limit = _require_positive("exposure_limit_seconds", "允许连续暴露时长（秒）")

    limit_raw = params.get("box_temp_limit")
    if not _is_finite_number(limit_raw):
        raise ThermalValidationError(
            "bad_param", "允许箱温必须是有限数值", "box_temp_limit"
        )
    box_temp_limit = float(limit_raw)

    # ---------- 复冷记忆（可选，质控员在审计页启用） ----------
    recool_cfg: Optional[_RecoolConfig] = None
    recool_field = params.get("recool")
    if recool_field is not None:
        if not isinstance(recool_field, dict):
            raise ThermalValidationError(
                "bad_param", "复冷记忆配置 recool 必须是对象", "parameters.recool"
            )
        enabled = recool_field.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ThermalValidationError(
                "bad_param", "复冷记忆 enabled 必须是布尔值 true/false", "parameters.recool.enabled"
            )
        if enabled:
            rc_raw = recool_field.get("recool_threshold")
            if not _is_finite_number(rc_raw):
                raise ThermalValidationError(
                    "bad_param", "复冷阈值必须是有限数值", "parameters.recool.recool_threshold"
                )
            rc_threshold = float(rc_raw)
            if not rc_threshold < box_temp_limit:
                raise ThermalValidationError(
                    "bad_param",
                    "复冷阈值必须严格低于允许箱温（原限温），复冷暂停带位于两道阈值之间",
                    "parameters.recool.recool_threshold",
                )
            confirm_raw = recool_field.get("confirm_seconds")
            if not _is_finite_number(confirm_raw):
                raise ThermalValidationError(
                    "bad_param", "复冷确认时长必须是有限数值（秒）", "parameters.recool.confirm_seconds"
                )
            confirm_seconds = float(confirm_raw)
            if not confirm_seconds > 0:
                raise ThermalValidationError(
                    "bad_param", "复冷确认时长必须大于 0", "parameters.recool.confirm_seconds"
                )
            recool_cfg = _RecoolConfig(rc_threshold, confirm_seconds)

    # 解析并逐条校验记录
    parsed: list[dict[str, Any]] = []
    iso_mode: Optional[bool] = None
    prev_t: Optional[float] = None
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ThermalValidationError(
                "bad_record", f"第 {idx + 1} 条记录必须是对象", f"records[{idx}]"
            )
        try:
            t, is_iso = parse_time(rec.get("time"))
        except ThermalValidationError as exc:
            exc.field = f"records[{idx}].time"
            raise
        if iso_mode is None:
            iso_mode = is_iso
        elif is_iso != iso_mode:
            raise ThermalValidationError(
                "mixed_time",
                "所有时间必须统一使用 ISO 8601 字符串或统一使用数值纪元秒，不得混用",
                f"records[{idx}].time",
            )
        if prev_t is not None and not t > prev_t:
            raise ThermalValidationError(
                "time_not_strict",
                f"第 {idx + 1} 条记录时间必须严格晚于上一条",
                f"records[{idx}].time",
            )

        box_t = rec.get("box_temp")
        amb_t = rec.get("ambient_temp")
        if not _is_finite_number(box_t):
            raise ThermalValidationError(
                "bad_temp", f"第 {idx + 1} 条箱温必须是有限数值", f"records[{idx}].box_temp"
            )
        if not _is_finite_number(amb_t):
            raise ThermalValidationError(
                "bad_temp", f"第 {idx + 1} 条环境温必须是有限数值", f"records[{idx}].ambient_temp"
            )
        lid_open = rec.get("lid_open")
        if not isinstance(lid_open, bool):
            raise ThermalValidationError(
                "bad_lid",
                f"第 {idx + 1} 条箱盖状态必须是布尔值 true/false",
                f"records[{idx}].lid_open",
            )
        parsed.append(
            {"t": t, "box": float(box_t), "amb": float(amb_t), "lid_open": lid_open}
        )
        prev_t = t

    t0 = parsed[0]["t"]
    total_duration = parsed[-1]["t"] - t0

    def fmt(t_abs: float) -> Any:
        if iso_mode:
            # 输入（含朴素时间按 UTC 解释）统一以 UTC 回显，避免容器时区造成错位
            return datetime.fromtimestamp(t_abs, tz=timezone.utc).isoformat()
        return round(t_abs, 3)

    segments: list[dict[str, Any]] = []
    raw_intervals: list[tuple[float, float]] = []
    curve: list[dict[str, Any]] = []
    # 全程区域恒定子区间（相对首条记录秒, 起, 止, 区域），跨记录直接拼接
    zone_pieces: list[tuple[float, float, str]] = []

    for i in range(len(parsed) - 1):
        r0, r1 = parsed[i], parsed[i + 1]
        duration = r1["t"] - r0["t"]
        a = r0["amb"]
        b = (r1["amb"] - r0["amb"]) / duration
        tau = tau_open if r0["lid_open"] else tau_closed
        t_start_box = r0["box"]

        def f(s: float, _ti=t_start_box, _a=a, _b=b, _tau=tau) -> float:
            return _box_temperature(s, _ti, _a, _b, _tau)

        # 端点解析值（末端闭式值应与该模型连续求解一致）
        t_end_model = f(duration)

        # 解析驻点 → 切分单调子区间
        s_star = _stationary_point(t_start_box, a, b, tau, duration)
        cuts = [0.0] + ([s_star] if s_star is not None else []) + [duration]

        seg_intervals: list[tuple[float, float]] = []
        crossings: list[dict[str, Any]] = []
        recool_crossings: list[dict[str, Any]] = []
        rc_threshold = recool_cfg.threshold if recool_cfg is not None else None

        for lo, hi in zip(cuts, cuts[1:]):
            # 默认口径：限温严格超限子区间
            piece = _exceedance_on_piece(f, lo, hi, box_temp_limit)
            if piece is not None:
                seg_intervals.append(piece)
                if piece[0] < piece[1] - MERGE_TOL:
                    raw_intervals.append(
                        (r0["t"] - t0 + piece[0], r0["t"] - t0 + piece[1])
                    )

            # 两道阈值在该单调子区间内的穿越根
            roots: list[tuple[float, float]] = []  # (s, level)  level: box_temp_limit / rc
            lim_root = _root_on_piece(f, lo, hi, box_temp_limit)
            if lim_root is not None:
                roots.append((lim_root, box_temp_limit))
                direction = "up" if f(hi) > box_temp_limit else "down"
                crossings.append(
                    {
                        "elapsed_seconds": round(r0["t"] - t0 + lim_root, 6),
                        "time": fmt(r0["t"] + lim_root),
                        "box_temp": box_temp_limit,
                        "direction": direction,
                    }
                )
            if rc_threshold is not None:
                rc_root = _root_on_piece(f, lo, hi, rc_threshold)
                if rc_root is not None:
                    roots.append((rc_root, rc_threshold))
                    rc_direction = "up" if f(hi) > rc_threshold else "down"
                    recool_crossings.append(
                        {
                            "elapsed_seconds": round(r0["t"] - t0 + rc_root, 6),
                            "time": fmt(r0["t"] + rc_root),
                            "box_temp": rc_threshold,
                            "direction": rc_direction,
                        }
                    )

            # 用两道阈值的根把该单调子区间切成区域恒定的小段
            if recool_cfg is not None:
                bounds = [lo] + [s for s, _ in sorted(roots)] + [hi]
                for ql, qh in zip(bounds, bounds[1:]):
                    if qh - ql <= MERGE_TOL:
                        continue
                    mid = 0.5 * (ql + qh)
                    zone = _classify(f(mid), box_temp_limit, rc_threshold)
                    zone_pieces.append(
                        (r0["t"] - t0 + ql, r0["t"] - t0 + qh, zone)
                    )

        # 驻点处相接的两个超温子区间属于同一连续区间，段内先合并
        seg_intervals = _merge_intervals(seg_intervals)

        # 段内极值（解析）
        candidates = [(0.0, t_start_box), (duration, t_end_model)]
        if s_star is not None:
            candidates.append((s_star, f(s_star)))
        s_max, val_max = max(candidates, key=lambda p: p[1])
        s_min, val_min = min(candidates, key=lambda p: p[1])

        u0 = r0["t"] - t0
        seg = {
            "index": i,
            "start_time": fmt(r0["t"]),
            "end_time": fmt(r1["t"]),
            "elapsed_start_seconds": round(u0, 6),
            "elapsed_end_seconds": round(u0 + duration, 6),
            "duration_seconds": round(duration, 6),
            "lid_open": r0["lid_open"],
            "tau_seconds": tau,
            "ambient_start": a,
            "ambient_end": r1["amb"],
            "ambient_slope_per_second": b,
            "box_temp_start": t_start_box,
            "box_temp_end_model": t_end_model,
            "box_temp_end_recorded": r1["box"],
            "model_record_gap": r1["box"] - t_end_model,
            "max_temp": {
                "time": fmt(r0["t"] + s_max),
                "elapsed_seconds": round(u0 + s_max, 6),
                "value": val_max,
                "kind": "interior" if 0.0 < s_max < duration else ("start" if s_max == 0 else "end"),
            },
            "min_temp": {
                "time": fmt(r0["t"] + s_min),
                "elapsed_seconds": round(u0 + s_min, 6),
                "value": val_min,
                "kind": "interior" if 0.0 < s_min < duration else ("start" if s_min == 0 else "end"),
            },
            "crossings": sorted(crossings, key=lambda c: c["elapsed_seconds"]),
            "exceedance_intervals": [
                {
                    "start_time": fmt(r0["t"] + s_lo),
                    "end_time": fmt(r0["t"] + s_hi),
                    "elapsed_start_seconds": round(u0 + s_lo, 6),
                    "elapsed_end_seconds": round(u0 + s_hi, 6),
                    "duration_seconds": round(s_hi - s_lo, 6),
                }
                for s_lo, s_hi in seg_intervals
            ],
        }
        if recool_cfg is not None:
            seg["recool_crossings"] = sorted(
                recool_crossings, key=lambda c: c["elapsed_seconds"]
            )
        segments.append(seg)

        # 画图采样（展示用途；裁决全部基于上面的解析结果）
        for k in range(DISPLAY_SAMPLES_PER_SEGMENT + 1):
            s = duration * k / DISPLAY_SAMPLES_PER_SEGMENT
            curve.append(
                {
                    "elapsed_seconds": round(u0 + s, 6),
                    "time": fmt(r0["t"] + s),
                    "box_temp": f(s),
                    "ambient_temp": a + b * s,
                    "lid_open": r0["lid_open"],
                }
            )

    # 全局连续超温区间（跨记录取并集，间隙才打断连续性）
    # 丢弃零宽度项：仅在切点接触阈值（T 始终 <= limit）不构成严格超限
    merged = [
        (lo, hi)
        for lo, hi in _merge_intervals(raw_intervals)
        if hi - lo > MERGE_TOL
    ]

    # ---------- 默认口径（连续区间）证据 ----------
    exceedance_intervals: list[dict[str, Any]] = []
    legacy_first_failure: Optional[dict[str, Any]] = None
    for n, (u_lo, u_hi) in enumerate(merged):
        piece_duration = u_hi - u_lo
        entry = {
            "index": n,
            "start_time": fmt(t0 + u_lo),
            "end_time": fmt(t0 + u_hi),
            "elapsed_start_seconds": round(u_lo, 6),
            "elapsed_end_seconds": round(u_hi, 6),
            "duration_seconds": round(piece_duration, 6),
            "reaches_limit": piece_duration + MERGE_TOL >= exposure_limit,
        }
        if entry["reaches_limit"] and legacy_first_failure is None:
            failure_elapsed = u_lo + exposure_limit
            legacy_first_failure = {
                "time": fmt(t0 + failure_elapsed),
                "elapsed_seconds": round(failure_elapsed, 6),
                "interval_index": n,
                "interval_start_time": entry["start_time"],
                "exposure_limit_seconds": exposure_limit,
            }
        exceedance_intervals.append(entry)

    total_exceedance = sum(e["duration_seconds"] for e in exceedance_intervals)

    # ---------- 复冷记忆状态机（启用时） ----------
    recool_block: Optional[dict[str, Any]] = None
    top_first_failure = legacy_first_failure
    if recool_cfg is not None:
        machine = _RecoolMachine(
            zone_pieces=zone_pieces,
            cfg=recool_cfg,
            exposure_limit=exposure_limit,
            total_duration=total_duration,
        )
        m_rounds, m_candidates, m_resets, m_failure, m_insufficient = machine.run()

        def round_entry(rd: dict[str, Any]) -> dict[str, Any]:
            reset_u = rd["reset_elapsed"]
            fail_u = rd["failure_elapsed"]
            end_u = (
                fail_u
                if fail_u is not None
                else (reset_u if reset_u is not None else total_duration)
            )
            return {
                "index": rd["index"],
                "start_time": fmt(t0 + rd["start_elapsed"]),
                "end_time": fmt(t0 + end_u),
                "elapsed_start_seconds": round(rd["start_elapsed"], 6),
                "elapsed_end_seconds": round(end_u, 6),
                "hot_exposure_seconds": round(rd["hot"], 6),
                "reset": reset_u is not None,
                "reset_time": fmt(t0 + reset_u) if reset_u is not None else None,
                "reset_elapsed_seconds": round(reset_u, 6) if reset_u is not None else None,
                "failed": fail_u is not None,
                "failure_time": fmt(t0 + fail_u) if fail_u is not None else None,
                "failure_elapsed_seconds": round(fail_u, 6) if fail_u is not None else None,
            }

        reason_text = {
            "confirmed": "连续不高于复冷阈值达到确认时长，累计暴露已清零并开始新一轮",
            "rewarmed": "复冷确认完成前短暂回暖（重新高于复冷阈值），本轮暴露保留",
            "observation_ended": "数据结束时连续不高于复冷阈值仍未达到确认时长，本轮暴露保留",
        }
        candidates_out = [
            {
                "index": c["index"],
                "start_time": fmt(t0 + c["start_elapsed"]),
                "end_time": fmt(t0 + c["end_elapsed"]),
                "elapsed_start_seconds": round(c["start_elapsed"], 6),
                "elapsed_end_seconds": round(c["end_elapsed"], 6),
                "duration_seconds": round(c["end_elapsed"] - c["start_elapsed"], 6),
                "confirm_target_seconds": round(
                    c["start_elapsed"] + recool_cfg.confirm_seconds, 6
                ),
                "confirmed": c["reason"] == "confirmed",
                "cleared_at": fmt(t0 + c["reset_elapsed"]) if c["reset_elapsed"] is not None else None,
                "cleared_elapsed_seconds": (
                    round(c["reset_elapsed"], 6) if c["reset_elapsed"] is not None else None
                ),
                "status": c["reason"],
                "status_text": reason_text[c["reason"]],
                "cleared_round_index": c["round_index"],
                "interrupted_round_index": c.get("interrupted_round_index"),
            }
            for c in m_candidates
        ]
        resets_out = [
            {
                "time": fmt(t0 + r["at_elapsed"]),
                "elapsed_seconds": round(r["at_elapsed"], 6),
                "candidate_index": r["candidate_index"],
                "cleared_round_index": r["round_index"],
                "hot_exposure_cleared_seconds": round(r["cleared_hot"], 6),
            }
            for r in m_resets
        ]
        insufficient_out: Optional[dict[str, Any]] = None
        if m_insufficient is not None:
            ins = m_insufficient
            insufficient_out = {
                "attempt_index": ins["attempt_index"],
                "candidate_index": ins["candidate_index"],
                "reason": ins["reason"],
                "reason_text": reason_text[ins["reason"]],
                "round_index": ins["round_index"],
                "interrupted_time": fmt(t0 + ins["at_elapsed"]),
                "interrupted_elapsed_seconds": round(ins["at_elapsed"], 6),
                "candidate_start_time": fmt(t0 + ins["candidate_start_elapsed"]),
                "candidate_start_elapsed_seconds": round(ins["candidate_start_elapsed"], 6),
            }

        failure_out: Optional[dict[str, Any]] = None
        if m_failure is not None:
            ff = m_failure
            failure_out = {
                "time": fmt(t0 + ff["elapsed"]),
                "elapsed_seconds": round(ff["elapsed"], 6),
                "round_index": ff["round_index"],
                "round_start_time": fmt(t0 + ff["round_start_elapsed"]),
                "round_start_elapsed_seconds": round(ff["round_start_elapsed"], 6),
                "cumulative_exposure_seconds": round(exposure_limit, 6),
                "exposure_limit_seconds": exposure_limit,
                "insufficient_recool_attempt_index": (
                    m_insufficient["attempt_index"] if m_insufficient is not None else None
                ),
                "insufficient_recool_candidate_index": (
                    m_insufficient["candidate_index"] if m_insufficient is not None else None
                ),
            }

        kept_rounds = [
            rd for rd in m_rounds
            if rd["reset_elapsed"] is None and rd["failure_elapsed"] is None
        ]
        uncleared = sum(rd["hot"] for rd in kept_rounds)
        if failure_out is not None:
            uncleared = exposure_limit

        verdict = "reject" if failure_out is not None else "pass"
        recool_block = {
            "enabled": True,
            "recool_threshold": recool_cfg.threshold,
            "confirm_seconds": recool_cfg.confirm_seconds,
            "rule": "T>限温累计暴露；复冷阈值<T<=限温只暂停累计并保留本轮记忆；"
            "连续 T<=复冷阈值达到确认时长才清零并开始新一轮；短暂回暖或结束未确认不清零",
            "rounds": [round_entry(rd) for rd in m_rounds],
            "recool_candidates": candidates_out,
            "resets": resets_out,
            "uncleared_cumulative_exposure_seconds": round(uncleared, 6),
            "insufficient_recool": insufficient_out,
            "first_failure_time": failure_out,
            "verdict": verdict,
        }
        # 启用复冷记忆时以“未被有效复冷清除的累计暴露”口径裁决；
        # 原连续区间证据仍在 exceedance_intervals 中保留，供新旧口径对照。
        top_first_failure = failure_out

    result: dict[str, Any] = {
        "status": "reject" if top_first_failure is not None else "pass",
        "verdict": "拒收" if top_first_failure is not None else "放行",
        "model": {
            "equation": "dT/dt = (T_env(t) - T) / tau",
            "ambient_assumption": "相邻记录间环境温度线性变化",
            "solver": "每段闭式解析解；阈值穿越为单调区间二分求根（容差 1e-12s），无离散采样裁决",
            "exceedance_rule": "严格超限 T > T_limit；连续超温区间在全局取并集",
            "segment_initial_condition": "每段以该记录时刻实测箱温为初值锚定，段内由闭式解推进；"
            "model_record_gap 给出段末模型值与下一读数的偏差作为证据",
            "tau_switching": "tau 取段起点箱盖状态（开启/关闭），状态在记录时刻切换",
        },
        "parameters": {
            "tau_closed": tau_closed,
            "tau_open": tau_open,
            "box_temp_limit": box_temp_limit,
            "exposure_limit_seconds": exposure_limit,
        },
        "record_count": len(parsed),
        "segments": segments,
        "exceedance_intervals": exceedance_intervals,
        "total_exceedance_seconds": round(total_exceedance, 6),
        "first_failure_time": top_first_failure,
        "curve": curve,
        "records_echo": [
            {
                "time": fmt(r["t"]),
                "elapsed_seconds": round(r["t"] - t0, 6),
                "box_temp": r["box"],
                "ambient_temp": r["amb"],
                "lid_open": r["lid_open"],
            }
            for r in parsed
        ],
    }
    if recool_block is not None:
        result["recool"] = recool_block
        result["model"]["recool_rule"] = recool_block["rule"]
    return result


class _RecoolMachine:
    """沿区域恒定子区间按时间推进复冷记忆。

    状态只在子区间边界（精确穿越时刻，含跨记录拼接处）迁移；
    cold 连续达到确认时长的“确认完成”同样是一个精确定位的事件。
    """

    def __init__(
        self,
        *,
        zone_pieces: list[tuple[float, float, str]],
        cfg: _RecoolConfig,
        exposure_limit: float,
        total_duration: float,
    ) -> None:
        self.pieces = zone_pieces
        self.cfg = cfg
        self.exposure_limit = exposure_limit
        self.total_duration = total_duration

        self.rounds: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.resets: list[dict[str, Any]] = []
        self.failure: Optional[dict[str, Any]] = None
        # 首个导致失效的复冷不足（回暖打断），用于拒收时指明哪次复冷不足
        self.insufficient: Optional[dict[str, Any]] = None

        self.cur: Optional[dict[str, Any]] = None
        self.zone: Optional[str] = None
        self.cand_start: Optional[float] = None
        self.reset_at: Optional[float] = None  # 已排定的确认完成绝对（相对）时刻

    def _new_round(self, u: float) -> dict[str, Any]:
        rd = {
            "index": len(self.rounds),
            "start_elapsed": u,
            "hot": 0.0,
            "reset_elapsed": None,
            "failure_elapsed": None,
        }
        self.rounds.append(rd)
        return rd

    def _open_candidate(self, u: float) -> None:
        # 仅当存在尚未清零的本轮记忆（已发生过超温）时，冷区才构成复冷候选；
        # 首段即冷（从未热过）或已清零后的冷区不产生候选。
        if self.cur is None:
            self.cand_start = None
            self.reset_at = None
            return
        self.cand_start = u
        # 失效为终局：失效之后的回落不再可能清零，也不排定确认
        self.reset_at = u + self.cfg.confirm_seconds if self.failure is None else None

    def _close_candidate(self, end_u: float, reason: str) -> None:
        if self.cand_start is None:
            return
        idx = len(self.candidates)
        reset_u = end_u if reason == "confirmed" else None
        self.candidates.append(
            {
                "index": idx,
                "start_elapsed": self.cand_start,
                "end_elapsed": end_u,
                "reason": reason,
                "reset_elapsed": reset_u,
                "round_index": self.cur["index"] if self.cur is not None else None,
                "interrupted_round_index": (
                    self.cur["index"] if self.cur is not None and reason != "confirmed" else None
                ),
            }
        )
        if reason == "rewarmed":
            # 每次回暖打断都更新“最近一次复冷不足”；后段失效时归咎于失效前
            # 最后一次未能清零的复冷尝试（本可阻止本次拒收的最近机会）。
            if self.failure is None:
                self.insufficient = {
                    "attempt_index": idx,
                    "candidate_index": idx,
                    "reason": "rewarmed",
                    "round_index": self.cur["index"] if self.cur is not None else None,
                    "at_elapsed": end_u,
                    "candidate_start_elapsed": self.cand_start,
                }
        elif reason == "observation_ended":
            if self.insufficient is None and self.failure is None and self.cur is not None:
                self.insufficient = {
                    "attempt_index": idx,
                    "candidate_index": idx,
                    "reason": "observation_ended",
                    "round_index": self.cur["index"],
                    "at_elapsed": end_u,
                    "candidate_start_elapsed": self.cand_start,
                }
        self.cand_start = None
        self.reset_at = None

    def _do_reset(self, u: float) -> None:
        assert self.cur is not None and self.cand_start is not None
        self.cur["reset_elapsed"] = u
        cleared_hot = self.cur["hot"]
        round_index = self.cur["index"]
        idx = len(self.candidates)
        # 候选区间在确认完成时刻闭合
        self.candidates.append(
            {
                "index": idx,
                "start_elapsed": self.cand_start,
                "end_elapsed": u,
                "reason": "confirmed",
                "reset_elapsed": u,
                "round_index": round_index,
                "interrupted_round_index": None,
            }
        )
        self.resets.append(
            {
                "at_elapsed": u,
                "candidate_index": idx,
                "round_index": round_index,
                "cleared_hot": cleared_hot,
            }
        )
        self.cur = None
        self.cand_start = None
        self.reset_at = None
        # 本轮已被有效复冷清零：此前该轮的“复冷不足”不再影响后续新轮，
        # 后段若再失效，应归咎于清零之后新轮中的复冷不足。
        self.insufficient = None

    def _enter(self, zone: str, u: float) -> None:
        """处理在 u 时刻进入新区段（离开旧区域的副作用先做）。"""
        old = self.zone
        if old == zone:
            return
        if old == ZONE_COLD:
            # 离开复冷区而未确认 → 本次复冷不足（回暖打断）
            self._close_candidate(u, "rewarmed")
        if zone == ZONE_HOT and self.cur is None:
            self.cur = self._new_round(u)
        if zone == ZONE_COLD:
            self._open_candidate(u)
        self.zone = zone

    def run(self) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        Optional[dict[str, Any]],
        Optional[dict[str, Any]],
    ]:
        if not self.pieces:
            return self.rounds, self.candidates, self.resets, self.failure, self.insufficient

        self.zone = self.pieces[0][2]
        if self.zone == ZONE_HOT:
            self.cur = self._new_round(0.0)
        elif self.zone == ZONE_COLD:
            self._open_candidate(0.0)

        for a, b, zone in self.pieces:
            self._enter(zone, a)
            # 区段内区域恒定；cold 时确认完成可能落在区段内部
            cur = a
            while b - cur > MERGE_TOL:
                if zone == ZONE_COLD and self.reset_at is not None and self.reset_at <= b:
                    # [cur, reset_at] 维持 cold：确认完成清零
                    u = self.reset_at
                    if self.cur is not None:
                        self._do_reset(u)
                    cur = u
                    # 清零后仍处 cold；不再排定确认，直至离开再重新进入 cold
                    continue
                span = b - cur
                if zone == ZONE_HOT:
                    # 该轮热暴露全程记账（失效后仍计入，用于展示该轮完整热暴露）
                    assert self.cur is not None
                    before = self.cur["hot"]
                    if self.failure is None and before + span + MERGE_TOL >= self.exposure_limit:
                        fail_u = cur + (self.exposure_limit - before)
                        self.cur["failure_elapsed"] = fail_u
                        self.failure = {
                            "elapsed": fail_u,
                            "round_index": self.cur["index"],
                            "round_start_elapsed": self.cur["start_elapsed"],
                        }
                    self.cur["hot"] += span
                cur = b

        # 收尾：仍有未确认候选区间（数据结束）
        if self.cand_start is not None:
            self._close_candidate(self.total_duration, "observation_ended")

        return self.rounds, self.candidates, self.resets, self.failure, self.insufficient
