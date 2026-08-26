"""Chequeo y aplicación del bootstrap comercial al arrancar (START_WAWA.bat).

Imprime progreso entendible en la consola (pasos [4/7]-[6/7]) y NUNCA bloquea
el arranque: si el bootstrap falla, el panel ofrece REPARAR Y CONTINUAR.
Idempotente: si ya está aplicado imprime BOOTSTRAP COMERCIAL YA APLICADO.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.container import build_container


def main() -> int:
    container = build_container(get_settings())
    try:
        status = container.bootstrap.status()
        if status.get("applied"):
            print("BOOTSTRAP COMERCIAL YA APLICADO")
            return 0
        if not status.get("assets_ok"):
            print("AVISO: activos de bootstrap no disponibles; usa REPARAR Y CONTINUAR desde el panel.")
            return 0
        print("Aplicando investigación verificada (3 candidatas, 18 misiones, 31 evidencias)...")
        result = container.bootstrap.apply()
        print(f"Ganadora determinista: {(result.get('winner_title') or '')[:70]}")
        print(f"READY_TO_CONNECT_SERVICES · evidencias: {result.get('evidences_attached')} · "
              f"PRE_CYCLE: {result.get('pre_cycle')} · producción: {result.get('production')}")
        return 0
    except Exception as exc:  # noqa: BLE001 — nunca bloquear el arranque local
        print(f"AVISO: el bootstrap no se pudo aplicar en este arranque: {exc}")
        print("El botón REPARAR Y CONTINUAR del panel reintentará automáticamente.")
        return 0
    finally:
        container.close()


if __name__ == "__main__":
    raise SystemExit(main())
