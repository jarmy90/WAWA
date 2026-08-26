# Investigación inicial — iteración 018 (provisional)

Fecha de consulta: 2026-08-26 · Método: búsqueda web autorizada (Serper/Google)

**ESTADO DE ESTA EVIDENCIA: PROVISIONAL.** Ningún fragmento de este archivo se
ha importado todavía a la base local ni cuenta como `verified=true`. La
verificación exigida por el proyecto es URL + fecha de consulta + fragmento
importados contra una `mission_id` LOCAL mediante la infraestructura de la
iteración 017 (`apply_reformulation_plan` + `resolve_research_package`). Este
archivo solo acelera la investigación real: cada fuente debe confirmarse en la
instalación del propietario antes de subir `evidence_backed_venture_score`.

Nada de esto son cifras inventadas: son fragmentos textuales de resultados de
búsqueda con su URL. La interpretación (¿demanda?, ¿presupuesto?) sigue siendo
HIPÓTESIS hasta verificarse en las misiones.

---

## C1 — Benchmark de tarifas de ortodoncia para clínicas dentales (77,5)

Pregunta: ¿Existe dispersión de precios de ortodoncia en España y fuentes
públicas que la documenten? (Relevante para: ¿hay dolor de "fijar precio" y
fuentes primarias para un benchmark anónimo?)

| URL | Fragmento (exacto) | Fecha |
|---|---|---|
| https://www.sanitas.es/dental/precios-tratamientos-dentales | "Estudio radiológico para ortodoncia, Incluido, 62,50 € ; Estudio y diagnóstico para planificación personalizada del tratamiento, 80,90 €, 105,50 €" | 2026-08-26 |
| https://www.prodentis.es/blog/guia-precios-dentales-malaga-2026 | "Un empaste cuesta entre 50 y 120 €, un implante completo entre 1.200 y 2.300 €, y una ortodoncia Invisalign entre 2.500 y 5.500 €" | 2026-08-26 |
| https://smile2impress.com/es/blog/el-precio-de-la-ortodoncia-en-espana | "Brackets metálicos - Aproximadamente entre 2,200€ y 3,200€ · Brackets autoligables - Aproximadamente entre 3,000€ y 5,000€" | 2026-08-26 |
| https://www.operarme.es/blog/precio-brackets-cuanto-cuesta-ortodoncia-y-tipos/ | "Ortodoncia con Brackets Metálicos por 1.976 € · Tratamiento con Brackets Autoligables por 2.627 €" | 2026-08-26 |

Interpretación provisional (HIPÓTESIS, no evidencia):
- Existe dispersión de precios públicamente documentada (rango amplio para el
  mismo tratamiento), lo que sostiene la hipótesis de que "fijar precio" es una
  decisión con información imperfecta.
- Fuentes primarias potenciales: tarifarios públicos de clínicas y aseguradoras
  (Sanitas, Adeslas), guías de precios por ciudad.
- Contradicción a buscar: si la clínica ya usa software de pricing o si el
  precio lo fija la cadena central (Vitaldent/DentalCorp), el comprador no
  decide.

## C2 — Benchmark de honorarios para gestorías (72,5)

Pregunta: ¿Existen tarifas públicas de gestorías y dispersión suficiente para
que un benchmark tenga valor?

| URL | Fragmento (exacto) | Fecha |
|---|---|---|
| https://gestoriaautonomosbarcelona.com/precios-tarifas-gestoria | "Tarifas claras para autónomos: cuota mensual desde 60 € + IVA, por impuesto desde 50 € y trámites puntuales. Sin permanencia." | 2026-08-26 |
| https://www.gonzalbes.com/asesoria-tarifas | "29,95 €/ mes. IVA incluido. Programa de facturación online. Confección de libros contables" | 2026-08-26 |
| https://www.asred.es/tarifas/ | "Autónomos: 40€/mes + I.V.A.. Sociedades: 75€/mes + I.V.A." | 2026-08-26 |
| https://driassessoria.com/blog/cuanto-cobra-asesoria-llevar-contabilidad-precios | "A partir de 100 apuntes contables al mes, el precio medio en España se sitúa entre 150 € y 250 € al mes, sin IVA" | 2026-08-26 |
| https://www.sage.com/es-es/blog/precio-servicio-contabilidad/ | "No existe una tarifa única para llevar la contabilidad. El precio depende del volumen documental, las obligaciones fiscales…" | 2026-08-26 |

Interpretación provisional (HIPÓTESIS):
- Dispersión enorme entre gestorías (29,95 €/mes vs 150-250 €/mes según
  volumen): el precio depende de variables que no se publican normalizadas.
- Hipótesis de producto: convertir la dispersión en un benchmark anónimo por
  perfil (autónomo simple / sociedad / volumen de apuntes).
- Contradicción a buscar: los precios se negocian en privado y las gestorías
  no publican → ¿de dónde salen los datos?; riesgo de datos personales de
  clientes.

## C3 — Benchmark de costes de instalación para empresas de placas solares (72,5)

Pregunta: ¿El coste de instalación tiene dispersión pública y el comprador
(empresa instaladora) tiene dificultad para presupuestar?

| URL | Fragmento (exacto) | Fecha |
|---|---|---|
| https://solfy.net/autoconsumo/placas-solares/precio/ | "El precio medio de instalar placas solares en una vivienda unifamiliar en España en 2026 oscila entre 4.000 y 9.000€" | 2026-08-26 |
| https://www.sfe-solar.com/instalaciones-fotovoltaicas/precio/ | "En 2025, el precio de instalación residencial es de media de 1.215 €/kW para una instalación de 5,5 kW según la Asociación de Empresas de Energías Renovables" | 2026-08-26 |
| https://www.aficlima.com/instalar-placas-solares/ | "el coste de una instalación fotovoltaica en España para una vivienda unifamiliar se sitúa entre 3.500 € y 7.000 €, aunque puede superar los 10.000 €" | 2026-08-26 |
| https://sotysolar.es/placas-solares/instalacion/precio | "El precio medio de una instalación solar para una vivienda unifamiliar en España es de entre 4.000 y los 9.000 euros" | 2026-08-26 |

Interpretación provisional (HIPÓTESIS):
- El coste final depende de potencia y componentes: dispersión 4.000-10.000 €.
- Para una empresa instaladora, presupuestar mal erosiona margen: hipótesis de
  dolor comprador plausible.
- Contradicción a buscar: subvenciones autonómicas cambian el precio neto
  según zona; el margen del instalador es privado y difícil de benchmarkear
  sin datos reales.

---

## Declaración de honestidad

- Estas fuentes NO se han importado a ninguna base de datos.
- No se declara `proven_demand` ni se sube `evidence_backed_venture_score`.
- El razonamiento de este archivo es MODEL_HYPOTHESIS; las fuentes son
  PROVISIONALES y deben confirmarse en la instalación local del propietario
  contra sus `mission_id` reales.
- Kill conditions de las misiones (plan portable) siguen vigentes: si las
  misiones no encuentran manifestaciones independientes con URL+fecha+
  fragmento, la candidata se descarta aunque este archivo exista.
