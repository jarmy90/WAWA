# OPERACIÓN: REFORMULACIÓN DE DIRECCIONES ABSTRACTAS → CANDIDATAS INVESTIGABLES

- **Fecha**: 2026-08-24
- **Sistema**: WAWA v0.15.0 · iteración 016 (sin cambios de código)
- **Método**: mecanismos existentes de la iteración 016, 100% offline, sin LLM (sin GPT/Grok/Gemini/OpenRouter/OmniRoute)
- **Regla aplicada**: toda formulación es HIPÓTESIS; `proven_demand` y `evidence_backed_venture_score` permanecen en 0; ninguna evidencia se inventa ni se verifica.

---

## 1. campaign_id

La operación se ejecutó sobre una **reproducción fiel y aislada** de PRIMERA CAMPAÑA REAL 001 (base SQLite temporal, misma configuración y mismo generador determinista que la instalación del propietario):

- **run_id**: `a4816245686b4590a2aca6bf58f8db10`
- **discovery_campaign_id (reproducción)**: `bf496d71cf9f4cff91c6ad4baa02d823`

> Los `concept_id`/`mission_id` de este informe corresponden a la reproducción. La campaña del propietario contiene **los mismos 66 conceptos con los mismos títulos** (generador determinista), pero los identificadores pueden diferir. El propietario debe localizar sus direcciones por **título** (tabla del punto 3) o aplicar los briefs del JSON entregado en su propio panel.

## 2. Estado inicial (verificado, idéntico al del propietario)

- Estado orquestador: **RESEARCH_PENDING**
- Total conceptos: **66**
- `COMMODITY_BLOCKED`: 3 · `DIVERSITY_ELIMINATED`: 51 · `NEEDS_REFORMULATION`: **6** · `RECOMBINATION_INCOHERENT`: **6**
- `RESEARCH_CANDIDATE`: **0** · Finalistas: 0 · Misiones: 0
- Próxima acción inicial: **REFORMULAR** (sin misión que copiar)

## 3. Los seis concept_id reformulados (dirección original → reformulación concreta)

| concept_id (reproducción) | Dirección original (título en el panel del propietario) | Reformulación concreta (brief aprobado) |
|---|---|---|
| `25da39d3f67c46a786042c3545072f30` | Activo de memoria personal para intermediarios opacos | **Cuaderno de cuotas y servicios para comunidades que contratan administradores de fincas** |
| `2c46270f784047f0930b9aa93934e1cd` | Cooperativa de datos para decisiones con alta incertidumbre | **Benchmark anónimo de tarifas para clínicas dentales que fijan precios de ortodoncia** |
| `05c80f5162aa4fd9ae27fb8f8bd8b63b` | Vender tiempo ahorrado para cambios regulatorios | **Preparación del modelo 232 de operaciones vinculadas para asesorías contables** |
| `764f7f687705449dbd5b71f84581e587` | El cliente es la distribución para trabajo invisible y administrativo | Partes de fisioterapia sin papeleo para clínicas de barrio *(no seleccionada en torneo)* |
| `fce01fbf92fd4645b0212f2839480e1f` | El cliente es la distribución para intermediarios opacos | Dossier de comisiones y entregables para propietarios que venden con agencia *(no seleccionada)* |
| `36bd86cef693482a860d3c22dcf9b432` | Activo de memoria personal para fraude y verificación | Registro de verificación de documentos para inmobiliarias que alquilan pisos *(no seleccionada)* |

## 4. Reformulaciones propuestas

Las **6 reformulaciones completas** (19 campos del Opportunity Brief cada una, comprador específico, prueba de 48 h, canal, riesgo de IA generalista, activo acumulativo, supuestos) están en:
`deliverables/operacion_reformulacion_2026-08-24/reformulaciones_briefs.json`

Todas etiquetadas como HIPÓTESIS (campo `assumptions` explícito; `prohibited_claims` prohibe afirmar demanda). Ninguna usa compradores genéricos (empresas/profesionales/usuarios/pymes).

## 5. Resultado del Opportunity Brief de cada una (Quality Gate determinista)

