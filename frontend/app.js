/* Autonomous Business Lab — dashboard (vanilla JS, sin dependencias). */
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  items: [],
  selectedId: null,
  detail: null,
};

const STATUS_LABEL = {
  draft: "Borrador",
  researching: "En investigación",
  evaluated: "Evaluada",
  approved: "Aprobada",
  needs_more_research: "Necesita investigación",
  deferred: "Aplazada",
  rejected: "Rechazada",
  blocked: "Bloqueada",
};

const BASIS_LABEL = { evidence: "Evidencia", estimate: "Estimación", unknown: "Desconocido" };

/* ------------------------------------------------------------------ */
/* API helpers                                                         */
/* ------------------------------------------------------------------ */
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.error?.message || JSON.stringify(body);
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/* Loading                                                             */
/* ------------------------------------------------------------------ */
async function loadHealth() {
  try {
    const health = await api("/api/health");
    // Versión visible + detección de frontend obsoleto (iteración 011):
    // si el HTML servido no coincide con la versión del servidor, el
    // navegador está sirviendo una copia antigua → aviso con Ctrl+F5.
    const htmlVersion = document.documentElement.dataset.wawaVersion || "";
    const vChip = $("#wawa-version");
    if (vChip) vChip.textContent = `v${health.version}`;
    if (htmlVersion && health.version && htmlVersion !== health.version) {
      const warn = $("#version-warning");
      if (warn) {
        warn.classList.remove("hidden");
        warn.textContent = `⚠ Frontend desactualizado (HTML v${htmlVersion} pero servidor v${health.version}). Recarga con Ctrl+F5 o reinicia WAWA.`;
      }
    }
    const b = health.budget;
    const parts = [];
    if (b.free_mode) parts.push("modo gratuito");
    if (b.simulation_mode) parts.push("simulación");
    const daily = `$${b.daily.spent.toFixed(4)} / $${b.daily.limit}`;
    $("#budget-chip").textContent = `Presupuesto: ${daily} · ${parts.join(" · ")} · evaluaciones ${b.deep_evaluations.today}/${b.deep_evaluations.max}`;
    const p = health.providers;
    $("#providers-info").innerHTML =
      `<div>Activo: <strong>${p.primary.name}</strong></div>` +
      `<div>Gemini: ${p.gemini.configured ? "configurado" : "no configurado"} (${p.gemini.available ? "disponible" : "no disponible"})</div>` +
      `<div>Manual/Freebuff: ${p.manual.available ? "disponible" : "—"}</div>`;
    renderEngine(health.engine);
  } catch (e) {
    $("#budget-chip").textContent = "sin conexión";
  }
}

async function loadEngine() {
  try {
    const status = await api("/api/engine/status");
    renderEngine(status);
    const feed = await api("/api/engine/events?limit=12");
    renderFeed(feed.items);
  } catch (e) {
    /* el motor siempre debe estar disponible */
  }
}

async function loadEconomy() {
  try {
    const status = await api("/api/economy/status");
    const metrics = await api("/api/economy/metrics");
    const ledger = await api("/api/economy/ledger?limit=8");
    renderEconomy(status, metrics, ledger.items);
  } catch (e) {
    $("#economy-info").textContent = `Economía no disponible: ${e.message}`;
  }
}

function renderEconomy(status, metrics, entries) {
  if (!status) return;
  const egg = $("#egg");
  egg.dataset.survival = status.survival_status?.status || "UNKNOWN";
  $("#economy-warning").classList.remove("hidden");
  const rec = status.reconciliation || {};
  const recLabel = rec.reconciled === undefined ? "sin ejecutar" : rec.reconciled ? "OK" : "INCONSISTENTE";
  const survival = status.survival_status || {};
  const avail = metrics.available_balance?.value;
  const kpis = `
    <div class="eco-kpis">
      <div class="eco-kpi"><div class="k">Saldo disponible</div><div class="v">${avail != null ? avail : "—"} ${esc(status.currency)}</div></div>
      <div class="eco-kpi"><div class="k">Supervivencia</div><div class="v"><span class="survival-chip survival-${esc(survival.status || "UNKNOWN")}">${esc(survival.label || "—")}</span></div></div>
      <div class="eco-kpi"><div class="k">Ingresos confirm.</div><div class="v">${fmtVal(metrics.confirmed_income?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Gastos confirm.</div><div class="v">${fmtVal(metrics.confirmed_expenses?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Comprometidos</div><div class="v">${fmtVal(metrics.committed_expenses?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Runway</div><div class="v">${fmtVal(metrics.runway_days?.value)} ${metrics.runway_days?.unit || ""}</div></div>
      <div class="eco-kpi"><div class="k">Burn rate</div><div class="v">${fmtVal(metrics.daily_burn_rate?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Hoy / límite</div><div class="v">${fmtVal(metrics.today_spent?.value)} / ${fmtVal(metrics.daily_limit?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Coste/oportunidad</div><div class="v">${fmtVal(metrics.cost_per_opportunity?.value)}</div></div>
      <div class="eco-kpi"><div class="k">Coste/experimento</div><div class="v">${fmtVal(metrics.cost_per_experiment?.value)}</div></div>
    </div>
    <div style="margin-top:8px" class="eco-row"><span class="k">Reconciliación</span><span class="v">${recLabel}</span></div>`;
  $("#economy-info").innerHTML = status.simulation_active ? kpis : '<p style="font-size:12px;color:var(--muted)">Sin simulación activa. Inicia una para operar con capital ficticio.</p>';
  const feed = $("#economy-ledger");
  if (!entries?.length) {
    feed.innerHTML = '<div class="feed-item">Sin movimientos.</div>';
  } else {
    feed.innerHTML = entries
      .map(
        (e) =>
          `<div class="feed-item"><span class="when">${esc((e.created_at || "").slice(11, 19))}</span><strong>${esc(e.entry_type)}</strong> ${e.direction === "credit" ? "+" : "−"}${esc(e.amount)} ${esc(e.currency)} · ${esc(e.status)}<br/><span class="when">${esc(e.description.slice(0, 60))}</span></div>`
      )
      .join("");
  }
}

function fmtVal(v) {
  return v != null ? v : "—";
}

function renderEngine(st) {
  if (!st) return;
  const egg = $("#egg");
  egg.dataset.state = st.engine_state;
  egg.dataset.mode = st.mode;
  $("#egg-label").textContent = st.engine_state_label.toLowerCase();
  $("#egg-wrap").title = `Motor: ${st.engine_state_label} · Modo: ${st.mode_label}`;
  const chip = $("#engine-mode-chip");
  const color = st.mode === "autonomous_production" ? "green" : st.mode === "safe_pause" ? "red" : st.mode === "simulation" ? "amber" : "neutral";
  chip.className = `chip chip-${color}`;
  chip.textContent = st.mode_label;
  const uptime = st.uptime_seconds != null ? fmtDuration(st.uptime_seconds) : "—";
  $("#engine-info").innerHTML =
    `<div class="engine-row"><span class="k">Estado</span><span class="v">${esc(st.engine_state_label)}</span></div>` +
    `<div class="engine-row"><span class="k">Tarea actual</span><span class="v">${esc(st.current_task || "—")}</span></div>` +
    `<div class="engine-row"><span class="k">Último resultado</span><span class="v">${esc((st.last_result || "—").slice(0, 60))}</span></div>` +
    `<div class="engine-row"><span class="k">Heartbeat</span><span class="v">${esc((st.heartbeat_at || "—").slice(11, 19))}</span></div>` +
    `<div class="engine-row"><span class="k">Tiempo activo</span><span class="v">${uptime}</span></div>` +
    `<div class="engine-row"><span class="k">Eventos</span><span class="v">${st.counts.events}</span></div>` +
    `<div class="engine-row"><span class="k">Transiciones</span><span class="v">${st.counts.transitions}</span></div>`;
}

function renderFeed(items) {
  const feed = $("#engine-feed");
  if (!items.length) {
    feed.innerHTML = '<div class="feed-item">Sin actividad todavía.</div>';
    return;
  }
  feed.innerHTML = items
    .map(
      (e, i) =>
        `<div class="feed-item${i === 0 ? " new" : ""}"><span class="when">${esc((e.timestamp || "").slice(11, 19))}</span>${esc(e.summary)}</div>`
    )
    .join("");
}

function fmtDuration(seconds) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

async function loadList() {
  const status = $("#filter-status").value;
  const minScore = $("#filter-min-score").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (minScore !== "") params.set("min_score", minScore);
  const data = await api(`/api/opportunities?${params.toString()}`);
  state.items = data.items;
  $("#count-badge").textContent = data.count;
  renderList();
}

