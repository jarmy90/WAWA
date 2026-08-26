/* WAWA — Mission Control (iteración 020)
 * Consume /api/agent-telemetry (datos REALES). Modo demo (?demo=1 o botón)
 * usa el conjunto etiquetado de viz-core y se marca "DEMO DATA · NOT REAL
 * ACTIVITY". Todos los valores se escapan (XSS-safe). Nunca muestra cero para
 * una métrica no conectada: SIN DATOS / NO CONECTADO / DESCONOCIDO / SIMULADO. */
(function () {
  "use strict";
  var V = window.WAWA_Viz;
  if (!V) return;

  var state = {
    auto: true,
    demo: false,
    data: null,
    timer: null,
    selectedAgentId: null,
  };

  var $ = function (id) { return document.getElementById(id); };

  function setText(id, text) { $(id).textContent = text; }
  function setHtml(id, html) { $(id).innerHTML = html; }

  function show(id) { $(id).classList.remove("hidden"); }
  function hide(id) { $(id).classList.add("hidden"); }

  function setConn(label, cls) {
    var el = $("mc-conn");
    el.classList.toggle("offline", cls === "offline");
    el.classList.toggle("demo", cls === "demo");
    setText("mc-conn-label", label);
  }

  function applyDemoBanner() {
    if (state.demo) {
      show("mc-demo-banner");
      $("mc-mode").textContent = "DEMO DATA · NOT REAL ACTIVITY";
      $("mc-mode").classList.add("chip-demo");
      $("btn-mc-demo").textContent = "SALIR DE DEMO";
      $("btn-mc-demo").setAttribute("aria-pressed", "true");
    } else {
      hide("mc-demo-banner");
      $("mc-mode").textContent = "REAL · datos persistidos";
      $("mc-mode").classList.remove("chip-demo");
      $("btn-mc-demo").textContent = "ACTIVAR DEMO";
      $("btn-mc-demo").setAttribute("aria-pressed", "false");
    }
    setConn(state.demo ? "MODO DEMO ACTIVO" : "CONECTADO A /api/agent-telemetry", state.demo ? "demo" : "online");
  }

  function loadData() {
    if (state.demo) {
      state.data = V.demoTelemetry();
      render(state.data);
      setConn("MODO DEMO ACTIVO", "demo");
      return Promise.resolve();
    }
    setConn("CARGANDO…", "online");
    return V.fetchJSON(V.API).then(function (json) {
      state.data = json;
      render(json);
      setConn("CONECTADO A /api/agent-telemetry", "online");
    }).catch(function (err) {
      setText("mc-error", "Error al cargar la telemetría: " + V.escapeHtml(err && err.message ? err.message : String(err)));
      show("mc-error");
      setConn("DESCONECTADO — " + V.escapeHtml(err && err.message ? err.message : "error"), "offline");
    });
  }

  function render(d) {
    hide("mc-error");
    var health = d.system_health || {};
    var hState = health.system_health || "NO_DATA";
    var hChip = $("mc-health");
    hChip.textContent = "SALUD: " + hState;
    hChip.className = "chip " + (hState === "OK" ? "chip-ok" : hState === "DEGRADED" || hState === "SAFE_PAUSE" ? "chip-warn" : "chip-bad");
    setText("mc-health-val", hState);
    setText("mc-health-sub", health.safe_pause ? "SAFE_PAUSE activa" : (health.snapshot_at ? "Snapshot " + V.fmtTimestamp(health.snapshot_at) : "—"));

    var prod = d.production_capability || {};
    setText("mc-prod", "PRODUCCIÓN: " + (prod.state || "DESCONOCIDO"));
    var prodChip = $("mc-prod");
    prodChip.className = "chip " + (prod.state === "AVAILABLE" ? "chip-ok" : "chip-warn");
    setText("mc-prod-val", prod.state || "DESCONOCIDO");
    setText("mc-prod-sub", prod.reason ? prod.reason : "—");

    setText("mc-project", d.active_project || "SIN DATOS");
    setText("mc-campaign", d.campaign_id ? d.campaign_id : "SIN DATOS");
    setText("mc-run", d.run && d.run.title ? d.run.title + " · " + d.run.state : "SIN DATOS");
    setText("mc-snapshot", "SNAPSHOT: " + V.fmtTimestamp(d.snapshot_at));

    renderRoster(d.agents || []);
    renderActions(d);
    renderList("mc-scheduled", d.scheduled_tasks || [], "task");
    renderList("mc-queue", d.mission_queue || [], "mission");
    renderBlockers(d.blockers || []);
    renderEvidence(d);
    renderCommittee(d);
    renderCosts(d.costs || {});
    renderBudget(d.budget || {});
    renderTimeline(d.recent_events || []);
    renderCommercial(d.commercial_metrics || {});
    renderExperiment(d.experiment_state || {});
    renderRelations(d.agent_relationships || [], d.agents || []);
    renderWinner(d.launch_winner || null);
    renderServices(d.services_required || []);
    renderServicesWizard(d.services_required || []);
    renderMandate(d.authorization_mandate || null);
    renderRepair(d.bootstrap || null);
    setText("mc-footnote", d.note ? d.note : "—");
  }

  /* --- Iteración 022: REPARAR Y CONTINUAR AUTOMÁTICAMENTE ------------- */
  function renderRepair(bs) {
    if (!bs) { setHtml("mc-repair-state", '<p class="mc-empty">SIN DATOS</p>'); return; }
    if (bs.applied) {
      setHtml("mc-repair-state", '<p class="mc-empty">BOOTSTRAP COMERCIAL YA APLICADO · ' +
        V.escapeHtml(bs.applied_version || "") + "</p>");
      hide("btn-mc-repair");
      setHtml("mc-repair-preview", "");
      setHtml("mc-repair-result", "");
    } else if (bs.can_repair) {
      setHtml("mc-repair-state", '<p class="mc-empty">Instalación incompleta o recuperable detectada.</p>');
      setHtml("mc-repair-preview", "<p class='mc-sub'>WAWA aplicará automáticamente: investigación verificada 021 " +
        "(3 candidatas, 18 misiones, 31 evidencias), ganadora determinista, experimento, cola de comité " +
        "y READY_TO_CONNECT_SERVICES. Sin comandos, sin archivos, sin IDs.</p>");
      show("btn-mc-repair");
      setHtml("mc-repair-result", "");
    } else {
      setHtml("mc-repair-state", '<p class="mc-empty">Sin reparación necesaria.</p>');
      hide("btn-mc-repair");
      setHtml("mc-repair-preview", "");
      setHtml("mc-repair-result", "");
    }
    var diag = (bs.diagnosis || []).map(function (d) {
      return '<div class="diag-item"><span class="k">' + V.escapeHtml(d.component || "?") + "</span>" +
        '<span class="v">' + V.escapeHtml(d.message || "") +
        (d.recovery_action ? ' <em>→ ' + V.escapeHtml(d.recovery_action) + "</em>" : "") + "</span></div>";
    }).join("");
    setHtml("mc-repair-diagnosis", diag || '<p class="mc-empty">Sin diagnóstico pendiente.</p>');
  }

  function runRepair() {
    var btn = $("btn-mc-repair");
    btn.disabled = true;
    btn.textContent = "REPARANDO…";
    setHtml("mc-repair-result", '<span style="color:var(--mc-amber)">Ejecutando bootstrap comercial (idempotente)…</span>');
    return fetch("/api/bootstrap/commercial", { method: "POST", headers: { Accept: "application/json" } })
      .then(function (res) { return res.json().then(function (d) { return { res: res, d: d }; }); })
      .then(function (out) {
        var d = out.d;
        btn.disabled = false;
        btn.textContent = "REPARAR Y CONTINUAR AUTOMÁTICAMENTE";
        if (!out.res.ok) {
          setHtml("mc-repair-result", '<span style="color:var(--mc-red)">' + V.escapeHtml((d.error && d.error.message) || "Error al reparar.") + "</span>");
          return;
        }
        setHtml("mc-repair-result", '<span style="color:var(--mc-green)">✓ Reparado: ' +
          V.escapeHtml(d.readiness_state || "") + " · " + V.escapeHtml(String(d.evidences_attached || 0)) +
          " evidencias · ganadora: " + V.escapeHtml((d.winner_title || "").slice(0, 60)) + "</span>");
        loadData(); // refrescar campaña y Mission Control
      })
      .catch(function (err) {
        btn.disabled = false;
        btn.textContent = "REPARAR Y CONTINUAR AUTOMÁTICAMENTE";
        setHtml("mc-repair-result", '<span style="color:var(--mc-red)">' + V.escapeHtml(err && err.message ? err.message : "Error de red.") + "</span>");
      });
  }

  /* --- Iteración 022: asistente CONECTAR SERVICIOS --------------------- */
  function renderServicesWizard(services) {
    var eligible = (services || []).filter(function (s) { return s.status !== "CONNECTED" && s.env_var && s.env_var !== "—"; });
    if (!eligible.length) { setHtml("mc-services-wizard", ""); setText("mc-services-result", ""); return; }
    var html = '<div class="svc-wizard"><h4>Asistente local</h4>' + eligible.map(function (s) {
      return '<div class="svc-row"><div class="svc-meta"><b>' + V.escapeHtml(s.name) + "</b> · " +
        '<code>' + V.escapeHtml(s.env_var) + '</code><div class="a-action">' + V.escapeHtml(s.purpose || "") +
        (s.format_hint ? " · formato: " + V.escapeHtml(s.format_hint) : "") + "</div></div>" +
        '<div class="svc-inputs"><input type="password" autocomplete="off" data-svc="' + V.escapeHtml(s.env_var) + '" ' +
        'aria-label="Credencial ' + V.escapeHtml(s.env_var) + '" placeholder="Pega la clave (nunca se muestra después)" />' +
        '<button type="button" class="mc-btn" data-svc-check="' + V.escapeHtml(s.env_var) + '">PROBAR CONEXIÓN</button>' +
        '<span class="svc-check-result" data-svc-result="' + V.escapeHtml(s.env_var) + '"></span></div></div>';
    }).join("") +
      '<button type="button" id="btn-svc-save" class="mc-btn primary">GUARDAR LOCALMENTE</button>' +
      "</div>";
    setHtml("mc-services-wizard", html);
    Array.prototype.forEach.call(document.querySelectorAll("[data-svc-check]"), function (btn) {
      btn.addEventListener("click", function () { checkService(btn); });
    });
    var save = $("btn-svc-save");
    if (save) save.addEventListener("click", saveServices);
  }

  function collectServiceValues() {
    var values = {};
    Array.prototype.forEach.call(document.querySelectorAll("[data-svc]"), function (input) {
      var v = input.value.trim();
      if (v) values[input.getAttribute("data-svc")] = v;
    });
    return values;
  }

  function checkService(btn) {
    var key = btn.getAttribute("data-svc-check");
    var input = document.querySelector('[data-svc="' + key + '"]');
    var values = {};
    if (input && input.value.trim()) values[key] = input.value.trim();
    var out = document.querySelector('[data-svc-result="' + key + '"]');
    out.textContent = "comprobando…";
    return fetch("/api/services/check", {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ values: values }),
    }).then(function (res) { return res.json(); }).then(function (d) {
      var r = (d.results || []).filter(function (x) { return x.key === key; })[0];
      if (!r) { out.textContent = "sin resultado"; return; }
      out.textContent = r.state + " — " + r.message;
      out.className = "svc-check-result " + (r.state === "OK" || r.state === "CONNECTED" ? "ok" : "bad");
    }).catch(function () { out.textContent = "error de red"; });
  }

  function saveServices() {
    var values = collectServiceValues();
    if (!Object.keys(values).length) {
      setText("mc-services-result", "Introduce al menos una credencial para guardar.");
      return;
    }
    var btn = $("btn-svc-save");
    btn.disabled = true;
    setText("mc-services-result", "Guardando localmente (fuera de Git)…");
    return fetch("/api/services/save", {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ values: values }),
    }).then(function (res) { return res.json(); }).then(function (d) {
      btn.disabled = false;
      setText("mc-services-result", d.saved ? "✓ " + d.message : "✗ " + (d.message || "no guardado"));
      loadData();
    }).catch(function () {
      btn.disabled = false;
      setText("mc-services-result", "Error de red al guardar.");
    });
  }

  function renderWinner(w) {
    if (!w) { setHtml("mc-winner", '<p class="mc-empty">SIN DATOS — aún no hay ganadora seleccionada</p>'); return; }
    var rows = [
      ["Estado readiness", w.readiness_state || "—"],
      ["Oferta", w.offer || "—"],
      ["Precio hipótesis", w.price_usd != null ? w.price_usd + " EUR" : "DESCONOCIDO"],
      ["Evidencias verificadas", w.evidence_verified != null ? String(w.evidence_verified) : "SIN DATOS"],
      ["Grupos independientes", w.evidence_groups != null ? String(w.evidence_groups) : "SIN DATOS"],
      ["Experiment ID", w.experiment_id || "—"]
    ];
    var html = '<div class="mc-winner-title">' + V.escapeHtml(w.title || "—") + "</div><ul class='dl'>" +
      rows.map(function (r) { return "<li><span>" + V.escapeHtml(r[0]) + "</span><span>" + V.escapeHtml(r[1]) + "</span></li>"; }).join("") +
      "</ul>";
    setHtml("mc-winner", html);
  }

  function renderServices(services) {
    if (!services.length) { setHtml("mc-services", '<li class="mc-empty">SIN DATOS</li>'); return; }
    setHtml("mc-services", services.map(function (s) {
      var st = s.status || "MISSING";
      var cls = st === "CONNECTED" ? "chip-ok" : "chip-bad";
      return '<li><span class="k"><span class="chip ' + cls + '">' + V.escapeHtml(st) + "</span></span>" +
        '<span class="v"><b>' + V.escapeHtml(s.name) + "</b> · " + V.escapeHtml(s.env_var || "—") +
        '<div class="a-action">' + V.escapeHtml(s.purpose || "") + "</div></span></li>";
    }).join(""));
  }

  function renderMandate(m) {
    if (!m) { setHtml("mc-mandate", '<p class="mc-empty">SIN DATOS — mandato pendiente de ganadora</p>'); return; }
    var rows = [
      ["Duración", (m.duration_days || 0) + " días"],
      ["Presupuesto máximo", m.max_budget_usd + " USD (0 = sin gasto real autorizado)"],
      ["Gasto diario máximo", m.max_daily_spend_usd + " USD"],
      ["Rango de precio", (m.price_optimization_range_usd || []).join(" - ") + " EUR"],
      ["Condición de éxito", m.success_condition || "—"],
      ["Condición de pivot", m.pivot_condition || "—"],
      ["Condición de cierre", m.close_condition || "—"],
      ["Estado", m.state || "—"]
    ];
    var html = '<ul class="dl">' + rows.map(function (r) {
      return "<li><span>" + V.escapeHtml(r[0]) + "</span><span>" + V.escapeHtml(r[1]) + "</span></li>";
    }).join("") + "</ul>" +
      "<div class='mc-sub'><b>Canales permitidos:</b> " + V.escapeHtml((m.allowed_channels || []).join(" · ")) + "</div>" +
      "<div class='mc-sub'><b>Acciones automáticas:</b> " + V.escapeHtml((m.automatic_actions || []).join(" · ")) + "</div>" +
      "<div class='mc-sub' style='color:var(--mc-red)'><b>Acciones bloqueadas:</b> " + V.escapeHtml((m.blocked_actions || []).join(" · ")) + "</div>" +
      "<div class='mc-sub'><b>Requieren intervención humana:</b> " + V.escapeHtml((m.human_intervention_cases || []).join(" · ")) + "</div>";
    setHtml("mc-mandate", html);
  }

  function statusChip(agent) {
    var st = V.safeState(agent.status);
    var color = V.stateColor(st);
    return '<span class="a-status" style="color:' + color + ';border-color:' + color + '" title="' + V.escapeHtml(V.stateLabel(st)) + '">' + V.escapeHtml(st) + "</span>";
  }

  function renderRoster(agents) {
    if (!agents.length) { setHtml("mc-roster", '<p class="mc-empty">SIN DATOS</p>'); return; }
    var html = agents.map(function (a) {
      var st = V.safeState(a.status);
      var color = V.stateColor(st);
      var live = st === "ACTIVE" || st === "WORKING";
      var sel = state.selectedAgentId === a.id ? " selected" : "";
      return '<button type="button" class="agent-row' + sel + '" data-agent="' + V.escapeHtml(a.id) + '" aria-label="Inspeccionar ' + V.escapeHtml(a.name) + '">' +
        '<span class="pulse' + (live ? " live" : "") + '" style="background:' + color + ';box-shadow:0 0 8px ' + color + '" aria-hidden="true"></span>' +
        '<span><span class="a-name">' + V.escapeHtml(a.name) + '</span><div class="a-action">' + V.escapeHtml(a.current_action || "—") + "</div></span>" +
        statusChip(a) + "</button>";
    }).join("");
    setHtml("mc-roster", html);
    Array.prototype.forEach.call(document.querySelectorAll(".agent-row"), function (btn) {
      btn.addEventListener("click", function () {
        state.selectedAgentId = btn.getAttribute("data-agent");
        renderRoster(agents);
        var agent = agents.filter(function (a) { return a.id === state.selectedAgentId; })[0];
        if (agent) openDrawer(agent);
      });
    });
  }

  function renderActions(d) {
    var agents = d.agents || [];
    if (!agents.length) { setHtml("mc-actions", '<p class="mc-empty">SIN DATOS</p>'); return; }
    var html = agents.slice(0, 12).map(function (a) {
      var st = V.safeState(a.status);
      return '<li><span class="k" style="color:' + V.stateColor(st) + '">' + V.escapeHtml(a.name) + "</span>" +
        '<span class="v">' + V.escapeHtml(a.current_action || "—") + "</span></li>";
    }).join("");
    setHtml("mc-actions", "<ul class='mc-list'>" + html + "</ul>");
  }

  function renderList(id, items, kind) {
    if (!items || !items.length) { setHtml(id, '<li class="mc-empty">SIN DATOS</li>'); return; }
    var html = items.slice(0, 12).map(function (it) {
      if (kind === "mission") {
        return '<li><span class="k">' + V.escapeHtml(it.status || "?") + "</span>" +
          '<span class="v">' + V.escapeHtml(it.mission_id || "") + (it.opportunity_id ? " · " + V.escapeHtml(it.opportunity_id) : "") + "</span></li>";
      }
      return '<li><span class="k">' + V.escapeHtml(it.state || it.status || "?") + "</span>" +
        '<span class="v">' + V.escapeHtml(it.task || it.summary || "") + "</span></li>";
    }).join("");
    setHtml(id, html);
  }

  function renderBlockers(blockers) {
    if (!blockers || !blockers.length) {
      setHtml("mc-blockers", '<li class="mc-empty">SIN BLOQUEADORES ACTIVOS</li>');
      return;
    }
    setHtml("mc-blockers", blockers.map(function (b) {
      return '<li><span class="k" style="color:var(--mc-red)">' + V.escapeHtml(b.kind || "?") + "</span>" +
        '<span class="v">' + V.escapeHtml(b.detail || "") + "</span></li>";
    }).join(""));
  }

  function renderEvidence(d) {
    var ev = d && d.evidence;
    if (!ev) {
      // La telemetría no incluye el desglose de evidencias; se usa el resumen
      // honesto del snapshot real si está disponible en la respuesta.
      ev = { verified: null, total: null, unverified: null, max_evidence_score: null };
    }
    setText("mc-evidence", ev.verified == null ? "SIN DATOS" : ev.verified + "/" + ev.total + " verificadas");
    setText("mc-evidence-sub", ev.verified == null ? "—" :
      "no verificadas: " + ev.unverified + " · tope de puntuación: " + ev.max_evidence_score);
  }

  function renderCommittee(d) {
    var c = d.reviews;
    if (!c) { setText("mc-committee", "SIN DATOS"); setText("mc-committee-sub", "—"); return; }
    setText("mc-committee", c.review_count == null ? "SIN DATOS" : c.review_count + " revisiones");
    setText("mc-committee-sub", "síntesis: " + (c.synthesis_count == null ? "SIN DATOS" : c.synthesis_count) +
      " · opiniones MODEL_*, nunca evidencia");
  }

  function renderCosts(costs) {
    var items = [];
    if (costs.display_status === "NO_CALLS" || (costs.reported_total == null && costs.estimated_total == null && !(costs.unknown_cost_calls > 0))) {
      items.push('<li><span class="k">Estado</span><span class="v">SIN DATOS / NO_CALLS</span></li>');
    } else {
      items.push('<li><span class="k">Estado</span><span class="v">' + V.escapeHtml(costs.display_status || "DESCONOCIDO") + "</span></li>");
      items.push('<li><span class="k">Reportado</span><span class="v">' + V.fmtCost(costs.reported_total) + "</span></li>");
      items.push('<li><span class="k">Estimado</span><span class="v">' + V.fmtCost(costs.estimated_total) + "</span></li>");
    }
    if (costs.unknown_cost_calls != null && costs.unknown_cost_calls > 0) {
      items.push('<li><span class="k">Desconocidos</span><span class="v" style="color:var(--mc-amber)">' + costs.unknown_cost_calls + " llamadas sin coste conocido (NUNCA se convierten en 0)</span></li>");
    }
    if (costs.zero_cost_calls != null && costs.zero_cost_calls > 0) {
      items.push('<li><span class="k">Cero reales</span><span class="v">' + costs.zero_cost_calls + " llamadas con coste real 0</span></li>");
    }
    items.push('<li><span class="k">Verificación</span><span class="v">' + (costs.billing_verified ? "verificado" : "no reconciliado (billing_verified=false)") + "</span></li>");
    setHtml("mc-costs", items.join(""));
  }

  function renderBudget(b) {
    setText("mc-budget", b.limit_usd == null ? "SIN DATOS" : "$" + b.limit_usd + " / día (simulado)");
    setText("mc-budget-sub", b.daily_reached ? "LÍMITE DIARIO ALCANZADO" : "límite diario no alcanzado");
  }

  function renderTimeline(events) {
    if (!events || !events.length) { setHtml("mc-timeline", '<p class="mc-empty">SIN DATOS</p>'); return; }
    setHtml("mc-timeline", events.slice(0, 14).map(function (e) {
      var kind = V.escapeHtml(e.kind || "event");
      var cls = kind === "critical" || kind === "incident" ? "color:var(--mc-red)" : kind === "DECISION" ? "color:var(--mc-green)" : "color:var(--mc-cyan)";
      return '<div class="feed-item"><span class="t" style="' + cls + '">' + kind + " · " + V.fmtTimestamp(e.timestamp) + "</span>" +
        '<span class="s">' + V.escapeHtml(e.summary || "") + "</span></div>";
    }).join(""));
  }

  function renderCommercial(metrics) {
    var html = ["visits", "leads", "payments"].map(function (k) {
      return '<li><span class="k">' + k + "</span><span class='v'>" + V.escapeHtml(metrics[k] || "NO CONECTADO") + "</span></li>";
    }).join("");
    setHtml("mc-commercial", html);
  }

  function renderExperiment(exp) {
    if (!exp || exp.state == null) { setHtml("mc-experiment", '<p class="mc-empty">SIN DATOS</p>'); return; }
    var rows = [];
    rows.push('<li><span class="k">Estado</span><span class="v">' + V.escapeHtml(exp.state) + "</span></li>");
    rows.push('<li><span class="k">Readiness</span><span class="v">' + V.escapeHtml(exp.readiness_state || "—") + "</span></li>");
    if (exp.candidate_id) rows.push('<li><span class="k">Candidata</span><span class="v">' + V.escapeHtml(exp.candidate_id) + "</span></li>");
    if (exp.experiment_id) rows.push('<li><span class="k">Experimento</span><span class="v">' + V.escapeHtml(exp.experiment_id) + "</span></li>");
    var missing = exp.readiness_missing || [];
    rows.push('<li><span class="k">Falta</span><span class="v">' + (missing.length ? missing.map(V.escapeHtml).join(", ") : "ninguna") + "</span></li>");
    var blockers = exp.readiness_blockers || [];
    rows.push('<li><span class="k">Bloqueos</span><span class="v">' + (blockers.length ? blockers.map(V.escapeHtml).join(", ") : "ninguno") + "</span></li>");
    setHtml("mc-experiment", "<ul class='mc-list'>" + rows.join("") + "</ul>");
  }

  function renderRelations(rels, agents) {
    if (!rels || !rels.length) { setHtml("mc-relations", '<p class="mc-empty">SIN DATOS</p>'); return; }
    var names = {};
    (agents || []).forEach(function (a) { names[a.id] = a.name; });
    setHtml("mc-relations", '<ul class="mc-list">' + rels.slice(0, 14).map(function (r) {
      return '<li><span class="k">' + V.escapeHtml(names[r.parent] || r.parent) + "</span>" +
        '<span class="v">→ ' + V.escapeHtml(names[r.child] || r.child) + "</span></li>";
    }).join("") + "</ul>");
  }

  function openDrawer(agent) {
    var body = [
      ["Estado", V.stateLabel(V.safeState(agent.status)) + " (" + V.safeState(agent.status) + ")"],
      ["Rol", agent.role || "—"],
      ["Acción actual", agent.current_action || "—"],
      ["Último evento", V.fmtTimestamp(agent.last_event_at)],
      ["Actividad", agent.activity_level == null ? "SIN DATOS" : String(agent.activity_level)],
      ["Prioridad", agent.priority == null ? "—" : String(agent.priority)],
      ["Eventos", agent.event_count == null ? "SIN DATOS" : String(agent.event_count)],
      ["Errores", agent.error_count == null ? "SIN DATOS" : String(agent.error_count)],
      ["Coste", agent.cost == null ? "SIN DATOS" : V.fmtCost(agent.cost)],
      ["Herramientas", (agent.tools || []).join(", ") || "—"],
      ["Misiones", (agent.missions || []).join(", ") || "—"],
      ["Padre", agent.parent_agent_id || "—"],
      ["Bloqueado por", agent.blocked_reason || "—"],
      ["Naturaleza", agent.data_nature || "REAL"],
    ];
    setText("drawer-title", agent.name);
    setText("drawer-role", agent.role || "—");
    setHtml("drawer-body", body.map(function (row) {
      return '<li><span class="k">' + V.escapeHtml(row[0]) + '</span><span class="v">' + V.escapeHtml(row[1]) + "</span></li>";
    }).join(""));
    show("mc-drawer");
    $("mc-drawer").hidden = false;
    $("btn-drawer-close").focus();
  }

  function closeDrawer() {
    $("mc-drawer").hidden = true;
    hide("mc-drawer");
  }

  function toggleFullscreen() {
    var el = $("mc-view");
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(function () {});
    } else if (el.requestFullscreen) {
      el.requestFullscreen().catch(function () {});
    }
  }

  function toggleAuto() {
    state.auto = !state.auto;
    $("btn-mc-auto").classList.toggle("active", state.auto);
    $("btn-mc-auto").setAttribute("aria-pressed", state.auto ? "true" : "false");
    $("btn-mc-auto").textContent = state.auto ? "AUTO · 10s" : "AUTO OFF";
    if (state.auto) schedule();
  }

  function schedule() {
    if (state.timer) clearInterval(state.timer);
    if (!state.auto) return;
    state.timer = setInterval(function () {
      if (document.hidden) return; // no polling en pestañas ocultas
      loadData();
    }, 10000);
  }

  function toggleDemo() {
    state.demo = V.setDemoActive(!state.demo);
    applyDemoBanner();
    loadData();
  }

  /* --- Inicialización ------------------------------------------------ */
  function init() {
    state.demo = V.initDemoState(); // OFF por defecto; ?demo=1 activa y se limpia
    $("btn-mc-refresh").addEventListener("click", loadData);
    var repairBtn = $("btn-mc-repair");
    if (repairBtn) repairBtn.addEventListener("click", runRepair);
    $("btn-mc-auto").addEventListener("click", toggleAuto);
    $("btn-mc-demo").addEventListener("click", toggleDemo);
    $("btn-mc-fullscreen").addEventListener("click", toggleFullscreen);
    $("btn-drawer-close").addEventListener("click", closeDrawer);
    $("mc-drawer").addEventListener("click", function (e) { if (e.target === $("mc-drawer")) closeDrawer(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("mc-drawer").hidden) closeDrawer();
    });
    applyDemoBanner();
    loadData().then(schedule);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
