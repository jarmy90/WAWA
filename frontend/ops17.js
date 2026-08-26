/* Autonomous Business Lab — Iteración 017.
   Operación automática sobre la campaña REAL local:
   1) Aplicar un plan de reformulación portátil (reformulaciones_briefs.json):
      los concept_id del JSON son de una reproducción aislada y NUNCA se
      insertan; el backend localiza los conceptos LOCALES por título
      normalizado / territorio+lente+arquetipo y rechaza ambigüedades.
   2) Importar un paquete de investigación portable asociándolo a misiones
      LOCALES por mapeo estable; la evidencia solo se verifica con URL+fecha+
      fragmento (el backend lo garantiza).
   Cargado DESPUÉS de app.js: reutiliza $, api, esc y loadOrchestrator globales. */
"use strict";

(function () {
  const $sel = (s) => document.querySelector(s);

  async function readJsonFile(inputId) {
    const input = $sel(inputId);
    const file = input && input.files && input.files[0];
    if (!file) throw new Error("Selecciona primero un archivo .json");
    try {
      return JSON.parse(await file.text());
    } catch (_) {
      throw new Error(`El archivo ${file.name} no es JSON válido.`);
    }
  }

  function showPlanResult(ok, payload) {
    const box = $sel("#plan-result");
    if (!box) return;
    box.classList.remove("hidden");
    box.textContent = (ok ? "OK\n" : "ERROR\n") + JSON.stringify(payload, null, 2);
  }

  async function runPlanOperation(endpoint, body, btnId, reloadAfter) {
    const btn = $sel(btnId);
    if (btn) btn.disabled = true;
    try {
      const result = await api(endpoint, { method: "POST", body: JSON.stringify(body) });
      showPlanResult(true, result);
      if (reloadAfter && typeof loadOrchestrator === "function") await loadOrchestrator();
    } catch (e) {
      showPlanResult(false, { message: e.message });
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function on(id, fn) {
    const el = $sel(id);
    if (el) el.addEventListener("click", fn);
  }

  on("#btn-apply-plan-preview", async () => {
    try {
      const plan = await readJsonFile("#file-reformulation-plan");
      await runPlanOperation("/api/orchestrator/reformulation-plan", { plan, preview: true }, "#btn-apply-plan-preview", false);
    } catch (e) { alert(e.message); }
  });

  on("#btn-apply-plan", async () => {
    if (!confirm("¿Aplicar el plan de reformulación a la campaña REAL local? Los IDs del JSON nunca se insertan: el sistema localiza tus conceptos locales y rechaza coincidencias ambiguas.")) return;
    try {
      const plan = await readJsonFile("#file-reformulation-plan");
      await runPlanOperation("/api/orchestrator/reformulation-plan", { plan, preview: false }, "#btn-apply-plan", true);
    } catch (e) { alert(e.message); }
  });

  on("#btn-import-package-preview", async () => {
    try {
      const pkg = await readJsonFile("#file-research-package");
      await runPlanOperation("/api/orchestrator/research-package", { package: pkg, apply: false }, "#btn-import-package-preview", false);
    } catch (e) { alert(e.message); }
  });

  on("#btn-import-package", async () => {
    if (!confirm("¿Importar el paquete de investigación y asociarlo a las misiones LOCALES por mapeo estable? Las asociaciones ambiguas se rechazan; la evidencia solo se verifica con URL + fecha + fragmento.")) return;
    try {
      const pkg = await readJsonFile("#file-research-package");
      await runPlanOperation("/api/orchestrator/research-package", { package: pkg, apply: true }, "#btn-import-package", true);
    } catch (e) { alert(e.message); }
  });
})();
