"use strict";
(function () {
  function $(id) { return document.getElementById(id); }
  function esc(value) { return String(value == null ? "" : value).replace(/[&<>\"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[c]; }); }
  function api(path) { return fetch(path).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }); }
  function stateLabel(state) {
    return ({ OPERATING_24_7: "OPERANDO 24/7", CONFIGURATION_REQUIRED: "CONFIGURACIÓN PENDIENTE", SAFE_PAUSED: "EN PAUSA SEGURA" })[state] || "SIN ACTIVIDAD REAL";
  }
  function render(data) {
    var runtime = data.runtime || {};
    var router = runtime.llm_router || {};
    var state = data.status || "CONFIGURATION_REQUIRED";
    $("owner-global-status").textContent = stateLabel(state);
    $("owner-global-status").className = "owner-status owner-status-" + state.toLowerCase();
    $("owner-omni").textContent = router.available ? "CONECTADO" : "DESCONECTADO";
    $("owner-scheduler").textContent = runtime.scheduler_running ? "ACTIVO" : "DETENIDO";
    $("owner-worker").textContent = runtime.worker_running ? "ACTIVO" : "DETENIDO";
    $("owner-pause").textContent = runtime.safe_pause && runtime.safe_pause.active ? "ACTIVA" : "INACTIVA";
    var winner = data.winner;
    if (!winner || !winner.opportunity) {
      $("owner-winner").innerHTML = '<div class="owner-empty"><strong>AÚN NO HAY GANADORA</strong><span>La selección real aparecerá cuando exista una oportunidad evaluada.</span></div>';
      $("owner-primary-action").textContent = "VER ACTIVIDAD";
      return;
    }
    var o = winner.opportunity, s = winner.synthesis, reviews = winner.reviews || [];
    var risks = reviews.map(function (r) { return r.primary_risk; }).filter(Boolean).slice(0, 3);
    $("owner-winner").innerHTML = '<div class="winner-label">IDEA GANADORA ACTUAL · DATOS REALES</div>' +
      '<h3>' + esc(o.title) + '</h3>' +
      '<div class="winner-grid"><div><b>Comprador</b><span>' + esc(o.target_customer || "DESCONOCIDO") + '</span></div><div><b>Score</b><span>' + esc(o.final_score == null ? "SIN DATOS" : o.final_score.toFixed(1)) + '</span></div><div><b>Estado</b><span>' + esc(o.status || "DESCONOCIDO") + '</span></div><div><b>Revisiones</b><span>' + esc(reviews.length || "NINGUNA") + '</span></div></div>' +
      '<p><b>Problema:</b> ' + esc(o.problem || "DESCONOCIDO") + '</p>' +
      (s ? '<div class="verdict"><b>VEREDICTO DEL COMITÉ:</b> ' + esc(s.recommended_next_action || "SIN DECISIÓN") + ' · confianza ' + esc(s.average_confidence == null ? "SIN DATOS" : s.average_confidence) + '<br><span>' + esc((s.missing_evidence || []).slice(0, 2).join(" · ") || "Sin evidencia ausente declarada") + '</span></div>' : '<div class="verdict">REVISIONES PENDIENTES DE EVALUACIÓN</div>') +
      (risks.length ? '<div class="winner-risks"><b>Riesgos señalados:</b> ' + risks.map(esc).join(" · ") + '</div>' : "");
    $("owner-primary-action").textContent = data.next_action === "EVALUATE_CRITIQUES" ? "EVALUAR CRÍTICAS" : "IMPORTAR REVISIONES";
    $("owner-primary-action").onclick = function () { location.hash = "committee"; };
  }
  function load() { api("/api/owner/summary").then(render).catch(function () { $("owner-global-status").textContent = "ESTADO NO DISPONIBLE"; }); }
  document.addEventListener("DOMContentLoaded", function () { load(); setInterval(load, 15000); });
})();
