/* WAWA — Sistema Solar de agentes (iteración 020)
 * Canvas 2D, requestAnimationFrame + delta time, devicePixelRatio,
 * ResizeObserver, pausa en pestaña oculta, límite de partículas, degradación
 * automática, prefers-reduced-motion, navegación por teclado, tooltips,
 * focus mode, filtros por estado, panel lateral.
 *
 * Semántica visual (nunca simula actividad sin evento real):
 *  - Sol central = CampaignOrchestrator (WAWA Core)
 *  - Planetas    = agentes (tamaño = prioridad, velocidad = actividad,
 *                  brillo = actividad actual, color = estado)
 *  - Lunas       = herramientas del agente
 *  - Anillos     = tareas programadas
 *  - Asteroides  = cola de misiones
 *  - Cometas     = alertas / bloqueadores
 *  - Líneas      = relaciones padre→hijo reales de agent_relationships
 *  - Órbita congelada = WAITING / IDLE
 *  - Planeta rojo intermitente = BLOCKED / ERROR
 *  - Pulso       = evento reciente */
(function () {
  "use strict";
  var V = window.WAWA_Viz;
  if (!V) return;

  var canvas, ctx, dpr = 1;
  var width = 0, height = 0;
  var rafId = null, lastTs = 0, paused = false, running = false;
  var reduced = V.prefersReducedMotion();
  var demo = false; // OFF por defecto; se inicializa en init() (iteración 022)
  var data = null;
  var focusId = null;
  var filterState = "ALL";
  var selectedIndex = -1;
  var hoverIndex = -1;
  var zoom = 1, panX = 0, panY = 0;
  var particles = [];
  var asteroids = [];
  var comets = [];
  var slowDevice = false;
  var time = 0;
  var quality = 1;

  var $ = function (id) { return document.getElementById(id); };
  function setText(id, t) { $(id).textContent = t; }
  function setHtml(id, h) { $(id).innerHTML = h; }
  function show(id) { $(id).classList.remove("hidden"); }
  function hide(id) { $(id).classList.add("hidden"); }

  /* --- Detección de capacidad ---------------------------------------- */
  function detectSlow() {
    try {
      var cores = navigator.hardwareConcurrency || 4;
      slowDevice = cores <= 2;
    } catch (e) { slowDevice = false; }
    if (reduced) slowDevice = true;
  }

  /* --- Datos --------------------------------------------------------- */
  function loadData() {
    if (demo) {
      data = V.demoTelemetry();
      render();
      return Promise.resolve();
    }
    setHtml("sv-error", "");
    hide("sv-error");
    return V.fetchJSON(V.API).then(function (json) {
      data = json;
      render();
    }).catch(function (err) {
      var msg = V.escapeHtml(err && err.message ? err.message : String(err));
      setText("sv-error", "Error al cargar la telemetría: " + msg);
      show("sv-error");
    });
  }

  function agents() { return (data && data.agents) || []; }

  function visibleAgents() {
    var list = agents().filter(function (a) {
      return a.id === "orchestrator" || filterState === "ALL" || V.safeState(a.status) === filterState;
    });
    return list;
  }

  /* --- Render DOM (fallback textual + panel + leyenda) --------------- */
  function render() {
    var list = agents();
    var health = (data && data.system_health) || {};
    var hState = health.system_health || "NO_DATA";
    $("sv-health").textContent = "SALUD: " + hState;
    $("sv-health").className = "chip " + (hState === "OK" ? "chip-ok" : hState === "DEGRADED" || hState === "SAFE_PAUSE" ? "chip-warn" : "chip-bad");
    $("sv-snapshot").textContent = "SNAPSHOT: " + V.fmtTimestamp(data && data.snapshot_at);
    $("sv-mode").textContent = demo ? "DEMO DATA · NOT REAL ACTIVITY" : "REAL · datos persistidos";
    $("sv-mode").classList.toggle("chip-demo", demo);

    // Alternativa textual
    if (!list.length) {
      setHtml("sv-agents-text", '<p class="mc-empty">SIN DATOS — sin agentes con actividad persistida.</p>');
    } else {
      setHtml("sv-agents-text", "<ul class='mc-list'>" + list.map(function (a) {
        var st = V.safeState(a.status);
        return '<li><span class="k" style="color:' + V.stateColor(st) + '">' + V.escapeHtml(st) + "</span>" +
          '<span class="v">' + V.escapeHtml(a.name) + " — " + V.escapeHtml(a.current_action || "") + "</span></li>";
      }).join("") + "</ul>");
    }

    // Leyenda
    var legend = ["ACTIVE", "WORKING", "WAITING", "BLOCKED", "IDLE", "ERROR", "OFFLINE", "NO_DATA"].map(function (st) {
      return '<li><span class="k" style="color:' + V.stateColor(st) + '">' + V.escapeHtml(st) + "</span>" +
        '<span class="v">' + V.escapeHtml(V.stateLabel(st)) + "</span></li>";
    }).join("");
    setHtml("sv-legend", legend);

    setText("sv-footnote", (data && data.note) ? data.note : "—");

    // Selección
    var vis = visibleAgents();
    if (selectedIndex >= vis.length) selectedIndex = -1;
    if (vis.length && selectedIndex < 0) selectedIndex = 0;
    if (vis.length) renderAgentPanel(vis[selectedIndex]);
    else renderAgentPanel(null);
  }

  function renderAgentPanel(agent) {
    if (!agent) {
      setHtml("sv-agent-panel", '<p class="mc-empty">Sin agentes para mostrar con el filtro actual.</p>');
      return;
    }
    var st = V.safeState(agent.status);
    var rows = [
      ["Estado", V.stateLabel(st) + " (" + st + ")"],
      ["Rol", agent.role || "—"],
      ["Acción actual", agent.current_action || "—"],
      ["Último evento", V.fmtTimestamp(agent.last_event_at)],
      ["Prioridad", agent.priority == null ? "—" : String(agent.priority)],
      ["Eventos", agent.event_count == null ? "SIN DATOS" : String(agent.event_count)],
      ["Errores", agent.error_count == null ? "SIN DATOS" : String(agent.error_count)],
      ["Coste", agent.cost == null ? "SIN DATOS" : V.fmtCost(agent.cost)],
      ["Herramientas", (agent.tools || []).join(", ") || "—"],
      ["Padre", agent.parent_agent_id || "—"],
      ["Bloqueado por", agent.blocked_reason || "—"],
    ];
    var html = '<div class="agent-row selected" style="margin-bottom:10px;cursor:default">' +
      '<span class="pulse" style="background:' + V.stateColor(st) + ';box-shadow:0 0 8px ' + V.stateColor(st) + '" aria-hidden="true"></span>' +
      "<span><span class='a-name'>" + V.escapeHtml(agent.name) + "</span>" +
      '<div class="a-action">' + V.escapeHtml(agent.current_action || "") + "</div></span>" +
      '<span class="a-status" style="color:' + V.stateColor(st) + ';border-color:' + V.stateColor(st) + '">' + V.escapeHtml(st) + "</span></div>";
    html += "<ul class='mc-list'>" + rows.map(function (r) {
      return '<li><span class="k">' + V.escapeHtml(r[0]) + '</span><span class="v">' + V.escapeHtml(r[1]) + "</span></li>";
    }).join("") + "</ul>";
    setHtml("sv-agent-panel", html);
  }

  /* --- Geometría del sistema ----------------------------------------- */
  function sunPos() { return { x: width / 2 + panX * 10, y: height / 2 + panY * 10 }; }

  function agentOrbit(agent, index, total) {
    var radius = Math.min(width, height) * (0.16 + 0.10 * index);
    var speed = activitySpeed(agent);
    var angle = (time * speed + (index * 1.7)) % (Math.PI * 2);
    var frozen = V.safeState(agent.status) === "WAITING" || V.safeState(agent.status) === "IDLE" || reduced || paused;
    if (frozen) angle = (index * 1.7) % (Math.PI * 2); // órbita congelada
    var sun = sunPos();
    return {
      x: sun.x + Math.cos(angle) * radius * zoom,
      y: sun.y + Math.sin(angle) * radius * zoom * 0.62,
      radius: radius,
      angle: angle,
      frozen: frozen,
    };
  }

  function activitySpeed(agent) {
    var base = (agent.activity_level == null ? 0 : Number(agent.activity_level));
    var st = V.safeState(agent.status);
    if (st === "ACTIVE") return 0.9 + base * 0.4;
    if (st === "WORKING") return 0.55 + base * 0.3;
    if (st === "BLOCKED" || st === "ERROR") return 0.12; // rojo intermitente, casi parado
    if (st === "WAITING" || st === "IDLE") return 0; // congelado
    return 0.2;
  }

  function agentSize(agent) {
    var p = agent.priority == null ? 5 : Number(agent.priority);
    var base = Math.max(10, 30 - p * 2); // prioridad 1 (orquestador) → grande
    if (agent.id === "orchestrator") base = 42;
    return base * zoom * quality;
  }

  function statePulse(agent) {
    var st = V.safeState(agent.status);
    if (st === "BLOCKED" || st === "ERROR") return (Math.sin(time * 4) + 1) / 2; // intermitente
    if (st === "ACTIVE" || st === "WORKING") return (Math.sin(time * 2.2) + 1) / 2;
    return 0.35;
  }

  /* --- Partículas (estrellas + nebulosa sutil) ------------------------ */
  function initParticles() {
    var maxParticles = slowDevice ? 70 : 150;
    particles = [];
    for (var i = 0; i < maxParticles; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.4 + 0.2,
        tw: Math.random() * Math.PI * 2,
        sp: Math.random() * 0.02 + 0.004,
      });
    }
    // Asteroides = cola de misiones (máx. 14)
    asteroids = [];
    var queue = (data && data.mission_queue) || [];
    var nAst = Math.min(queue.length, 14);
    for (var j = 0; j < nAst; j++) {
      asteroids.push({ x: 0, y: 0, r: 3 + Math.random() * 2, angle: Math.random() * Math.PI * 2, speed: 0.25 + Math.random() * 0.2 });
    }
    // Cometas = bloqueadores / incidentes (máx. 6)
    comets = [];
    var blockers = ((data && data.blockers) || []).filter(function (b) { return b.kind && b.kind !== "NINGUNO"; });
    var nComets = Math.min(blockers.length, 6);
    for (var c = 0; c < nComets; c++) {
      comets.push({ x: Math.random() * width, y: Math.random() * height, vx: (Math.random() - 0.5) * 2.4, vy: (Math.random() - 0.5) * 2.4, life: 0 });
    }
  }

  function drawBackground() {
    ctx.clearRect(0, 0, width, height);
    // Nebulosa sutil
    var g = ctx.createRadialGradient(width * 0.25, height * 0.2, 10, width * 0.25, height * 0.2, Math.max(width, height) * 0.7);
    g.addColorStop(0, "rgba(139, 92, 246, 0.10)");
    g.addColorStop(1, "rgba(6, 10, 18, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, width, height);
    // Estrellas con parpadeo suave
    if (!reduced) {
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.tw += p.sp;
        var a = 0.35 + Math.sin(p.tw) * 0.25;
        ctx.fillStyle = "rgba(219, 231, 244, " + a.toFixed(3) + ")";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  /* --- Órbitas -------------------------------------------------------- */
  function drawOrbits(vis) {
    var sun = sunPos();
    vis.forEach(function (agent, index) {
      var o = agentOrbit(agent, index, vis.length);
      ctx.strokeStyle = "rgba(94, 234, 212, 0.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(sun.x, sun.y, o.radius * zoom, o.radius * zoom * 0.62, 0, 0, Math.PI * 2);
      ctx.stroke();
      // Anillos = tareas programadas
      var ringCount = scheduledFor(agent).length;
      if (ringCount > 0) {
        ctx.strokeStyle = "rgba(167, 139, 250, 0.28)";
        ctx.setLineDash([4, 6]);
        ctx.beginPath();
        ctx.ellipse(sun.x, sun.y, (o.radius + 14) * zoom, (o.radius + 14) * zoom * 0.62, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  }

  function scheduledFor(agent) {
    var tasks = (data && data.scheduled_tasks) || [];
    // Las tareas globales se asocian visualmente al orquestador y a quien
    // corresponda por nombre; es representación, nunca datos nuevos.
    if (agent.id === "orchestrator") return tasks;
    return tasks.filter(function (t) {
      return (t.task || "").toLowerCase().indexOf(agent.name.toLowerCase()) >= 0;
    });
  }

  /* --- Líneas de energía (relaciones reales) -------------------------- */
  function drawRelations(vis) {
    var rels = (data && data.agent_relationships) || [];
    if (!rels.length) return;
    var byId = {};
    vis.forEach(function (a) { byId[a.id] = a; });
    rels.forEach(function (r) {
      var parent = byId[r.parent], child = byId[r.child];
      if (!parent || !child) return;
      var po = agentOrbit(parent, vis.indexOf(parent), vis.length);
      var co = agentOrbit(child, vis.indexOf(child), vis.length);
      var pulse = reduced ? 0.18 : 0.14 + (Math.sin(time * 1.5 + po.angle) + 1) * 0.08;
      ctx.strokeStyle = "rgba(34, 211, 238, " + pulse.toFixed(3) + ")";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(po.x, po.y);
      ctx.lineTo(co.x, co.y);
      ctx.stroke();
    });
  }

  /* --- Asteroides (cola de misiones) --------------------------------- */
  function drawAsteroids() {
    if (reduced) return;
    var sun = sunPos();
    asteroids.forEach(function (a) {
      a.angle += a.speed * 0.008;
      a.x = sun.x + Math.cos(a.angle) * (Math.min(width, height) * 0.42) * zoom;
      a.y = sun.y + Math.sin(a.angle) * (Math.min(width, height) * 0.42) * zoom * 0.62;
      ctx.fillStyle = "rgba(148, 163, 184, 0.7)";
      ctx.beginPath();
      ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  /* --- Cometas (bloqueadores / incidentes) ---------------------------- */
  function drawComets() {
    if (reduced) return;
    comets.forEach(function (c) {
      c.x += c.vx; c.y += c.vy;
      if (c.x < -20 || c.x > width + 20) { c.vx *= -1; }
      if (c.y < -20 || c.y > height + 20) { c.vy *= -1; }
      c.life += 0.05;
      var a = 0.5 + Math.sin(c.life) * 0.3;
      ctx.strokeStyle = "rgba(248, 113, 113, " + a.toFixed(3) + ")";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(c.x, c.y);
      ctx.lineTo(c.x - c.vx * 8, c.y - c.vy * 8);
      ctx.stroke();
      ctx.fillStyle = "rgba(248, 113, 113, 0.9)";
      ctx.beginPath();
      ctx.arc(c.x, c.y, 2.4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  /* --- Sol central ---------------------------------------------------- */
  function drawSun(vis) {
    var orchestrator = null;
    vis.forEach(function (a) { if (a.id === "orchestrator") orchestrator = a; });
    var sun = sunPos();
    var r = orchestrator ? agentSize(orchestrator) : 42;
    var glow = ctx.createRadialGradient(sun.x, sun.y, 2, sun.x, sun.y, r * 3.2);
    glow.addColorStop(0, "rgba(125, 249, 255, 0.55)");
    glow.addColorStop(0.4, "rgba(34, 211, 238, 0.18)");
    glow.addColorStop(1, "rgba(34, 211, 238, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(sun.x, sun.y, r * 3.2, 0, Math.PI * 2);
    ctx.fill();
    var core = ctx.createRadialGradient(sun.x - r * 0.3, sun.y - r * 0.3, 2, sun.x, sun.y, r);
    core.addColorStop(0, "#e0feff");
    core.addColorStop(0.5, "#67e8f9");
    core.addColorStop(1, "#0e7490");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(sun.x, sun.y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#062a36";
    ctx.font = "700 " + Math.max(10, r * 0.34) + "px 'Cascadia Code', Consolas, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("WAWA", sun.x, sun.y);
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  /* --- Planetas + lunas ---------------------------------------------- */
  function drawAgents(vis) {
    vis.forEach(function (agent, index) {
      if (agent.id === "orchestrator") return; // es el sol
      var o = agentOrbit(agent, index, vis.length);
      var st = V.safeState(agent.status);
      var color = V.stateColor(st);
      var size = agentSize(agent);
      var pulse = statePulse(agent);
      var active = st === "ACTIVE" || st === "WORKING";
      // Brillo según actividad
      if (active && !reduced) {
        var glow = ctx.createRadialGradient(o.x, o.y, 1, o.x, o.y, size * 2.6);
        glow.addColorStop(0, color.replace(")", ", " + (0.32 + pulse * 0.2).toFixed(3) + ")").replace("rgb", "rgba"));
        glow.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(o.x, o.y, size * 2.6, 0, Math.PI * 2);
        ctx.fill();
      }
      // Cuerpo
      var grad = ctx.createRadialGradient(o.x - size * 0.3, o.y - size * 0.3, 1, o.x, o.y, size);
      grad.addColorStop(0, "#ffffff");
      grad.addColorStop(0.35, color);
      grad.addColorStop(1, shade(color, -0.55));
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(o.x, o.y, size, 0, Math.PI * 2);
      ctx.fill();
      // Borde de estado
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1.5, (active ? 3 : 1.5) * (0.6 + pulse * 0.8));
      ctx.beginPath();
      ctx.arc(o.x, o.y, size + 2, 0, Math.PI * 2);
      ctx.stroke();
      // Pulso de evento reciente
      if (active && !reduced && (agent.event_count || 0) > 0) {
        ctx.strokeStyle = "rgba(255,255,255,0.5)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(o.x, o.y, size + 5 + pulse * 6, 0, Math.PI * 2);
        ctx.stroke();
      }
      // Lunas = herramientas (hasta 5)
      var tools = (agent.tools || []).slice(0, 5);
      tools.forEach(function (_, ti) {
        var mAngle = time * (1.6 + ti * 0.4) + ti * 2.1;
        var mx = o.x + Math.cos(mAngle) * (size + 8);
        var my = o.y + Math.sin(mAngle) * (size + 8);
        ctx.fillStyle = "rgba(167, 139, 250, 0.85)";
        ctx.beginPath();
        ctx.arc(mx, my, Math.max(2, size * 0.14), 0, Math.PI * 2);
        ctx.fill();
      });
      // Etiqueta
      var isSel = vis[selectedIndex] && vis[selectedIndex].id === agent.id;
      ctx.font = "600 " + Math.max(10, 11 * zoom) + "px 'Segoe UI', system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillStyle = isSel ? "#ffffff" : "rgba(219, 231, 244, 0.8)";
      ctx.fillText(agent.name.length > 16 ? agent.name.slice(0, 15) + "…" : agent.name, o.x, o.y + size + 16);
      // Estado bajo el nombre
      ctx.fillStyle = color;
      ctx.font = "10px 'Cascadia Code', Consolas, monospace";
      ctx.fillText(st, o.x, o.y + size + 30);
      ctx.textAlign = "left";
    });
  }

  function shade(hex, amt) {
    // Convierte #rrggbb y oscurece/clarifica
    var h = hex.replace("#", "");
    if (h.length === 3) h = h.split("").map(function (c) { return c + c; }).join("");
    if (h.length !== 6) return hex;
    var num = parseInt(h, 16);
    var r = Math.min(255, Math.max(0, (num >> 16) + Math.round(amt * 255)));
    var g = Math.min(255, Math.max(0, ((num >> 8) & 0xff) + Math.round(amt * 255)));
    var b = Math.min(255, Math.max(0, (num & 0xff) + Math.round(amt * 255)));
    return "rgb(" + r + "," + g + "," + b + ")";
  }

  /* --- Tooltip -------------------------------------------------------- */
  function drawTooltip(vis) {
    if (hoverIndex < 0 || hoverIndex >= vis.length) return;
    var agent = vis[hoverIndex];
    if (agent.id === "orchestrator") return;
    var o = agentOrbit(agent, hoverIndex, vis.length);
    var st = V.safeState(agent.status);
    var lines = [
      agent.name,
      V.stateLabel(st) + " (" + st + ")",
      agent.current_action || "",
      "eventos: " + (agent.event_count == null ? "SIN DATOS" : agent.event_count),
      "prioridad: " + (agent.priority == null ? "—" : agent.priority),
    ];
    var pad = 10;
    ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
    var w = 0;
    lines.forEach(function (l) { w = Math.max(w, ctx.measureText(l).width); });
    var h = lines.length * 16 + pad;
    var tx = Math.min(o.x + 18, width - w - pad - 8);
    var ty = Math.max(8, o.y - h - 12);
    ctx.fillStyle = "rgba(6, 10, 18, 0.92)";
    ctx.strokeStyle = V.stateColor(st);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(tx, ty, w + pad * 2, h, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#dbe7f4";
    lines.forEach(function (l, i) {
      ctx.fillStyle = i === 0 ? "#ffffff" : "#dbe7f4";
      ctx.fillText(l, tx + pad, ty + pad + 12 + i * 16);
    });
  }

  /* --- Selección por teclado/ratón ----------------------------------- */
  function hitTest(mx, my) {
    var vis = visibleAgents();
    for (var i = 0; i < vis.length; i++) {
      var a = vis[i];
      if (a.id === "orchestrator") {
        var sun = sunPos();
        if (Math.hypot(mx - sun.x, my - sun.y) <= 42 * zoom + 6) return i;
        continue;
      }
      var o = agentOrbit(a, i, vis.length);
      if (Math.hypot(mx - o.x, my - o.y) <= agentSize(a) + 6) return i;
    }
    return -1;
  }

  function toCanvasCoords(ev) {
    var rect = canvas.getBoundingClientRect();
    return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
  }

  /* --- Bucle principal ----------------------------------------------- */
  function frame(ts) {
    if (!running) return;
    if (paused || document.hidden || reduced) {
      // Pintar un frame estático y esperar
      drawFrame();
      lastTs = ts;
      rafId = requestAnimationFrame(frame);
      return;
    }
    var dt = Math.min(50, ts - lastTs || 16);
    lastTs = ts;
    time += dt / 1000;
    drawFrame();
    rafId = requestAnimationFrame(frame);
  }

  function drawFrame() {
    if (!ctx) return;
    var vis = visibleAgents();
    drawBackground();
    drawOrbits(vis);
    drawRelations(vis);
    drawSun(vis);
    drawAsteroids();
    drawComets();
    drawAgents(vis);
    drawTooltip(vis);
  }

  function start() {
    if (running) return;
    running = true;
    lastTs = 0;
    rafId = requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
  }

  /* --- Resize / DPR -------------------------------------------------- */
  function resize() {
    var rect = canvas.parentElement.getBoundingClientRect();
    var w = Math.max(320, Math.floor(rect.width));
    var h = Math.max(280, Math.floor(Math.min(rect.height || 720, w * 0.62)));
    dpr = (typeof window.devicePixelRatio === "number") ? Math.min(2, window.devicePixelRatio || 1) : 1;
    if (slowDevice) dpr = 1;
    width = w; height = h;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    initParticles();
  }

  /* --- Controles ----------------------------------------------------- */
  function togglePause() {
    paused = !paused;
    $("btn-sv-pause").classList.toggle("active", paused);
    $("btn-sv-pause").setAttribute("aria-pressed", paused ? "true" : "false");
    $("btn-sv-pause").textContent = paused ? "▶ REANUDAR" : "⏸ PAUSAR MOVIMIENTO";
  }

  function toggleFocus() {
    focusId = focusId ? null : "orchestrator";
    $("btn-sv-focus").classList.toggle("active", !!focusId);
  }

  function toggleFullscreen() {
    var el = $("sv-view");
    if (document.fullscreenElement) document.exitFullscreen().catch(function () {});
    else if (el.requestFullscreen) el.requestFullscreen().catch(function () {});
  }

  function applyDemoUI() {
    $("sv-mode").textContent = demo ? "DEMO DATA · NOT REAL ACTIVITY" : "REAL · datos persistidos";
    $("sv-mode").classList.toggle("chip-demo", demo);
    if (demo) show("sv-demo-banner"); else hide("sv-demo-banner");
    $("btn-sv-demo").textContent = demo ? "SALIR DE DEMO" : "ACTIVAR DEMO";
    $("btn-sv-demo").setAttribute("aria-pressed", demo ? "true" : "false");
  }

  function toggleDemo() {
    demo = V.setDemoActive(!demo);
    applyDemoUI();
    loadData();
  }

  function applyFilter() {
    filterState = $("sv-filter").value;
    selectedIndex = -1;
    render();
  }

  function cycleSelection(dir) {
    var vis = visibleAgents();
    if (!vis.length) return;
    selectedIndex = (selectedIndex + dir + vis.length) % vis.length;
    renderAgentPanel(vis[selectedIndex]);
  }

  /* --- Inicialización ------------------------------------------------ */
  function init() {
    canvas = $("sv-canvas");
    if (!canvas) return;
    detectSlow();
    resize();
    if (typeof ResizeObserver !== "undefined") {
      var ro = new ResizeObserver(function () { resize(); });
      ro.observe(canvas.parentElement);
    }
    // Pausa cuando la pestaña queda oculta
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else start();
    });

    $("btn-sv-refresh").addEventListener("click", loadData);
    $("btn-sv-pause").addEventListener("click", togglePause);
    $("btn-sv-demo").addEventListener("click", toggleDemo);
    $("btn-sv-focus").addEventListener("click", toggleFocus);
    $("btn-sv-fullscreen").addEventListener("click", toggleFullscreen);
    $("sv-filter").addEventListener("change", applyFilter);

    canvas.addEventListener("mousemove", function (ev) {
      var p = toCanvasCoords(ev);
      hoverIndex = hitTest(p.x, p.y);
    });
    canvas.addEventListener("mouseleave", function () { hoverIndex = -1; });
    canvas.addEventListener("click", function (ev) {
      var p = toCanvasCoords(ev);
      var idx = hitTest(p.x, p.y);
      if (idx >= 0) { selectedIndex = idx; render(); }
    });
    canvas.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowRight") { ev.preventDefault(); cycleSelection(1); }
      else if (ev.key === "ArrowLeft") { ev.preventDefault(); cycleSelection(-1); }
      else if (ev.key === "Escape") { selectedIndex = -1; render(); }
    });
    // Zoom con rueda (limitado)
    canvas.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      zoom = Math.min(1.6, Math.max(0.6, zoom - ev.deltaY * 0.001));
    }, { passive: false });

    demo = V.initDemoState(); // OFF por defecto; ?demo=1 activa y se limpia
    applyDemoUI();
    loadData().then(function () {
      start();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
