# Riesgos de términos y dependencias (iteración 008)

## Riesgos principales

1. **Proveedores upstream** (342 en el catálogo): cada uno tiene sus propios
   términos, límites, precios y políticas de entrenamiento. **El gateway no
   garantiza cumplimiento**: la responsabilidad de autorizar cada conexión es
   de WAWA vía allowlist (`app/core/omniroute_allowlist.py`).
2. **Cuentas web / OAuth / sesiones**: algunos proveedores requieren sesión
   web o tokens de cuenta personal. Eso es **frágil y no automatizable de
   forma estable**; dichas conexiones se marcan `BLOCKED` o `UNKNOWN` (=
   bloqueadas para producción) hasta revisión explícita.
3. **Modelos gratuitos**: no son una garantía. Un tier free puede desaparecer,
   cambiar límites o degradarse. WAWA trata cada llamada como independiente
   (`actual_model` registrado), nunca asume disponibilidad.
4. **`auto` no es determinista**: dos llamadas con `auto` pueden resolver a
   modelos distintos. Por eso el comité principal usa un modelo fijo y las
   métricas se agrupan por modelo real.
5. **Structured outputs**: soporte documentado en los handlers del gateway,
   **no verificado** con ningún proveedor real. Antes de depender de JSON
   estructurado en producción, hay que probarlo con el modelo elegido.
6. **Telemetría del gateway**: no auditada en esta iteración. La allowlist lo
   registra como desconocido; cualquier conexión en producción exige auditoría
   de privacidad previa.

## Datos prohibidos de enviar a proveedores upstream

- secretos y claves
- wallets / claves privadas / frases de recuperación
- datos personales o de clientes
- credenciales
- información financiera sensible
- código confidencial completo (solo fragmentos mínimos necesarios)

## Regla de autorización

Para que una conexión OmniRoute se use en **producción** debe registrar:
proveedor, método de autenticación, términos de servicio, permiso de
automatización, permiso de uso comercial, política de entrenamiento,
retención de datos, región, tipo de datos permitido, fecha de revisión y
estado final (`ALLOWED`).

Por defecto: **UNKNOWN = bloqueado para producción**.

## Estado en esta iteración

- Solo `omniroute-gateway` (localhost) está en `TEST_ONLY`.
- Ninguna conexión upstream está autorizada.
- Ninguna llamada real a OmniRoute se ejecutó (ENOSPC al instalar el gateway
  en el sandbox). Las 5 llamadas reales máximas de la iteración quedan
  pendientes para un entorno con disco suficiente.
