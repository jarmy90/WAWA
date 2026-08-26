"""Capturas de verificación visual (iteración 022) con Playwright/Chromium.

Requisitos: servidor WAWA en http://127.0.0.1:8938 y base local con el
bootstrap comercial aplicado (o una base limpia recién bootstrapada).
Genera PNG en deliverables/iteracion_022_capturas/.

Escenarios:
  1. / (Inicio después de bootstrap)
  2. /candidates (tres candidatas)
  3. /candidates (tarjeta ganadora de ortodoncia)
  4. /candidates (wizard GPT/Grok/Gemini abierto)
  5. /mission-control (sin demo)
  6. /mission-control?demo=1 (con demo, etiqueta visible)
  7. /mission-control después de SALIR DE DEMO (URL sin ?demo=1)
  8. /mission-control (sección CONECTAR SERVICIOS)
  9. Vista móvil de /candidates
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8938"
OUT = Path("deliverables/iteracion_022_capturas")


def main() -> int:
    from playwright.sync_api import TimeoutError as PWTimeout

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=1, locale="es-ES")
        page = ctx.new_page()

        # 1. Inicio (dashboard)
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "01_inicio_despues_bootstrap.png"), full_page=False)

        # 2. Candidatas (tres tarjetas)
        page.goto(BASE + "/candidates", wait_until="domcontentloaded")
        page.wait_for_selector(".cand-grid .cand-card", timeout=15000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "02_candidatas.png"), full_page=False)

        # 3. Tarjeta ganadora (ortodoncia)
        page.evaluate("""() => {
          const cards = document.querySelectorAll('.cand-card');
          for (const c of cards) {
            if (c.textContent.indexOf('GANADORA DETERMINISTA PARA EXPERIMENTO') >= 0) {
              c.scrollIntoView({block: 'center'}); break;
            }
          }
        }""")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "03_tarjeta_ortodoncia.png"), full_page=False)

        # 4. Wizard GPT/Grok/Gemini (abrir el primer botón de comité)
        try:
            page.evaluate("""() => {
              const btn = document.querySelector('.wizard-actions button, button[data-rev]');
              if (btn) btn.click();
            }""")
            page.wait_for_timeout(500)
        except Exception:
            pass
        page.screenshot(path=str(OUT / "04_wizard_comite.png"), full_page=False)

        # 5. Mission Control sin demo
        page.goto(BASE + "/mission-control", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "05_mission_control_sin_demo.png"), full_page=False)

        # 6. Mission Control con demo (?demo=1)
        page.goto(BASE + "/mission-control?demo=1", wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "06_mission_control_con_demo.png"), full_page=False)

        # 7. Salir de demo: clic en SALIR DE DEMO y comprobar URL limpia
        try:
            page.click("button:has-text('SALIR DE DEMO')", timeout=5000)
            page.wait_for_timeout(600)
        except PWTimeout:
            print("AVISO: no se encontró el botón SALIR DE DEMO")
        url_after = page.url
        print("URL tras salir de demo:", url_after)
        assert "demo" not in url_after, "la URL conserva ?demo tras salir de demo"
        page.screenshot(path=str(OUT / "07_mission_control_despues_salir_demo.png"), full_page=False)

        # 8. CONECTAR SERVICIOS (sección del panel: wizard en #mc-services-wizard)
        page.evaluate("""() => {
          const el = document.getElementById('mc-services-wizard') ||
                     document.querySelector('#mc-services') ||
                     document.querySelector('.mc-services');
          if (el) el.scrollIntoView({block: 'center'});
        }""")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "08_conectar_servicios.png"), full_page=False)

        # 9. Vista móvil
        mctx = browser.new_context(viewport={"width": 390, "height": 844},
                                   device_scale_factor=2, is_mobile=True, locale="es-ES")
        mpage = mctx.new_page()
        mpage.goto(BASE + "/candidates", wait_until="domcontentloaded")
        mpage.wait_for_selector(".cand-grid .cand-card", timeout=15000)
        mpage.wait_for_timeout(600)
        mpage.screenshot(path=str(OUT / "09_movil_candidatas.png"), full_page=False)
        mctx.close()

        ctx.close()
        browser.close()

    print("CAPTURAS_OK:", sorted(p.name for p in OUT.iterdir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or (1 if "FAIL" in "".join(sys.argv[1:]) else 0))
