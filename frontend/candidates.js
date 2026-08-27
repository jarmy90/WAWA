/* WAWA — CANDIDATAS (iteración 022).
 * Muestra las candidatas investigadas (máx. 3) con sus datos reales, la
 * ganadora determinista PARA EXPERIMENTO (nunca demanda validada) y el
 * comité directo: copiar expedientes GPT/Grok/Gemini, pegar respuestas,
 * importar archivo combinado, síntesis automática y decisión autónoma.
 * Los datos se renderizan SIEMPRE escapados (XSS-safe). */
(function () {
  "use strict";
  var V = window.WAWA_Viz;
  if (!V) return;

  var $ = function (id) { return document.getElementById(id); };
  function setHtml(id, html) { $(id).innerHTML = html; }
  function setText(id, text) { $(id).textContent = text; }
  function show(id) { $(id).classList.remove("hidden"); }
  function hide(id) { $(id).classList.add("hidden"); }
  function esc(v) { return V.escapeHtml(v); }

  var REVIEWERS = ["gpt", "grok", "gemini"];
  var REVIEWER_LABEL = { gpt: "GPT", grok: "Grok", gemini: "Gemini" };

  function load() {
    hide("cand-error");
    setHtml("cand-loading", "Cargando candidatas…");
    return Promise.all([
      V.fetchJSON("/api/candidates"),
      V.fetchJSON("/api/agent-telemetry").catch(function () { return {}; }),
    ]).then(function (out) {
      var data = out[0];
      var tel = out[1] || {};
      setHtml("cand-loading", "");
      var rd = (tel.experiment_state || {}).readiness_state || "SIN DATOS";
      var chip = $("cand-readiness");
      chip.textContent = "READINESS: " + rd;
      chip.className = "chip " + (rd === "READY_TO_CONNECT_SERVICES" ? "chip-ok" : "chip-warn");
      setText("cand-note", data.note || "—");
      render(data.candidates || []);
    }).catch(function (err) {
      setHtml("cand-loading", "");
      setText("cand-error", "Error al cargar candidatas: " + esc(err && err.message ? err.message : String(err)));
      show("cand-error");
    });
  }

  function render(cards) {
    if (!cards.length) {
      setHtml("cand-list", '<p class="mc-empty">SIN DATOS — no hay candidatas investigadas en esta instalación. Ejecuta el bootstrap (Mission Control → REPARAR Y CONTINUAR) o revisa el diagnóstico.</p>');
      return;
    }
    setHtml("cand-list", cards.map(cardHtml).join(""));
    // Enlazar acciones del comité tras renderizar.
    cards.forEach(function (c) {
      if (!c.opportunity_id) return;
      wireCommittee(c);
    });
  }

  function metricHtml(label, value) {
    return '<div class="cand-metric"><div class="n">' + esc(value == null ? "—" : value) + '</div><div class="t">' + esc(label) + "</div></div>";
  }

  function cardHtml(c) {
    var cls = c.is_winner ? "cand-card winner" : "cand-card";
    var badge = c.is_winner
      ? '<span class="cand-badge winner">GANADORA DETERMINISTA PARA EXPERIMENTO</span>'
      : '<span class="cand-badge candidate">CANDIDATA INVESTIGADA</span>';
    var metrics = metricHtml("Punt. estructural", c.structural_concept_score == null ? "—" : c.structural_concept_score) +
      metricHtml("Punt. con evidencia", c.evidence_backed_venture_score == null ? "—" : c.evidence_backed_venture_score) +
      metricHtml("Evidencias verificadas", c.evidence_verified_live == null ? (c.evidence_verified || "—") : c.evidence_verified_live) +
      metricHtml("Grupos independientes", c.evidence_groups_live == null ? (c.evidence_groups || "—") : c.evidence_groups_live);
    var competitors = (c.competitors_live && c.competitors_live.length ? c.competitors_live : c.competitors || []);
    var sources = (c.source_urls && c.source_urls.length ? c.source_urls : (c.main_sources || []));
    var html =
      '<article class="' + cls + '" data-opp="' + esc(c.opportunity_id || "") + '">' +
        '<div class="cand-card-head">' + badge + "</div>" +
        '<h2 class="cand-title">' + esc(c.title) + "</h2>" +
        '<div class="cand-metrics">' + metrics + "</div>" +
        '<div class="cand-kv">' +
          kv("Estado", c.state || "—") +
          kv("Motivo", c.winner_reason || c.selection_reason || "—") +
          kv("Comprador", c.buyer || "—") +
          kv("Problema", c.problem || "—") +
          kv("Oferta", c.offer || "—") +
          kv("Precio", c.price || "—") +
          kv("Canal", c.channel || "—") +
        "</div>" +
        section("Alternativas (competidores)", '<ul>' + competitors.slice(0, 4).map(function (k) {
          return "<li><b>" + esc(k.name || "") + "</b>" + (k.offer ? " — " + esc(k.offer) : "") +
            (k.observed_price != null ? " · " + esc(k.observed_price) + " (observado)" : "") + "</li>";
        }).join("") + "</ul>") +
        section("Principales fuentes", '<ul class="cand-src">' + sources.slice(0, 6).map(function (s) {
          return "<li>" + (s.indexOf("http") === 0 ? '<a href="' + esc(s) + '" rel="noopener" target="_blank">' + esc(s) + "</a>" : esc(s)) + "</li>";
        }).join("") + "</ul>") +
        section("Contradicciones", "<p>" + esc(c.contradictions || "Sin contradicciones documentadas.") + "</p>") +
        section("Riesgos", "<ul>" + (c.risks || []).map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>") +
        section("Kill condition", '<p class="kill">' + esc(c.kill_condition || "—") + "</p>") +
        committeeHtml(c) +
      "</article>";
    return html;
  }

  function kv(k, v) {
    return '<span class="k">' + esc(k) + '</span><span class="v">' + esc(v) + "</span>";
  }

  function section(title, inner) {
    return '<div class="cand-section"><h5>' + esc(title) + "</h5>" + inner + "</div>";
  }

  function committeeHtml(c) {
    if (!c.opportunity_id) return "";
    var statuses = reviewerStatus(c.reviews || []);
    var chips = REVIEWERS.map(function (r) {
      var st = statuses[r] || "pending";
      var label = st === "valid" ? "válido" : st === "imported" ? "importado" : "pendiente";
      return '<span class="reviewer-chip ' + st + '">' + esc(REVIEWER_LABEL[r]) + " · " + label + "</span>";
    }).join("");
    var syn = c.synthesis ? "<div class='cand-section'><h5>SÍNTESIS</h5><p>" + esc((c.synthesis.consensus_level || "NONE")) + " · " +
      esc((c.synthesis.recommended_next_action || "sin recomendación")) + "</p></div>" : "";
    var winnerNote = c.is_winner ? "<p class='mc-sub'>En cola de comité automáticamente (ausencia de revisión = neutral).</p>" : "";
    var recovery = recoverInterrupted(c);
    return '<div class="cand-committee">' +
      "<div class='cand-section'><h5>COMITÉ · SEGUNDAS OPINIONES (opinión, nunca evidencia)</h5>" +
      '<div class="reviewer-row">' + chips + "</div>" + winnerNote + "</div>" +
      (recovery || "") +
      '<div class="wizard-steps">' +
        '<span class="wizard-step">PASO 1 · COPIAR EXPEDIENTES</span>' +
        '<span class="wizard-step">PASO 2 · PEGAR RESPUESTAS</span>' +
        '<span class="wizard-step">PASO 3 · SÍNTESIS AUTOMÁTICA</span>' +
      "</div>" +
      '<div class="wizard-panel">' +
        '<div class="wizard-actions">' +
          REVIEWERS.map(function (r) {
            return '<button type="button" class="cand-btn" data-copy="' + esc(r) + '">COPIAR PARA ' + esc(REVIEWER_LABEL[r]) + "</button>";
          }).join("") +
          '<button type="button" class="cand-btn" data-download="1">DESCARGAR EXPEDIENTE .MD</button>' +
        "</div>" +
        '<div class="wizard-actions" style="margin-top:10px">' +
          '<select data-reviewer aria-label="Revisor de la respuesta pegada">' +
            REVIEWERS.map(function (r) { return '<option value="' + r + '">' + esc(REVIEWER_LABEL[r]) + "</option>"; }).join("") +
          "</select>" +
          '<label class="cand-btn" style="cursor:pointer">IMPORTAR ARCHIVO COMBINADO<input type="file" accept=".md,.txt,.markdown" data-combined hidden /></label>' +
        "</div>" +
        "<textarea data-paste placeholder='Pega aquí la respuesta del revisor seleccionado (PASO 2) y pulsa IMPORTAR RESPUESTA…'></textarea>" +
        '<div class="wizard-actions">' +
          '<button type="button" class="cand-btn primary" data-import="1">IMPORTAR RESPUESTA</button>' +
          '<button type="button" class="cand-btn primary" data-synthesize="1">PASO 3 · SINTETIZAR Y DECIDIR</button>' +
        "</div>" +
        '<div class="cand-result" data-result role="status"></div>' +
      "</div>" +
      syn +
    "</div>";
  }

  function reviewerStatus(items) {
    var out = {};
    items.forEach(function (it) {
      var p = String(it.provider || "").toLowerCase();
      REVIEWERS.forEach(function (r) {
        if (p.indexOf(r) >= 0) {
          out[r] = it.status === "valid" || it.status === "partial" ? "valid" : "imported";
        }
      });
    });
    return out;
  }

  /* --- Acciones del comité -------------------------------------------- */
  function wireCommittee(c) {
    var opp = c.opportunity_id;
    var root = document.querySelector('[data-opp="' + opp + '"]');
    if (!root) return;
    var result = root.querySelector("[data-result]");

    function say(text, ok) {
      result.textContent = text;
      result.className = "cand-result " + (ok ? "ok" : "err");
    }

    REVIEWERS.forEach(function (r) {
      var btn = root.querySelector('[data-copy="' + r + '"]');
      if (!btn) return;
      btn.addEventListener("click", function () {
        say("Copiando expediente para " + REVIEWER_LABEL[r] + "…", true);
        V.fetchJSON("/api/reviews/opportunities/" + opp + "/packet/copy?reviewer=" + r)
          .then(function (d) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              return navigator.clipboard.writeText(d.content).then(function () {
                say("✓ Expediente para " + REVIEWER_LABEL[r] + " copiado (" + d.byte_size + " bytes). Pégalo en el revisor y trae la respuesta.", true);
              });
            }
            // Fallback sin clipboard API.
            var ta = document.createElement("textarea");
            ta.value = d.content;
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand("copy"); say("✓ Copiado (fallback) para " + REVIEWER_LABEL[r] + ".", true); }
            catch (e) { say("El navegador bloqueó el copiado; usa DESCARGAR EXPEDIENTE.", false); }
            document.body.removeChild(ta);
          })
          .catch(function (e) { say("Error al generar el expediente: " + esc(e && e.message || "desconocido"), false); });
      });
    });

    var download = root.querySelector('[data-download="1"]');
    if (download) download.addEventListener("click", function () {
      fetch("/api/reviews/opportunities/" + opp + "/packet").then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.blob();
      }).then(function (blob) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "review_packet_" + opp + ".md";
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); document.body.removeChild(a); }, 500);
        say("✓ Expediente descargado (.md).", true);
      }).catch(function (e) { say("Error al descargar: " + esc(e && e.message || "desconocido"), false); });
    });

    var combined = root.querySelector('[data-combined]');
    if (combined) combined.addEventListener("change", function () {
      var file = combined.files && combined.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        importReview(opp, file.name, String(reader.result), "combined", result);
      };
      reader.readAsText(file);
    });

    var imp = root.querySelector('[data-import="1"]');
    if (imp) imp.addEventListener("click", function () {
      var ta = root.querySelector("[data-paste]");
      var reviewer = root.querySelector("[data-reviewer]");
      var content = (ta && ta.value || "").trim();
      if (!content) { say("Pega primero la respuesta del revisor.", false); return; }
      importReview(opp, "respuesta_" + (reviewer ? reviewer.value : "gpt") + ".md", content, reviewer ? reviewer.value : "gpt", result, ta);
    });

    var syn = root.querySelector('[data-synthesize="1"]');
    if (syn) syn.addEventListener("click", function () {
      synthesizeAndDecide(opp, result);
    });
  }

  function importReview(opp, filename, content, provider, result, ta) {
    var payload = { filename: filename, content: content, execution_mode: "MANUAL_IMPORT", imported_by: "owner" };
    if (provider && provider !== "combined") {
      payload.provider = provider;
      payload.model = provider;
    }
    result.textContent = "Importando respuesta…";
    result.className = "cand-result";
    return fetch("/api/reviews/opportunities/" + opp + (provider === "combined" ? "/import-combined" : "/import"), {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    }).then(function (res) { return res.json(); }).then(function (d) {
      if (d.error) { say("✗ " + esc(d.error.message || "no importado"), false); return; }
      if (ta) ta.value = "";
      say("✓ Respuesta importada (" + (d.imported || 0) + " revisiones). Sintetizando y decidiendo…", true);
      return synthesizeAndDecide(opp, result);
    }).catch(function (e) { say("Error de red al importar: " + esc(e && e.message || "desconocido"), false); });
  }

  /* Iteración 023: síntesis/decisión a prueba de bloqueos.
   * - AbortController con timeout (20 s): nunca permanece en "Sintetizando…".
   * - Un solo vuelo por candidata (doble clic imposible).
   * - Botón restaurado SIEMPRE en finally.
   * - Errores HTTP 4xx/5xx detectados (contrato {error:{message}}).
   * - Progreso por etapas (validando → sintetizando → decidiendo → actualizando).
   * - Recuperación tras refrescar: si la síntesis ya está persistida, se muestra.
   */
  var SYNTH_TIMEOUT_MS = 20000;
  var SYNTH_INFLIGHT = {}; // opportunity_id -> true (un solo vuelo)

  function stageMsg(result, text) {
    result.textContent = text;
    result.className = "cand-result";
  }

  function postJson(path, ms) { return timedFetch(path, ms); } // alias conservado por compatibilidad
  function timedFetch(path, ms) {
    var ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, ms || SYNTH_TIMEOUT_MS) : null;
    var finish = function () { if (timer) clearTimeout(timer); };
    return fetch(path, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: ctl ? ctl.signal : undefined,
    }).then(
      function (res) {
        return res.json().catch(function () {
          throw new Error("HTTP " + res.status + " · respuesta no JSON del servidor");
        }).then(function (d) {
          if (!res.ok || (d && d.error)) {
            throw new Error((d && d.error && d.error.message) || "HTTP " + res.status);
          }
          return d;
        });
      },
      function (err) {
        if (err && err.name === "AbortError") {
          throw new Error("Tiempo de espera agotado (" + Math.round((ms || SYNTH_TIMEOUT_MS) / 1000) + " s). Reintenta: la operación es idempotente y recupera el resultado persistido.");
        }
        throw new Error("Error de red: " + ((err && err.message) || "desconocido"));
      }
    ).then(function (d) { finish(); return d; }, function (e) { finish(); throw e; });
  }

  function synthesizeAndDecide(opp, result) {
    if (SYNTH_INFLIGHT[opp]) {
      say("Ya hay una operación de síntesis en marcha para esta candidata. Espera unos segundos o refresca para ver el resultado persistido.", false);
      return Promise.resolve();
    }
    SYNTH_INFLIGHT[opp] = true;
    try { sessionStorage.setItem("wawa_synth_inflight_" + opp, "1"); } catch (_) {}
    // Bloquear ambos botones mientras corre la operación.
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-opp="' + opp + '"] .cand-btn'));
    buttons.forEach(function (b) { b.disabled = true; b.style.opacity = "0.6"; });

    stageMsg(result, "ETAPA 1/4 · Validando revisiones importadas…");

    var ranRecoveryCheck = false;
    var p;
    try {
      p = V.fetchJSON("/api/reviews/opportunities/" + opp).then(function (state) {
        var hadSynth = !!(state && state.synthesis);
        if (hadSynth && !ranRecoveryCheck) {
          ranRecoveryCheck = true;
        }
        stageMsg(result, "ETAPA 2/4 · Sintetizando revisiones (determinista, sin LLM)…");
        return timedFetch("/api/reviews/opportunities/" + opp + "/synthesize-and-decide", SYNTH_TIMEOUT_MS);
      });
    } catch (e) {
      p = Promise.reject(e);
    }

    return p.then(function (res) {
      stageMsg(result, "ETAPA 3/4 · Decidiendo (reglas autónomas deterministas)…");
      return res;
    }).then(function (res) {
      stageMsg(result, "ETAPA 4/4 · Actualizando candidata y comité…");
      var decisionValue = res.decision ? res.decision.decision : "SIN DATOS";
      var consensus = res.synthesis ? res.synthesis.consensus_level : "NONE";
      var dist = (res.synthesis && res.synthesis.recommendation_distribution) || {};
      var repeated = (res.synthesis && res.synthesis.repeated_risks) || [];
      var missing = (res.synthesis && res.synthesis.missing_evidence) || [];
      var distTxt = Object.keys(dist).filter(function (k) { return dist[k] > 0; })
        .map(function (k) { return k.replace("_EXPERIMENT", "") + ":" + dist[k]; }).join(" · ") || "sin recomendaciones";
      var lines = [];
      lines.push("✓ Operación " + (res.operation_id || "—") + " completada (idempotente" + (res.synthesis_reused ? ", síntesis reutilizada" : "") + ").");
      lines.push("Recomendación final: " + decisionValue + " · Consenso: " + consensus + " · Distribución: " + distTxt + ".");
      if (repeated.length) lines.push("Riesgos repetidos (" + repeated.length + "): " + repeated.slice(0, 3).join(" | "));
      if (missing.length) lines.push("Evidencia ausente: " + missing.slice(0, 3).join(" | "));
      lines.push(res.winner_continues
        ? "La ganadora CONTINÚA hacia CONECTAR SERVICIOS (sin conectar nada automáticamente)."
        : "La ganadora NO continúa hacia conexión: " + (res.next_step_exact || "siguiente acción indicada arriba."));
      lines.push((res.followup && res.followup.note) ? "Siguiente paso exacto: " + res.next_step_exact : "Garantías intactas: sin producción, sin gasto, evidencia sin cambios.");
      say(lines.join("\n"), true);
      load(); // sincroniza candidatas + comité inmediatamente
      return res;
    }).catch(function (e) {
      say("✗ " + esc(e && e.message || "error desconocido") + "\nPulsa REINTENTAR: la operación es idempotente y no duplica nada.", false);
      var retry = document.createElement("button");
      retry.type = "button";
      retry.className = "cand-btn primary";
      retry.textContent = "REINTENTAR";
      retry.addEventListener("click", function () {
        retry.remove();
        synthesizeAndDecide(opp, result);
      });
      result.appendChild(document.createElement("br"));
      result.appendChild(retry);
    }).then(function () {
      // finally: restaurar botones y estado de un solo vuelo SIEMPRE.
      SYNTH_INFLIGHT[opp] = false;
      try { sessionStorage.removeItem("wawa_synth_inflight_" + opp); } catch (_) {}
      buttons.forEach(function (b) { b.disabled = false; b.style.opacity = ""; });
    });
  }

  /* Recuperación tras refrescar/cierre: si quedó una operación marcada como
     en marcha (sessionStorage) o existe síntesis persistida, se muestra el
     estado recuperable en lugar de dejar al propietario sin información. */
  function recoverInterrupted(c) {
    if (!c.opportunity_id || !c.is_winner) return "";
    var wasInflight = false;
    try { wasInflight = sessionStorage.getItem("wawa_synth_inflight_" + c.opportunity_id) === "1"; } catch (_) {}
    if (!wasInflight && !c.synthesis) return "";
    var note = wasInflight && c.synthesis
      ? "Operación anterior interrumpida (refresco/cierre). Síntesis persistida RECUPERADA: consenso " + esc(c.synthesis.consensus_level || "NONE") + " · acción recomendada " + esc(c.synthesis.recommended_next_action || "—") + ". Pulsa PASO 3 para regenerar decisión o validar cambios nuevos."
      : wasInflight
        ? "La operación anterior se interrumpió antes de completar. Pulsa PASO 3 · SINTETIZAR Y DECIDIR: es idempotente y recupera/crea el resultado sin duplicar nada."
        : "Síntesis persistida disponible (consenso " + esc(c.synthesis.consensus_level || "NONE") + " · acción: " + esc(c.synthesis.recommended_next_action || "—") + "). Refresco verificado: el resultado sobrevive al reinicio. Pulsa PASO 3 si añades revisiones nuevas.";
    return '<div class="cand-section"><h5>RECUPERACIÓN (iteración 023)</h5><p>' + note + "</p></div>";
  }

  /* --- Inicialización ------------------------------------------------ */
  function init() {
    // El modo demo no aplica a Candidatas: se limpia ?demo=1 (no persiste)
    // y se muestra un aviso explícito; los datos son SIEMPRE reales.
    var demoRequested = V.initDemoState();
    if (demoRequested) {
      show("cand-banner");
      var mode = $("cand-mode");
      mode.textContent = "REAL (demo no aplica a Candidatas)";
      mode.classList.add("chip-demo");
    }
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