function renderList() {
  const grid = $("#opportunities");
  const empty = $("#empty-state");
  if (!state.items.length) {
    grid.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  grid.innerHTML = state.items
    .map((o) => {
      const score = o.final_score != null ? `<span class="score-pill">${o.final_score.toFixed(1)}</span>` : '<span class="score-pill" style="color:var(--muted)">—</span>';
      const chip = statusChip(o.status);
      const selected = o.id === state.selectedId ? " selected" : "";
      return `
        <div class="opp-card${selected}" data-id="${o.id}">
          <h4>${esc(o.title)}</h4>
          <div class="problem">${esc(o.problem)}</div>
          <div class="meta">
            <span class="sector">${esc(o.sector || "")}</span>
            ${chip}
            ${score}
          </div>
        </div>`;
    })
    .join("");
  grid.querySelectorAll(".opp-card").forEach((card) => {
    card.addEventListener("click", () => selectOpportunity(card.dataset.id));
  });
}

function statusChip(status) {
  const color = {
    approved: "green",
    needs_more_research: "amber",
    deferred: "neutral",
    rejected: "red",
    blocked: "red",
    draft: "neutral",
    researching: "amber",
    evaluated: "neutral",
  }[status] || "neutral";
  return `<span class="chip chip-${color}">${STATUS_LABEL[status] || status}</span>`;
}

/* ------------------------------------------------------------------ */
/* Detail                                                              */
/* ------------------------------------------------------------------ */
async function selectOpportunity(id) {
  state.selectedId = id;
  renderList();
  const detail = await api(`/api/opportunities/${id}`);
  state.detail = detail;
  renderDetail();
}

function renderDetail() {
  const d = state.detail;
  const $detail = $("#detail");
  $detail.classList.remove("hidden");
  const o = d.opportunity;
  const ev = d.evaluation;

  let scoreBlock = "";
  if (ev) {
    const color = scoreColor(ev.final_score);
    scoreBlock = `
      <div class="score-ring" style="background: conic-gradient(${color} ${ev.final_score}%, var(--slate-soft) 0)">
        <div class="ring-inner">
          <div>
            <div class="ring-val" style="color:${color}">${ev.final_score.toFixed(1)}</div>
            <div class="ring-label">/ 100</div>
          </div>
        </div>
      </div>`;
  } else {
    scoreBlock = `<div class="score-ring" style="background:var(--slate-soft)"><div class="ring-inner"><div class="ring-val" style="color:var(--muted)">—</div></div></div>`;
  }

  $("#detail-content").innerHTML = `
    <div class="detail-head">
      <div>
        <h2>${esc(o.title)}</h2>
        <div class="sub">${esc(o.sector || "")} · ${esc(o.source || "")} · creada ${esc((o.created_at || "").slice(0, 19).replace("T", " "))}</div>
        ${statusChip(o.status)}
      </div>
      ${scoreBlock}
    </div>

    <div class="actions">
      <button class="btn btn-primary btn-sm" data-act="approve">Aprobar</button>
      <button class="btn btn-secondary btn-sm" data-act="research">Necesita investigación</button>
      <button class="btn btn-secondary btn-sm" data-act="defer">Aplazar</button>
      <button class="btn btn-danger-ghost btn-sm" data-act="reject">Rechazar</button>
      <span style="flex:1"></span>
      <button class="btn btn-ghost btn-sm" data-act="reeval">Reevaluar</button>
      <button class="btn btn-ghost btn-sm" data-act="export-json">Exportar JSON</button>
      <button class="btn btn-ghost btn-sm" data-act="export-md">Exportar MD</button>
    </div>

    <div class="section">
      <h3>Problema</h3>
      <p>${esc(o.problem)}</p>
      ${o.proposed_solution ? `<h3>Solución propuesta</h3><p>${esc(o.proposed_solution)}</p>` : ""}
      <h3>Cliente objetivo</h3>
      <p>${esc(o.target_customer || "DESCONOCIDO")}</p>
    </div>

    ${ev ? renderEvaluation(ev) : '<div class="section"><h3>Evaluación</h3><p>Sin evaluar. Pulsa "Reevaluar" para ejecutar el pipeline completo.</p></div>'}

    <div class="section">
      <h3>Evidencias (${d.evidences.length})</h3>
      ${d.evidences.length ? d.evidences.map(renderEvidence).join("") : "<p>Sin evidencias guardadas.</p>"}
    </div>

    <div class="section">
      <h3>Competidores y precios observados (${d.competitors.length})</h3>
      ${d.competitors.length ? renderCompetitors(d.competitors) : "<p>Sin competidores identificados.</p>"}
    </div>

    ${ev && ev.experiment ? renderExperiment(ev.experiment) : ""}

    <div class="section">
      <h3>Registro de decisiones (auditoría)</h3>
      ${d.decision_log.length ? d.decision_log.slice().reverse().map(renderLog).join("") : "<p>Sin registros.</p>"}
    </div>
  `;

  $detail.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => handleAction(btn.dataset.act));
  });
}

function renderEvaluation(ev) {
  const order = [
    ["pain", "Dolor y urgencia", 0.2],
    ["demand", "Evidencia de demanda", 0.2],
    ["customer_reach", "Localizar clientes", 0.15],
    ["automation", "Automatización", 0.15],
    ["margin", "Margen estimado", 0.1],
    ["build_speed", "Velocidad y coste", 0.1],
    ["differentiation", "Diferenciación", 0.05],
    ["safety", "Seguridad legal", 0.05],
  ];
  const bars = order
    .map(([key, label, weight]) => {
      const c = ev.per_criterion?.[key];
      const score = c ? c.score : 0;
      const basis = c ? c.basis : "unknown";
      const color = basis === "evidence" ? "var(--accent)" : basis === "estimate" ? "#d97706" : "#94a3b8";
      return `
        <div class="bar-row">
          <div class="name">${label} <small>${BASIS_LABEL[basis]} · ${Math.round(weight * 100)}%</small></div>
          <div class="bar"><div style="width:${score}%;background:${color}"></div></div>
          <div class="val">${score.toFixed(1)}</div>
        </div>`;
    })
    .join("");

  const kpis = `
    <div class="kpis">
      <div class="kpi"><div class="k">Calidad de evidencia</div><div class="v">${ev.evidence_quality_score.toFixed(1)}</div></div>
      <div class="kpi"><div class="k">Confianza</div><div class="v">${ev.confidence_score.toFixed(1)}</div></div>
      <div class="kpi"><div class="k">Evidencias independientes</div><div class="v">${ev.independent_evidence_count}</div></div>
      <div class="kpi"><div class="k">Suposiciones sin verificar</div><div class="v">${ev.unverified_assumptions_count}</div></div>
    </div>`;

  const blockers = ev.blockers?.length
    ? `<h3>Bloqueadores</h3><ul class="blocker-list">${ev.blockers.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
    : "";

  const risks = ev.risks?.length
    ? `<h3>Riesgos (Compliance)</h3>${ev.risks
        .map(
          (r) => `<div class="risk ${esc(r.severity)}"><strong>${esc(r.category)}</strong> · ${esc(r.severity)}<br/>${esc(r.description)}${r.mitigation ? `<br/><em>Mitigación: ${esc(r.mitigation)}</em>` : ""}</div>`
        )
        .join("")}`
    : "";

  const estimates = ev.estimates ? renderEstimates(ev.estimates) : "";

  return `
    <div class="section">
      <h3>Puntuación desglosada</h3>
      ${bars}
      ${kpis}
      ${blockers}
      <div style="margin-top:12px">
        ${ev.approval_reason ? `<p><strong>Motivo para aprobar:</strong> ${esc(ev.approval_reason)}</p>` : ""}
        ${ev.rejection_reason ? `<p><strong>Motivo para rechazar:</strong> ${esc(ev.rejection_reason)}</p>` : ""}
      </div>
    </div>
    ${ev.skeptic_critique ? `<div class="section"><h3>Crítica del Skeptic</h3><p>${esc(ev.skeptic_critique)}</p></div>` : ""}
    ${estimates}
    ${risks}
  `;
}

function renderEstimates(est) {
  const rows = [
    ["Complejidad", est.complexity],
    ["Días de construcción", est.build_days_low != null ? `${est.build_days_low}–${est.build_days_high}` : null],
    ["Coste de construcción (USD)", est.build_cost_low_usd != null ? `${est.build_cost_low_usd}–${est.build_cost_high_usd}` : null],
    ["Precio estimado (USD)", est.price_low_usd != null ? `${est.price_low_usd}–${est.price_high_usd}` : null],
    ["Margen estimado (%)", est.margin_low_pct != null ? `${est.margin_low_pct}–${est.margin_high_pct}` : null],
    ["Recurrencia", est.recurrence],
    ["Tiempo hasta primera venta", est.time_to_first_sale_days != null ? `${est.time_to_first_sale_days} días` : null],
    ["Gasto inicial", est.initial_spend_level],
    ["Llegada a compradores", est.reachability],
    ["Automatización", est.automation_degree != null ? `${est.automation_degree}%` : null],
    ["Dependencias de plataforma", est.platform_dependencies?.length ? est.platform_dependencies.join(", ") : null],
  ];
  const items = rows
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v" style="font-size:13px">${esc(String(v))}</div></div>`)
    .join("");
  return `<div class="section"><h3>Estimaciones (Economist + Builder)</h3><div class="kpis">${items}</div></div>`;
}

