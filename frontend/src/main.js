import "./styles.css";

const PRESETS = {
  reject: {
    label: "拒收演示：读数全合格、途中升温",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 25, lid_open: false },
      { time: 60, box_temp: 7.806654, ambient_temp: 25, lid_open: false },
      { time: 1560, box_temp: 7.254505, ambient_temp: 3, lid_open: false },
      { time: 2460, box_temp: 3.211819, ambient_temp: 3, lid_open: false },
      { time: 3360, box_temp: 3.010546, ambient_temp: 3, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
  },
  pass: {
    label: "放行演示：全程低温",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 3.0, lid_open: false },
      { time: 300, box_temp: 3.551819, ambient_temp: 3.5, lid_open: false },
      { time: 600, box_temp: 3.703003, ambient_temp: 4.0, lid_open: false },
      { time: 900, box_temp: 3.817165, ambient_temp: 3.8, lid_open: false },
      { time: 1200, box_temp: 3.585587, ambient_temp: 3.2, lid_open: false },
      { time: 1500, box_temp: 3.268274, ambient_temp: 3.0, lid_open: false },
      { time: 1800, box_temp: 3.025116, ambient_temp: 2.8, lid_open: false },
      { time: 2100, box_temp: 2.772452, ambient_temp: 2.5, lid_open: false },
      { time: 2400, box_temp: 2.41629, ambient_temp: 2.0, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
  },
  short: {
    label: "短时超温：有暴露但不足时长",
    records: [
      { time: 0, box_temp: 4.0, ambient_temp: 4, lid_open: false },
      { time: 600, box_temp: 15.92102, ambient_temp: 25, lid_open: true },
      { time: 1200, box_temp: 23.771294, ambient_temp: 25, lid_open: false },
      { time: 1800, box_temp: 12.912692, ambient_temp: 4, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 3600 },
  },
  recoolInsuf: {
    label: "复冷记忆·拒收：复冷不足，累计暴露达限",
    records: [
      { time: 0, box_temp: 3.0, ambient_temp: 25, lid_open: false },
      { time: 300, box_temp: 7.709666, ambient_temp: 0, lid_open: false },
      { time: 900, box_temp: 1.04339, ambient_temp: 0, lid_open: false },
      { time: 1200, box_temp: 9.580828, ambient_temp: 25, lid_open: false },
      { time: 1600, box_temp: 9.743104, ambient_temp: 0, lid_open: false },
      { time: 2200, box_temp: 1.318586, ambient_temp: 0, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
    recool: { enabled: true, recool_threshold: 4, confirm_seconds: 600 },
  },
  recoolReset: {
    label: "复冷记忆·放行：有效复冷清零后新一轮",
    records: [
      { time: 0, box_temp: 3.0, ambient_temp: 25, lid_open: false },
      { time: 300, box_temp: 7.709666, ambient_temp: 0, lid_open: false },
      { time: 1100, box_temp: 0.535694, ambient_temp: 0, lid_open: false },
      { time: 1700, box_temp: 14.264189, ambient_temp: 25, lid_open: false },
      { time: 1850, box_temp: 13.161869, ambient_temp: 0, lid_open: false },
      { time: 2400, box_temp: 2.104316, ambient_temp: 0, lid_open: false },
    ],
    parameters: { tau_closed: 300, tau_open: 90, box_temp_limit: 8, exposure_limit_seconds: 600 },
    recool: { enabled: true, recool_threshold: 4, confirm_seconds: 600 },
  },
};

const state = {
  records: structuredClone(PRESETS.reject.records),
  parameters: { ...PRESETS.reject.parameters },
  recool: { enabled: false, recool_threshold: 4, confirm_seconds: 600 },
  result: null,
  error: null,
  loading: false,
};

const app = document.getElementById("app");

function fmtElapsed(sec) {
  const s = Math.round(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}
function fmtTemp(v) {
  return Number(v).toFixed(2);
}
function fmtDuration(sec) {
  const s = Number(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = Math.round(s % 60);
  if (h > 0) return `${h} 小时 ${m} 分 ${r} 秒`;
  if (m > 0) return `${m} 分 ${r} 秒`;
  return `${r} 秒`;
}

/* ---------------- 录入区 ---------------- */

function renderRecoolForm() {
  const rc = state.recool;
  return `
  <div class="recool-box${rc.enabled ? " on" : ""}">
    <label class="recool-head">
      <input id="recool_enabled" type="checkbox" ${rc.enabled ? "checked" : ""} style="width:auto" />
      <span>③ 启用“复冷记忆”（短暂回落不再自动恢复稳定）</span>
    </label>
    <div class="recool-body">
      <div class="hint" style="margin-top:0">
        启用后：箱温 <b>&gt; 允许箱温</b> 时累计暴露；处于
        <b>复冷阈值 与 限温之间</b> 时只暂停累计并保留本轮记忆；
        只有<b>连续不高于复冷阈值达到确认时长</b>才清零并开始新一轮；
        短暂回暖或记录结束时未确认的累计暴露不会清零，后段超温与之累计。
        未启用时沿用原裁决口径，原请求、结论及证据不变。
      </div>
      <div class="params-grid">
        <label class="field"><span>复冷阈值（℃，须严格低于允许箱温）</span>
          <input id="recool_threshold" type="number" step="0.1" value="${rc.recool_threshold}" ${rc.enabled ? "" : "disabled"} /></label>
        <label class="field"><span>复冷确认时长（秒，连续达标才清零）</span>
          <input id="recool_confirm" type="number" step="any" value="${rc.confirm_seconds}" ${rc.enabled ? "" : "disabled"} /></label>
      </div>
    </div>
  </div>`;
}

function renderForm() {
  const p = state.parameters;
  return `
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${state.records
          .map(
            (r, i) => `
        <tr>
          <td><input data-k="time" data-i="${i}" value="${r.time}" /></td>
          <td><input data-k="box_temp" data-i="${i}" type="number" step="0.01" value="${r.box_temp}" /></td>
          <td><input data-k="ambient_temp" data-i="${i}" type="number" step="0.01" value="${r.ambient_temp}" /></td>
          <td style="text-align:center"><input data-k="lid_open" data-i="${i}" type="checkbox" ${r.lid_open ? "checked" : ""} /></td>
          <td><button class="row-btn" data-del="${i}" title="删除该行">✕</button></td>
        </tr>`
          )
          .join("")}
      </tbody>
    </table>
    </div>
    <div class="count-note">当前 ${state.records.length} 条（须 4–30 条）</div>

    <h2 style="margin-top:18px">② 模型参数与保存要求</h2>
    <div class="params-grid">
      <label class="field"><span>箱盖关闭热惯性 τ关闭（秒）</span>
        <input id="tau_closed" type="number" step="any" value="${p.tau_closed}" /></label>
      <label class="field"><span>箱盖开启热惯性 τ开启（秒）</span>
        <input id="tau_open" type="number" step="any" value="${p.tau_open}" /></label>
      <label class="field"><span>允许箱温（℃）</span>
        <input id="box_temp_limit" type="number" step="0.1" value="${p.box_temp_limit}" /></label>
      <label class="field"><span>允许连续暴露时长（秒）</span>
        <input id="exposure_limit_seconds" type="number" step="any" value="${p.exposure_limit_seconds}" /></label>
    </div>
    ${renderRecoolForm()}
    <div class="hint">约定：相邻记录之间环境温度按<b>线性变化</b>；箱温按一阶模型
      <code>dT/dt=(T_env−T)/τ</code> 逐段闭式求解；箱盖状态在记录时刻切换 τ。</div>

    <div class="btn-row">
      <button class="action" id="submit">提交审计</button>
      <button class="ghost" id="addRow">+ 增加记录</button>
    </div>
    <div class="btn-row">
      <button class="ghost" data-preset="reject">拒收演示数据</button>
      <button class="ghost" data-preset="pass">放行演示数据</button>
      <button class="ghost" data-preset="short">短时超温数据</button>
    </div>
    <div class="btn-row">
      <button class="ghost" data-preset="recoolInsuf">复冷记忆·拒收（复冷不足）</button>
      <button class="ghost" data-preset="recoolReset">复冷记忆·放行（有效复冷）</button>
    </div>
    ${state.error ? `<div class="error-box">${state.error}</div>` : ""}
  </div>`;
}

function collectInputs() {
  const recs = state.records.map((r, i) => {
    const t = document.querySelector(`[data-k="time"][data-i="${i}"]`).value.trim();
    return {
      time: /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : t,
      box_temp: Number(document.querySelector(`[data-k="box_temp"][data-i="${i}"]`).value),
      ambient_temp: Number(document.querySelector(`[data-k="ambient_temp"][data-i="${i}"]`).value),
      lid_open: document.querySelector(`[data-k="lid_open"][data-i="${i}"]`).checked,
    };
  });
  const params = {
    tau_closed: Number(document.getElementById("tau_closed").value),
    tau_open: Number(document.getElementById("tau_open").value),
    box_temp_limit: Number(document.getElementById("box_temp_limit").value),
    exposure_limit_seconds: Number(document.getElementById("exposure_limit_seconds").value),
  };
  const recool = {
    enabled: document.getElementById("recool_enabled").checked,
    recool_threshold: Number(document.getElementById("recool_threshold").value),
    confirm_seconds: Number(document.getElementById("recool_confirm").value),
  };
  if (recool.enabled) params.recool = recool;
  return { recs, params, recool };
}

async function submitAudit() {
  const { recs, params, recool } = collectInputs();
  state.records = recs;
  state.parameters = params;
  state.recool = recool;
  state.loading = true;
  state.error = null;
  state.result = null;
  render();
  try {
    const resp = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: recs, parameters: params }),
    });
    const body = await resp.json();
    if (body.status === "invalid") {
      state.error = body.errors
        .map((e) => `<div><code>${e.code}</code> ${e.message}${e.field ? `（字段：${e.field}）` : ""}</div>`)
        .join("");
    } else {
      state.result = body;
    }
  } catch (e) {
    state.error = `无法连接审计 API：${e.message}`;
  } finally {
    state.loading = false;
    render();
  }
}

/* ---------------- 结果区 ---------------- */

function renderVerdict(r) {
  if (state.loading) return `<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温…</div></div>`;
  if (state.error)
    return `<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;
  if (!r)
    return `<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;

  if (r.status === "pass") {
    let extra = "";
    if (r.recool) {
      extra = `<br/>复冷记忆：已清零 <strong>${r.recool.resets.length}</strong> 轮，
        未被清除的累计暴露 <strong>${fmtDuration(r.recool.uncleared_cumulative_exposure_seconds)}</strong>（未达限额）。`;
    }
    return `<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">箱温连续曲线全程未形成达到 <strong>${fmtDuration(
        r.parameters.exposure_limit_seconds
      )}</strong> 的连续超温区间。<br/>
      累计超温时长 <strong>${fmtDuration(r.total_exceedance_seconds)}</strong>，
      连续超温区间 <strong>${r.exceedance_intervals.length}</strong> 个。${extra}</div></div>`;
  }
  const ff = r.first_failure_time;
  let recoolNote = "";
  if (r.recool) {
    const ins = r.recool.insufficient_recool;
    recoolNote = `<br/>复冷记忆口径：未被有效复冷清除的同一轮累计热暴露达到限额。` +
      (ins
        ? ` 此前第 <strong>${ins.candidate_index + 1}</strong> 次复冷（${ins.reason === "rewarmed" ? "回暖打断" : "结束未确认"}）不足，未能清零。`
        : " 该轮此前无有效复冷。");
  }
  return `<div class="verdict reject"><div class="badge">拒 收</div>
    <div class="sub">油样自 <strong>${ff.time}</strong>
    （距首条记录 ${fmtElapsed(ff.elapsed_seconds)}）起失效。<br/>
    共 ${r.exceedance_intervals.length} 个连续超温区间，累计超温 ${fmtDuration(
    r.total_exceedance_seconds
  )}。${recoolNote}</div></div>`;
}

function renderFailureCard(r) {
  if (!r || r.status !== "reject") return "";
  const ff = r.first_failure_time;
  if (r.recool) {
    const rc = r.recool;
    const ins = rc.insufficient_recool;
    const round = rc.rounds[ff.round_index];
    return `<div class="failure-card">
    <h3>最早失效时刻证据（复冷记忆口径）</h3>
    <div class="kv">
      暴露轮次起点：<b>${round ? round.start_time : ff.round_start_time}</b>
      （距首条记录 ${fmtElapsed(ff.round_start_elapsed_seconds)}）<br/>
      该轮热暴露累计：<b>${fmtDuration(ff.cumulative_exposure_seconds)}</b> ＝ 允许
      ${fmtDuration(r.parameters.exposure_limit_seconds)}（跨多段超温与暂停带累计，未被清零）<br/>
      失效解析时刻：<b>${ff.time}</b>（距首条记录 ${fmtElapsed(ff.elapsed_seconds)}，
      闭式曲线精确定位，非采样点）<br/>
      归咎的复冷不足：${
        ins
          ? `第 <b>${ins.candidate_index + 1}</b> 次复冷候选区间
             起于 ${ins.candidate_start_time}，因「${ins.reason_text}」
             于 ${ins.interrupted_time} 中断（第 ${ins.round_index + 1} 轮记忆保留）`
          : "<b>无</b>——失效轮此前未发生过有效复冷，也无可归咎的复冷尝试"
      }
    </div></div>`;
  }
  const iv = r.exceedance_intervals[ff.interval_index];
  return `<div class="failure-card">
    <h3>最早失效时刻证据</h3>
    <div class="kv">
      超温区间起点：<b>${iv.start_time}</b>（${fmtElapsed(iv.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${iv.end_time}</b>（${fmtElapsed(iv.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${fmtDuration(iv.duration_seconds)}</b> ≥ 允许 ${fmtDuration(
    r.parameters.exposure_limit_seconds
  )}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${ff.time}</b>
      （距首条记录 ${fmtElapsed(ff.elapsed_seconds)}）
    </div></div>`;
}

/* ---------------- 复冷记忆 ---------------- */

function renderRecool(r) {
  const rc = r.recool;
  if (!rc) return "";
  const roundsRows = rc.rounds
    .map((rd) => `<tr>
      <td>${rd.index + 1}</td>
      <td>${rd.start_time}</td>
      <td>${rd.end_time}</td>
      <td class="num">${fmtDuration(rd.hot_exposure_seconds)}（${rd.hot_exposure_seconds.toFixed(1)}s）</td>
      <td>${
        rd.failed
          ? `<span class="tag yes">拒收 @ ${rd.failure_time}</span>`
          : rd.reset
          ? `<span class="tag no">已清零 @ ${rd.reset_time}</span>`
          : `<span class="tag closed">保留至结束</span>`
      }</td>
    </tr>`)
    .join("");
  const candRows = rc.recool_candidates
    .map((c) => {
      const tag =
        c.status === "confirmed"
          ? `<span class="tag yes">确认清零</span>`
          : c.status === "rewarmed"
          ? `<span class="tag no">回暖打断（复冷不足）</span>`
          : `<span class="tag no">结束未确认</span>`;
      return `<tr>
        <td>${c.index + 1}</td>
        <td>${c.start_time}</td>
        <td>${c.end_time}</td>
        <td class="num">${c.duration_seconds.toFixed(1)}s（需 ${rc.confirm_seconds}s）</td>
        <td>${tag}</td>
        <td>${c.cleared_at ? c.cleared_at : "—"}</td>
        <td>${c.status_text}</td>
      </tr>`;
    })
    .join("");
  return `
  <div class="recool-panel">
    <div class="section-title" style="margin-top:4px">复冷记忆 · 逐轮暴露与复冷裁决</div>
    <div class="hint" style="margin:0 0 8px">
      复冷阈值 <b>${rc.recool_threshold}℃</b>，确认时长 <b>${fmtDuration(rc.confirm_seconds)}</b>。
      ${rc.rule}
    </div>
    <table class="data">
      <thead><tr><th>轮次</th><th>本轮起</th><th>本轮止</th><th class="num">热暴露累计</th><th>结局（清零 / 拒收时刻）</th></tr></thead>
      <tbody>${roundsRows}</tbody>
    </table>
    <div class="section-title" style="font-size:13px">复冷候选区间（连续不高于复冷阈值）</div>
    <table class="data">
      <thead><tr><th>#</th><th>进入复冷</th><th>离开/确认</th><th class="num">持续/要求</th><th>状态</th><th>清零时刻</th><th>原因</th></tr></thead>
      <tbody>${candRows}</tbody>
    </table>
  </div>`;
}

/* ---------------- SVG 连续曲线 ---------------- */

function buildChart(r) {
  const W = 920, H = 380, ML = 56, MR = 18, MT = 18, MB = 44;
  const iw = W - ML - MR, ih = H - MT - MB;
  const curve = r.curve;
  const xmax = curve[curve.length - 1].elapsed_seconds;
  const extraLevels = [r.parameters.box_temp_limit];
  if (r.recool) extraLevels.push(r.recool.recool_threshold);
  const allT = curve.flatMap((p) => [p.box_temp, p.ambient_temp]).concat(extraLevels);
  let ymin = Math.min(...allT), ymax = Math.max(...allT);
  const pad = Math.max(1, (ymax - ymin) * 0.08);
  ymin -= pad; ymax += pad;
  const X = (t) => ML + (t / xmax) * iw;
  const Y = (v) => MT + ih - ((v - ymin) / (ymax - ymin)) * ih;

  // 箱盖开启背景（由连续曲线点合并相邻同状态）
  const lidRects = [];
  let start = null;
  for (let i = 0; i < curve.length; i++) {
    if (curve[i].lid_open && start === null) start = curve[i].elapsed_seconds;
    if ((!curve[i].lid_open || i === curve.length - 1) && start !== null) {
      const end = curve[i].lid_open ? curve[i].elapsed_seconds : curve[i - 1].elapsed_seconds;
      lidRects.push([start, end]);
      start = null;
    }
  }

  const path = (key) =>
    curve.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.elapsed_seconds).toFixed(2)},${Y(p[key]).toFixed(2)}`).join(" ");

  // 超温区间红色遮罩
  const hotRects = r.exceedance_intervals
    .map(
      (iv) =>
        `<rect x="${X(iv.elapsed_start_seconds)}" y="${MT}" width="${
          X(iv.elapsed_end_seconds) - X(iv.elapsed_start_seconds)
        }" height="${ih}" fill="#ff5d5d" fill-opacity="0.16" />`
    )
    .join("");

  const lid = lidRects
    .map(
      ([a, b]) =>
        `<rect x="${X(a)}" y="${MT}" width="${X(b) - X(a)}" height="${ih}" fill="#f5a623" fill-opacity="0.10" />`
    )
    .join("");

  // 复冷候选区间底色：确认清零=绿，回暖打断/结束未确认（复冷不足）=蓝
  let recoolRects = "";
  let resetMarks = "";
  if (r.recool) {
    recoolRects = r.recool.recool_candidates
      .map((c) => {
        const color = c.confirmed ? "#2ecc71" : "#4da3ff";
        return `<rect x="${X(c.elapsed_start_seconds)}" y="${MT}" width="${
          X(c.elapsed_end_seconds) - X(c.elapsed_start_seconds)
        }" height="${ih}" fill="${color}" fill-opacity="0.10" />`;
      })
      .join("");
    resetMarks = r.recool.resets
      .map(
        (z) => `<line x1="${X(z.elapsed_seconds)}" y1="${MT}" x2="${X(z.elapsed_seconds)}" y2="${MT + ih}"
          stroke="#2ecc71" stroke-width="1.6" stroke-dasharray="3 5"/>
        <text x="${X(z.elapsed_seconds)}" y="${MT + 28}" fill="#2ecc71" font-size="11" text-anchor="middle">清零 ${z.time}</text>`
      )
      .join("");
  }

  const rcThreshold = r.recool
    ? `<line x1="${ML}" y1="${Y(r.recool.recool_threshold)}" x2="${W - MR}" y2="${Y(r.recool.recool_threshold)}"
        stroke="#4da3ff" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="${W - MR}" y="${Y(r.recool.recool_threshold) - 5}" fill="#4da3ff" font-size="11" text-anchor="end">复冷阈值 ${r.recool.recool_threshold}℃</text>`
    : "";

  // 坐标轴与网格
  const yTicks = [];
  const steps = 5;
  for (let k = 0; k <= steps; k++) {
    const v = ymin + ((ymax - ymin) * k) / steps;
    yTicks.push(`<line x1="${ML}" y1="${Y(v)}" x2="${W - MR}" y2="${Y(v)}" stroke="#22303f" stroke-width="1"/>
      <text x="${ML - 8}" y="${Y(v) + 4}" fill="#93a4b5" font-size="11" text-anchor="end">${v.toFixed(1)}</text>`);
  }
  const xTicks = [];
  const nx = 6;
  for (let k = 0; k <= nx; k++) {
    const t = (xmax * k) / nx;
    xTicks.push(`<line x1="${X(t)}" y1="${MT + ih}" x2="${X(t)}" y2="${MT + ih + 5}" stroke="#93a4b5"/>
      <text x="${X(t)}" y="${MT + ih + 20}" fill="#93a4b5" font-size="11" text-anchor="middle">${fmtElapsed(t)}</text>`);
  }

  const limit = r.parameters.box_temp_limit;
  const dots = r.records_echo
    .map(
      (rec) =>
        `<circle cx="${X(rec.elapsed_seconds)}" cy="${Y(rec.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${rec.time}：箱温 ${fmtTemp(rec.box_temp)}℃，环境 ${fmtTemp(
          rec.ambient_temp
        )}℃，箱盖${rec.lid_open ? "开启" : "关闭"}</title></circle>`
    )
    .join("");

  const ff = r.first_failure_time;
  const ffLine = ff
    ? `<line x1="${X(ff.elapsed_seconds)}" y1="${MT}" x2="${X(ff.elapsed_seconds)}" y2="${MT + ih}"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${X(ff.elapsed_seconds)}" y="${MT + 12}" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${ff.time}</text>`
    : "";

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="箱温连续曲线">
    ${lid}${hotRects}${recoolRects}
    ${yTicks.join("")}${xTicks.join("")}
    <line x1="${ML}" y1="${Y(limit)}" x2="${W - MR}" y2="${Y(limit)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="${W - MR}" y="${Y(limit) - 5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${limit}℃</text>
    ${rcThreshold}
    <path d="${path("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${path("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${dots}${ffLine}${resetMarks}
    <line x1="${ML}" y1="${MT + ih}" x2="${W - MR}" y2="${MT + ih}" stroke="#93a4b5"/>
    <line x1="${ML}" y1="${MT}" x2="${ML}" y2="${MT + ih}" stroke="#93a4b5"/>
    <text x="${ML}" y="${H - 6}" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    ${r.recool ? `<span class="swatch"><i style="background:#4da3ff"></i>复冷阈值</span>
      <span class="swatch"><i style="background:#2ecc71"></i>复冷确认清零</span>
      <span class="swatch"><i style="background:#4da3ff;opacity:.5"></i>复冷候选（不足）</span>` : ""}
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`;
}

/* ---------------- 表格 ---------------- */

function renderIntervals(r) {
  if (!r.exceedance_intervals.length)
    return `<div class="hint">无任何箱温超过允许值的连续区间。</div>`;
  return `<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${r.exceedance_intervals
      .map(
        (iv) => `<tr>
        <td>${iv.index + 1}</td><td>${iv.start_time}</td><td>${iv.end_time}</td>
        <td class="num">${fmtDuration(iv.duration_seconds)}（${iv.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${iv.reaches_limit ? "yes" : "no"}">${iv.reaches_limit ? "达到 → 拒收" : "未达到"}</span></td>
      </tr>`
      )
      .join("")}</tbody></table>`;
}

function renderSegments(r) {
  return `<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${r.segments
      .map((s) => {
        const cross = s.crossings
          .map((c) => `<span class="${c.direction}">限温${c.direction === "up" ? "↑" : "↓"}@${c.elapsed_seconds.toFixed(1)}</span>`)
          .join("，");
        const rcCross = (s.recool_crossings || [])
          .map((c) => `<span class="rc-cross">复冷${c.direction === "up" ? "↑" : "↓"}@${c.elapsed_seconds.toFixed(1)}</span>`)
          .join("，");
        return `<tr>
        <td>${s.index + 1}</td>
        <td>${s.elapsed_start_seconds} → ${s.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${s.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${s.lid_open ? "open" : "closed"}">${s.lid_open ? "开启" : "关闭"}</span></td>
        <td class="num">${s.tau_seconds}</td>
        <td class="num">${fmtTemp(s.max_temp.value)}</td>
        <td>${s.max_temp.kind === "interior" ? "段内 " + s.max_temp.elapsed_seconds.toFixed(1) + "s" : s.max_temp.kind === "start" ? "段起点" : "段终点"}</td>
        <td class="num">${fmtTemp(s.min_temp.value)}</td>
        <td>${cross || "—"}${rcCross ? `<br/>${rcCross}` : ""}</td>
      </tr>`;
      })
      .join("")}</tbody></table>`;
}

function renderResult(r) {
  if (!r) return "";
  return `
  <div class="model-note">
    求解方式：<code>${r.model.equation}</code>；${r.model.ambient_assumption}；${r.model.solver}。<br/>
    每段从记录时刻实测箱温锚定（段末模型值与下一读数偏差见各段证据），
    ${r.model.tau_switching}。${r.model.exceedance_rule}。
    ${r.recool ? `<br/>复冷口径：${r.model.recool_rule}` : ""}
  </div>
  ${renderFailureCard(r)}
  <div class="chart-wrap">${buildChart(r)}</div>

  ${r.recool ? renderRecool(r) : ""}

  <div class="section-title">${r.recool ? "原口径连续超温区间（新旧口径可对照）" : "累计连续超温区间（跨记录取并集）"}</div>
  ${renderIntervals(r)}

  <div class="section-title">各段解析极值与${r.recool ? "两道阈值" : "阈值"}穿越</div>
  ${renderSegments(r)}`;
}

function render() {
  app.innerHTML = `
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${renderForm()}
    <div>
      ${renderVerdict(state.result)}
      ${state.result ? renderResult(state.result) : `<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>`}
    </div>
  </div>`;
  bind();
}

function bind() {
  document.getElementById("submit")?.addEventListener("click", submitAudit);
  document.getElementById("addRow")?.addEventListener("click", () => {
    const { recs, params } = collectInputs();
    if (recs.length >= 30) return;
    const last = recs[recs.length - 1];
    recs.push({
      time: typeof last.time === "number" ? last.time + 600 : last.time,
      box_temp: last.box_temp, ambient_temp: last.ambient_temp, lid_open: false,
    });
    state.records = recs; state.parameters = params; render();
  });
  document.querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", () => {
      const { recs, params } = collectInputs();
      recs.splice(Number(b.dataset.del), 1);
      state.records = recs; state.parameters = params; render();
    })
  );
  document.querySelectorAll("[data-preset]").forEach((b) => {
    b.addEventListener("click", () => {
      const pre = PRESETS[b.dataset.preset];
      state.records = structuredClone(pre.records);
      state.parameters = { ...pre.parameters };
      state.recool = pre.recool
        ? structuredClone(pre.recool)
        : { enabled: false, recool_threshold: 4, confirm_seconds: 600 };
      state.result = null; state.error = null; render();
    });
  });
  document.getElementById("recool_enabled")?.addEventListener("change", () => {
    const { recool } = collectInputs();
    state.recool = recool;
    render();
  });
}

render();