`validate_opportunity_brief` (gate de la iteración 016: 19 campos obligatorios ≥ 8 caracteres, sin marcadores genéricos):

| concept_id | Verdict | Estado tras gate |
|---|---|---|
| 25da39d3… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |
| 2c46270f… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |
| 05c80f51… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |
| 764f7f68… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |
| fce01fbf… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |
| 36bd86ce… | **OK (0 marcadores)** | RESEARCH_CANDIDATE |

## 6. Resultado del General AI Substitution Test

- Las 6 direcciones **superaron el filtro de comoditización** en el pipeline original (ninguna es `COMMODITY_BLOCKED`; las 3 bloqueadas ya están descartadas y no se tocaron).
- Cada brief declara su **limitación de IA generalista** (campo obligatorio del gate): requisitos por mutua, datos anónimos de provincia, padrón de socios/requisitos del modelo 232, actas y facturas reales, historial de verificación con fecha.
- La **confirmación externa** de no-sustitución por IA es la misión de Fase 1 `GENERAL_AI_SUBSTITUTION_CHECK` de cada candidata (**sin ejecutar**; se ejecutará con fuentes reales).

## 7. Resultado del torneo (determinista, `run_reformulation_tournament`)

- Participantes: 6 candidatas con brief validado.
- **Seleccionadas: 3** (máximo permitido 3) por `structural_concept_score` (sin evidencia).
- Las 3 no seleccionadas volvieron a `NEEDS_REFORMULATION` **conservando su brief guardado** (reformulables en un segundo pase si el propietario lo decide).

## 8. Número de candidatas válidas

**3 candidatas** promovidas a oportunidad con misiones de Fase 1. (Resultado permitido 0–3; no se fabricó ninguna para cumplir cuota.)

## 9. Detalle por candidata

### C1 — Cuaderno de cuotas y servicios para comunidades que contratan administradores de fincas
- **concept_id**: `25da39d3f67c46a786042c3545072f30` · **opportunity_id**: `bd367d32070c4477a23cbd537fbec777`
- **Comprador**: Presidente de una comunidad de propietarios de 10-40 viviendas que paga a un administrador de fincas
- **Problema observable**: en la junta anual nadie puede contrastar la cuota con los servicios realmente prestados
- **Alternativa actual**: actas en papel de años anteriores y la memoria que redacta el administrador
- **Entregable**: cuaderno anual por comunidad con cuota, servicios incluidos, facturas y entregables, exportable
- **Resultado medible**: la junta dispone del cuaderno completo una semana antes de la reunión anual
- **Canal inicial**: presidentes de comunidades del mismo barrio vía junta de vecinos
- **Experimento 48 h**: rellenar el cuaderno de dos comunidades con sus actas y facturas y pedir su valoración
- **Puntuación estructural**: 64.56 · **Puntuación con evidencia**: **0.0**
- **Supuestos**: dolor, precio (60 EUR/cuaderno anual, hipótesis) y formato sin verificar
- **Bloqueadores**: ninguno

### C2 — Benchmark anónimo de tarifas para clínicas dentales que fijan precios de ortodoncia
- **concept_id**: `2c46270f784047f0930b9aa93934e1cd` · **opportunity_id**: `b029c89ee0ef42d8b6cc71ceb4919f6f`
- **Comprador**: gerente de una clínica dental de 2-5 dentistas que fija precios de ortodoncia
- **Problema observable**: no sabe si su precio está fuera del rango de la zona y pierde margen o pacientes
- **Alternativa actual**: preguntar a dos o tres colegas y ajustar por intuición
- **Entregable**: informe trimestral de tarifas por provincia con percentiles por tipo de tratamiento
- **Resultado medible**: tarifa fijada con un rango de referencia provincial en la próxima revisión
- **Canal inicial**: invitación personal a diez clínicas de la provincia para aportar tarifas de forma anónima
- **Experimento 48 h**: recoger tarifas anónimas de cinco clínicas conocidas y devolver el primer informe de prueba
- **Puntuación estructural**: 64.05 · **Puntuación con evidencia**: **0.0**
- **Supuestos**: participación anónima, dolor de precio y pago (90 EUR/informe, hipótesis) sin verificar
- **Bloqueadores**: ninguno

