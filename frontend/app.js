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

$("#btn-demo").addEventListener("click", async () => {
  if (!confirm("¿Cargar las oportunidades de demostración (MQL5)? Se crearán nuevas oportunidades de ejemplo.")) return;
  try {
    const res = await api("/api/demo/load?evaluate=true", { method: "POST" });
    alert(`Demo cargada: ${res.created} creadas, ${res.evaluated} evaluadas.`);
    await loadList();
    await loadHealth();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
});

$("#filter-status").addEventListener("change", loadList);
$("#filter-min-score").addEventListener("input", debounce(loadList, 300));

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
/* Init                                                                */
/* ------------------------------------------------------------------ */
(async function init() {
  try {
    await loadHealth();
    await loadEngine();
    await loadEconomy();
    await loadList();
  } catch (e) {
    $("#empty-state").textContent = `Error cargando datos: ${e.message}`;
    $("#empty-state").classList.remove("hidden");
  }
})();

// Refresco periódico del motor y la economía (timeline en vivo, ligero).
setInterval(() => {
  loadEngine();
  loadEconomy();
}, 15000);
