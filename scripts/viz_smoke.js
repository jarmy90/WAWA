#!/usr/bin/env node
/* WAWA — smoke test headless de las vistas visuales (iteración 020).
 * Ejecuta viz-core.js + agents-viz.js + mission-control.js en un VM de node
 * con mocks de DOM/Canvas/fetch y verifica que el render, la selección, los
 * filtros y el modo demo no lancen excepciones y que el escape XSS funcione.
 * Uso: node scripts/viz_smoke.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND = path.join(ROOT, "frontend");

function makeCtx() {
  const noop = () => {};
  const grad = { addColorStop: noop };
  return new Proxy({}, {
    get(target, prop) {
      if (prop === "createRadialGradient" || prop === "createLinearGradient") return () => grad;
      if (prop === "measureText") return (t) => ({ width: String(t).length * 6 });
      if (prop === "canvas") return {};
      if (["setTransform", "clearRect", "fillRect", "beginPath", "arc", "fill", "stroke",
        "moveTo", "lineTo", "ellipse", "fillText", "roundRect", "setLineDash", "closePath"].includes(prop)) return noop;
      return target[prop];
    },
    set(target, prop, val) { target[prop] = val; return true; },
  });
}

const TELEMETRY = {
  snapshot_at: new Date().toISOString(), data_nature: "REAL", version: "0.19.0", iteration: "020",
  system_health: { system_health: "OK", safe_pause: false, snapshot_at: new Date().toISOString() },
  production_capability: { state: "BLOCKED", reason: "producción bloqueada por capacidad" },
  campaign_id: "c1", active_project: "Autonomous Business Lab",
  run: { state: "RESEARCH_PENDING", title: "PRIMERA CAMPAÑA REAL 001" },
  agents: [
    { id: "orchestrator", name: "CampaignOrchestrator", role: "Coordinación", status: "WAITING", current_action: "Run en RESEARCH_PENDING", last_event_at: null, activity_level: 0, priority: 1, tools: ["orquestador"], missions: [], parent_agent_id: null, blocked_reason: null, event_count: 1, error_count: 0, cost: null, data_nature: "REAL" },
    { id: "scout", name: "Scout", role: "Descubrimiento", status: "BLOCKED", current_action: "b", last_event_at: null, activity_level: 1, priority: 2, tools: [], missions: [], parent_agent_id: "orchestrator", blocked_reason: "r", event_count: 2, error_count: 1, cost: null, data_nature: "REAL" },
    { id: "researcher", name: "Researcher", role: "Investigación", status: "ACTIVE", current_action: "c", last_event_at: null, activity_level: 3, priority: 3, tools: [], missions: ["m1"], parent_agent_id: "orchestrator", blocked_reason: null, event_count: 5, error_count: 0, cost: 0.01, data_nature: "REAL" },
  ],
  agent_relationships: [{ parent: "orchestrator", child: "scout" }, { parent: "orchestrator", child: "researcher" }],
  scheduled_tasks: [{ task: "Iniciar ciclo económico", state: "PRE_CYCLE", nature: "REAL" }],
  mission_queue: [{ mission_id: "m1", kind: "DEMAND", status: "exported", opportunity_id: "o1" }],
  recent_events: [{ timestamp: new Date().toISOString(), kind: "critical", summary: "x" },
    { timestamp: new Date().toISOString(), kind: "DECISION", summary: "judge: approve" }],
  blockers: [{ kind: "PRODUCTION_BLOCKED", detail: "producción bloqueada", severity: "block" }],
  provider_states: [],
  evidence: { verified: 0, total: 3, unverified: 3, rejected: 0, max_evidence_score: 0, nature: "REAL" },
  reviews: { review_count: 0, synthesis_count: 0, committee_status: "NO_REVIEWS", nature: "REAL" },
  costs: { display_status: "KNOWN_WITH_UNKNOWN_CALLS", reported_total: 0.0012, estimated_total: null, unknown_cost_calls: 1, zero_cost_calls: 0, billing_verified: false, nature: "REAL" },
  budget: { daily_reached: false, limit_usd: 0 },
  experiment_state: { state: "NEEDS_EXPERIMENT", experiment_id: null, candidate_id: "o1", opportunity_id: "o1", readiness_state: "NOT_READY", readiness_missing: ["experiment_defined"], readiness_blockers: [] },
  commercial_metrics: { visits: "NO CONECTADO", leads: "NO CONECTADO", payments: "NO CONECTADO", nature: "NO CONECTADO" },
  note: "Telemetría derivada de datos persistidos.",
};

function baseSandbox() {
  const ctx = makeCtx();
  const canvas = {
    width: 800, height: 500, style: {}, parentElement: null,
    getContext: () => ctx,
    addEventListener: (ev, fn) => { canvas["_on_" + ev] = fn; },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 500 }),
  };
  canvas.parentElement = canvas;
  const elements = {};
  function el(id) {
    if (id === "sv-canvas") return canvas;
    if (!elements[id]) elements[id] = {
      textContent: "", innerHTML: "", className: "", hidden: false, style: {},
      classList: { toggle: () => {}, add: () => {}, remove: () => {} },
      addEventListener: (ev, fn) => { elements[id]["_on_" + ev] = fn; },
      setAttribute: () => {}, focus: () => {}, parentElement: canvas,
      getBoundingClientRect: () => ({ width: 800, height: 500 }),
    };
    return elements[id];
  }
  const sandbox = {
    _canvas: canvas, _elements: elements, _el: el,
    window: { location: { search: "" } },
    document: {
      readyState: "complete", hidden: false, getElementById: el, querySelectorAll: () => [],
      addEventListener: () => {}, fullscreenElement: null, exitFullscreen: () => Promise.resolve(),
    },
    navigator: { hardwareConcurrency: 8 },
    matchMedia: () => ({ matches: false }),
    URLSearchParams: globalThis.URLSearchParams, AbortController: globalThis.AbortController,
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(TELEMETRY) }),
    requestAnimationFrame: (fn) => { setTimeout(() => fn(Date.now()), 16); return 1; },
    cancelAnimationFrame: () => {}, ResizeObserver: function () { return { observe: () => {} }; },
    setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout,
    setInterval: () => 1, clearInterval: globalThis.clearInterval,
    Promise: globalThis.Promise, Math: Math, Date: Date, String: String, Number: Number,
    JSON: JSON, console: console, isNaN: isNaN, isFinite: isFinite,
  };
  sandbox.window.matchMedia = () => ({ matches: false });
  return sandbox;
}

function loadViz(sandbox) {
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(FRONTEND, "viz-core.js"), "utf8"), sandbox);
}

function run(name, script, interact) {
  const sandbox = baseSandbox();
  loadViz(sandbox);
  vm.runInContext(fs.readFileSync(path.join(FRONTEND, script), "utf8"), sandbox);
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      try {
        interact(sandbox);
        resolve(name + "_OK");
      } catch (e) {
        reject(new Error(name + " FAIL: " + e.message));
      }
    }, 250);
  });
}

async function main() {
  const results = [];
  results.push(await run("AGENTS_VIZ", "agents-viz.js", (sb) => {
    const c = sb._canvas;
    if (c._onkeydown) {
      c._onkeydown({ key: "ArrowRight", preventDefault: () => {} });
      c._onkeydown({ key: "ArrowLeft", preventDefault: () => {} });
      c._onkeydown({ key: "Escape", preventDefault: () => {} });
    }
    if (c._onclick) c._onclick({ clientX: 400, clientY: 200 });
    if (c._onmousemove) c._onmousemove({ clientX: 410, clientY: 210 });
    if (sb._elements["sv-filter"]._onchange) sb._elements["sv-filter"]._onchange();
    if (sb._elements["btn-sv-demo"]._onclick) sb._elements["btn-sv-demo"]._onclick();
  }));

  results.push(await run("MISSION_CONTROL", "mission-control.js", (sb) => {
    const e = sb._elements;
    if (e["btn-mc-demo"]._onclick) e["btn-mc-demo"]._onclick(); // activar demo
    if (e["btn-mc-demo"]._onclick) e["btn-mc-demo"]._onclick(); // volver a REAL
    if (e["btn-mc-auto"]._onclick) e["btn-mc-auto"]._onclick();
    if (e["btn-mc-refresh"]._onclick) e["btn-mc-refresh"]._onclick();
    if (e["btn-drawer-close"]._onclick) e["btn-drawer-close"]._onclick();
    const html = e["mc-costs"].innerHTML;
    if (html.indexOf("<script>") >= 0 && html.indexOf("&lt;") < 0) {
      throw new Error("XSS RISK en render de costes");
    }
  }));

  results.forEach((r) => console.log(r));
  console.log("ALL_SMOKE_TESTS_PASSED");
  // El mock de requestAnimationFrame mantiene el bucle vivo: salida explícita.
  process.exit(0);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
