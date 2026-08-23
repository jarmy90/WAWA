# Selección de modelos en OmniRoute (iteración 008)

## "Alpha 0" — hallazgo

**No existe evidencia de un modelo "Alpha 0" / "Alpha Zero" / "alpha-0" en el
catálogo analizado** (código fuente `release/v3.8.50`, 2026-08-23).

- La única aparición de "Alpha" es el endpoint `/alpha/generate` de un
  proveedor (Command Code) — **no es un modelo**.
- **No se inventa el slug.** `OMNIROUTE_REVIEW_MODEL=auto` queda como
  predeterminado provisional.
- Cuando se despliegue OmniRoute en un entorno con disco suficiente, hay que:
  1. Consultar el endpoint de modelos del gateway.
  2. Guardar un snapshot sanitizado del catálogo.
  3. Buscar coincidencias exactas/aproximadas con Alpha 0 / alpha-0 / alpha0.
  4. Identificar slug real, proveedor real, gratuidad, límites, contexto,
     JSON estructurado, tool calling y estabilidad entre llamadas.
  5. Registrar el modelo realmente servido (`actual_model`).
  6. Revisar condiciones de uso antes de fijar nada.

Hasta que eso ocurra: **nada se configura como modelo por defecto basándose
en suposiciones**.

## Configuración

- `OMNIROUTE_REVIEW_MODEL=auto` (resuelto por el gateway por llamada).
- `OMNIROUTE_DISCOVERY_MODEL=auto` (desactivado hasta pasar el A/B).
- `OMNIROUTE_FALLBACK_MODEL=auto`.
- `OMNIROUTE_ALLOW_FREE_ONLY=true`: solo se permiten modelos gratuitos.
- `OMNIROUTE_REQUIRE_MODEL_ID=true`: cada respuesta debe indicar el modelo
  real; si no, la llamada no es válida para el comité.

## Modelo fijo vs. auto

- El **comité OpenRouter** mantiene un modelo **fijo** (comparabilidad entre
  revisiones).
- **OmniRoute `auto`** puede variar entre llamadas; por eso WAWA registra
  siempre `requested_model` y `actual_model`, y nunca asume que coinciden.
- Las métricas del comité se calculan por modelo real, no por el solicitado.

## Alternativas reales (a confirmar con catálogo real)

No se propone ningún slug concreto como "el modelo Alpha 0" porque no existe
evidencia. Tras desplegar, proponer alternativas observadas en el catálogo
real (proveedores gratuitos con contexto suficiente para el expediente de
revisión) y registrarlas en `docs/OMNIROUTE_RESEARCH.md`.
