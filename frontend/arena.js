/* WAWA Arena — Multi-Agent Ideation (iteración 024).
 * 7-step workflow: generate WAWA ideas → copy prompt → import external
 * → filter → tournament → review → approve.
 * Includes Solar System agent visualization, live event log, provider status.
 */
(function () {
  "use strict";

  var V = window.WAWA_Viz || {};
  var fetchJSON = V.fetchJSON || function (url) {
    return fetch(url).then(function (r) { return r.json(); });
  };
  var apiPost = function (url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (r) { return r.json(); });
  };
  function esc(v) { return V.escapeHtml ? V.escapeHtml(v) : String(v).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] || c; }); }
  function $(id) { return document.getElementById(id); }
  function show(el) { if (typeof el === "string") el = $(el); if (el) el.classList.remove("hidden"); }
  function hide(el) { if (typeof el === "string") el = $(el); if (el) el.classList.add("hidden"); }

  var PROVIDER_CLASSES = { wawa: "badge-wawa", gpt: "badge-gpt", grok: "badge-grok", gemini: "badge-gemini" };
  var PROVIDER_NAMES = { wawa: "WAWA", gpt: "GPT", grok: "Grok", gemini: "Gemini", other: "Otro" };
  var currentStep = 1;
  var selectedIdeas = new Set();
  var arenaState = null;
  var pollTimer = null;

  // =================================================================
  // Step navigation
  // =================================================================
  function setStep(n) {
    currentStep = n;
    document.querySelectorAll(".step").forEach(function (el) {
      var s = parseInt(el.dataset.step, 10);
      el.classList.toggle("active", s === n);
      el.classList.toggle("done", s < n);
    });
  }

  // =================================================================
  // Load state
  // =================================================================
  function loadState() {
    return fetchJSON("/api/arena/state").then(function (state) {
      arenaState = state;
      $("arena-phase").textContent = state.phase || "IDLE";
      $("arena-phase").className = "chip " + (state.phase === "IDLE" ? "chip-phase" : "chip-active");
      $("stat-total").textContent = state.total_ideas || 0;
      $("stat-wawa").textContent = state.wawa_count || 0;
      $("stat-external").textContent = state.external_count || 0;
      $("stat-duplicates").textContent = state.duplicates_removed || 0;
      $("stat-survivors").textContent = state.tournament_survivors || 0;
      $("stat-approved").textContent = state.approved_for_research || 0;
      renderProviders(state);
      renderIdeas(state);
      updateStepFromPhase(state.phase);
      return state;
    });
  }

  function updateStepFromPhase(phase) {
    var map = { IDLE: 1, GENERATING: 1, AWAITING_EXTERNAL: 2, IMPORTING: 3, NORMALIZING: 4, FILTERING: 4, TOURNAMENT: 5, REVIEW: 6, APPROVED: 7, MISSIONS_CREATED: 7 };
    setStep(map[phase] || 1);
    if (phase !== "IDLE") { show("panel-prompt"); show("panel-import"); }
    if (phase === "REVIEW" || phase === "APPROVED") { show("panel-review"); }
  }

  // =================================================================
  // Generate ideas
  // =================================================================
  $("btn-generate").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = "GENERANDO…";
    apiPost("/api/arena/generate", { count: 5 }).then(function (data) {
      show("panel-prompt");
      show("panel-import");
      $("generate-result").innerHTML = '<div class="idea-card"><span class="provider-badge badge-wawa">WAWA</span> <strong>' + esc(data.count) + ' ideas generadas</strong> <span class="meta">· batch ' + esc(data.batch_id || "").slice(0, 12) + '</span></div>';
      show("generate-result");
      loadState();
      loadPrompt();
    }).catch(function (e) {
      $("generate-result").innerHTML = '<div class="idea-card" style="border-color:var(--red)">Error: ' + esc(e.message) + '</div>';
      show("generate-result");
    }).finally(function () {
      btn.disabled = false;
      btn.textContent = "GENERAR IDEAS WAWA";
    });
  });

  // =================================================================
  // Prompt
  // =================================================================
  function loadPrompt() {
    fetchJSON("/api/arena/prompt?generator=EXTERNAL_MODEL").then(function (data) {
      $("prompt-content").textContent = data.content;
    });
  }

  window.copyPrompt = function (label) {
    var content = $("prompt-content").textContent;
    var batchLine = "Generador: " + label;
    content = content.replace("Generador: EXTERNAL_MODEL", batchLine);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(content).then(function () {
        showStep4();
      });
    } else {
      var ta = document.createElement("textarea");
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); showStep4(); } catch (e) { /* ignore */ }
      document.body.removeChild(ta);
    }
  };

  function showStep4() {
    show("panel-import");
    setStep(3);
  }

  $("btn-continue-step3").addEventListener("click", showStep4);

  // =================================================================
  // Import files
  // =================================================================
  var importArea = $("import-area");
  var fileInput = $("import-files");

  importArea.addEventListener("click", function () { fileInput.click(); });
  importArea.addEventListener("dragover", function (e) { e.preventDefault(); importArea.classList.add("active"); });
  importArea.addEventListener("dragleave", function () { importArea.classList.remove("active"); });
  importArea.addEventListener("drop", function (e) {
    e.preventDefault();
    importArea.classList.remove("active");
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", function () { handleFiles(this.files); });

  function handleFiles(files) {
    if (!files || !files.length) return;
    var results = [];
    var pending = files.length;

    Array.from(files).forEach(function (file) {
      var reader = new FileReader();
      reader.onload = function () {
        var content = String(reader.result);
        var provider = detectProvider(file.name, content);
        apiPost("/api/arena/import", {
          provider: provider,
          filename: file.name,
          content: content,
          max_ideas: 5,
        }).then(function (data) {
          results.push({ file: file.name, ok: true, count: data.imported ? data.imported.length : 0, errors: data.errors || [], excess: data.excess || 0 });
        }).catch(function (e) {
          results.push({ file: file.name, ok: false, error: e.message });
        }).finally(function () {
          pending--;
          if (pending === 0) showImportResults(results);
        });
      };
      reader.readAsText(file);
    });
  }

  function detectProvider(filename, content) {
    var lower = (filename + " " + content.slice(0, 500)).toLowerCase();
    if (/gpt|chatgpt|openai/.test(lower)) return "gpt";
    if (/grok|x\.?ai/.test(lower)) return "grok";
    if (/gemini|google/.test(lower)) return "gemini";
    return "other";
  }

  function showImportResults(results) {
    var html = "";
    results.forEach(function (r) {
      if (r.ok) {
        html += '<div class="idea-card"><span class="provider-badge badge-other">' + esc(r.file) + '</span> ';
        html += '<strong>' + esc(r.count) + ' ideas importadas</strong>';
        if (r.excess > 0) html += ' <span class="meta">· ' + esc(r.excess) + ' excedentes descartados</span>';
        if (r.errors && r.errors.length) {
          html += '<div class="meta" style="color:var(--gold)">';
          r.errors.forEach(function (e) { html += '⚠ ' + esc(e) + '<br>'; });
          html += '</div>';
        }
        html += '</div>';
      } else {
        html += '<div class="idea-card" style="border-color:var(--red)">' + esc(r.file) + ': ' + esc(r.error || "error") + '</div>';
      }
    });
    $("import-results").innerHTML = html;
    show("import-results");
    $("btn-filter").disabled = false;
    loadState();
  }

  // =================================================================
  // Filter + Tournament
  // =================================================================
  $("btn-filter").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = "FILTRANDO…";
    apiPost("/api/arena/filter").then(function () {
      return apiPost("/api/arena/tournament");
    }).then(function () {
      show("panel-review");
      setStep(6);
      loadState();
      loadReview();
    }).catch(function (e) {
      alert("Error: " + e.message);
    }).finally(function () {
      btn.disabled = false;
      btn.textContent = "FILTRAR IDEAS →";
    });
  });

  // =================================================================
  // Review
  // =================================================================
  function loadReview() {
    fetchJSON("/api/arena/review").then(function (data) {
      var ideas = data.ideas || [];
      selectedIdeas.clear();
      var html = "";
      ideas.forEach(function (idea) {
        var cls = PROVIDER_CLASSES[idea.provider] || "badge-other";
        html += '<div class="idea-card" data-id="' + esc(idea.id) + '">';
        html += '<span class="provider-badge ' + cls + '">' + esc(PROVIDER_NAMES[idea.provider] || idea.provider) + '</span> ';
        html += '<input type="checkbox" class="idea-check" data-id="' + esc(idea.id) + '" style="margin-left:8px">';
        html += '<h4>' + esc(idea.title) + '</h4>';
        html += '<div class="meta">' + esc(idea.buyer) + '</div>';
        html += '<div class="score">Score: ' + (idea.structural_score || 0).toFixed(1) + '</div>';
        if (idea.convergence_count > 0) html += '<div class="meta" style="color:var(--gold)">⚡ MULTI_MODEL_CONVERGENCE (' + esc(idea.convergence_count) + ' coincidencias)</div>';
        html += '</div>';
      });
      if (!ideas.length) {
        html = '<p style="color:var(--muted)">No hay supervivientes para revisar. Ejecuta FILTRAR + TORNEO primero.</p>';
      }
      $("review-ideas").innerHTML = html;
      // Bind checkboxes
      document.querySelectorAll(".idea-check").forEach(function (cb) {
        cb.addEventListener("change", function () {
          if (this.checked) { selectedIdeas.add(this.dataset.id); } else { selectedIdeas.delete(this.dataset.id); }
          $("btn-approve").disabled = selectedIdeas.size === 0 || selectedIdeas.size > 3;
        });
      });
    });
  }

  // =================================================================
  // Approve
  // =================================================================
  $("btn-approve").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    var ids = Array.from(selectedIdeas);
    apiPost("/api/arena/approve", { idea_ids: ids }).then(function (data) {
      btn.textContent = "✓ " + (data.count || 0) + " APROBADAS";
      loadState();
    }).catch(function (e) {
      alert("Error: " + e.message);
      btn.disabled = false;
    });
  });

  // =================================================================
  // Render ideas (all)
  // =================================================================
  function renderIdeas(state) {
    // This renders the summary; actual review panel is separate
  }

  // =================================================================
  // Render providers
  // =================================================================
  function renderProviders(state) {
    var providers = state.providers || {};
    var providerStatuses = [
      { name: "GPT", key: "gpt", count: providers.gpt || 0 },
      { name: "Grok", key: "grok", count: providers.grok || 0 },
      { name: "Gemini", key: "gemini", count: providers.gemini || 0 },
      { name: "Otro", key: "other", count: providers.other || 0 },
    ];
    var html = "";
    providerStatuses.forEach(function (p) {
      var cls = p.count > 0 ? "status-connected" : "status-nokey";
      html += '<div class="provider-card"><div class="name">' + esc(p.name) + '</div>';
      html += '<div class="status ' + cls + '">' + (p.count > 0 ? esc(p.count) + ' ideas' : 'SIN DATOS') + '</div></div>';
    });
    $("provider-grid").innerHTML = html;
  }

  // =================================================================
  // Reset
  // =================================================================
  $("btn-reset").addEventListener("click", function () {
    if (!confirm("¿Reiniciar la arena para un nuevo ciclo? Se conservan los eventos.")) return;
    apiPost("/api/arena/reset").then(function () {
      selectedIdeas.clear();
      hide("panel-prompt");
      hide("panel-import");
      hide("panel-review");
      hide("generate-result");
      $("btn-filter").disabled = true;
      setStep(1);
      loadState();
    });
  });

  // =================================================================
  // Solar System visualization (Canvas 2D)
  // =================================================================
  var solarCanvas, solarCtx, solarW, solarH, solarAnim = null;
  var agents = [
    { name: "WAWA Core", color: "#2de0b8", size: 18, orbit: 0, speed: 0, isCore: true },
    { name: "Scout", color: "#5cc8ff", size: 10, orbit: 60, speed: 0.008 },
    { name: "GPT Ideator", color: "#a78bfa", size: 9, orbit: 90, speed: -0.006, external: true },
    { name: "Grok Ideator", color: "#fb923c", size: 9, orbit: 110, speed: 0.007, external: true },
    { name: "Gemini Ideator", color: "#38bdf8", size: 9, orbit: 130, speed: -0.005, external: true },
    { name: "Researcher", color: "#34d399", size: 8, orbit: 155, speed: 0.004 },
    { name: "Skeptic", color: "#f87171", size: 7, orbit: 175, speed: -0.003 },
    { name: "Economist", color: "#fbbf24", size: 7, orbit: 195, speed: 0.0035 },
    { name: "Builder", color: "#60a5fa", size: 7, orbit: 210, speed: -0.004 },
    { name: "Compliance", color: "#c084fc", size: 6, orbit: 225, speed: 0.003 },
    { name: "Judge", color: "#f472b6", size: 8, orbit: 245, speed: -0.0025 },
    { name: "Orchestrator", color: "#2dd4bf", size: 7, orbit: 260, speed: 0.002 },
  ];
  var agentAngles = {};

  function initSolar() {
    solarCanvas = $("solar-canvas");
    if (!solarCanvas) return;
    solarCtx = solarCanvas.getContext("2d");
    resizeSolar();
    agents.forEach(function (a) { agentAngles[a.name] = Math.random() * Math.PI * 2; });
    drawSolar();
    solarAnim = requestAnimationFrame(animateSolar);
  }

  function resizeSolar() {
    var rect = solarCanvas.parentElement.getBoundingClientRect();
    solarW = rect.width - 32;
    solarH = 400;
    solarCanvas.width = solarW;
    solarCanvas.height = solarH;
  }

  function animateSolar() {
    drawSolar();
    solarAnim = requestAnimationFrame(animateSolar);
  }

  function drawSolar() {
    if (!solarCtx) return;
    var cx = solarW / 2, cy = solarH / 2;
    solarCtx.clearRect(0, 0, solarW, solarH);

    // Background stars
    solarCtx.fillStyle = "rgba(200,220,255,.15)";
    for (var i = 0; i < 60; i++) {
      var sx = ((i * 137.5) % solarW);
      var sy = ((i * 97.3) % solarH);
      solarCtx.fillRect(sx, sy, 1, 1);
    }

    // Orbits
    agents.forEach(function (a) {
      if (a.orbit === 0) return;
      solarCtx.beginPath();
      solarCtx.arc(cx, cy, a.orbit, 0, Math.PI * 2);
      solarCtx.strokeStyle = "rgba(80,140,255,.06)";
      solarCtx.lineWidth = 1;
      solarCtx.stroke();
    });

    // Agent nodes
    agents.forEach(function (a) {
      if (a.isCore) {
        // Draw sun glow
        var grad = solarCtx.createRadialGradient(cx, cy, 0, cx, cy, 30);
        grad.addColorStop(0, "rgba(45,224,184,.25)");
        grad.addColorStop(1, "rgba(45,224,184,0)");
        solarCtx.fillStyle = grad;
        solarCtx.beginPath();
        solarCtx.arc(cx, cy, 30, 0, Math.PI * 2);
        solarCtx.fill();
        // Draw core
        solarCtx.beginPath();
        solarCtx.arc(cx, cy, a.size, 0, Math.PI * 2);
        solarCtx.fillStyle = a.color;
        solarCtx.fill();
        solarCtx.fillStyle = "#fff";
        solarCtx.font = "bold 8px Inter,system-ui";
        solarCtx.textAlign = "center";
        solarCtx.textBaseline = "middle";
        solarCtx.fillText("W", cx, cy);
      } else {
        agentAngles[a.name] = (agentAngles[a.name] || 0) + a.speed;
        var ax = cx + Math.cos(agentAngles[a.name]) * a.orbit;
        var ay = cy + Math.sin(agentAngles[a.name]) * a.orbit;

        // Pulse for external
        if (a.external) {
          solarCtx.beginPath();
          solarCtx.arc(ax, ay, a.size + 4, 0, Math.PI * 2);
          solarCtx.fillStyle = a.color.replace(")", ",.08)").replace("rgb", "rgba");
          solarCtx.fill();
        }

        // Node
        solarCtx.beginPath();
        solarCtx.arc(ax, ay, a.size, 0, Math.PI * 2);
        solarCtx.fillStyle = a.color;
        solarCtx.globalAlpha = 0.85;
        solarCtx.fill();
        solarCtx.globalAlpha = 1;

        // Label
        solarCtx.fillStyle = "rgba(200,220,255,.6)";
        solarCtx.font = "9px Inter,system-ui";
        solarCtx.textAlign = "center";
        solarCtx.fillText(a.name, ax, ay + a.size + 10);
      }
    });

    // Asteroid belt (ideas pending)
    var totalIdeas = arenaState ? (arenaState.total_ideas || 0) : 0;
    if (totalIdeas > 0) {
      solarCtx.fillStyle = "rgba(244,201,93,.3)";
      for (var j = 0; j < Math.min(totalIdeas, 20); j++) {
        var angle = (j / Math.min(totalIdeas, 20)) * Math.PI * 2 + Date.now() * 0.0001;
        var r = 280 + (j % 3) * 5;
        var ax2 = cx + Math.cos(angle) * r;
        var ay2 = cy + Math.sin(angle) * r;
        solarCtx.beginPath();
        solarCtx.arc(ax2, ay2, 1.5, 0, Math.PI * 2);
        solarCtx.fill();
      }
    }
  }

  // =================================================================
  // Live Log (polling)
  // =================================================================
  function loadLog() {
    fetchJSON("/api/arena/events?limit=50").then(function (data) {
      var events = (data.events || []).reverse(); // oldest first
      var html = "";
      events.forEach(function (ev) {
        var ts = ev.timestamp ? ev.timestamp.slice(11, 19) : "--:--:--";
        var cls = "log-info";
        if (ev.kind === "warning") cls = "log-warning";
        if (ev.kind === "error") cls = "log-error";
        if (ev.kind === "intervention") cls = "log-intervention";
        html += '<div class="log-line ' + cls + '">';
        html += '<span class="log-ts">' + esc(ts) + '</span>';
        html += '<span class="log-agent">' + esc(ev.agent) + '</span>';
        html += '<span class="log-msg">' + esc(ev.message) + '</span>';
        html += '</div>';
      });
      $("log-terminal").innerHTML = html || '<div class="log-line"><span class="log-ts">--:--:--</span><span class="log-agent">SYSTEM</span><span class="log-msg">Sin eventos aún</span></div>';
      // Auto-scroll
      $("log-terminal").scrollTop = $("log-terminal").scrollHeight;
    });
  }

  // =================================================================
  // Init
  // =================================================================
  function init() {
    loadState().then(function () {
      loadLog();
      initSolar();
      // Poll for updates
      pollTimer = setInterval(function () {
        loadLog();
        loadState();
      }, 5000);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