function renderEvidence(e) {
  const verifiedTag = e.verified
    ? '<span class="tag tag-verified">verificada</span>'
    : e.reliability_score <= 0
      ? '<span class="tag tag-unknown">desconocido</span>'
      : '<span class="tag tag-unverified">sin verificar</span>';
  return `
    <div class="evidence-item">
      <div class="ev-head">
        <span class="tag">${esc(e.evidence_type)}</span>
        ${verifiedTag}
        <span class="tag">fiabilidad ${e.reliability_score.toFixed(2)}</span>
        <span class="tag">grupo: ${esc(e.independence_group || "—")}</span>
        <span class="tag">${esc(e.method)}</span>
      </div>
      <div class="summary">${esc(e.summary)}</div>
      <div class="src">${e.source_url ? `<a href="${esc(e.source_url)}" target="_blank" rel="noopener">${esc(e.source_url)}</a>` : esc(e.source_name || "")}</div>
      ${e.verification_notes ? `<div class="src">${esc(e.verification_notes)}</div>` : ""}
    </div>`;
}

function renderCompetitors(list) {
  return `<ul>${list
    .map(
      (c) =>
        `<li><strong>${esc(c.name)}</strong>${c.url ? ` — <a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)}</a>` : ""}<br/>` +
        `${esc(c.offer || "")} · precio observado: <strong>${c.observed_price != null ? c.observed_price + " USD" : "desconocido"}</strong>` +
        `${c.strengths ? `<br/><em>Fortalezas: ${esc(c.strengths)}</em>` : ""}${c.weaknesses ? `<br/><em>Debilidades: ${esc(c.weaknesses)}</em>` : ""}</li>`
    )
    .join("")}</ul>`;
}

function renderExperiment(exp) {
  const rows = [
    ["Hipótesis", exp.hypothesis],
    ["Test más barato", exp.cheapest_test],
    ["Presupuesto máximo", exp.maximum_budget != null ? `${exp.maximum_budget} USD` : null],
    ["Métrica de éxito", exp.success_metric],
    ["Umbral de éxito", exp.success_threshold],
    ["Umbral de fracaso", exp.failure_threshold],
    ["Duración", exp.duration],
  ];
  return `
    <div class="section">
      <h3>Experimento propuesto <span class="tag">${esc(exp.status)}</span></h3>
      <ul>${rows.filter(([, v]) => v != null).map(([k, v]) => `<li><strong>${k}:</strong> ${esc(String(v))}</li>`).join("")}</ul>
    </div>`;
}

function renderLog(l) {
  return `
    <div class="log-entry">
      <span class="agent">${esc(l.agent)}</span>
      <span style="flex:1">${esc(l.output_summary || "")}</span>
      <span class="when">${esc((l.timestamp || "").slice(0, 19).replace("T", " "))}</span>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Actions                                                             */
/* ------------------------------------------------------------------ */
async function handleAction(act) {
  if (!state.selectedId) return;
  const id = state.selectedId;
  try {
    if (act === "approve") await api(`/api/opportunities/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: "approved" }) });
    if (act === "research") await api(`/api/opportunities/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: "needs_more_research" }) });
    if (act === "defer") await api(`/api/opportunities/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: "deferred" }) });
    if (act === "reject") await api(`/api/opportunities/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: "rejected" }) });
    if (act === "reeval") await api(`/api/opportunities/${id}/evaluate`, { method: "POST" });
    if (act === "export-json") window.location.href = `/api/opportunities/${id}/export?format=json`;
    if (act === "export-md") window.location.href = `/api/opportunities/${id}/export?format=md`;
    await loadList();
    await selectOpportunity(id);
    await loadHealth();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

/* ------------------------------------------------------------------ */
/* Modals                                                              */
/* ------------------------------------------------------------------ */
function openModal(name) { $(`#modal-${name}`).classList.remove("hidden"); }
function closeModal(name) { $(`#modal-${name}`).classList.add("hidden"); }

function showMsg(modal, text, ok) {
  const el = $(`#modal-${modal}-msg`);
  el.textContent = text;
  el.className = `msg ${ok ? "ok" : "err"}`;
  el.classList.remove("hidden");
}

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => closeModal(btn.dataset.close));
});

$("#btn-new").addEventListener("click", () => openModal("new"));
$("#btn-import").addEventListener("click", () => openModal("import"));

$("#btn-discover").addEventListener("click", async () => {
  const problem = $("#new-problem").value.trim();
  if (problem.length < 10) return showMsg("new", "Describe el problema con al menos 10 caracteres.", false);
  try {
    const res = await api("/api/opportunities/discover", { method: "POST", body: JSON.stringify({ problem, source: "manual" }) });
    showMsg("new", `Scout propuso ${res.count} oportunidad(es).`, true);
    if (res.created?.length) {
      selectOpportunity(res.created[0].id);
      loadList();
    }
  } catch (e) {
    showMsg("new", `Error: ${e.message}`, false);
  }
});

$("#btn-create").addEventListener("click", async () => {
  const title = $("#new-title").value.trim();
  const problem = $("#new-desc").value.trim();
  if (!title || problem.length < 10) return showMsg("new", "Título y problema (mín. 10 caracteres) son obligatorios.", false);
  try {
    const res = await api("/api/opportunities", {
      method: "POST",
      body: JSON.stringify({
        title,
        problem,
        proposed_solution: $("#new-solution").value.trim() || null,
        target_customer: $("#new-customer").value.trim() || null,
        sector: $("#new-sector").value.trim() || null,
        source: "manual",
      }),
    });
    showMsg("new", "Oportunidad creada.", true);
    selectOpportunity(res.opportunity.id);
    loadList();
  } catch (e) {
    showMsg("new", `Error: ${e.message}`, false);
  }
});

$("#btn-import-go").addEventListener("click", async () => {
  const raw = $("#import-json").value.trim();
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    return showMsg("import", "JSON inválido.", false);
  }
  try {
    const res = await api("/api/import", { method: "POST", body: JSON.stringify(payload) });
    showMsg("import", `Importadas ${res.evidences_imported} evidencias y ${res.competitors_imported} competidores. ${res.reevaluated ? "Reevaluada." : ""}`, true);
    if (res.opportunity_id) {
      selectOpportunity(res.opportunity_id);
      loadList();
    }
  } catch (e) {
    showMsg("import", `Error: ${e.message}`, false);
  }
});