### C3 — Preparación del modelo 232 de operaciones vinculadas para asesorías contables
- **concept_id**: `05c80f5162aa4fd9ae27fb8f8bd8b63b` · **opportunity_id**: `0cf4b0ca03f4419e96344cdb35705391`
- **Comprador**: titular de una asesoría contable de 1-5 empleados con clientes que declaran operaciones vinculadas
- **Problema observable**: el contable pierde horas recopilando el padrón de socios y las operaciones vinculadas de cada cliente
- **Alternativa actual**: recopilación manual con mensajes al cliente y datos en hojas de cálculo separadas
- **Entregable**: checklist por cliente con plantilla de recogida de datos y borrador del modelo 232 listo para revisión
- **Resultado medible**: borrador del modelo 232 por cliente en menos de dos horas de trabajo del contable
- **Canal inicial**: mensaje directo a diez asesorías contables de la provincia que publican servicios de declaraciones
- **Experimento 48 h**: preparar el borrador del modelo 232 de un cliente real de una asesoría conocida
- **Puntuación estructural**: 62.56 · **Puntuación con evidencia**: **0.0**
- **Supuestos**: dolor, precio (49 EUR/mes, hipótesis) y urgencia sin verificar
- **Bloqueadores**: ninguno

## 10–11. Misiones de Fase 1 creadas (6 por candidata, PROGRESIVAS) y sus mission_id

Solo Fase 1 (`RESEARCH_PHASE1_KINDS`); **no** se crearon fases posteriores. Total: **18 misiones**, todas en estado `exported`.

**C1 (25da39d3…):**
| mission_id | Tipo |
|---|---|
| `62a9bff2830a48dfa1cab93ffddf82a8` | DEMAND_REALITY_CHECK |
| `d1fbe8cbebb84d0d88c2e752b73eac9e` | BUYER_BUDGET_CHECK |
| `a4fcfc9de3e74cf09d0f22a494e2bf5e` | CURRENT_ALTERNATIVE_CHECK |
| `8a607c7eea6c4c51b6fa0ad77f356eaa` | DISTRIBUTION_ACCESS_CHECK |
| `702f234534fc4b5b8634ec4c3e4d5025` | COMPETITOR_EQUIVALENT_SEARCH |
| `fae7dc493ef34211916b1ef26745a607` | GENERAL_AI_SUBSTITUTION_CHECK |

**C2 (2c46270f…):**
| mission_id | Tipo |
|---|---|
| `f0db12ab6f484c12b37da613147a11c4` | DEMAND_REALITY_CHECK |
| `afcfc9292ff04aaf9c38d62e9603ab4a` | BUYER_BUDGET_CHECK |
| `e91f4e80e451412bae1fadec6aa2da89` | CURRENT_ALTERNATIVE_CHECK |
| `29b5efe094664aa2b4a873cff5f9dc34` | DISTRIBUTION_ACCESS_CHECK |
| `5f0e54ca67c54bb99a5ace4bff62ccc9` | COMPETITOR_EQUIVALENT_SEARCH |
| `fef2e6d186c346edb8d2e6c93267c305` | GENERAL_AI_SUBSTITUTION_CHECK |

**C3 (05c80f51…):**
| mission_id | Tipo |
|---|---|
| `9255662bf3c64d078c2cd4077b4ccf0f` | DEMAND_REALITY_CHECK |
| `481dbcc1d6af405aa0e4e336e3292bfa` | BUYER_BUDGET_CHECK |
| `2f7f2f8fa349424990013b09e960a351` | CURRENT_ALTERNATIVE_CHECK |
| `55bb293bb76e48c1a5708cd1c229d9b4` | DISTRIBUTION_ACCESS_CHECK |
| `87c669ce03d74eeaba961e406f9a0e88` | COMPETITOR_EQUIVALENT_SEARCH |
| `5ad4f11ab6914c2d8feb99b10fa573f3` | GENERAL_AI_SUBSTITUTION_CHECK |

