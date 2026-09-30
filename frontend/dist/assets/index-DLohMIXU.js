(function(){const s=document.createElement("link").relList;if(s&&s.supports&&s.supports("modulepreload"))return;for(const e of document.querySelectorAll('link[rel="modulepreload"]'))i(e);new MutationObserver(e=>{for(const o of e)if(o.type==="childList")for(const l of o.addedNodes)l.tagName==="LINK"&&l.rel==="modulepreload"&&i(l)}).observe(document,{childList:!0,subtree:!0});function n(e){const o={};return e.integrity&&(o.integrity=e.integrity),e.referrerPolicy&&(o.referrerPolicy=e.referrerPolicy),e.crossOrigin==="use-credentials"?o.credentials="include":e.crossOrigin==="anonymous"?o.credentials="omit":o.credentials="same-origin",o}function i(e){if(e.ep)return;e.ep=!0;const o=n(e);fetch(e.href,o)}})();const w={reject:{label:"拒收演示：读数全合格、途中升温",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:60,box_temp:7.806654,ambient_temp:25,lid_open:!1},{time:1560,box_temp:7.254505,ambient_temp:3,lid_open:!1},{time:2460,box_temp:3.211819,ambient_temp:3,lid_open:!1},{time:3360,box_temp:3.010546,ambient_temp:3,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},pass:{label:"放行演示：全程低温",records:[{time:0,box_temp:4,ambient_temp:3,lid_open:!1},{time:300,box_temp:3.551819,ambient_temp:3.5,lid_open:!1},{time:600,box_temp:3.703003,ambient_temp:4,lid_open:!1},{time:900,box_temp:3.817165,ambient_temp:3.8,lid_open:!1},{time:1200,box_temp:3.585587,ambient_temp:3.2,lid_open:!1},{time:1500,box_temp:3.268274,ambient_temp:3,lid_open:!1},{time:1800,box_temp:3.025116,ambient_temp:2.8,lid_open:!1},{time:2100,box_temp:2.772452,ambient_temp:2.5,lid_open:!1},{time:2400,box_temp:2.41629,ambient_temp:2,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:600}},short:{label:"短时超温：有暴露但不足时长",records:[{time:0,box_temp:4,ambient_temp:4,lid_open:!1},{time:600,box_temp:15.92102,ambient_temp:25,lid_open:!0},{time:1200,box_temp:23.771294,ambient_temp:25,lid_open:!1},{time:1800,box_temp:12.912692,ambient_temp:4,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:3600},recooling:{enabled:!1,recool_temp:5,confirm_seconds:600}},recoolReject:{label:"复冷记忆：短暂回落不足确认，后段累计拒收",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:100,box_temp:9.952842,ambient_temp:25,lid_open:!1},{time:101,box_temp:9.96629,ambient_temp:3,lid_open:!1},{time:1100,box_temp:3.249345,ambient_temp:3,lid_open:!1},{time:1101,box_temp:3.285141,ambient_temp:25,lid_open:!1},{time:1500,box_temp:19.256914,ambient_temp:25,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:400},recooling:{enabled:!0,recool_temp:5,confirm_seconds:700}},recoolPass:{label:"复冷记忆：连续复冷达确认时长，清零放行",records:[{time:0,box_temp:4,ambient_temp:25,lid_open:!1},{time:100,box_temp:9.952842,ambient_temp:25,lid_open:!1},{time:101,box_temp:9.96629,ambient_temp:3,lid_open:!1},{time:1100,box_temp:3.249345,ambient_temp:3,lid_open:!1},{time:1101,box_temp:3.285141,ambient_temp:25,lid_open:!1},{time:1500,box_temp:19.256914,ambient_temp:25,lid_open:!1}],parameters:{tau_closed:300,tau_open:90,box_temp_limit:8,exposure_limit_seconds:400},recooling:{enabled:!0,recool_temp:5,confirm_seconds:600}}},d={records:structuredClone(w.reject.records),parameters:{...w.reject.parameters},recooling:{enabled:!1,recool_temp:5,confirm_seconds:600},result:null,error:null,loading:!1},H=document.getElementById("app");function u(t){const s=Math.round(t),n=Math.floor(s/3600),i=Math.floor(s%3600/60),e=s%60;return n>0?`${n}:${String(i).padStart(2,"0")}:${String(e).padStart(2,"0")}`:`${i}:${String(e).padStart(2,"0")}`}function k(t){return Number(t).toFixed(2)}function p(t){const s=Number(t),n=Math.floor(s/3600),i=Math.floor(s%3600/60),e=Math.round(s%60);return n>0?`${n} 小时 ${i} 分 ${e} 秒`:i>0?`${i} 分 ${e} 秒`:`${e} 秒`}function D(){const t=d.parameters;return`
  <div class="panel">
    <h2>① 运输记录（按时间严格递增，4–30 条）</h2>
    <div style="max-height:340px;overflow:auto">
    <table class="records">
      <thead><tr>
        <th style="width:26%"># 时间(秒或ISO)</th><th>箱温℃</th><th>环境温℃</th><th>箱盖开启</th><th></th>
      </tr></thead>
      <tbody>
        ${d.records.map((s,n)=>`
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
    <div class="count-note">当前 ${d.records.length} 条（须 4–30 条）</div>

    <h2 style="margin-top:18px">② 模型参数与保存要求</h2>
    <div class="params-grid">
      <label class="field"><span>箱盖关闭热惯性 τ关闭（秒）</span>
        <input id="tau_closed" type="number" step="any" value="${t.tau_closed}" /></label>
      <label class="field"><span>箱盖开启热惯性 τ开启（秒）</span>
        <input id="tau_open" type="number" step="any" value="${t.tau_open}" /></label>
      <label class="field"><span>允许箱温（℃）</span>
        <input id="box_temp_limit" type="number" step="0.1" value="${t.box_temp_limit}" /></label>
      <label class="field"><span>允许连续暴露时长（秒）</span>
        <input id="exposure_limit_seconds" type="number" step="any" value="${t.exposure_limit_seconds}" /></label>
    </div>
    <div class="hint">约定：相邻记录之间环境温度按<b>线性变化</b>；箱温按一阶模型
      <code>dT/dt=(T_env−T)/τ</code> 逐段闭式求解；箱盖状态在记录时刻切换 τ。</div>

    <h2 style="margin-top:18px">③ 复冷记忆（可选）</h2>
    <label class="field recool-toggle">
      <input id="recool_enabled" type="checkbox" ${d.recooling.enabled?"checked":""} />
      <span>启用「复冷记忆」：短暂回落到限温以下不清零，只有连续不高于复冷阈值达到确认时长才清零</span>
    </label>
    <div class="params-grid">
      <label class="field"><span>复冷阈值（℃，须严格低于允许箱温）</span>
        <input id="recool_temp" type="number" step="0.1" value="${d.recooling.recool_temp}"
          ${d.recooling.enabled?"":"disabled"} /></label>
      <label class="field"><span>复冷确认时长（秒，连续不高于阈值）</span>
        <input id="recool_confirm_seconds" type="number" step="any" value="${d.recooling.confirm_seconds}"
          ${d.recooling.enabled?"":"disabled"} /></label>
    </div>
    <div class="hint">未启用时，请求参数、裁决结论与证据口径与原来完全一致。启用后：
      箱温高于限温累计本轮热暴露；处于复冷阈值与限温之间仅<b>暂停累计并保留记忆</b>；
      只有<b>连续不高于复冷阈值达到确认时长</b>才清零并开始新一轮。</div>

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
      <button class="ghost" data-preset="recoolReject">复冷不足→后段拒收</button>
      <button class="ghost" data-preset="recoolPass">有效复冷→清零放行</button>
    </div>
    ${d.error?`<div class="error-box">${d.error}</div>`:""}
  </div>`}function M(){const t=d.records.map((i,e)=>{const o=document.querySelector(`[data-k="time"][data-i="${e}"]`).value.trim();return{time:/^-?\d+(\.\d+)?$/.test(o)?Number(o):o,box_temp:Number(document.querySelector(`[data-k="box_temp"][data-i="${e}"]`).value),ambient_temp:Number(document.querySelector(`[data-k="ambient_temp"][data-i="${e}"]`).value),lid_open:document.querySelector(`[data-k="lid_open"][data-i="${e}"]`).checked}}),s={tau_closed:Number(document.getElementById("tau_closed").value),tau_open:Number(document.getElementById("tau_open").value),box_temp_limit:Number(document.getElementById("box_temp_limit").value),exposure_limit_seconds:Number(document.getElementById("exposure_limit_seconds").value)},n={enabled:document.getElementById("recool_enabled").checked,recool_temp:Number(document.getElementById("recool_temp").value),confirm_seconds:Number(document.getElementById("recool_confirm_seconds").value)};return{recs:t,params:s,recooling:n}}async function J(){const{recs:t,params:s,recooling:n}=M();d.records=t,d.parameters=s,d.recooling=n,d.loading=!0,d.error=null,d.result=null,$();try{const i={records:t,parameters:s};n.enabled&&(i.recooling={enabled:!0,recool_temp:n.recool_temp,confirm_seconds:n.confirm_seconds});const o=await(await fetch("/api/audit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)})).json();o.status==="invalid"?d.error=o.errors.map(l=>`<div><code>${l.code}</code> ${l.message}${l.field?`（字段：${l.field}）`:""}</div>`).join(""):d.result=o}catch(i){d.error=`无法连接审计 API：${i.message}`}finally{d.loading=!1,$()}}function K(t){if(d.loading)return'<div class="verdict"><div class="badge">…</div><div class="sub">正在连续求解各段箱温…</div></div>';if(d.error)return`<div class="verdict invalid"><div class="badge">数据不合法</div>
      <div class="sub">服务端拒绝裁决，请依据右侧字段提示修正后重新提交。</div></div>`;if(!t)return`<div class="verdict"><div class="badge" style="background:var(--panel-2);color:var(--muted)">待提交</div>
      <div class="sub">填写记录与参数后点击「提交审计」，服务端将以一阶热响应模型逐段解析求解。</div></div>`;if(t.status==="pass"){const o=t.recooling;return`<div class="verdict pass"><div class="badge">放 行</div>
      <div class="sub">${o&&o.enabled?`复冷记忆已启用：共 <strong>${o.rounds.length}</strong> 轮暴露，有效复冷清零 <strong>${o.rounds.filter(T=>T.reset).length}</strong> 次，复冷候选 <strong>${o.candidates.length}</strong> 个。<br/>`:""}箱温曲线全程未使热暴露累计达到 <strong>${p(t.parameters.exposure_limit_seconds)}</strong>。<br/>
      连续超温区间 <strong>${t.exceedance_intervals.length}</strong> 个，
      超温合计 <strong>${p(t.total_exceedance_seconds)}</strong>。</div></div>`}const s=t.first_failure_time,n=t.recooling;return`<div class="verdict reject"><div class="badge">拒 收</div>
    <div class="sub">${n&&n.enabled&&s.round_index!==void 0?`复冷记忆口径：第 <strong>${s.round_index+1}</strong> 轮热暴露累计达限额`+(n.insufficient_recool_at_failure?`，此前 <strong>第 ${n.insufficient_recool_at_failure.index+1} 次复冷不足</strong>（仅连续 ${p(n.insufficient_recool_at_failure.continuous_below_recool_seconds)}，缺口 ${p(n.insufficient_recool_at_failure.shortfall_seconds)}）`:"")+"。<br/>":""}油样自 <strong>${s.time}</strong>
    （距首条记录 ${u(s.elapsed_seconds)}${s.segment_index!==void 0&&s.segment_index!==null?`，解析定位在第 ${s.segment_index+1} 段`:""}）起失效。<br/>
    共 ${t.exceedance_intervals.length} 个连续超温区间，累计超温 ${p(t.total_exceedance_seconds)}。</div></div>`}function V(t){if(!t||t.status!=="reject")return"";const s=t.first_failure_time,n=t.recooling;if(n&&n.enabled&&s.round_index!==void 0){const e=n.rounds[s.round_index],o=n.insufficient_recool_at_failure;return`<div class="failure-card">
    <h3>复冷记忆 · 首个失效时刻证据</h3>
    <div class="kv">
      暴露轮次：<b>第 ${s.round_index+1} 轮</b>，起于 <b>${e.start_time}</b>
      （${u(e.elapsed_start_seconds)}）<br/>
      该轮热暴露累计：<b>${p(e.heat_exposure_seconds)}</b> 达到允许
      ${p(t.parameters.exposure_limit_seconds)}<br/>
      ${o?`此前复冷不足：<b>第 ${o.index+1} 次候选</b>（${o.start_time} → ${o.end_time}），
          连续不高于复冷阈值仅 <b>${p(o.continuous_below_recool_seconds)}</b>，
          距确认时长还差 <b>${p(o.shortfall_seconds)}</b>，
          中断原因：${o.outcome_text}<br/>`:""}
      首个失效（解析）时刻：<b>${s.time}</b>（距首条记录 ${u(s.elapsed_seconds)}，第 ${s.segment_index+1} 段）
    </div></div>`}const i=t.exceedance_intervals[s.interval_index];return`<div class="failure-card">
    <h3>最早失效时刻证据</h3>
    <div class="kv">
      超温区间起点：<b>${i.start_time}</b>（${u(i.elapsed_start_seconds)}）<br/>
      连续超温区间终点：<b>${i.end_time}</b>（${u(i.elapsed_end_seconds)}）<br/>
      该区间持续：<b>${p(i.duration_seconds)}</b> ≥ 允许 ${p(t.parameters.exposure_limit_seconds)}<br/>
      最早失效时刻 = 区间起点 + 允许暴露时长 = <b>${s.time}</b>
      （距首条记录 ${u(s.elapsed_seconds)}）
    </div></div>`}function X(t){const m=t.curve,j=m[m.length-1].elapsed_seconds,L=m.flatMap(a=>[a.box_temp,a.ambient_temp]).concat([t.parameters.box_temp_limit]).concat(t.recooling&&t.recooling.enabled?[t.recooling.recool_temp]:[]);let h=Math.min(...L),g=Math.max(...L);const E=Math.max(1,(g-h)*.08);h-=E,g+=E;const r=a=>56+a/j*846,_=a=>336-(a-h)/(g-h)*318,R=[];let f=null;for(let a=0;a<m.length;a++)if(m[a].lid_open&&f===null&&(f=m[a].elapsed_seconds),(!m[a].lid_open||a===m.length-1)&&f!==null){const c=m[a].lid_open?m[a].elapsed_seconds:m[a-1].elapsed_seconds;R.push([f,c]),f=null}const S=a=>m.map((c,C)=>`${C===0?"M":"L"}${r(c.elapsed_seconds).toFixed(2)},${_(c[a]).toFixed(2)}`).join(" "),O=t.exceedance_intervals.map(a=>`<rect x="${r(a.elapsed_start_seconds)}" y="18" width="${r(a.elapsed_end_seconds)-r(a.elapsed_start_seconds)}" height="318" fill="#ff5d5d" fill-opacity="0.16" />`).join(""),q=R.map(([a,c])=>`<rect x="${r(a)}" y="18" width="${r(c)-r(a)}" height="318" fill="#f5a623" fill-opacity="0.10" />`).join(""),N=[],F=5;for(let a=0;a<=F;a++){const c=h+(g-h)*a/F;N.push(`<line x1="56" y1="${_(c)}" x2="902" y2="${_(c)}" stroke="#22303f" stroke-width="1"/>
      <text x="48" y="${_(c)+4}" fill="#93a4b5" font-size="11" text-anchor="end">${c.toFixed(1)}</text>`)}const I=[],B=6;for(let a=0;a<=B;a++){const c=j*a/B;I.push(`<line x1="${r(c)}" y1="336" x2="${r(c)}" y2="341" stroke="#93a4b5"/>
      <text x="${r(c)}" y="356" fill="#93a4b5" font-size="11" text-anchor="middle">${u(c)}</text>`)}const v=t.parameters.box_temp_limit,b=t.recooling,y=b&&b.enabled,P=y?b.candidates.map(a=>`<rect x="${r(a.elapsed_start_seconds)}" y="18" width="${Math.max(1,r(a.elapsed_end_seconds)-r(a.elapsed_start_seconds))}" height="318" fill="${a.reset?"#2ecc71":"#f5a623"}" fill-opacity="${a.reset?"0.14":"0.16"}" />`).join(""):"",W=y?`<line x1="56" y1="${_(b.recool_temp)}" x2="902" y2="${_(b.recool_temp)}"
        stroke="#2ecc71" stroke-width="1.4" stroke-dasharray="2 5"/>
      <text x="902" y="${_(b.recool_temp)-5}" fill="#2ecc71" font-size="11" text-anchor="end">复冷阈值 ${b.recool_temp}℃</text>`:"",z=t.records_echo.map(a=>`<circle cx="${r(a.elapsed_seconds)}" cy="${_(a.box_temp)}" r="4.5" fill="#0f1720" stroke="#e6edf3" stroke-width="2">
          <title>记录 ${a.time}：箱温 ${k(a.box_temp)}℃，环境 ${k(a.ambient_temp)}℃，箱盖${a.lid_open?"开启":"关闭"}</title></circle>`).join(""),x=t.first_failure_time,A=x?`<line x1="${r(x.elapsed_seconds)}" y1="18" x2="${r(x.elapsed_seconds)}" y2="336"
        stroke="#ff5d5d" stroke-width="1.6" stroke-dasharray="6 4"/>
      <text x="${r(x.elapsed_seconds)}" y="30" fill="#ff5d5d" font-size="11" text-anchor="middle">最早失效 ${x.time}</text>`:"";return`<svg viewBox="0 0 920 380" role="img" aria-label="箱温连续曲线">
    ${q}${P}${O}
    ${N.join("")}${I.join("")}
    <line x1="56" y1="${_(v)}" x2="902" y2="${_(v)}" stroke="#f5a623" stroke-width="1.6" stroke-dasharray="8 4"/>
    <text x="902" y="${_(v)-5}" fill="#f5a623" font-size="11" text-anchor="end">允许箱温 ${v}℃</text>
    ${W}
    <path d="${S("ambient_temp")}" fill="none" stroke="#7d8fa1" stroke-width="1.6" stroke-dasharray="3 3"/>
    <path d="${S("box_temp")}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>
    ${z}${A}
    <line x1="56" y1="336" x2="902" y2="336" stroke="#93a4b5"/>
    <line x1="56" y1="18" x2="56" y2="336" stroke="#93a4b5"/>
    <text x="56" y="374" fill="#93a4b5" font-size="11">经过时间（时:分:秒） →</text>
  </svg>
  <div class="legend">
    <span class="swatch"><i style="background:#4da3ff"></i>箱温连续曲线（闭式解析解）</span>
    <span class="swatch"><i style="background:#7d8fa1"></i>环境温（段间线性）</span>
    <span class="swatch"><i style="background:#f5a623"></i>允许箱温</span>
    ${y?'<span class="swatch"><i style="background:#2ecc71"></i>复冷阈值 / 有效复冷候选</span>':""}
    ${y?'<span class="swatch"><i style="background:#f5a623"></i>复冷不足候选（中断）</span>':""}
    <span class="swatch"><i style="background:var(--hot);border:1px solid #ff5d5d"></i>连续超温区间</span>
    <span class="swatch"><i style="background:var(--lid);border:1px solid #f5a623"></i>箱盖开启时段</span>
    <span class="swatch">◦ 空心圆点为录入的箱温读数</span>
  </div>`}function Y(t){return t.exceedance_intervals.length?`<table class="data">
    <thead><tr><th>#</th><th>起始时刻</th><th>结束时刻</th><th class="num">持续时长(秒)</th><th>是否达到暴露限额</th></tr></thead>
    <tbody>${t.exceedance_intervals.map(s=>`<tr>
        <td>${s.index+1}</td><td>${s.start_time}</td><td>${s.end_time}</td>
        <td class="num">${p(s.duration_seconds)}（${s.duration_seconds.toFixed(1)}s）</td>
        <td><span class="tag ${s.reaches_limit?"yes":"no"}">${s.reaches_limit?"达到 → 拒收":"未达到"}</span></td>
      </tr>`).join("")}</tbody></table>`:'<div class="hint">无任何箱温超过允许值的连续区间。</div>'}function G(t){const s=t.recooling&&t.recooling.enabled;return`<table class="data">
    <thead><tr>
      <th>#</th><th>段起→止(s)</th><th>箱盖</th><th class="num">τ(秒)</th>
      <th class="num">段内最高℃</th><th>最高位置</th>
      <th class="num">段内最低℃</th><th>限温穿越(相对秒)</th>${s?"<th>复冷阈值穿越(相对秒)</th>":""}
    </tr></thead>
    <tbody>${t.segments.map(n=>{const i=n.crossings.map(o=>`<span class="${o.direction}">${o.direction==="up"?"↑上穿":"↓下穿"}@${o.elapsed_seconds.toFixed(1)}</span>`).join("，"),e=s?(n.recool_crossings||[]).map(o=>`<span class="${o.direction==="up"?"recool-up":"recool-down"}">${o.direction==="up"?"↑上穿":"↓下穿"}@${o.elapsed_seconds.toFixed(1)}</span>`).join("，")||"—":"";return`<tr>
        <td>${n.index+1}</td>
        <td>${n.elapsed_start_seconds} → ${n.elapsed_end_seconds}<br/><span class="hint" style="margin:0">${n.duration_seconds.toFixed(0)}s</span></td>
        <td><span class="tag ${n.lid_open?"open":"closed"}">${n.lid_open?"开启":"关闭"}</span></td>
        <td class="num">${n.tau_seconds}</td>
        <td class="num">${k(n.max_temp.value)}</td>
        <td>${n.max_temp.kind==="interior"?"段内 "+n.max_temp.elapsed_seconds.toFixed(1)+"s":n.max_temp.kind==="start"?"段起点":"段终点"}</td>
        <td class="num">${k(n.min_temp.value)}</td>
        <td>${i||"—"}</td>${s?`<td>${e}</td>`:""}
      </tr>`}).join("")}</tbody></table>`}function Q(t){const s=t.recooling;if(!s||!s.enabled)return"";const n=`<table class="data">
    <thead><tr><th>轮次</th><th>起始时刻</th><th>结束时刻</th><th class="num">热暴露累计(秒)</th><th>清零/结束原因</th></tr></thead>
    <tbody>${s.rounds.map(e=>`<tr>
        <td>第 ${e.index+1} 轮</td>
        <td>${e.start_time}<br/><span class="hint" style="margin:0">${u(e.elapsed_start_seconds)}</span></td>
        <td>${e.end_time}<br/><span class="hint" style="margin:0">${u(e.elapsed_end_seconds)}</span></td>
        <td class="num">${e.heat_exposure_seconds.toFixed(1)}</td>
        <td><span class="tag ${e.reset||e.end_reason==="failure"?"yes":"no"}">${e.reset?"已清零":"未清零"}</span>
          ${e.end_reason_text}</td>
      </tr>`).join("")}</tbody></table>`,i=s.candidates.length?`<table class="data">
      <thead><tr><th>#</th><th>所属轮</th><th>候选区间(起→止)</th>
        <th class="num">连续不高于复冷阈值(秒)</th><th class="num">确认要求(秒)</th>
        <th class="num">缺口(秒)</th><th>结果 / 中断原因</th></tr></thead>
      <tbody>${s.candidates.map(e=>`<tr>
        <td>${e.index+1}</td>
        <td>第 ${e.round_index+1} 轮</td>
        <td>${e.start_time} → ${e.end_time}<br/><span class="hint" style="margin:0">${u(e.elapsed_start_seconds)} → ${u(e.elapsed_end_seconds)}</span></td>
        <td class="num">${e.continuous_below_recool_seconds.toFixed(1)}</td>
        <td class="num">${e.required_confirm_seconds.toFixed(0)}</td>
        <td class="num">${e.shortfall_seconds.toFixed(1)}</td>
        <td><span class="tag ${e.reset?"yes":"no"}">${e.reset?"确认达成→清零":"复冷不足"}</span>
          ${e.outcome_text}</td>
      </tr>`).join("")}</tbody></table>`:`<div class="hint">无复冷候选区间（箱温未回落至复冷阈值 ${s.recool_temp}℃ 以下）。</div>`;return`
  <div class="section-title">复冷记忆 · 各轮起止与热暴露累计</div>
  ${n}
  <div class="section-title">复冷候选区间（连续不高于复冷阈值的确认情况）</div>
  ${i}`}function U(t){return t?`
  <div class="model-note">
    求解方式：<code>${t.model.equation}</code>；${t.model.ambient_assumption}；${t.model.solver}。<br/>
    每段以记录时刻实测箱温为初值锚定（段末模型值与下一读数偏差见审计数据），
    ${t.model.tau_switching}。${t.model.exceedance_rule}。
  </div>
  ${V(t)}
  <div class="chart-wrap">${X(t)}</div>

  <div class="section-title">累计连续超温区间（跨记录取并集）</div>
  ${Y(t)}
  ${Q(t)}

  <div class="section-title">各段解析极值与阈值穿越</div>
  ${G(t)}`:""}function $(){H.innerHTML=`
  <header>
    <h1>海上平台油样运输箱 · 温控审计</h1>
    <p>一阶热响应模型逐段闭式解析 · 阈值穿越精确定位 · 跨记录连续暴露累计 —— 拒绝"只看离散读数"的误放行</p>
  </header>
  <div class="layout">
    ${D()}
    <div>
      ${K(d.result)}
      ${d.result?U(d.result):'<div class="chart-wrap"><div class="hint">提交后在此展示箱温连续曲线、各段解析极值、累计暴露区间与最早失效时刻。</div></div>'}
    </div>
  </div>`,Z()}function Z(){var t,s,n;(t=document.getElementById("submit"))==null||t.addEventListener("click",J),(s=document.getElementById("recool_enabled"))==null||s.addEventListener("change",i=>{const{recooling:e}=M();d.recooling=e,$()}),(n=document.getElementById("addRow"))==null||n.addEventListener("click",()=>{const{recs:i,params:e,recooling:o}=M();if(i.length>=30)return;const l=i[i.length-1];i.push({time:typeof l.time=="number"?l.time+600:l.time,box_temp:l.box_temp,ambient_temp:l.ambient_temp,lid_open:!1}),d.records=i,d.parameters=e,d.recooling=o,$()}),document.querySelectorAll("[data-del]").forEach(i=>i.addEventListener("click",()=>{const{recs:e,params:o,recooling:l}=M();e.splice(Number(i.dataset.del),1),d.records=e,d.parameters=o,d.recooling=l,$()})),document.querySelectorAll("[data-preset]").forEach(i=>{i.addEventListener("click",()=>{const e=w[i.dataset.preset];d.records=structuredClone(e.records),d.parameters={...e.parameters},d.recooling=e.recooling?{...e.recooling}:{enabled:!1,recool_temp:5,confirm_seconds:600},d.result=null,d.error=null,$()})})}$();
