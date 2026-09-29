(function(){const s=document.createElement("link").relList;if(s&&s.supports&&s.supports("modulepreload"))return;for(const t of document.querySelectorAll('link[rel="modulepreload"]'))a(t);new MutationObserver(t=>{for(const d of t)if(d.type==="childList")for(const f of d.addedNodes)f.tagName==="LINK"&&f.rel==="modulepreload"&&a(f)}).observe(document,{childList:!0,subtree:!0});function n(t){const d={};return t.integrity&&(d.integrity=t.integrity),t.referrerPolicy&&(d.referrerPolicy=t.referrerPolicy),t.crossOrigin==="use-credentials"?d.credentials="include":t.crossOrigin==="anonymous"?d.credentials="omit":d.credentials="same-origin",d}function a(t){if(t.ep)return;t.ep=!0;const d=n(t);fetch(t.href,d)}})();const k={reject:{label:"拒收演示：读数全合格、途中升温",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:60,box_temp:7.806654,ambient_temp:25,lid_open:!1},{time:1560,box_temp:7.254505,ambient_temp:3,lid_open:!1},{time:2460,box_temp:3.211819,ambient_temp:3,lid_open:!1},{time:3360,box_temp:3.010546,ambient_temp:3,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},pass:{label:"放行演示：全程低温",records:[{time:0,box_temp:4,ambient_temp:3,lid_open:!1},{time:300,box_temp:3.551819,ambient_temp:3.5,lid_open:!1},{time:600,box_temp:3.703003,ambient_temp:4,lid_open:!1},{time:900,box_temp:3.817165,ambient_temp:3.8,lid_open:!1},{time:1200,box_temp:3.585587,ambient_temp:3.2,lid_open:!1},{time:1500,box_temp:3.268274,ambient_temp:3,lid_open:!1},{time:1800,box_temp:3.025116,ambient_temp:2.8,lid_open:!1},{time:2100,box_temp:2.772452,ambient_temp:2.5,lid_open:!1},{time:2400,box_temp:2.41629,ambient_temp:2,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},short:{label:"短时超温：有暴露但不足时长",records:[{time:0,box_temp:4,ambient_temp:4,lid_open:!1},{time:600,box_temp:15.92102,ambient_temp:25,lid_open:!0},{time:1200,box_temp:23.771294,ambient_temp:25,lid_open:!1},{time:1800,box_temp:12.912692,ambient_temp:4,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:3600}},recoolInsuf:{label:"复冷记忆·拒收：复冷不足，累计暴露达限",records:[{time:0,box_temp:3,ambient_temp:25,lid_open:!1},{time:300,box_temp:7.709666,ambient_temp:0,lid_open:!1},{time:900,box_temp:1.04339,ambient_temp:0,lid_open:!1},{time:1200,box_temp:9.580828,ambient_temp:25,lid_open:!1},{time:1600,box_temp:9.743104,ambient_temp:0,lid_open:!1},{time:2200,box_temp:1.318586,ambient_temp:0,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600},recool:{enabled:!0,recool_threshold:4,confirm_seconds:600}},recoolReset:{label:"复冷记忆·放行：有效复冷清零后新一轮",records:[{time:0,box_temp:3,ambient_temp:25,lid_open:!1},{time:300,box_temp:7.709666,ambient_temp:0,lid_open:!1},{time:1100,box_temp:.535694,ambient_temp:0,lid_open:!1},{time:1700,box_temp:14.264189,ambient_temp:25,lid_open:!1},{time:1850,box_temp:13.161869,ambient_temp:0,lid_open:!1},{time:2400,box_temp:2.104316,ambient_temp:0,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600},recool:{enabled:!0,recool_threshold:4,confirm_seconds:600}}},i={records:structuredClone(k.reject.records),parameters:{...k.reject.parameters},recool:{enabled:!1,recool_threshold:4,confirm_seconds:600},result:null,error:null,loading:!1},A=document.getElementById("app");function _(e){const s=Math.round(e),n=Math.floor(s/3600),a=Math.floor(s%3600/60),t=s%60;return n>0?`${n}:${String(a).padStart(2,"0")}:${String(t).padStart(2,"0")}`:`${a}:${String(t).padStart(2,"0")}`}function g(e){return Number(e).toFixed(2)}function p(e){const s=Number(e),n=Math.floor(s/3600),a=Math.floor(s%3600/60),t=Math.round(s%60);return n>0?`${n} 小时 ${a} 分 ${t} 秒`:a>0?`${a} 分 ${t} 秒`:`${t} 秒`}function H(){const e=i.recool;return`
  <div class="recool-box${e.enabled?" on":""}">
    <label class="recool-head">
      <input id="recool_enabled" type="checkbox" ${e.enabled?"checked":""} style="width:auto" />
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
          <input id="recool_threshold" type="number" step="0.1" value="${e.recool_threshold}" ${e.enabled?"":"disabled"} /></label>
        <label class="field"><span>复冷确认时长（秒，连续达标才清零）</span>
          <input id="recool_confirm" type="number" step="any" value="${e.confirm_seconds}" ${e.enabled?"":"disabled"} /></label>
      </div>
    </div>
  </div>`}function D(){const e=i.parameters;return`
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${i.records.map((s,n)=>`
        <tr>
          <td><input data-k="time" data-i="${n}" value="${s.time}" /></td>
          <td><input data-k="box_temp" data-i="${n}" type="number" step="0.01" value="${s.box_temp}" /></td>
          <td><input data-k="ambient_temp" data-i="${n}" type="number" step="0.01" value="${s.ambient_temp}" /></td>
          <td style="text-align:center"><input data-k="lid_open" data-i="${n}" type="checkbox" ${s.lid_open?"checked":""} /></td>
          <td><button class="row-btn" data-del="${n}" title="删除该行">✕</button></td>
        </tr>`).join("")}
      </tbody>
    </table>
    </div>
    <div class="count-note">当前 ${i.records.length} 条（须 4–30 条）</div>

    <h2 style="margin-top:18px">② 模型参数与保存要求</h2>
    <div class="params-grid">
      <label class="field"><span>箱盖关闭热惯性 τ关闭（秒）</span>
        <input id="tau_closed" type="number" step="any" value="${e.tau_closed}" /></label>
      <label class="field"><span>箱盖开启热惯性 τ开启（秒）</span>
        <input id="tau_open" type="number" step="any" value="${e.tau_open}" /></label>
      <label class="field"><span>允许箱温（℃）</span>
        <input id="box_temp_limit" type="number" step="0.1" value="${e.box_temp_limit}" /></label>
      <label class="field"><span>允许连续暴露时长（秒）</span>
        <input id="exposure_limit_seconds" type="number" step="any" value="${e.exposure_limit_seconds}" /></label>
    </div>
    ${H()}
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
    ${i.error?`<div class="error-box">${i.error}</div>`:""}
  </div>`}function y(){const e=i.records.map((a,t)=>{const d=document.querySelector(`[data-k="time"][data-i="${t}"]`).value.trim();return{time:/^-?\d+(\.\d+)?$/.test(d)?Number(d):d,box_temp:Number(document.querySelector(`[data-k="box_temp"][data-i="${t}"]`).value),ambient_temp:Number(document.querySelector(`[data-k="ambient_temp"][data-i="${t}"]`).value),lid_open:document.querySelector(`[data-k="lid_open"][data-i="${t}"]`).checked}}),s={tau_closed:Number(document.getElementById("tau_closed").value),tau_open:Number(document.getElementById("tau_open").value),box_temp_limit:Number(document.getElementById("box_temp_limit").value),exposure_limit_seconds:Number(document.getElementById("exposure_limit_seconds").value)},n={enabled:document.getElementById("recool_enabled").checked,recool_threshold:Number(document.getElementById("recool_threshold").value),confirm_seconds:Number(document.getElementById("recool_confirm").value)};return n.enabled&&(s.recool=n),{recs:e,params:s,recool:n}}async function J(){const{recs:e,params:s,recool:n}=y();i.records=e,i.parameters=s,i.recool=n,i.loading=!0,i.error=null,i.result=null,u();try{const t=await(await fetch("/api/audit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({records:e,parameters:s})})).json();t.status==="invalid"?i.error=t.errors.map(d=>`<div><code>${d.code}</code> ${d.message}${d.field?`（字段：${d.field}）`:""}</div>`).join(""):i.result=t}catch(a){i.error=`无法连接审计 API：${a.message}`}finally{i.loading=!1,u()}}function K(e){if(i.loading)return'<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温…</div></div>';if(i.error)return`<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;if(!e)return`<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;if(e.status==="pass"){let a="";return e.recool&&(a=`<br/>复冷记忆：已清零 <strong>${e.recool.resets.length}</strong> 轮，
        未被清除的累计暴露 <strong>${p(e.recool.uncleared_cumulative_exposure_seconds)}</strong>（未达限额）。`),`<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">箱温连续曲线全程未形成达到 <strong>${p(e.parameters.exposure_limit_seconds)}</strong> 的连续超温区间。<br/>
      累计超温时长 <strong>${p(e.total_exceedance_seconds)}</strong>，
      连续超温区间 <strong>${e.exceedance_intervals.length}</strong> 个。${a}</div></div>`}const s=e.first_failure_time;let n="";if(e.recool){const a=e.recool.insufficient_recool;n="<br/>复冷记忆口径：未被有效复冷清除的同一轮累计热暴露达到限额。"+(a?` 此前第 <strong>${a.candidate_index+1}</strong> 次复冷（${a.reason==="rewarmed"?"回暖打断":"结束未确认"}）不足，未能清零。`:" 该轮此前无有效复冷。")}return`<div class="verdict reject"><div class="badge">拒 收</div>
    <div class="sub">油样自 <strong>${s.time}</strong>
    （距首条记录 ${_(s.elapsed_seconds)}）起失效。<br/>
    共 ${e.exceedance_intervals.length} 个连续超温区间，累计超温 ${p(e.total_exceedance_seconds)}。${n}</div></div>`}function V(e){if(!e||e.status!=="reject")return"";const s=e.first_failure_time;if(e.recool){const a=e.recool,t=a.insufficient_recool,d=a.rounds[s.round_index];return`<div class="failure-card">
    <h3>最早失效时刻证据（复冷记忆口径）</h3>
    <div class="kv">
      暴露轮次起点：<b>${d?d.start_time:s.round_start_time}</b>
      （距首条记录 ${_(s.round_start_elapsed_seconds)}）<br/>
      该轮热暴露累计：<b>${p(s.cumulative_exposure_seconds)}</b> ＝ 允许
      ${p(e.parameters.exposure_limit_seconds)}（跨多段超温与暂停带累计，未被清零）<br/>
      失效解析时刻：<b>${s.time}</b>（距首条记录 ${_(s.elapsed_seconds)}，
      闭式曲线精确定位，非采样点）<br/>
      归咎的复冷不足：${t?`第 <b>${t.candidate_index+1}</b> 次复冷候选区间
             起于 ${t.candidate_start_time}，因「${t.reason_text}」
             于 ${t.interrupted_time} 中断（第 ${t.round_index+1} 轮记忆保留）`:"<b>无</b>——失效轮此前未发生过有效复冷，也无可归咎的复冷尝试"}
    </div></div>`}const n=e.exceedance_intervals[s.interval_index];return`<div class="failure-card">
    <h3>最早失效时刻证据</h3>
    <div class="kv">
      超温区间起点：<b>${n.start_time}</b>（${_(n.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${n.end_time}</b>（${_(n.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${p(n.duration_seconds)}</b> ≥ 允许 ${p(e.parameters.exposure_limit_seconds)}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${s.time}</b>
      （距首条记录 ${_(s.elapsed_seconds)}）
    </div></div>`}function X(e){const s=e.recool;if(!s)return"";const n=s.rounds.map(t=>`<tr>
      <td>${t.index+1}</td>
      <td>${t.start_time}</td>
      <td>${t.end_time}</td>
      <td class="num">${p(t.hot_exposure_seconds)}（${t.hot_exposure_seconds.toFixed(1)}s）</td>
      <td>${t.failed?`<span class="tag yes">拒收 @ ${t.failure_time}</span>`:t.reset?`<span class="tag no">已清零 @ ${t.reset_time}</span>`:'<span class="tag closed">保留至结束</span>'}</td>
    </tr>`).join(""),a=s.recool_candidates.map(t=>{const d=t.status==="confirmed"?'<span class="tag yes">确认清零</span>':t.status==="rewarmed"?'<span class="tag no">回暖打断（复冷不足）</span>':'<span class="tag no">结束未确认</span>';return`<tr>
        <td>${t.index+1}</td>
        <td>${t.start_time}</td>
        <td>${t.end_time}</td>
        <td class="num">${t.duration_seconds.toFixed(1)}s（需 ${s.confirm_seconds}s）</td>
        <td>${d}</td>
        <td>${t.cleared_at?t.cleared_at:"—"}</td>
        <td>${t.status_text}</td>
      </tr>`}).join("");return`
  <div class="recool-panel">
    <div class="section-title" style="margin-top:4px">复冷记忆 · 逐轮暴露与复冷裁决</div>
    <div class="hint" style="margin:0 0 8px">
      复冷阈值 <b>${s.recool_threshold}℃</b>，确认时长 <b>${p(s.confirm_seconds)}</b>。
      ${s.rule}
    </div>
    <table class="data">
      <thead><tr><th>轮次</th><th>本轮起</th><th>本轮止</th><th class="num">热暴露累计</th><th>结局（清零 / 拒收时刻）</th></tr></thead>
      <tbody>${n}</tbody>
    </table>
    <div class="section-title" style="font-size:13px">复冷候选区间（连续不高于复冷阈值）</div>
    <table class="data">
      <thead><tr><th>#</th><th>进入复冷</th><th>离开/确认</th><th class="num">持续/要求</th><th>状态</th><th>清零时刻</th><th>原因</th></tr></thead>
      <tbody>${a}</tbody>
    </table>
  </div>`}function Y(e){const c=e.curve,M=c[c.length-1].elapsed_seconds,w=[e.parameters.box_temp_limit];e.recool&&w.push(e.recool.recool_threshold);const T=c.flatMap(o=>[o.box_temp,o.ambient_temp]).concat(w);let b=Math.min(...T),x=Math.max(...T);const L=Math.max(1,(x-b)*.08);b-=L,x+=L;const l=o=>56+o/M*846,m=o=>336-(o-b)/(x-b)*318,j=[];let h=null;for(let o=0;o<c.length;o++)if(c[o].lid_open&&h===null&&(h=c[o].elapsed_seconds),(!c[o].lid_open||o===c.length-1)&&h!==null){const r=c[o].lid_open?c[o].elapsed_seconds:c[o-1].elapsed_seconds;j.push([h,r]),h=null}const E=o=>c.map((r,z)=>`${z===0?"M":"L"}${l(r.elapsed_seconds).toFixed(2)},${m(r[o]).toFixed(2)}`).join(" "),O=e.exceedance_intervals.map(o=>`<rect x="${l(o.elapsed_start_seconds)}" y="18" width="${l(o.elapsed_end_seconds)-l(o.elapsed_start_seconds)}" height="318" fill="#ff5d5d" fill-opacity="0.16" />`).join(""),W=j.map(([o,r])=>`<rect x="${l(o)}" y="18" width="${l(r)-l(o)}" height="318" fill="#f5a623" fill-opacity="0.10" />`).join("");let R="",S="";e.recool&&(R=e.recool.recool_candidates.map(o=>{const r=o.confirmed?"#2ecc71":"#4da3ff";return`<rect x="${l(o.elapsed_start_seconds)}" y="18" width="${l(o.elapsed_end_seconds)-l(o.elapsed_start_seconds)}" height="318" fill="${r}" fill-opacity="0.10" />`}).join(""),S=e.recool.resets.map(o=>`<line x1="${l(o.elapsed_seconds)}" y1="18" x2="${l(o.elapsed_seconds)}" y2="336"
          stroke="#2ecc71" stroke-width="1.6" stroke-dasharray="3 5"/>
        <text x="${l(o.elapsed_seconds)}" y="46" fill="#2ecc71" font-size="11" text-anchor="middle">清零 ${o.time}</text>`).join(""));const q=e.recool?`<line x1="56" y1="${m(e.recool.recool_threshold)}" x2="902" y2="${m(e.recool.recool_threshold)}"
        stroke="#4da3ff" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="902" y="${m(e.recool.recool_threshold)-5}" fill="#4da3ff" font-size="11" text-anchor="end">复冷阈值 ${e.recool.recool_threshold}℃</text>`:"",I=[],N=5;for(let o=0;o<=N;o++){const r=b+(x-b)*o/N;I.push(`<line x1="56" y1="${m(r)}" x2="902" y2="${m(r)}" stroke="#22303f" stroke-width="1"/>
      <text x="48" y="${m(r)+4}" fill="#93a4b5" font-size="11" text-anchor="end">${r.toFixed(1)}</text>`)}const F=[],B=6;for(let o=0;o<=B;o++){const r=M*o/B;F.push(`<line x1="${l(r)}" y1="336" x2="${l(r)}" y2="341" stroke="#93a4b5"/>
      <text x="${l(r)}" y="356" fill="#93a4b5" font-size="11" text-anchor="middle">${_(r)}</text>`)}const v=e.parameters.box_temp_limit,C=e.records_echo.map(o=>`<circle cx="${l(o.elapsed_seconds)}" cy="${m(o.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${o.time}：箱温 ${g(o.box_temp)}℃，环境 ${g(o.ambient_temp)}℃，箱盖${o.lid_open?"开启":"关闭"}</title></circle>`).join(""),$=e.first_failure_time,P=$?`<line x1="${l($.elapsed_seconds)}" y1="18" x2="${l($.elapsed_seconds)}" y2="336"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${l($.elapsed_seconds)}" y="30" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${$.time}</text>`:"";return`<svg viewBox="0 0 920 380" role="img" aria-label="箱温连续曲线">
    ${W}${O}${R}
    ${I.join("")}${F.join("")}
    <line x1="56" y1="${m(v)}" x2="902" y2="${m(v)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="902" y="${m(v)-5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${v}℃</text>
    ${q}
    <path d="${E("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${E("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${C}${P}${S}
    <line x1="56" y1="336" x2="902" y2="336" stroke="#93a4b5"/>
    <line x1="56" y1="18" x2="56" y2="336" stroke="#93a4b5"/>
    <text x="56" y="374" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    ${e.recool?`<span class="swatch"><i style="background:#4da3ff"></i>复冷阈值</span>
      <span class="swatch"><i style="background:#2ecc71"></i>复冷确认清零</span>
      <span class="swatch"><i style="background:#4da3ff;opacity:.5"></i>复冷候选（不足）</span>`:""}
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`}function G(e){return e.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${e.exceedance_intervals.map(s=>`<tr>
        <td>${s.index+1}</td><td>${s.start_time}</td><td>${s.end_time}</td>
        <td class="num">${p(s.duration_seconds)}（${s.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${s.reaches_limit?"yes":"no"}">${s.reaches_limit?"达到 → 拒收":"未达到"}</span></td>
      </tr>`).join("")}</tbody></table>`:'<div class="hint">无任何箱温超过允许值的连续区间。</div>'}function Q(e){return`<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>穿越(相对秒)</th>
    </tr></thead>
    <tbody>${e.segments.map(s=>{const n=s.crossings.map(t=>`<span class="${t.direction}">限温${t.direction==="up"?"↑":"↓"}@${t.elapsed_seconds.toFixed(1)}</span>`).join("，"),a=(s.recool_crossings||[]).map(t=>`<span class="rc-cross">复冷${t.direction==="up"?"↑":"↓"}@${t.elapsed_seconds.toFixed(1)}</span>`).join("，");return`<tr>
        <td>${s.index+1}</td>
        <td>${s.elapsed_start_seconds} → ${s.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${s.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${s.lid_open?"open":"closed"}">${s.lid_open?"开启":"关闭"}</span></td>
        <td class="num">${s.tau_seconds}</td>
        <td class="num">${g(s.max_temp.value)}</td>
        <td>${s.max_temp.kind==="interior"?"段内 "+s.max_temp.elapsed_seconds.toFixed(1)+"s":s.max_temp.kind==="start"?"段起点":"段终点"}</td>
        <td class="num">${g(s.min_temp.value)}</td>
        <td>${n||"—"}${a?`<br/>${a}`:""}</td>
      </tr>`}).join("")}</tbody></table>`}function U(e){return e?`
  <div class="model-note">
    求解方式：<code>${e.model.equation}</code>；${e.model.ambient_assumption}；${e.model.solver}。<br/>
    每段从记录时刻实测箱温锚定（段末模型值与下一读数偏差见各段证据），
    ${e.model.tau_switching}。${e.model.exceedance_rule}。
    ${e.recool?`<br/>复冷口径：${e.model.recool_rule}`:""}
  </div>
  ${V(e)}
  <div class="chart-wrap">${Y(e)}</div>

  ${e.recool?X(e):""}

  <div class="section-title">${e.recool?"原口径连续超温区间（新旧口径可对照）":"累计连续超温区间（跨记录取并集）"}</div>
  ${G(e)}

  <div class="section-title">各段解析极值与${e.recool?"两道阈值":"阈值"}穿越</div>
  ${Q(e)}`:""}function u(){A.innerHTML=`
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${D()}
    <div>
      ${K(i.result)}
      ${i.result?U(i.result):'<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>'}
    </div>
  </div>`,Z()}function Z(){var e,s,n;(e=document.getElementById("submit"))==null||e.addEventListener("click",J),(s=document.getElementById("addRow"))==null||s.addEventListener("click",()=>{const{recs:a,params:t}=y();if(a.length>=30)return;const d=a[a.length-1];a.push({time:typeof d.time=="number"?d.time+600:d.time,box_temp:d.box_temp,ambient_temp:d.ambient_temp,lid_open:!1}),i.records=a,i.parameters=t,u()}),document.querySelectorAll("[data-del]").forEach(a=>a.addEventListener("click",()=>{const{recs:t,params:d}=y();t.splice(Number(a.dataset.del),1),i.records=t,i.parameters=d,u()})),document.querySelectorAll("[data-preset]").forEach(a=>{a.addEventListener("click",()=>{const t=k[a.dataset.preset];i.records=structuredClone(t.records),i.parameters={...t.parameters},i.recool=t.recool?structuredClone(t.recool):{enabled:!1,recool_threshold:4,confirm_seconds:600},i.result=null,i.error=null,u()})}),(n=document.getElementById("recool_enabled"))==null||n.addEventListener("change",()=>{const{recool:a}=y();i.recool=a,u()})}u();