Cada misión incluye su `mission_id` en el paquete copiable (COPIAR MISIÓN PARA FREEBUFF). Markdowns exportados en `deliverables/operacion_reformulacion_2026-08-24/misiones/` (18 archivos).

## 12. Confirmación: ninguna misión fue ejecutada

- Las 18 misiones están en estado **`exported`** (ninguna `imported`).
- `mission_results`: **0 filas** · `imported_at`: NULL en todas.

## 13. Confirmación: no se inventó evidencia

- Tabla `evidence`: **0 filas**.
- `proven_demand` = 0 en todas las candidatas; `evidence_backed_venture_score` = **0.0** en todas (tope por diseño: <3 grupos independientes).
- Las reformulaciones son hipótesis de formulación (etiquetadas), no afirmaciones de mercado.

## 14. Confirmación: PRE_CYCLE sigue detenido

- `cycle_state`: **sin fila** (nunca se consultó ni inicializó en esta operación) ⇒ `started_at` = NULL, reloj de 30 días **no iniciado**.
- La operación no llamó a `POST /api/economy/cycle/start` ni a ninguna precondición económica.

## 15. Confirmación: gasto en 0

- `ledger_entries`: **0 asientos** · `llm_call_log`: **0 llamadas** · presupuesto real consumido: **0 €**.
- El sistema sigue en modo simulación; `real_money_moved=false`.

## 16. Próxima acción exacta del propietario

**Opción A (recomendada, mínima intervención):** en su instalación real, en la pestaña **Ideas** localice las 6 direcciones por título (tabla del punto 3) y complete el Opportunity Brief de cada una con el contenido de `reformulaciones_briefs.json` (o pida a Freebuff que lo aplique). Pulsar **CONTINUAR CAMPAÑA REAL** en la portada: el orquestador re-planifica y crea las 6 misiones de Fase 1 por candidata.

**Opción B (directa):** copiar directamente una misión de las 18 exportadas (incluyen mission_id), entregarla a Freebuff, pegar la respuesta en el panel **solo contra esa mission_id**; la evidencia solo se marcará `verified=true` con URL + fecha de consulta + fragmento.

**Después:** sin investigación externa todavía (parada aquí por orden). Las misiones están listas para copiar cuando el propietario autorice el siguiente paso.

---

## Anexo A — Presupuesto (PASO 6: política propuesta, sin iniciar ciclo ni mover nada)

| Concepto | Política propuesta del propietario | Configuración actual del sistema |
|---|---|---|
| Presupuesto consumido | 0 € | 0 (ledger vacío) |
| Reserva máxima primer ciclo | 50 € | Ciclo 30 días / 50 USD (configurado) |
| Primer experimento | máx. 10 € | Sin parámetro específico; gasto real no existe (simulación) |
| Ampliación > 10 € | requiere autorización explícita | No implementada (no aplica sin dinero real) |
| 100 € | NO autorizado | No existe vía de gasto real |
| Regla previa | ningún gasto antes de candidata + evidencia + canal + experimento aprobado | Coherente: no hay gasto posible en este estado |

**Conclusión**: la política propuesta es **compatible** con la configuración actual; no se requiere desarrollo ni cambios de reglas económicas. El sistema no autoriza movimiento alguno (simulación, `real_money_moved=false`).

## Anexo B — Archivos de esta operación

| Archivo | Contenido |
|---|---|
| `deliverables/operacion_reformulacion_2026-08-24/reformulaciones_briefs.json` | Las 6 reformulaciones completas (19 campos), listas para aplicar en el panel |
| `deliverables/operacion_reformulacion_2026-08-24/INFORME_REFORMULACION_2026-08-24.md` | Este informe |
| `deliverables/operacion_reformulacion_2026-08-24/misiones/*.md` | 18 misiones de Fase 1 exportadas (COPIAR MISIÓN PARA FREEBUFF) |

*Los archivos están guardados en el workspace del repositorio (pendientes de commit/push si se desean enlaces directos descargables; el panel de Changes de Freebuff gestiona el guardado).*
