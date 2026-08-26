/* Centro de mando (iteración 018) — panel agregado con datos 100% reales.
 * Consume GET /api/command-center. Nunca inventa cifras: cualquier dato
 * ausente se muestra como DESCONOCIDO / NO CONECTADO / SIN DATOS / SIMULACIÓN.
 *
 * Código de color:
 *   cian   = trabajando     verde  = confirmado     ámbar  = hipótesis/desconocido
 *   violeta= razonamiento   rojo   = bloqueo        blanco = decisión determinista
 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const statusColor = (nature) => {
    const n = String(nature || "").toUpperCase();
    if (n.includes("REAL") || n.includes("CONFIRM")) return "green";
    if (n.includes("BLOQUE") || n.includes("FAIL")) return "red";
    if (n.includes("SIMUL") || n.includes("HIPÓTESIS") || n.includes("HIPOTESIS")) return "amber";
    if (n.includes("MODELO")) return "violet";
    if (n.includes("TRABAJANDO") || n.includes("PENDIENTE")) return "cyan";
    if (n.includes("NO CONECTADO") || n.includes("SIN DATOS") || n.includes("DESCONOCIDO")) return "amber";
    return "white";
  };

  const natureChip = (nature) => {
    const c = statusColor(nature);
    return `<span class="nature nature-${c}">${esc(nature || "DESCONOCIDO")}</span>`;
  };

  const card = (title, body, nature) => `
    <div class="cmd-card">
      <div class="cmd-card-head"><h3>${esc(title)}</h3>${nature ? natureChip(nature) : ""}</div>
      <div class="cmd-card-body">${body}</div>
    </div>`;

  const kv = (rows) =>
    `<table class="cmd-kv">${rows
      .map(
        ([k, v, cls]) =>
          `<tr><td class="cmd-k">${esc(k)}</td><td class="cmd-v ${cls || ""}">${v === null || v === undefined || v === "" ? '<span class="muted">DESCONOCIDO</span>' : v}</td></tr>`
      )
      .join("")}</table>`;

  const badge = (n, cls = "green") =>
    `<span class="badge badge-${cls}">${esc(n)}</span>`;

  function render(data) {
    const grid = $("command-grid");
    if (!grid) return;
    const e = data.engine || {};
    const cam = data.campaign || {};
    const miss = data.missions || {};
    const ev = data.evidence || {};
    const rev = data.reviews || {};
    const llm = data.llm_costs || {};
    const bud = data.budget || {};
    const eco = data.economy || {};
    const cyc = data.cycle || {};
    const perms = data.permissions || {};
    const svc = data.services || [];
    const blk = data.blockers || [];
    const timeline = data.timeline || [];

    const conceptStatus = Object.entries(cam.concept_status || {})
      .map(([k, v]) => `${esc(k)}=${esc(v)}`)
      .join(" · ") || "<span class='muted'>SIN DATOS</span>";

    const statusCounts =
      Object.entries(cam.concept_status || {})
        .map(([k, v]) => `<span class="status-pill">${esc(k)}: ${esc(v)}</span>`)
        .join("") || "<span class='muted'>SIN DATOS</span>";

    // Motor / campaña
    const engineBody = kv([
      ["Modo", esc(e.mode_label || e.mode || "DESCONOCIDO"), `c-${statusColor(e.mode === "DEVELOPMENT" ? "white" : "amber")}`],
      ["Estado motor", esc(e.engine_state_label || e.engine_state || "DESCONOCIDO"), `c-${statusColor(e.engine_state === "SAFE_PAUSE" ? "red" : "cyan")}`],
      ["Tarea actual", esc(e.current_task || "DESCONOCIDO")],
      ["Último heartbeat", esc(e.heartbeat_at || "SIN DATOS")],
      ["Próxima acción", esc(e.next_action || "SIN DATOS")],
      ["Uptime", e.uptime_seconds ? `${Math.round(e.uptime_seconds / 60)} min` : "SIN DATOS"],
      ["Producción", perms.production_armed ? "PRODUCTION_ARMED" : perms.autonomous_production ? "ACTIVA" : "BLOQUEADA", "c-red"],
    ]);

    const campaignBody = kv([
      ["Campaña", esc(cam.campaign_title || "SIN CAMPAÑA")],
      ["Estado orquestador", esc((cam.run || {}).state || "SIN DATOS"), `c-cyan`],
      ["Conceptos totales", cam.concepts_total ?? "DESCONOCIDO"],
      ["Recuentos por estado", statusCounts || "SIN DATOS"],
    ]);

    // Misiones
    const missionsBody =
      miss.count === 0
        ? `<p class="muted">${esc(miss.explanation || "SIN DATOS")}</p>`
        : kv([
            ["Pendientes", miss.pending ?? "DESCONOCIDO", "c-cyan"],
            ["Importadas", miss.imported ?? "DESCONOCIDO", "c-green"],
            ["Total", miss.count ?? "DESCONOCIDO"],
          ]) +
          `<details class="cmd-detail"><summary>Ver misiones (${esc(miss.items?.length || 0)})</summary><ul class="cmd-list">${
            (miss.items || []).map((m) => `<li>${natureChip(m.status)} <code>${esc(m.kind)}</code> · ${esc(m.mission_id || "")}</li>`).join("") || "<li class='muted'>SIN DATOS</li>"
          }</ul></details>`;

    // Evidencias
    const evidenceBody = kv([
      ["Evidencias totales", ev.total ?? "SIN DATOS", ev.total ? "c-green" : "c-amber"],
      ["Verificadas (URL+fecha+fragmento)", ev.verified ?? "SIN DATOS", ev.verified ? "c-green" : "c-amber"],
      ["Grupos independientes", ev.independent_groups ?? "SIN DATOS"],
      ["Tope evidence score", ev.max_evidence_score ?? "0", "c-amber"],
      ["Nota", esc(ev.note || "")],
    ]);

    // Revisiones / comité
    const reviewsBody = kv([
      ["En cola", rev.queue ?? "SIN DATOS", "c-cyan"],
      ["Pendientes", rev.pending ?? "SIN DATOS"],
      ["Importadas", rev.imported ?? "SIN DATOS", rev.imported ? "c-green" : "c-amber"],
      ["Nota", esc(rev.note || "")],
    ]);

    // LLM coste honesto
    const llmBody = kv([
      ["Llamadas registradas", llm.calls ?? "SIN DATOS"],
      ["Fallos", llm.failures ?? "SIN DATOS", llm.failures ? "c-red" : "c-green"],
      ["Coste reportado (USD)", llm.reported_cost_usd ?? "DESCONOCIDO", "c-amber"],
      ["Coste estimado (USD)", llm.estimated_cost_usd ?? "DESCONOCIDO", "c-amber"],
      ["cost_source", esc(llm.cost_source || "UNKNOWN"), "c-violet"],
      ["billing_verified", llm.billing_verified === true ? "true" : "false", llm.billing_verified ? "c-green" : "c-red"],
      ["Modelos", esc((llm.models || []).join(", ") || "SIN DATOS")],
    ]);

    // Presupuesto
    const budgetBody = kv([
      ["Gasto hoy (USD)", bud.daily?.spent ?? "SIN DATOS", "c-amber"],
      ["Límite diario (USD)", bud.daily?.limit ?? "SIN DATOS"],
      ["Límite alcanzado", bud.daily?.reached ? "SÍ" : "no", bud.daily?.reached ? "c-red" : "c-green"],
      ["Free mode", bud.free_mode ? "sí" : "no", bud.free_mode ? "c-green" : "c-amber"],
      ["Simulation mode", bud.simulation_mode ? "sí" : "no", "c-amber"],
    ]);

    // Economía
    const ecoMetrics = eco.metrics || {};
    const economyBody = kv([
      ["Saldo disponible (USD)", ecoMetrics.available_balance ?? "DESCONOCIDO", "c-amber"],
      ["Gastos comprometidos", ecoMetrics.committed_expenses ?? "DESCONOCIDO", "c-amber"],
      ["Ingresos confirmados", ecoMetrics.confirmed_income ?? "DESCONOCIDO", "c-green"],
      ["Survival status", esc(ecoMetrics.survival_status || "DESCONOCIDO"), `c-${statusColor(ecoMetrics.survival_status || "DESCONOCIDO")}`],
      ["Aviso", esc(eco.status?.warning || "SIMULACIÓN"), "c-amber"],
    ]);

    // Ciclo
    const cycleBody = kv([
      ["Estado ciclo", esc(cyc.status || cyc.state || "DESCONOCIDO"), `c-${statusColor(cyc.status || cyc.state || "DESCONOCIDO")}`],
      ["Día", cyc.day ?? "SIN DATOS"],
      ["Días restantes", cyc.days_left ?? "SIN DATOS"],
      ["Presupuesto", cyc.budget_usd ?? "DESCONOCIDO", "c-amber"],
      ["Gasto real confirmado", cyc.real_payment_confirmed ? "sí" : "no", cyc.real_payment_confirmed ? "c-green" : "c-amber"],
      ["Prórroga", esc(cyc.extension_state || "SIN DATOS")],
    ]);

    // Bloqueadores
    const blockersBody =
      blk.length === 0
        ? `<p class="muted">SIN BLOQUEADORES</p>`
        : `<ul class="cmd-list">${blk
            .map(
              (b) =>
                `<li><span class="nature nature-${b.severity === "block" ? "red" : "amber"}">${esc(b.severity || "?")}</span> ${esc(b.kind || "")} — ${esc(b.detail || "")}</li>`
            )
            .join("")}</ul>`;

    // Servicios
    const servicesBody = `<ul class="cmd-list">${svc
      .map(
        (s) =>
          `<li><span class="dot dot-${s.connected ? "green" : "amber"}"></span> ${esc(s.name)} — ${esc(s.note || (s.connected ? "CONECTADO" : "NO CONECTADO"))} ${natureChip(s.nature)}</li>`
      )
      .join("") || "<li class='muted'>SIN DATOS</li>"}</ul>`;

    // Autonomous Launch (B10)
    const launch = data.autonomous_launch || {};
    const launchBody = kv([
      ["Estado", esc(launch.state || "NOT_STARTED"), `c-${statusColor(launch.ready_to_launch ? "red" : launch.state === "READY_TO_CONNECT_SERVICES" ? "cyan" : "amber")}`],
      ["READY_TO_CONNECT_SERVICES", launch.ready_to_connect_services ? "sí" : "no", launch.ready_to_connect_services ? "c-cyan" : "c-amber"],
      ["READY_TO_LAUNCH", launch.ready_to_launch ? "SÍ (requiere autorización única)" : "no — bloqueado", "c-red"],
      ["Campaña activa", launch.conditions?.campaña_activa ? "sí" : "no", launch.conditions?.campaña_activa ? "c-green" : "c-amber"],
      ["Candidatas priorizadas", launch.conditions?.candidatas_priorizadas ? "sí" : "no", "c-cyan"],
      ["Evidencia verificada", launch.conditions?.evidencia_verificada ? "sí" : "no", launch.conditions?.evidencia_verificada ? "c-green" : "c-amber"],
      ["Servicios conectados", "no", "c-red"],
      ["Autorización única owner", "no", "c-red"],
      ["Nota", esc(launch.note || "")],
    ]);

    // Permisos
    const permsBody = kv([
      ["AUTONOMOUS_PRODUCTION", perms.autonomous_production ? "SÍ" : "NO", perms.autonomous_production ? "c-red" : "c-green"],
      ["production_capability_available", perms.production_capability_available ? "true" : "false", "c-red"],
      ["production_armed", perms.production_armed ? "true" : "false", "c-amber"],
      ["Motivo de bloqueo", esc(perms.production_block_reason || "—")],
      ["api_budget_usd", perms.api_budget_usd ?? "0", "c-green"],
      ["Gasto real autorizado", esc(perms.gasto_real_autorizado || "0 EUR — solo simulación"), "c-green"],
      ["SAFE PAUSE", perms.safe_pause ? "ACTIVO" : "inactivo", perms.safe_pause ? "c-red" : "c-green"],
    ]);

    // Timeline
    const timelineBody = `<div class="cmd-timeline">${
      timeline.length === 0
        ? "<p class='muted'>SIN DATOS</p>"
        : timeline
            .map(
              (t) =>
                `<div class="tl-row"><span class="tl-time">${esc((t.timestamp || "").slice(11, 19) || "?")}</span><span class="nature nature-${statusColor(t.nature)}">${esc(t.kind || t.nature || "?")}</span><span class="tl-summary">${esc(t.summary || "")}</span></div>`
            )
            .join("")
    }</div>`;

    // Funnel operativo: trabajando/confirmado/bloqueado
    const funnel = (miss.pending ?? 0) + (rev.pending ?? 0) > 0
      ? `<span class="nature nature-cyan">TRABAJANDO</span>`
      : (blk.some((b) => b.severity === "block") ? `<span class="nature nature-red">BLOQUEADO</span>` : `<span class="nature nature-green">EN ESPERA</span>`);

    grid.innerHTML =
      `<div class="cmd-banner">${funnel} CICLO 0/30 · ${esc(cyc.status || cyc.state || "PRE_CYCLE")} · ${esc(data.real_money_moved ? "dinero real" : "SIMULACIÓN — sin dinero real")} · ${esc(data.generated_at || "")}</div>` +
      card("Motor", engineBody, "REAL") +
      card("Campaña", campaignBody, "REAL") +
      card("Misiones Fase 1", missionsBody, miss.nature || "SIN DATOS") +
      card("Evidencias", evidenceBody, ev.nature || "SIN DATOS") +
      card("Comité de contraste", reviewsBody, rev.nature || "SIN DATOS") +
      card("Coste LLM honesto", llmBody, llm.nature || "SIN DATOS") +
      card("Presupuesto (BudgetGuard)", budgetBody, "REAL") +
      card("Economía simulada", economyBody, "SIMULADO") +
      card("Ciclo económico 30d/50USD", cycleBody, "REAL") +
      card("Bloqueadores", blockersBody, blk.some((b) => b.severity === "block") ? "BLOQUEO" : "CONFIRMADO") +
      card("Servicios externos", servicesBody, "REAL") +
      card("Autonomous Launch", launchBody, "REAL") +
      card("Permisos y seguridad", permsBody, "REAL") +
      card("Timeline en vivo", timelineBody, "REAL") +
      `<details class="cmd-detail"><summary>Expediente crudo (JSON)</summary><pre class="code cmd-raw">${esc(JSON.stringify(data, null, 2))}</pre></details>`;

    const badgeEl = $("cmd-badge");
    if (badgeEl) badgeEl.textContent = (miss.pending ?? 0) + (rev.pending ?? 0);
  }

  async function load() {
    try {
      const res = await fetch("/api/command-center");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      render(data);
    } catch (err) {
      const grid = $("command-grid");
      if (grid) grid.innerHTML = `<div class="cmd-banner"><span class="nature nature-red">ERROR</span> No se pudo cargar el centro de mando: ${esc(err.message)}</div>`;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const grid = $("command-grid");
    if (!grid) return;
    load();
    $("btn-cmd-refresh")?.addEventListener("click", load);
    $("btn-cmd-fullscreen")?.addEventListener("click", () => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
      else document.exitFullscreen?.();
    });
    setInterval(load, 30000);
  });
})();