$("#btn-sim-start").addEventListener("click", async () => {
  const raw = prompt("Capital inicial SIMULADO (USD, p. ej. 50):");
  const capital = parseFloat(raw);
  if (!capital || capital <= 0) return alert("Capital inválido.");
  const daily = prompt("Límite de gasto diario simulado (USD, opcional):") || null;
  try {
    const res = await api("/api/economy/simulation/start", {
      method: "POST",
      body: JSON.stringify({
        initial_capital: capital,
        currency: "USD",
        maximum_daily_spend: daily ? parseFloat(daily) : null,
        simulation_name: "Simulación del panel",
      }),
    });
    alert(res.warning || "Simulación iniciada (SIMULADA).");
    await loadEconomy();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#btn-sim-income").addEventListener("click", async () => {
  const amount = parseFloat(prompt("Ingreso simulado (USD):"));
  if (!amount || amount <= 0) return;
  try {
    await api("/api/economy/income", {
      method: "POST",
      body: JSON.stringify({
        amount,
        currency: "USD",
        source_type: "manual_simulation",
        description: "Ingreso simulado desde el panel",
      }),
    });
    await loadEconomy();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#btn-sim-expense").addEventListener("click", async () => {
  const amount = parseFloat(prompt("Gasto simulado (USD):"));
  if (!amount || amount <= 0) return;
  try {
    const res = await api("/api/economy/expense/request", {
      method: "POST",
      body: JSON.stringify({
        amount,
        currency: "USD",
        description: "Gasto simulado desde el panel",
      }),
    });
    const id = res.entry?.id;
    if (id && confirm("Gasto COMMITTED. ¿Confirmarlo ahora?")) {
      await api(`/api/economy/expense/${id}/confirm`, { method: "POST" });
    }
    await loadEconomy();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#btn-reconcile").addEventListener("click", async () => {
  try {
    const res = await api("/api/economy/reconcile", { method: "POST" });
    alert(`Reconciliación: ${res.reconciled ? "OK" : "INCONSISTENTE (" + res.issues.length + " problemas)"}`);
    await loadHealth();
    await loadEconomy();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#btn-safe-pause").addEventListener("click", async () => {
  if (!confirm("¿Pausa segura? Se bloquean gastos y experimentos; los datos se conservan.")) return;
  try {
    await api("/api/engine/mode", { method: "POST", body: JSON.stringify({ mode: "safe_pause", reason: "Pausa solicitada desde el panel." }) });
    await loadHealth();
    await loadEngine();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#btn-resume-dev").addEventListener("click", async () => {
  try {
    await api("/api/engine/mode", { method: "POST", body: JSON.stringify({ mode: "development_and_review", reason: "Reanudación desde el panel." }) });
    await loadHealth();
    await loadEngine();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

/* Franja de estado (iteración 011): PRE_CYCLE + campaña real siempre visibles. */
async function loadStatus() {
  try {
    const cycle = await api("/api/economy/cycle");
    const st = $("#st-cycle");
    if (st) {
      st.textContent = cycle.clock_running
        ? `Ciclo: ACTIVO · ${cycle.days_remaining} días restantes · ${cycle.status}`
        : `Ciclo: ${cycle.status} · 30 días · sin reloj (activación deliberada)`;
    }
  } catch (_) {
    /* sin ciclo todavía */
  }
  try {
    const data = await api("/api/orchestrator/current");
    const run = data.run;
    const st = $("#st-campaign");
    const act = $("#st-action");
    if (run) {
      if (st) st.textContent = `Campaña: ${run.state} · ${run.title || ""}`;
      if (act) act.textContent = `Próxima acción: ${data.next_action || "—"}`;
    } else if (st) {
      st.textContent = "Campaña: sin iniciar — pulsa INICIAR CAMPAÑA REAL";
      if (act) act.textContent = "Próxima acción: iniciar la PRIMERA CAMPAÑA REAL 001";
    }
  } catch (_) {
    /* sin ejecución */
  }
}

$("#btn-st-campaign")?.addEventListener("click", () => switchView("orchestrator"));
$("#btn-st-csv")?.addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "csv");
});

$("#filter-status").addEventListener("change", loadList);
$("#filter-min-score").addEventListener("input", debounce(loadList, 300));

/* ------------------------------------------------------------------ */
/* Descubrimiento (Ruta B: campañas de conceptos)                      */
/* ------------------------------------------------------------------ */
const PHASE_LABEL = {
  created: "Creada",
  phase1: "Fase 1: exploración",
  phase2: "Filtro",
  phase3: "Recombinación",
  shortlist: "Shortlist",
  tournament: "Torneo",
  finalists: "Finalistas",
};

const PHASE_ORDER = ["created", "phase1", "phase2", "phase3", "shortlist", "tournament", "finalists"]; // ok

let campaigns = [];

function switchView(name) {
  const showOpps = name === "opps";
  $("#view-opportunities").classList.toggle("hidden", !showOpps);
  $("#view-discovery").classList.toggle("hidden", !(name === "discovery"));
  $("#view-reviews").classList.toggle("hidden", !(name === "reviews"));
  $("#view-orchestrator").classList.toggle("hidden", !(name === "orchestrator"));
  $("#view-ideas").classList.toggle("hidden", !(name === "ideas"));
  $("#view-campaigns").classList.toggle("hidden", !(name === "campaigns"));
  $("#tab-opps").classList.toggle("active", showOpps);
  $("#tab-discovery").classList.toggle("active", name === "discovery");
  $("#tab-reviews").classList.toggle("active", name === "reviews");
  $("#tab-orchestrator").classList.toggle("active", name === "orchestrator");
  $("#tab-ideas").classList.toggle("active", name === "ideas");
  $("#tab-campaigns").classList.toggle("active", name === "campaigns");
  if (name === "discovery") loadDiscovery();
  if (name === "reviews") loadReviews();
  if (name === "orchestrator") loadOrchestrator();
  if (name === "ideas") loadIdeas();
  if (name === "campaigns") loadCampaigns();
}

$("#tab-opps").addEventListener("click", () => switchView("opps"));
$("#tab-discovery").addEventListener("click", () => switchView("discovery"));
$("#tab-reviews").addEventListener("click", () => switchView("reviews"));
$("#tab-orchestrator").addEventListener("click", () => switchView("orchestrator"));
$("#tab-ideas").addEventListener("click", () => switchView("ideas"));
$("#tab-campaigns").addEventListener("click", () => switchView("campaigns"));

$("#btn-campaigns-demo").addEventListener("click", async () => {
  const btn = $("#btn-campaigns-demo");
  btn.disabled = true;
  try {
    const res = await api("/api/campaigns/demo", { method: "POST" });
    alert(res.note || "Piloto sintético creado.");
    loadCampaigns();
  } catch (e) {
    alert("Error: " + e.message);
  } finally {
    btn.disabled = false;
  }
});

$("#btn-campaign-new").addEventListener("click", () => openModal("campaign"));

$("#btn-campaign-create").addEventListener("click", async () => {
  const title = $("#camp-title").value.trim();
  if (!title) return showMsg("campaign", "El título es obligatorio.", false);
  const splitKeys = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
  try {
    const res = await api("/api/discovery/campaigns", {
      method: "POST",
      body: JSON.stringify({
        title,
        territory_keys: splitKeys($("#camp-territories").value),
        lens_keys: splitKeys($("#camp-lenses").value),
        archetype_keys: splitKeys($("#camp-archetypes").value),
        phase1_target: parseInt($("#camp-p1").value || "60", 10),
        shortlist_target: parseInt($("#camp-sl").value || "10", 10),
        finalists_target: parseInt($("#camp-fin").value || "3", 10),
      }),
    });
    closeModal("campaign");
    $("#camp-title").value = "";
    await loadDiscovery();
  } catch (e) {
    showMsg("campaign", `Error: ${e.message}`, false);
  }
});

async function loadDiscovery() {
  try {
    const data = await api("/api/discovery/campaigns");
    campaigns = data.items;
    $("#disc-badge").textContent = campaigns.length;
    const container = $("#discovery");
    $("#discovery-empty").classList.toggle("hidden", campaigns.length > 0);
    container.innerHTML = "";
    for (const camp of campaigns) {
      const detail = await api(`/api/discovery/campaigns/${camp.id}`);
      container.appendChild(renderCampaign(detail));
    }
  } catch (e) {
    $("#discovery-empty").textContent = `Error: ${e.message}`;
    $("#discovery-empty").classList.remove("hidden");
  }
}

function renderCampaign(detail) {
  const camp = detail.campaign;
  const card = document.createElement("div");
  card.className = "campaign-card";
  const phaseIdx = PHASE_ORDER.indexOf(camp.phase);
  const steps = PHASE_ORDER.map((p, i) => {
    const cls = i < phaseIdx ? "done" : i === phaseIdx ? "active" : "";
    return `<span class="phase-step ${cls}">${PHASE_LABEL[p] || p}</span>`;
  }).join("");
  const concepts = detail.concepts || [];
  const shortlist = concepts.filter((c) => c.status === "shortlisted" || c.status === "finalist");
  const finalists = concepts.filter((c) => c.status === "finalist");
  const blocked = concepts.filter((c) => c.status === "blocked");
  const shown = finalists.length ? finalists : shortlist;
  card.innerHTML = `
    <div class="campaign-head">
      <div>
        <h3>${esc(camp.title)}</h3>
        <div class="campaign-meta">${concepts.length} conceptos · diversidad ${(camp.diversity || 0).toFixed(2)} · ${esc((camp.created_at || "").slice(0, 10))}</div>
      </div>
      <span class="chip chip-neutral">${PHASE_LABEL[camp.phase] || camp.phase}</span>
    </div>
    <div class="phase-steps">${steps}</div>
    <div class="campaign-actions">
      ${phaseBtn("phase1", "Fase 1: generar", camp.id, phaseIdx < 0)}
      ${phaseBtn("filter", "Filtro", camp.id, phaseIdx < 1)}
      ${phaseBtn("recombine", "Recombinar", camp.id, phaseIdx < 2)}
      ${phaseBtn("shortlist", "Shortlist", camp.id, phaseIdx < 3)}
      ${phaseBtn("tournament", "Torneo", camp.id, phaseIdx < 4)}
    </div>
    ${shown.length ? renderConcepts(shown, camp.id) : ""}
    ${blocked.length ? `<div class="mission-block">${blocked.length} conceptos bloqueados (wrappers de IA / sin comprador / sin resultado).</div>` : ""}
    <div class="mission-block">
      <span>Misión de investigación Freebuff:</span>
      <select class="mission-kind" data-campaign="${camp.id}">
        <option value="campaign">campaña</option>
        <option value="signal">señal</option>
        <option value="tournament">torneo</option>
        <option value="competitors">competidores</option>
      </select>
      <button class="btn btn-ghost btn-sm btn-mission" data-campaign="${camp.id}">Crear misión</button>
    </div>
  `;
  card.querySelectorAll("[data-phase]").forEach((b) => {
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await api(`/api/discovery/campaigns/${camp.id}/${b.dataset.phase}`, { method: "POST" });
        await loadDiscovery();
      } catch (e) {
        alert(`Error: ${e.message}`);
        b.disabled = false;
      }
    });
  });
  card.querySelectorAll("[data-promote]").forEach((b) => {
    b.addEventListener("click", async () => {
      if (!confirm("¿Promover este concepto a oportunidad? Se creará una Opportunity con estado borrador.")) return;
      try {
        await api(`/api/discovery/concepts/${b.dataset.promote}/promote`, { method: "POST" });
        await loadDiscovery();
        switchView("opps");
        await loadList();
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll("[data-mission-concept]").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        const res = await api("/api/discovery/missions", {
          method: "POST",
          body: JSON.stringify({ kind: "candidate", concept_id: b.dataset.missionConcept }),
        });
        window.location.href = `/api/discovery/missions/${res.mission.mission_id}/export`;
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll(".btn-mission").forEach((b) => {
    b.addEventListener("click", async () => {
      const kind = card.querySelector(".mission-kind").value;
      try {
        const res = await api("/api/discovery/missions", {
          method: "POST",
          body: JSON.stringify({ kind, campaign_id: b.dataset.campaign }),
        });
        window.location.href = `/api/discovery/missions/${res.mission.mission_id}/export`;
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  return card;
}

function phaseBtn(phase, label, campaignId, enabled) {
  return `<button class="btn btn-ghost btn-sm" data-phase="${phase}" data-campaign="${campaignId}" ${enabled ? "" : "disabled"}>${label}</button>`;
}

function renderConcepts(list, campaignId) {
  return `<div class="concept-list">${list.map((c) => {
    const v = c.venture || {};
    const s = c.substitution || {};
    const blockedCls = s.verdict === "blocked" ? " blocked" : "";
    const labels = (v.labels || []).slice(0, 2).map((l) => `<span class="tag">${esc(l)}</span>`).join("");
    const classification = s.classification ? `<span class="tag ${s.verdict === "blocked" ? "tag-commodity" : ""}">${esc(s.classification)}</span>` : "";
    const statusTag = c.status === "finalist" ? `<span class="tag tag-verified">finalista</span>` : "";
    return `
      <div class="concept-row${c.status === "finalist" ? " finalist" : ""}">
        <div class="concept-top">
          <h4>${esc(c.title)}</h4>
          <div class="concept-tags">
            <span class="vscore${blockedCls}">${v.final_score != null ? v.final_score.toFixed(1) : "—"}</span>
            ${classification}
            ${labels}
            ${statusTag}
          </div>
        </div>
        <div class="concept-body">${esc((c.mechanism || "").slice(0, 220))}</div>
        <div class="concept-actions">
          ${c.status === "shortlisted" || c.status === "finalist" ? `<button class="btn btn-primary btn-sm" data-promote="${c.id}">Promover a oportunidad</button>` : ""}
          <button class="btn btn-ghost btn-sm" data-mission-concept="${c.id}">Misión de investigación</button>
        </div>
      </div>`;
  }).join("")}</div>`;
}

/* ------------------------------------------------------------------ */
/* Laboratorio de oportunidades (comité de contraste, iteración 005)    */
/* ------------------------------------------------------------------ */
const REC_LABEL = {
  REJECT: "Rechazar",
  MORE_RESEARCH: "Más investigación",
  SMALL_EXPERIMENT: "Experimento pequeño",
  PRIORITY_EXPERIMENT: "Experimento prioritario",
};

const QUEUE_STATE_LABEL = { pending: "Pendiente", continued: "Continuada", waiting: "Esperando", reviewed: "Revisada" };
const COMMITTEE_STATE_LABEL = {
  pendiente: "Pendiente",
  importada: "Importada",
  procesada: "Procesada",
  parcial: "Parcial",
  invalida: "Inválida",
  caducada: "Caducada",
  pendiente_validacion: "Pendiente de validación",
  continuada_sin_revision: "Continuó sin revisión",
  revisada: "Revisada",
};
const REVIEW_PROVIDER_LABEL = { gpt: "GPT", grok: "Grok", gemini: "Gemini", claude: "Claude", deepseek: "DeepSeek", openrouter: "OpenRouter", omniroute: "OmniRoute", human: "Humano" };

let reviewQueue = [];
let reviewImportTarget = null;
let reviewCombinedMode = false;

async function loadReviews() {
  try {
    const data = await api("/api/reviews/queue");
    reviewQueue = data.items;
    $("#rev-badge").textContent = data.count;
    let autoLine = "";
    try {
      const auto = (await api("/api/reviews/auto-status")).auto_status;
      const cb = auto.circuit_breaker || {};
      autoLine =
        `<div class="reviews-config-row auto-config">OpenRouter: ` +
        `${auto.configured ? "✅ configurado" : "⚠️ sin clave (la ausencia de revisión es neutral)"} · ` +
        `modelo ${esc(auto.review_model)}${auto.configured ? ` (fallback ${esc(auto.fallback_model)})` : ""} · ` +
        `hoy ${auto.usage_today.requests}/${auto.usage_today.limit} llamadas · ` +
        `coste hoy ${auto.usage_today.cost_usd.toFixed(5)}/${auto.usage_today.cost_limit_usd} USD · ` +
        `circuit breaker ${cb.open ? "ABIERTO (pausado)" : "cerrado"} · ` +
        `máx ${auto.max_reviews_per_opportunity} revisión(es) automática(s)/oportunidad</div>`;
    } catch (e) {
      autoLine = `<div class="reviews-config-row auto-config">OpenRouter: estado no disponible (${esc(e.message)})</div>`;
    }
    let omniLine = "";
    try {
      const om = await api("/api/providers/omniroute/status");
      const h = om.health || {};
      omniLine =
        `<div class="reviews-config-row auto-config omni-config">OmniRoute (aislado): ` +
        `${om.enabled ? "🟢 habilitado" : "⚪ desactivado (por defecto)"} · ` +
        `endpoint ${esc(h.endpoint || "—")} · modelo ${esc(h.review_model || "auto")} · ` +
        `heartbeat ${h.last_heartbeat_at ? esc(String(h.last_heartbeat_at)) : "—"} · ` +
        `solicitudes hoy ${om.requests_today}/${om.daily_request_limit} · ` +
        `allowlist ${om.allowlist_default.allowed ? "permitido (pruebas)" : om.allowlist_default.reason} · ` +
        `última incidencia ${h.last_incident ? esc(String(h.last_incident)) : "ninguna"}</div>`;
    } catch (e) {
      omniLine = `<div class="reviews-config-row auto-config omni-config">OmniRoute: estado no disponible (${esc(e.message)})</div>`;
    }
    $("#reviews-config").innerHTML =
      `<div class="reviews-config-row">Umbral interno: <strong>${data.threshold}</strong> · ` +
      `Máximo finalistas/semana: <strong>${data.max_per_week}</strong> · ` +
      `Ventana: <strong>${data.window_hours}h</strong> · ` +
      `Continuar sin revisión: <strong>${data.continue_without_review ? "sí (neutral)" : "no"}</strong></div>` +
      autoLine +
      omniLine;
    const container = $("#reviews-queue");
    $("#reviews-empty").classList.toggle("hidden", data.items.length > 0);
    container.innerHTML = "";
    data.items.forEach((item) => container.appendChild(renderReviewItem(item)));
  } catch (e) {
    $("#reviews-empty").textContent = `Error: ${e.message}`;
    $("#reviews-empty").classList.remove("hidden");
  }
}

function renderReviewItem(item) {
  const card = document.createElement("div");
  card.className = "review-card";
  const syn = item.synthesis || {};
  const recs = item.recommendations || [];
  const recChips = recs
    .map((r) => `<span class="rec-chip rec-${r}">${REC_LABEL[r] || r}</span>`)
    .join("");
  const riskList = (syn.repeated_risks || [])
    .map((r) => `<li>${esc(r)}</li>`)
    .join("");
  const consensus = syn.consensus_level || "NONE";
  const stateLabel = QUEUE_STATE_LABEL[item.status] || item.status;
  const cState = COMMITTEE_STATE_LABEL[item.committee_state] || item.committee_state || stateLabel;
  const deadline = item.window_deadline ? `Ventana hasta: ${esc((item.window_deadline || "").slice(0, 19).replace("T", " "))}` : "";
  const windowLeft = item.window_remaining_hours != null
    ? ` · tiempo restante: <strong>${item.window_remaining_hours}h</strong>`
    : "";
  const perProv = (item.per_provider || {});
  const provChips = Object.keys(perProv)
    .map((p) => `<span class="chip chip-${perProv[p] === "valid" ? "ok" : perProv[p] === "partial" ? "amber" : perProv[p] === "invalid" ? "red" : "neutral"}" title="estado: ${esc(perProv[p])}">${esc(REVIEW_PROVIDER_LABEL[p] || p)}: ${esc(perProv[p])}</span>`)
    .join(" ");
  card.innerHTML = `
    <div class="review-head">
      <div>
        <h4>${esc(item.title)}</h4>
        <div class="review-meta">Puntuación interna <strong>${item.internal_score.toFixed(1)}</strong> · ${esc(item.status_label)} · ${deadline}${windowLeft}</div>
      </div>
      <div class="review-tags">
        <span class="chip chip-${item.reviewed_without_external ? "amber" : "neutral"}">${esc(cState)}</span>
        ${item.reviewed_without_external ? `<span class="chip chip-amber">sin revisión externa (neutral)</span>` : ""}
        ${provChips}
      </div>
    </div>
    <div class="review-row">
      <span>Revisiones: <strong>${item.valid_reviews_count}</strong>/<strong>${item.reviews_count}</strong> válidas</span>
      <span>Consenso: <strong class="cons-${consensus}">${consensus}</strong></span>
      <span>Confianza media: <strong>${syn.average_confidence != null ? syn.average_confidence : "—"}</strong></span>
      <span>Acción recomendada: <strong>${syn.recommended_next_action ? (REC_LABEL[syn.recommended_next_action] || syn.recommended_next_action) : "—"}</strong></span>
    </div>
    ${recChips ? `<div class="review-row">${recChips}</div>` : ""}
    ${riskList ? `<div class="review-risks"><strong>Riesgos repetidos entre revisores:</strong><ul>${riskList}</ul></div>` : ""}
    ${syn.missing_evidence && syn.missing_evidence.length ? `<div class="review-risks"><strong>Evidencia ausente señalada:</strong> ${syn.missing_evidence.slice(0, 2).map(esc).join(" · ")}</div>` : ""}
    <div class="review-actions">
      <span class="review-action-label">Expediente:</span>
      <button class="btn btn-primary btn-sm" data-copy="${item.opportunity_id}" data-reviewer="gpt" title="Copia el expediente completo para pegarlo en GPT">Copiar para GPT</button>
      <button class="btn btn-primary btn-sm" data-copy="${item.opportunity_id}" data-reviewer="grok" title="Copia el expediente completo para pegarlo en Grok">Copiar para Grok</button>
      <button class="btn btn-primary btn-sm" data-copy="${item.opportunity_id}" data-reviewer="gemini" title="Copia el expediente completo para pegarlo en Gemini">Copiar para Gemini</button>
      <button class="btn btn-secondary btn-sm" data-packet="${item.opportunity_id}">Descargar .md</button>
    </div>
    <div class="review-actions">
      <button class="btn btn-secondary btn-sm" data-import="${item.opportunity_id}" title="Pegar respuesta o importar TXT/Markdown">Pegar respuesta / Importar</button>
      <button class="btn btn-secondary btn-sm" data-import-combined="${item.opportunity_id}" title="Importa un único archivo con secciones # GPT / # GROK / # GEMINI">Importar archivo combinado</button>
      <button class="btn btn-ghost btn-sm" data-synthesize="${item.opportunity_id}">Síntesis</button>
      <button class="btn btn-ghost btn-sm" data-decide="${item.opportunity_id}" title="Decisión autónoma por reglas deterministas (sin votos): prioridad + confianza limitada. Nunca autoriza producción, gasto ni ingresos.">Decidir (automático)</button>
      <button class="btn btn-ghost btn-sm" data-auto-review="${item.opportunity_id}" title="Opción A: una revisión de contraste vía OpenRouter (guardas deterministas; sin clave no hace nada)">Revisión automática</button>
      ${item.status === "pending" ? `<button class="btn btn-ghost btn-sm" data-continue="${item.opportunity_id}">Continuar sin revisión</button>` : ""}
    </div>
    ${item.notes ? `<div class="review-notes">Notas: ${esc(item.notes)}</div>` : ""}
  `;
  card.querySelectorAll("[data-packet]").forEach((b) => {
    b.addEventListener("click", () => {
      window.location.href = `/api/reviews/opportunities/${b.dataset.packet}/packet`;
    });
  });
  card.querySelectorAll("[data-import]").forEach((b) => {
    b.addEventListener("click", () => {
      reviewImportTarget = b.dataset.import;
      reviewCombinedMode = false;
      $("#review-combined-note").classList.add("hidden");
      $("#review-provider").disabled = false;
      openModal("review");
    });
  });
  card.querySelectorAll("[data-synthesize]").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        const res = await api(`/api/reviews/opportunities/${b.dataset.synthesize}/synthesize`, { method: "POST" });
        alert(`Síntesis: consenso ${res.synthesis.consensus_level} · acción recomendada ${res.synthesis.recommended_next_action || "—"} · ${res.synthesis.valid_reviews_count} revisiones válidas`);
        await loadReviews();
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll("[data-continue]").forEach((b) => {
    b.addEventListener("click", async () => {
      if (!confirm("¿Continuar sin revisión externa? La ausencia es NEUTRAL (no es aprobación).")) return;
      try {
        await api(`/api/reviews/opportunities/${b.dataset.continue}/continue`, { method: "POST" });
        await loadReviews();
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll("[data-copy]").forEach((b) => {
    b.addEventListener("click", async () => {
      const reviewer = b.dataset.reviewer;
      const label = (REVIEW_PROVIDER_LABEL[reviewer] || reviewer).toUpperCase();
      try {
        const res = await api(`/api/reviews/opportunities/${b.dataset.copy}/packet/copy?reviewer=${reviewer}`);
        const text = res.content;
        let ok = false;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          try {
            await navigator.clipboard.writeText(text);
            ok = true;
          } catch (e) {
            ok = false;
          }
        }
        if (!ok) {
          const ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
          ok = true;
        }
        if (ok) {
          alert(`Expediente copiado para ${label}. Pégalo completo en ${label} y guarda la respuesta para pegarla aquí (Pegar respuesta / Importar).`);
        } else {
          alert("No se pudo copiar automáticamente; abre el expediente (Descargar .md) y cópialo manualmente.");
        }
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll("[data-import-combined]").forEach((b) => {
    b.addEventListener("click", () => {
      reviewImportTarget = b.dataset.importCombined;
      reviewCombinedMode = true;
      $("#review-combined-note").classList.remove("hidden");
      $("#review-provider").disabled = true;
      openModal("review");
    });
  });
  card.querySelectorAll("[data-decide]").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        const res = await api(`/api/reviews/opportunities/${b.dataset.decide}/decide`, { method: "POST" });
        alert(
          `Decisión autónoma: ${res.decision} · Δconfianza ${res.confidence_delta > 0 ? "+" : ""}${res.confidence_delta} · ` +
          `(producción no autorizada, gasto no autorizado, opinión ≠ evidencia)`
        );
        await loadReviews();
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });
  card.querySelectorAll("[data-auto-review]").forEach((b) => {
    b.addEventListener("click", async () => {
      if (!confirm("¿Solicitar UNA revisión automática vía OpenRouter? (Opinión de modelo, nunca evidencia; coste registrado con honestidad.)")) return;
      const btn = b;
      btn.disabled = true;
      try {
        const res = await api(`/api/reviews/opportunities/${b.dataset.autoReview}/auto-review`, { method: "POST" });
        if (res.status === "ok") {
          alert(`Revisión automática guardada (${res.review.model}) · cost_source ${res.cost_source} · billing_verified ${res.billing_verified}`);
        } else if (res.status === "skipped" || res.status === "blocked") {
          alert(`Sin revisión automática (${res.reason}): ${res.detail || "la ausencia es neutral."}`);
        } else {
          alert(`Fallo neutral (${res.reason}): ${res.detail || ""}`);
        }
        await loadReviews();
      } catch (e) {
        alert(`Error: ${e.message}`);
      } finally {
        btn.disabled = false;
      }
    });
  });
  return card;
}

$("#btn-reviews-demo").addEventListener("click", async () => {
  if (!confirm("¿Crear la demostración SINTÉTICA del comité de contraste? Todo queda etiquetado como demo (no es evidencia real).")) return;
  try {
    const res = await api("/api/reviews/demo", { method: "POST" });
    alert(`Demo del comité lista: puntuación interna ${res.internal_score.toFixed(1)} (umbral ${res.threshold}, sobrecédula demo auditable) · ${res.reviews.length} revisiones mock · consenso ${res.synthesis.consensus_level}`);
    await loadReviews();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#review-file").addEventListener("change", () => {
  const file = $("#review-file").files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    $("#review-content").value = String(reader.result || "");
  };
  reader.readAsText(file);
});

$("#btn-review-import").addEventListener("click", async () => {
  if (!reviewImportTarget) return showMsg("review", "Selecciona primero una oportunidad de la cola.", false);
  const content = $("#review-content").value.trim();
  if (!content) return showMsg("review", "Pega el contenido de la revisión o sube un archivo.", false);
  const file = $("#review-file").files[0];
  const filename = file ? file.name : "revision.txt";
  try {
    let res;
    if (reviewCombinedMode) {
      res = await api(`/api/reviews/opportunities/${reviewImportTarget}/import-combined`, {
        method: "POST",
        body: JSON.stringify({
          filename,
          content,
          default_model: $("#review-model").value.trim() || null,
          execution_mode: $("#review-mode").value,
          imported_by: "human (panel)",
        }),
      });
      const skipped = res.skipped && res.skipped.length ? ` · omitidas: ${res.skipped.map((s) => s.provider).join(", ")}` : "";
      showMsg("review", `Importación combinada: ${res.count} revisión(es) importada(s).${skipped}`, true);
    } else {
      res = await api(`/api/reviews/opportunities/${reviewImportTarget}/import`, {
        method: "POST",
        body: JSON.stringify({
          filename,
          content,
          provider: $("#review-provider").value.trim() || null,
          model: $("#review-model").value.trim() || null,
          execution_mode: $("#review-mode").value,
          imported_by: "human (panel)",
        }),
      });
      const warnings = res.warnings && res.warnings.length ? ` · avisos: ${res.warnings.join("; ")}` : "";
      showMsg("review", `Revisión importada (estado ${res.status}).${warnings}`, true);
    }
    $("#review-content").value = "";
    $("#review-file").value = "";
    $("#review-provider").disabled = false;
    reviewCombinedMode = false;
    $("#review-combined-note").classList.add("hidden");
    await loadReviews();
  } catch (e) {
    showMsg("review", `Error: ${e.message}`, false);
  }
});

/* ------------------------------------------------------------------ */
/* Orquestador end-to-end (iteración 010)                              */
/* ------------------------------------------------------------------ */
let currentRun = null;

async function loadOrchestrator() {
  try {
    const data = await api("/api/orchestrator/current");
    currentRun = data.run;
    renderOrchestrator(data);
  } catch (e) {
    $("#orchestrator-panel").innerHTML = `<p class="hint">Error: ${esc(e.message)}</p>`;
  }
}

function renderOrchestrator(data) {
  const run = data.run;
  const panel = $("#orchestrator-panel");
  const empty = $("#orchestrator-empty");
  const btnStart = $("#btn-orc-start");
  const btnAdvance = $("#btn-orc-advance");
  const btnPause = $("#btn-orc-pause");
  const btnResume = $("#btn-orc-resume");
  const btnCancel = $("#btn-orc-cancel");
  if (!run) {
    panel.innerHTML = "";
    empty.classList.remove("hidden");
    btnStart.classList.remove("hidden");
    [btnAdvance, btnPause, btnResume, btnCancel].forEach((b) => b.classList.add("hidden"));
    return;
  }
  empty.classList.add("hidden");
  btnStart.classList.add("hidden");
  btnAdvance.classList.toggle("hidden", !["RESEARCH_PENDING", "RESEARCH_IMPORTED", "COMMITTEE_COMPLETED", "CANDIDATES_READY"].includes(run.state) && !data.research_pending);
  btnPause.classList.toggle("hidden", run.state === "PAUSED" || ["COMPLETED", "FAILED", "CANCELLED"].includes(run.state));
  btnResume.classList.toggle("hidden", run.state !== "PAUSED");
  btnCancel.classList.toggle("hidden", ["COMPLETED", "FAILED", "CANCELLED"].includes(run.state));

  const disc = data.discovery || {};
  const concepts = disc.concepts || [];
  const byStatus = (s) => concepts.filter((c) => c.status === s).length;
  const funnel = `
    <div class="eco-kpis">
      <div class="eco-kpi"><div class="k">Estado</div><div class="v">${esc(run.state)}</div></div>
      <div class="eco-kpi"><div class="k">Iniciales</div><div class="v">${concepts.length}</div></div>
      <div class="eco-kpi"><div class="k">Descartadas</div><div class="v">${byStatus("blocked") + byStatus("eliminated")}</div></div>
      <div class="eco-kpi"><div class="k">Shortlist</div><div class="v">${byStatus("shortlisted")}</div></div>
      <div class="eco-kpi"><div class="k">Finalistas</div><div class="v">${byStatus("finalist")}</div></div>
      <div class="eco-kpi"><div class="k">En investigación</div><div class="v">${byStatus("promoted")}</div></div>
    </div>`;

  const nextAction = data.next_action ? `<p class="hint"><strong>Próxima acción:</strong> ${esc(data.next_action)}</p>` : "";
  const owner = data.owner_action_required ? `<p class="hint"><span class="tag tag-unverified">INTERVENCIÓN DEL PROPIETARIO NECESARIA</span></p>` : "";

  let research = "";
  if (data.research_pending) {
    research = `<div class="card"><h4>Investigación externa necesaria</h4><p class="hint">El orquestador se detiene aquí honestamente: no hay investigación web automática en este entorno. Copia cada misión, pégala en Freebuff (o en el modelo que prefieras), copia la respuesta y pégala abajo.</p><div id="orc-missions"></div><div class="row"><textarea id="orc-paste-research" class="input" rows="6" placeholder="Pega aquí la respuesta completa de la misión…"></textarea></div><div class="row"><button id="btn-orc-import-research" class="btn btn-primary btn-sm">Pegar investigación</button></div></div>`;
  }

  let committee = "";
  if (data.committee && data.committee.length) {
    committee = `<div class="card"><h4>Comité externo</h4><div class="stack">` + data.committee.map((c) => {
      const rec = c.synthesis ? `<div class="v">Recomendación: ${esc(c.synthesis.recommended_next_action)} · consenso ${esc(c.synthesis.consensus_level)}</div>` : `<div class="v">Sin síntesis · ${c.reviews_count} revisión(es)</div>`;
      return `<div class="feed-item"><strong>${esc(c.title)}</strong> (score ${c.final_score != null ? c.final_score.toFixed(1) : "—"}) ${rec}</div>`;
    }).join("") + `</div></div>`;
  }

  let experiment = "";
  if (data.experiment_plan) {
    const ep = data.experiment_plan;
    experiment = `<div class="card"><h4>Plan de experimento</h4><p><strong>Oferta:</strong> ${esc(ep.offer || "—")}</p><p><strong>Comprador:</strong> ${esc(ep.buyer || "—")} · <strong>Precio:</strong> ${esc(ep.price || "—")}</p><p><strong>Métrica de éxito:</strong> ${esc(ep.success_metric || "—")} · umbral ${esc(ep.success_threshold || "—")} · abandono ${esc(ep.kill_condition || "—")}</p><p><strong>Coste máximo:</strong> ${esc(ep.max_cost_usd != null ? ep.max_cost_usd : "—")} USD · duración ${esc(ep.duration_days || "—")} días</p></div>`;
  }

  panel.innerHTML = funnel + nextAction + owner + research + committee + experiment;

  if (data.research_pending) {
    loadOrchestratorMissions(run.id);
  }
  loadIdeas();
}

async function loadOrchestratorMissions(runId) {
  try {
    const data = await api(`/api/orchestrator/runs/${runId}/missions`);
    const box = $("#orc-missions");
    if (!box) return;
    if (!data.missions?.length) {
      box.innerHTML = `<p class="hint">Sin misiones planificadas todavía.</p>`;
      return;
    }
    box.innerHTML = data.missions.map((m) => `
      <div class="feed-item">
        <strong>${esc(m.title || m.mission_id)}</strong> <span class="tag tag-unverified">${esc(m.kind || "MISSION")}</span>
        <div class="row"><button class="btn btn-secondary btn-sm btn-copy-mission" data-md="${esc(m.markdown || "")}">Copiar misión</button></div>
      </div>`).join("");
    box.querySelectorAll(".btn-copy-mission").forEach((b) => {
      b.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(b.dataset.md);
          b.textContent = "¡Copiada!";
          setTimeout(() => (b.textContent = "Copiar misión"), 1500);
        } catch (_) {
          const ta = document.createElement("textarea");
          ta.value = b.dataset.md;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
          b.textContent = "¡Copiada!";
          setTimeout(() => (b.textContent = "Copiar misión"), 1500);
        }
      });
    });
  } catch (e) {
    const box = $("#orc-missions");
    if (box) box.innerHTML = `<p class="hint">Error: ${esc(e.message)}</p>`;
  }
}

async function orchestratorAction(path, btnId, after) {
  const btn = $(btnId);
  if (btn) btn.disabled = true;
  try {
    await api(path, { method: "POST" });
    await loadOrchestrator();
    if (after) after();
  } catch (e) {
    alert("Error: " + e.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

$("#btn-orc-start").addEventListener("click", () => orchestratorAction("/api/orchestrator/start", "#btn-orc-start"));
$("#btn-orc-advance").addEventListener("click", () => {
  if (!currentRun) return;
  orchestratorAction(`/api/orchestrator/runs/${currentRun.id}/advance`, "#btn-orc-advance");
});
$("#btn-orc-pause").addEventListener("click", () => {
  if (!currentRun) return;
  orchestratorAction(`/api/orchestrator/runs/${currentRun.id}/pause`, "#btn-orc-pause");
});
$("#btn-orc-resume").addEventListener("click", () => {
  if (!currentRun) return;
  orchestratorAction(`/api/orchestrator/runs/${currentRun.id}/resume`, "#btn-orc-resume");
});
$("#btn-orc-cancel").addEventListener("click", () => {
  if (!currentRun) return;
  if (!confirm("¿Cancelar la campaña real? Se conservan las ideas y los aprendizajes.")) return;
  orchestratorAction(`/api/orchestrator/runs/${currentRun.id}/cancel`, "#btn-orc-cancel");
});

document.addEventListener("click", (ev) => {
  const target = ev.target.closest("#btn-orc-import-research");
  if (!target || !currentRun) return;
  const text = $("#orc-paste-research")?.value?.trim();
  if (!text) return alert("Pega primero la respuesta de la misión.");
  (async () => {
    try {
      // Asocia la respuesta pegada a la primera misión pendiente.
      const missions = await api(`/api/orchestrator/runs/${currentRun.id}/missions`);
      const first = missions.missions?.[0];
      if (!first) return alert("No hay misiones pendientes a las que asociar la respuesta.");
      let payload = { mission_id: first.mission_id, evidences: [], notes: text.slice(0, 4000) };
      // Si la respuesta es el JSON estructurado que pedía la misión, pasa tal cual.
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object") {
          payload = {
            mission_id: first.mission_id,
            evidences: Array.isArray(parsed.evidences) ? parsed.evidences : [],
            competitors: Array.isArray(parsed.competitors) ? parsed.competitors : [],
            buyer_confirmed: parsed.buyer_confirmed || null,
            notes: String(parsed.notes || "").slice(0, 4000) || null,
          };
        }
      } catch (_) {
        /* texto libre: se guarda como nota, sin evidencias inventadas */
      }
      const res = await api(`/api/orchestrator/runs/${currentRun.id}/import-research`, {
        method: "POST",
        body: JSON.stringify([payload]),
      });
      alert(res.note || "Investigación importada.");
      await loadOrchestrator();
    } catch (e) {
      alert("Error: " + e.message);
    }
  })();
});

/* ------------------------------------------------------------------ */
/* Ideas (vista filtrable de la campaña real)                          */
/* ------------------------------------------------------------------ */
async function loadIdeas() {
  let run = currentRun;
  if (!run) {
    try {
      const data = await api("/api/orchestrator/current");
      run = data.run;
    } catch (_) {
      /* sin ejecución */
    }
  }
  const grid = $("#ideas-grid");
  const empty = $("#ideas-empty");
  if (!grid) return;
  if (!run) {
    grid.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  const detail = await api(`/api/orchestrator/runs/${run.id}`);
  currentRun = detail.run;
  const concepts = (detail.discovery?.concepts || []).slice().reverse();
  const filter = $("#ideas-filter")?.value || "all";
  const filtered = concepts.filter((c) => {
    if (filter === "all") return true;
    if (filter === "active") return ["draft", "shortlisted", "finalist", "promoted"].includes(c.status);
    if (filter === "blocked") return ["blocked", "eliminated"].includes(c.status);
    if (filter === "commodity") return c.status === "blocked" && (c.substitution?.classification === "COMMODITY_WRAPPER");
    if (filter === "shortlist") return c.status === "shortlisted";
    if (filter === "finalist") return c.status === "finalist";
    if (filter === "promoted") return c.status === "promoted";
    return true;
  });
  empty.classList.toggle("hidden", filtered.length > 0);
  grid.innerHTML = filtered.map((c) => {
    const sub = c.substitution?.classification || "sin test";
    const v = c.venture?.final_score;
    const vq = v != null ? `<div class="v">Venture: ${v.toFixed(1)}</div>` : "";
    const why = c.rejection_reason || c.venture?.blockers?.[0] || "";
    return `
      <div class="card idea-card">
        <div class="card-head"><strong>${esc(c.title)}</strong> <span class="tag ${c.status === "blocked" || c.status === "eliminated" ? "tag-bad" : "tag-ok"}">${esc(c.status)}</span></div>
        <p class="small">${esc((c.problem_hypothesis || "").slice(0, 140))}</p>
        <p class="small muted">Comprador: ${esc((c.buyer_hypothesis || "—").slice(0, 90))}</p>
        <div class="row small"><span class="tag tag-unverified">${esc(sub)}</span>${vq}</div>
        ${why ? `<p class="small muted">Motivo: ${esc(why.slice(0, 160))}</p>` : ""}
      </div>`;
  }).join("");
}

$("#ideas-filter").addEventListener("change", loadIdeas);

function exportHref(runId, fmt) {
  return `/api/orchestrator/runs/${runId}/exports/${fmt}`;
}

$("#btn-ideas-export").addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "csv");
});
$("#btn-ideas-export-md").addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "md");
});
$("#btn-ideas-export-json").addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "json");
});
$("#btn-ideas-export-finalists").addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "finalists");
});
$("#btn-ideas-export-research").addEventListener("click", () => {
  if (currentRun) location.href = exportHref(currentRun.id, "research_zip");
});

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function scoreColor(score) {
  if (score >= 75) return "#15803d";
  if (score >= 60) return "#b45309";
  if (score >= 40) return "#475569";
  return "#b91c1c";
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

/* ------------------------------------------------------------------ */
/* Campañas Freebuff-first (sesiones reanudables)                      */
/* ------------------------------------------------------------------ */
async function loadCampaigns() {
  try {
    const data = await api("/api/campaigns");
    const items = data.items || [];
    $("#camp-badge").textContent = items.length;
    const container = $("#campaigns");
    $("#campaigns-empty").classList.toggle("hidden", items.length > 0);
    container.innerHTML = "";
    for (const camp of items) {
      const detail = await api(`/api/campaigns/${camp.id}`);
      container.appendChild(renderFreebuffCampaign(detail));
    }
  } catch (e) {
    $("#campaigns-empty").textContent = `Error: ${e.message}`;
    $("#campaigns-empty").classList.remove("hidden");
  }
}

function renderFreebuffCampaign(detail) {
  const camp = detail.campaign || {};
  const card = document.createElement("div");
  card.className = "campaign-card";
  const sessions = (detail.sessions || []).slice(0, 3);
  const sessionRows = sessions.length
    ? sessions
        .map((s) => {
          const status = s.status === "completed" ? "✅" : s.status === "active" ? "⏳" : "○";
          return `<div class="session-row">${status} ${esc(s.session_id.slice(0, 8))} · ${s.time_budget_hours}h · ${esc(s.stage_start || "")}${s.stage_end ? " → " + esc(s.stage_end) : ""}</div>`;
        })
        .join("")
    : '<div class="session-row dim">sin sesiones</div>';
  card.innerHTML = `
    <div class="campaign-head">
      <div>
        <h3>${esc(camp.title || camp.id)}</h3>
        <div class="campaign-meta">
          ${camp.time_budget_hours}h/sesión · finalistas máx ${camp.maximum_finalists} ·
          ideas ${camp.concepts_count || 0} · rechazadas ${camp.concepts_rejected || 0} ·
          ${(camp.is_synthetic ? "SINTÉTICA" : "real")}
        </div>
      </div>
      <div class="camp-badges">
        <span class="chip chip-${camp.status === "completed" ? "ok" : camp.status === "blocked" ? "danger" : "neutral"}">${esc(camp.status || "")}</span>
        <span class="chip chip-neutral">${esc(camp.stage || "")}</span>
      </div>
    </div>
    <div class="session-list">${sessionRows}</div>
    <div class="campaign-actions">
      <button class="btn btn-ghost btn-sm btn-session" data-id="${esc(camp.id)}">Preparar sesión (2-6 h)</button>
      <button class="btn btn-ghost btn-sm btn-camp-prompt" data-id="${esc(camp.id)}">Prompt breve</button>
      ${camp.next_recommended_action ? `<span class="hint">${esc(camp.next_recommended_action)}</span>` : ""}
    </div>
    <div class="campaign-note">
      <span class="tag tag-unverified">FREEBUFF SESSION</span>
      <span class="tag tag-unverified">NO 24/7 GUARANTEED</span>
      <span class="tag tag-ok">API COST 0</span>
    </div>
  `;
  card.querySelector(".btn-session").addEventListener("click", async () => {
    const hours = prompt("Horas objetivo de la sesión (2-6):", "3");
    if (!hours) return;
    try {
      const res = await api(`/api/campaigns/${camp.id}/sessions`, {
        method: "POST",
        body: JSON.stringify({ hours: parseInt(hours, 10), actor: "human" }),
      });
      alert(`Sesión preparada: ${res.session.session_id}\n\n${res.session.short_prompt}`);
      await loadCampaigns();
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  });
  card.querySelector(".btn-camp-prompt").addEventListener("click", async () => {
    try {
      const res = await api(`/api/campaigns/${camp.id}/prompt`);
      alert(res.short_prompt);
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  });
  return card;
}

/* ------------------------------------------------------------------ */
/* Init                                                                */
/* ------------------------------------------------------------------ */
(async function init() {
  try {
    await loadHealth();
    await loadEngine();
    await loadEconomy();
    await loadList();
    await loadStatus();
  } catch (e) {
    $("#empty-state").textContent = `Error cargando datos: ${e.message}`;
    $("#empty-state").classList.remove("hidden");
  }
})();

// Refresco periódico del motor, la economía y la franja de estado.
setInterval(() => {
  loadEngine();
  loadEconomy();
  loadStatus();
}, 15000);
