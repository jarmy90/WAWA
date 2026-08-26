#!/usr/bin/env node
/* Smoke del estado demo (iteración 022) — sin navegador.
 * Ejecuta el gestor de demo de viz-core.js en un VM con window/history/
 * localStorage mockeados y verifica:
 *   1. demo OFF por defecto (sin ?demo=1);
 *   2. ?demo=1 activa demo al cargar y se limpia de la URL de inmediato
 *      (refrescar NUNCA reactiva demo);
 *   3. salir de demo limpia URL + localStorage/sessionStorage;
 *   4. reiniciar (nueva carga sin parámetro) NO reactiva demo;
 *   5. los datos demo quedan etiquetados DEMO (nunca mezclados);
 *   6. botones coherentes en ambas vistas (ACTIVAR DEMO / SALIR DE DEMO). */
"use strict";
const fs = require("fs");
const vm = require("vm");

let failures = 0;
function check(name, cond) {
  if (cond) { console.log("  ok - " + name); }
  else { console.error("  FAIL - " + name); failures += 1; }
}

function loadVizCore(initialUrl, storageKeys) {
  const replaceCalls = [];
  // Mock de Storage con entradas como propiedades enumerables propias,
  // para que Object.keys(localStorage) de viz-core las encuentre (como en
  // un navegador real).
  const METHODS = new Set(["getItem", "setItem", "removeItem", "key"]);
  const mkStore = () => {
    const store = {
      getItem(k) { return k in store && !METHODS.has(k) ? store[k] : null; },
      setItem(k, v) { store[k] = String(v); },
      removeItem(k) { delete store[k]; },
      key(i) { return Object.keys(store).filter((k) => !METHODS.has(k))[i] || null; },
      get length() { return Object.keys(store).filter((k) => !METHODS.has(k)).length; },
    };
    return store;
  };
  const storage = { local: mkStore(), session: mkStore() };
  (storageKeys || []).forEach(([area, k, v]) => { storage[area][k] = v; });
  const sandbox = {
    console,
    URLSearchParams: globalThis.URLSearchParams,
    window: {
      location: { search: initialUrl.split("?")[1] ? "?" + initialUrl.split("?")[1] : "", pathname: initialUrl.split("?")[0], hash: "" },
      history: { replaceState: (s, t, url) => { replaceCalls.push(url); } },
      matchMedia: () => ({ matches: false }),
    },
    localStorage: storage.local,
    sessionStorage: storage.session,
  };
  sandbox.window.localStorage = sandbox.localStorage;
  sandbox.window.sessionStorage = sandbox.sessionStorage;
  sandbox.window.URLSearchParams = globalThis.URLSearchParams;
  sandbox.window.history = sandbox.window.history;
  vm.createContext(sandbox);
  const src = fs.readFileSync("frontend/viz-core.js", "utf8");
  vm.runInContext(src, sandbox);
  return { viz: sandbox.window.WAWA_Viz, replaceCalls, storage };
}

console.log("DEMO STATE SMOKE");
const fresh = loadVizCore("/mission-control");
const V = fresh.viz;
if (!V) { console.error("WAWA_Viz no expuesto"); process.exit(9); }

// 1. OFF por defecto
check("demo OFF por defecto", V.initDemoState() === false);
check("isDemoMode() false tras init sin parametro", V.isDemoMode() === false);
check("sin ?demo=1 no se reescribe la URL", fresh.replaceCalls.length === 0);

// 2. ?demo=1 activa y limpia la URL (refrescar no reactiva)
const withParam = loadVizCore("/mission-control?demo=1&otro=2");
check("?demo=1 activa demo", withParam.viz.initDemoState() === true);
check("isDemoMode() true tras activar", withParam.viz.isDemoMode() === true);
check("se limpio ?demo=1 de la URL", withParam.replaceCalls.length === 1 &&
  withParam.replaceCalls[0].indexOf("demo") < 0 && withParam.replaceCalls[0].indexOf("otro=2") >= 0);

// 3. salir de demo: URL limpia + storage limpio
const exitCase = loadVizCore("/mission-control?demo=1", [["local", "wawa_demo_state", "1"], ["session", "demoMode", "x"]]);
exitCase.viz.initDemoState();
exitCase.viz.setDemoActive(false);
check("salir de demo -> isDemoMode() false", exitCase.viz.isDemoMode() === false);
check("salir de demo reescribe la URL sin demo", exitCase.replaceCalls.length >= 1 &&
  exitCase.replaceCalls[exitCase.replaceCalls.length - 1].indexOf("demo") < 0);
check("localStorage sin claves demo", exitCase.storage.local["wawa_demo_state"] === undefined);
check("sessionStorage sin claves demo", exitCase.storage.session["demoMode"] === undefined);

// 4. reiniciar (nueva carga) no reactiva demo
const restart = loadVizCore("/mission-control");
check("reinicio no reactiva demo", restart.viz.initDemoState() === false && restart.viz.isDemoMode() === false);

// 5. datos demo etiquetados, nunca mezclados
const demoData = fresh.viz.demoTelemetry();
check("demoTelemetry etiquetada DEMO", demoData.data_nature === "DEMO" && demoData.demo_notice === "DEMO DATA · NOT REAL ACTIVITY");
check("demo activa -> demoTelemetry", withParam.viz.isDemoMode() === true);

// 6. botones coherentes (estático en ambas vistas)
const mc = fs.readFileSync("frontend/mission-control.js", "utf8");
const sv = fs.readFileSync("frontend/agents-viz.js", "utf8");
check("Mission Control: ACTIVAR DEMO presente", mc.indexOf('"ACTIVAR DEMO"') >= 0);
check("Mission Control: SALIR DE DEMO presente", mc.indexOf('"SALIR DE DEMO"') >= 0);
check("Mission Control: setDemoActive usado", mc.indexOf("V.setDemoActive(") >= 0);
check("Mission Control: initDemoState usado", mc.indexOf("V.initDemoState()") >= 0);
check("Sistema Solar: ACTIVAR DEMO presente", sv.indexOf('"ACTIVAR DEMO"') >= 0);
check("Sistema Solar: SALIR DE DEMO presente", sv.indexOf('"SALIR DE DEMO"') >= 0);
check("Sistema Solar: setDemoActive usado", sv.indexOf("V.setDemoActive(") >= 0);
check("Sistema Solar: initDemoState usado", sv.indexOf("V.initDemoState()") >= 0);
const mcHtml = fs.readFileSync("frontend/mission-control.html", "utf8");
const svHtml = fs.readFileSync("frontend/agents-viz.html", "utf8");
check("HTML Mission Control: boton inicial ACTIVAR DEMO", mcHtml.indexOf(">ACTIVAR DEMO</button>") >= 0);
check("HTML Sistema Solar: boton inicial ACTIVAR DEMO", svHtml.indexOf(">ACTIVAR DEMO</button>") >= 0);

if (failures > 0) { console.error(failures + " comprobaciones fallidas"); process.exit(1); }
console.log("DEMO_STATE_SMOKE_OK");
