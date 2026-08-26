/* WAWA Viz Core — utilidades compartidas por Mission Control y Sistema Solar.
 * Sin dependencias externas, sin CDN, operación offline.
 * Convenciones: los datos se renderizan SIEMPRE escapados (XSS-safe); el modo
 * demo (?demo=1 o control explícito) se etiqueta "DEMO DATA · NOT REAL
 * ACTIVITY" y nunca se mezcla con datos reales. */
(function (global) {
  "use strict";

  var API = "/api/agent-telemetry";

  var STATE_COLORS = {
    ACTIVE: "#22d3ee",
    WORKING: "#38bdf8",
    WAITING: "#fbbf24",
    BLOCKED: "#f87171",
    IDLE: "#34d399",
    ERROR: "#fb7185",
    OFFLINE: "#94a3b8",
    NO_DATA: "#64748b",
  };

  var STATE_LABELS = {
    ACTIVE: "Activo",
    WORKING: "Trabajando",
    WAITING: "Esperando",
    BLOCKED: "Bloqueado",
    IDLE: "En reposo",
    ERROR: "Error",
    OFFLINE: "Sin conexión",
    NO_DATA: "Sin datos",
  };

  var ALLOWED_STATES = Object.keys(STATE_COLORS);

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function stateColor(state) {
    return STATE_COLORS[state] || STATE_COLORS.NO_DATA;
  }

  function stateLabel(state) {
    return STATE_LABELS[state] || "Sin datos";
  }

  function prefersReducedMotion() {
    return typeof window.matchMedia !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /* ------------------------------------------------------------------
   * Modo demo (iteración 022): estado SOLO en memoria, OFF por defecto.
   * - `?demo=1` en la URL activa demo al cargar y se limpia de la URL de
   *   inmediato (history.replaceState): refrescar NUNCA reactiva demo.
   * - El botón cambia el estado en memoria; al salir se limpian los
   *   parámetros de la URL y cualquier clave demo de localStorage o
   *   sessionStorage. Reiniciar WAWA tampoco reactiva demo (no hay
   *   persistencia). Los datos demo y reales nunca se mezclan: el
   *   consumidor usa una sola fuente por snapshot.
   * ---------------------------------------------------------------- */
  var demoState = { active: false };

  function clearDemoStorage() {
    try {
      if (typeof localStorage !== "undefined") {
        Object.keys(localStorage).forEach(function (k) {
          if (/demo/i.test(k)) localStorage.removeItem(k);
        });
      }
    } catch (e) { /* sin almacenamiento: ignorar */ }
    try {
      if (typeof sessionStorage !== "undefined") {
        Object.keys(sessionStorage).forEach(function (k) {
          if (/demo/i.test(k)) sessionStorage.removeItem(k);
        });
      }
    } catch (e) { /* sin almacenamiento: ignorar */ }
  }

  function stripDemoParam() {
    try {
      var params = new URLSearchParams(window.location.search);
      if (!params.has("demo")) return;
      params.delete("demo");
      var qs = params.toString();
      var url = window.location.pathname + (qs ? "?" + qs : "") + window.location.hash;
      window.history.replaceState(null, "", url);
    } catch (e) { /* entorno sin history: solo estado en memoria */ }
  }

  /* Inicializa el estado demo al cargar la vista. Devuelve si demo quedó
   * activo (solo si la URL lo pedía explícitamente con ?demo=1). */
  function initDemoState() {
    demoState.active = false;
    try {
      if (new URLSearchParams(window.location.search).get("demo") === "1") {
        demoState.active = true;
        stripDemoParam(); // refrescar no reactiva demo
      }
    } catch (e) {
      demoState.active = false;
    }
    clearDemoStorage();
    return demoState.active;
  }

  function isDemoMode() {
    return demoState.active;
  }

  function setDemoActive(active) {
    demoState.active = !!active;
    if (!demoState.active) {
      stripDemoParam();
      clearDemoStorage();
    }
    return demoState.active;
  }

  /* fetch con timeout y error legible (sin lanzar en red caída). */
  function fetchJSON(url, timeoutMs) {
    timeoutMs = timeoutMs || 8000;
    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, timeoutMs) : null;
    var opts = { headers: { Accept: "application/json" }, cache: "no-store" };
    if (controller) opts.signal = controller.signal;
    return fetch(url, opts).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).finally(function () {
      if (timer) clearTimeout(timer);
    });
  }

  function fmtTimestamp(iso) {
    if (!iso) return "SIN DATOS";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString("es-ES", { dateStyle: "short", timeStyle: "medium" });
  }

  function fmtCost(value) {
    if (value == null || value === "") return "DESCONOCIDO";
    var n = Number(value);
    if (!isFinite(n)) return "DESCONOCIDO";
    return "$" + n.toFixed(6).replace(/\.?0+$/, "") + " (simulado)";
  }

  /* ------------------------------------------------------------------
   * Conjunto demo: reproduce estados útiles, SIEMPRE etiquetado DEMO.
   * Nunca se mezcla con datos reales en el mismo agregado.
   * ---------------------------------------------------------------- */
  function demoTelemetry() {
    var now = new Date().toISOString();
    return {
      snapshot_at: now,
      version: "DEMO", iteration: "DEMO", build: "DEMO",
      data_nature: "DEMO",
      demo_notice: "DEMO DATA · NOT REAL ACTIVITY",
      system_health: { system_health: "OK", safe_pause: false, nature: "DEMO" },
      production_capability: { state: "BLOCKED", reason: "producción bloqueada por capacidad (demo)", nature: "DEMO" },
      campaign_id: "demo-campaign-001",
      active_project: "Autonomous Business Lab (DEMO)",
      run: { state: "RESEARCH_PENDING", id: "demo-run", title: "DEMO — campaña ilustrativa" },
      agents: [
        { id: "orchestrator", name: "CampaignOrchestrator", role: "Coordinación", status: "WORKING",
          current_action: "Run en RESEARCH_PENDING (demo)", last_event_at: now, activity_level: 2, priority: 1,
          tools: ["orquestador"], missions: [], parent_agent_id: null, blocked_reason: null,
          event_count: 24, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "scout", name: "Scout", role: "Descubrimiento", status: "ACTIVE",
          current_action: "Generando hipótesis Fase 1 (demo)", last_event_at: now, activity_level: 3, priority: 2,
          tools: ["territorios", "lentes"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 12, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "researcher", name: "Researcher", role: "Investigación", status: "WAITING",
          current_action: "2 misiones pendientes · 1 importada (demo)", last_event_at: now, activity_level: 0, priority: 3,
          tools: ["misiones"], missions: ["m-demo-1", "m-demo-2"], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 3, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "skeptic", name: "Skeptic", role: "Contraste", status: "IDLE",
          current_action: "4 revisiones · 1 síntesis (demo)", last_event_at: now, activity_level: 1, priority: 4,
          tools: ["revisiones"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 5, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "economist", name: "Economist", role: "Economía simulada", status: "WAITING",
          current_action: "Ciclo PRE_CYCLE — reloj detenido (demo)", last_event_at: null, activity_level: 0, priority: 5,
          tools: ["ledger"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 1, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "builder", name: "Builder", role: "Construcción", status: "BLOCKED",
          current_action: "Oportunidad sin plan de experimento (demo)", last_event_at: now, activity_level: 0, priority: 6,
          tools: ["experimento"], missions: [], parent_agent_id: "orchestrator",
          blocked_reason: "Falta plan de experimento (demo)", event_count: 0, error_count: 1, cost: null, data_nature: "DEMO" },
        { id: "compliance", name: "Compliance", role: "Riesgos", status: "IDLE",
          current_action: "Sin bloqueadores críticos (demo)", last_event_at: now, activity_level: 1, priority: 7,
          tools: ["TOS"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 2, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "judge", name: "Judge", role: "Puntuación determinista", status: "IDLE",
          current_action: "2/5 evidencias verificadas (demo)", last_event_at: now, activity_level: 1, priority: 8,
          tools: ["venture-score"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 8, error_count: 0, cost: null, data_nature: "DEMO" },
        { id: "openrouter", name: "OpenRouter (comité)", role: "revisión", status: "IDLE",
          current_action: "Configurado, sin llamadas (demo)", last_event_at: null, activity_level: 0, priority: 9,
          tools: ["llm_call_log"], missions: [], parent_agent_id: "orchestrator", blocked_reason: null,
          event_count: 0, error_count: 0, cost: 0.0042, data_nature: "DEMO" },
      ],
      agent_relationships: [{ parent: "orchestrator", child: "scout" }, { parent: "orchestrator", child: "researcher" },
        { parent: "orchestrator", child: "skeptic" }, { parent: "orchestrator", child: "economist" },
        { parent: "orchestrator", child: "builder" }, { parent: "orchestrator", child: "compliance" },
        { parent: "orchestrator", child: "judge" }],
      scheduled_tasks: [{ task: "Iniciar ciclo económico (demo)", state: "PRE_CYCLE", nature: "DEMO" },
        { task: "Resolver precondiciones de readiness (demo)", state: "NOT_READY", nature: "DEMO" }],
      mission_queue: [{ mission_id: "m-demo-1", kind: "DEMAND_PROOF", status: "exported", opportunity_id: "o-demo" },
        { mission_id: "m-demo-2", kind: "COMPETITORS", status: "exported", opportunity_id: "o-demo" }],
      recent_events: [{ timestamp: now, kind: "incident", summary: "Incidente demo: llamada fallida simulada", nature: "DEMO" },
        { timestamp: now, kind: "mission_completed", summary: "Misión m-demo-3 completada (demo)", nature: "DEMO" }],
      blockers: [{ kind: "PRODUCTION_BLOCKED", detail: "producción bloqueada por capacidad (demo)", severity: "block" }],
      provider_states: [{ id: "openrouter", status: "IDLE", current_action: "Configurado (demo)" }],
      costs: { reported_total: 0.02, estimated_total: 0.01, unknown_cost_calls: 1, zero_cost_calls: 0,
        display_status: "KNOWN_WITH_UNKNOWN_CALLS", billing_verified: false, nature: "DEMO" },
      budget: { daily_reached: false, limit_usd: 0 },
      experiment_state: { state: "NEEDS_EXPERIMENT", experiment_id: null, candidate_id: "o-demo",
        opportunity_id: "o-demo", readiness_state: "NOT_READY", readiness_missing: ["experiment_defined"], readiness_blockers: [] },
      commercial_metrics: { visits: "NO CONECTADO", leads: "NO CONECTADO", payments: "NO CONECTADO", nature: "NO CONECTADO" },
      note: "Conjunto DEMO: no representa actividad real de WAWA.",
    };
  }

  /* Filtra un dato a un estado permitido (seguridad del contrato). */
  function safeState(value) {
    var v = String(value || "NO_DATA").toUpperCase();
    return ALLOWED_STATES.indexOf(v) >= 0 ? v : "NO_DATA";
  }

  global.WAWA_Viz = {
    API: API,
    STATE_COLORS: STATE_COLORS,
    STATE_LABELS: STATE_LABELS,
    ALLOWED_STATES: ALLOWED_STATES,
    escapeHtml: escapeHtml,
    stateColor: stateColor,
    stateLabel: stateLabel,
    prefersReducedMotion: prefersReducedMotion,
    isDemoMode: isDemoMode,
    initDemoState: initDemoState,
    setDemoActive: setDemoActive,
    clearDemoStorage: clearDemoStorage,
    fetchJSON: fetchJSON,
    fmtTimestamp: fmtTimestamp,
    fmtCost: fmtCost,
    demoTelemetry: demoTelemetry,
    safeState: safeState,
  };
})(window);
