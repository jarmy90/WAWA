# Workflow de revisión externa (DEVELOPMENT_AND_REVIEW)

> **Instrucción permanente del proyecto.** Este documento forma parte del
> contrato de trabajo del repositorio: cualquier agente de desarrollo debe
> leerlo antes de empezar una iteración, junto con `AGENTS.md`,
> `docs/OPERATING_MODES.md` y `docs/ITERATION_HISTORY.md`.

## Fases del proyecto

El proyecto tiene dos fases **completamente diferenciadas**:

1. **DEVELOPMENT_AND_REVIEW** — supervisión externa, iteraciones y paquetes
   `.zip.txt`. Es la fase actual.
2. **AUTONOMOUS_PRODUCTION** — trabajo autónomo, continuo y silencioso, sin
   iteraciones rutinarias con Freebuff. Requiere activación expresa y auditable
   del propietario (ver `docs/OPERATING_MODES.md`).

La fase no cambia con este documento: se controla con el mecanismo de modos
(`/api/engine/mode` + configuración), nunca mezclando estados.

## Bucle de iteración

1. Freebuff inspecciona el repositorio.
2. Freebuff implementa una iteración.
3. Freebuff ejecuta pruebas y verificaciones.
4. Freebuff responde con un **informe textual completo** (28 puntos, ver abajo).
5. Freebuff genera un **paquete ZIP** del repositorio.
6. Freebuff cambia **únicamente la extensión** a `.zip.txt` (el contenido
   binario permanece intacto).
7. Freebuff **verifica** que el archivo sigue siendo un ZIP válido y cumple
   todas las comprobaciones.
8. El propietario descarga el archivo y se lo envía al supervisor externo.
9. El supervisor revisa el proyecto.
10. El propietario devuelve el prompt de corrección o de siguiente iteración.

Este procedimiento **no debe convertirse en dependencia** del funcionamiento
diario del producto terminado (AUTONOMOUS_PRODUCTION).

## Informe obligatorio tras cada iteración

Al terminar cada iteración, el agente responde con un informe estructurado con
estos 28 puntos (sin frases genéricas; distinguir claramente entre
*implementado / probado automáticamente / verificado manualmente / simulado /
parcial / pendiente / bloqueado*):

1. Número de iteración.
2. Objetivo.
3. Resumen del trabajo realizado.
4. Archivos nuevos.
5. Archivos modificados.
6. Archivos eliminados.
7. Decisiones técnicas tomadas.
8. Dependencias añadidas o retiradas.
9. Cambios en arquitectura.
10. Cambios en modelos de datos.
11. Cambios en prompts o agentes.
12. Cambios en scoring y reglas de decisión.
13. Cambios en seguridad o gestión presupuestaria.
14. Pruebas ejecutadas.
15. Comandos exactos utilizados.
16. Número de pruebas superadas.
17. Número de pruebas fallidas.
18. Errores encontrados y correcciones aplicadas.
19. Comprobaciones manuales realizadas.
20. Funcionalidades no verificadas.
21. Elementos simulados o mock.
22. Dependencias de servicios externos.
23. Limitaciones conocidas.
24. Riesgos abiertos.
25. Deuda técnica.
26. Elementos concretos que debe supervisar el revisor externo.
27. Instrucciones de instalación y ejecución.
28. Próximo paso recomendado.

## Paquete obligatorio para revisión

**Siempre** que una iteración cree, elimine o modifique código, tests,
configuración, documentación técnica, prompts, scoring, dependencias, base de
datos o arquitectura:

1. Crear un ZIP real (script: `scripts/package_for_review.py`).
2. Cambiar **solo** la extensión final a `.zip.txt`.
3. El contenido binario debe permanecer intacto.

Prohibido: convertirlo a texto, reabrirlo con editor, codificarlo en Base64,
añadir texto al principio/final, entregar un TXT descriptivo en su lugar,
entregar solo archivos modificados, o inventar enlaces de descarga.

