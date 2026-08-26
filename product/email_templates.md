# Email transaccional (plantillas — NO conectado)

Requisito: `EMAIL_API_KEY` (proveedor transaccional, p. ej. Resend u otro
autorizado). Estado `MISSING` hasta que el propietario la aporte. Las
plantillas son texto plano adaptable; sin seguimiento de aperturas de
terceros salvo el propio proveedor.

## 1. Confirmación de pedido

**Asunto:** Tu informe de tarifas de ortodoncia · {provincia}

```
Hola,

Hemos recibido tu pedido del informe de tarifas de ortodoncia de {provincia}.
Importe: {price} EUR (pago único).

Entregaremos el informe en PDF y te contactaremos para agendar la revisión
(videollamada, ~30 min) en un plazo máximo de 48 h laborables.

Si tienes dudas, responde a este correo.

— WAWA Autonomous Business Command
```

## 2. Entrega del informe

**Asunto:** Tu informe está listo · {provincia}

```
Adjunto tienes tu informe de tarifas de ortodoncia de {provincia}.

Incluye rangos y percentiles por tratamiento, con las fuentes públicas
citadas (URL + fecha de consulta). Este informe es anónimo y agregado: no
identifica clínicas ni usa datos de pacientes.

Agenda tu revisión aquí: {link_videollamada}

— WAWA
```

## 3. Recordatorio de revisión (opcional, 1 aviso)

**Asunto:** Revisión de tu informe — ¿te va bien este horario?

```
Te recordamos que tu revisión incluye una videollamada de 30 min para
interpretar el informe y decidir tu tarifa. Responde con un horario que te
venga bien.

— WAWA
```

## Guardas

- Un único aviso de revisión (nunca mensajería masiva).
- `decision_log` registra cada envío (append-only) con `simulated=true` hasta
  que exista pago real.
- Las claves van en el gestor de credenciales (`EMAIL_API_KEY`), nunca en Git.