Formato del nombre:

```
autonomous-business-lab_iteracion-NNN_AAAA-MM-DD.zip.txt
```

Ejemplo: `autonomous-business-lab_iteracion-002_2026-08-23.zip.txt`
La numeración es **consecutiva y no se reutiliza**: se detecta automáticamente
la última iteración (ver `docs/ITERATION_HISTORY.md`).

### Contenido del paquete (debe incluir)

Código fuente, backend, frontend, tests, scripts, configuración **sin
secretos**, migraciones, datos seed pequeños, prompts de agentes, reglas de
scoring, documentación, README.md, AGENTS.md, historial de iteraciones,
manifiesto de la entrega, archivos de dependencias, instrucciones de
instalación, ejecución y pruebas.

### Contenido del paquete (debe excluir)

`.git/`, `.env`, claves API, tokens, contraseñas, claves privadas, wallets
reales, frases de recuperación, cookies/sesiones, `node_modules/`, entornos
virtuales, cachés, paquetes de iteraciones anteriores, logs pesados, builds
descargables, datos personales, datos privados de clientes, bases de datos de
producción, archivos temporales, dependencias reinstalables.

## Manifiesto de cada iteración

Cada entrega crea `deliverables/ITERATION_NNN_MANIFEST.md` (plantilla en
`deliverables/MANIFEST_TEMPLATE.md`). Debe incluir: identificador, fecha/hora,
objetivo, estado, resumen de cambios, archivos nuevos/modificados/eliminados,
cambios arquitectónicos, de agentes, de scoring, de seguridad, dependencias,
comandos de instalación/ejecución/pruebas, resultado exacto de las pruebas,
problemas conocidos, limitaciones, riesgos, componentes a revisar por el
supervisor, próxima acción, nombre/tamaño/SHA-256 del paquete y, si Git está
disponible, commit actual, estado del repo, `git diff --stat` y lista de
archivos cambiados. **No** incluir `.git` en el paquete.

## Creación y verificación del paquete

- `scripts/package_for_review.py`: determina el número de iteración, comprueba
  que existe el manifiesto, aplica exclusiones, detecta posibles secretos,
  crea el ZIP completo, evita incluirse a sí mismo y paquetes anteriores, lo
  renombra a `.zip.txt`, calcula su SHA-256, muestra ruta/tamaño/hash y
  registra la entrega en el historial.
- `scripts/verify_review_package.py`: comprueba existencia, sufijo `.zip.txt`,
  firma binaria ZIP, apertura como ZIP, integridad, extracción temporal, ausencia
  de path traversal, ausencia de rutas absolutas, presencia de README.md,
  AGENTS.md y el manifiesto correcto, ausencia de archivos prohibidos, ausencia
  de secretos detectables, ausencia del propio paquete, y coincidencia del
  SHA-256 con el registrado.

> **Nota sobre el SHA-256 registrado**: el manifiesto vive DENTRO del paquete
> y contiene su propio hash, lo que crea una referencia circular (el hash de
> un archivo depende de su contenido, que incluye el hash). Por eso el SHA-256
> registrado es el **hash canónico del contenido del ZIP** (nombres + bytes de
> todos los miembros, EXCEPTO el propio manifiesto). Es autoconsistente,
> detecta cualquier manipulación del resto del paquete y permite que la
> verificación pase tanto en el workspace como desde un paquete extraído por
> el revisor. El verifier imprime además el hash del archivo completo como
> referencia.

**Obligatorio ejecutar la verificación antes de entregar el archivo.** Si
falla: no declarar válido el paquete, corregir, regenerar, repetir la
verificación y explicar el fallo y su corrección.

### Entrega del archivo

Facilitar un enlace directo descargable o adjuntar el archivo usando las
posibilidades reales del entorno. Si no es posible: indicarlo claramente,
proporcionar la ruta exacta, explicar cómo descargarlo. **No inventar enlaces
ni afirmar que está adjunto cuando no lo está.**
