# Cómo abrir WAWA (Autonomous Business Lab) — v0.21.0 (iteración 022)

WAWA es una **web local** que se abre en tu propio ordenador en
`http://127.0.0.1:8000`. **No necesitas abrir PowerShell ni escribir ningún
comando**: solo descargar, extraer y hacer doble clic en `START_WAWA.bat`.

---

## Recorrido normal (7 pasos)

### 1. Extraer

1. Descarga el archivo `.zip.txt` más reciente de `deliverables/packages/`
   del repositorio (o el que te haya pasado el supervisor). El repositorio es
   **privado**: descarga desde la interfaz web de GitHub con tu cuenta o
   desde el workspace de Freebuff.
2. Clic derecho → **Extraer todo** (el `.zip.txt` es un ZIP normal; si
   Windows no lo reconoce, renómbralo a `wawa.zip` e inténtalo de nuevo).

### 2. Ejecutar START_WAWA.bat

- Haz **doble clic** en `START_WAWA.bat` (dentro de la carpeta extraída).
- La primera vez tarda un poco: crea el entorno, instala dependencias,
  **aplica automáticamente la activación comercial** (3 candidatas, 18
  misiones, 31 evidencias, ganadora y READY_TO_CONNECT_SERVICES) y abre el
  navegador solo.
- Verás el progreso en la consola: `[1/7]` … `[7/7]`. Si ya estaba aplicado,
  verás `BOOTSTRAP COMERCIAL YA APLICADO` y no cambia nada.

> **Versión correcta**: el topbar muestra `v0.21.0`. Si el botón muestra
> `ACTIVAR DEMO`, estás en modo real (correcto). Demo solo se activa si tú
> lo pides con el botón o con `?demo=1` en la URL, y al salir se limpia todo.

### 3. Abrir Candidatas

- En la web, abre la entrada **CANDIDATAS** (menú superior).
- Verás las **3 candidatas investigadas** con sus tarjetas. La ganadora lleva
  el distintivo **GANADORA DETERMINISTA PARA EXPERIMENTO** (no es "demanda
  validada": todavía no hay ningún pago real).

### 4. Copiar para GPT / Grok / Gemini

- En la tarjeta de la ganadora (o de cualquier candidata apta), pulsa
  **COPIAR PARA GPT**, **COPIAR PARA GROK** y **COPIAR PARA GEMINI**
  (los tres expedientes son el mismo contenido; solo cambia la cabecera).
- Pega cada expediente en el modelo correspondiente (GPT, Grok, Gemini) y
  copia la respuesta. También puedes **DESCARGAR EXPEDIENTE .MD**.

### 5. Importar respuestas

- Vuelve a CANDIDATAS y pega cada respuesta en **PEGAR RESPUESTA** (o sube el
  **ARCHIVO COMBINADO**).
- El sistema las valida, conserva el texto original y sintetiza
  automáticamente (PASO 3 · SÍNTESIS AUTOMÁTICA). Puedes continuar con una,
  dos o tres respuestas: la ausencia de revisión es neutral y nunca bloquea.

### 6. Conectar servicios

- Abre **CONECTAR SERVICIOS** (panel Mission Control). Introduce las claves
  de Stripe, email, hosting, dominio y analytics cuando las tengas.
- Botón **PROBAR CONEXIÓN** (comprobación local de formato) y
  **GUARDAR LOCALMENTE** (se guardan fuera de Git; la pantalla solo muestra
  estado y últimos 4 caracteres). GitHub permanece CONNECTED.

### 7. Autorizar ciclo

- Cuando todo esté conectado, pulsa **AUTORIZAR CICLO AUTÓNOMO · 30 DÍAS**
  y revisa el mandato (presupuesto, canales, acciones bloqueadas, éxito,
  pivot y cierre). Sin esa autorización explícita, WAWA permanece en
  `READY_TO_CONNECT_SERVICES` con producción bloqueada — por diseño.

---

## Detenerla

- **Windows**: doble clic en `STOP_WAWA.bat`.
- **Linux/macOS**: `sh stop_wawa.sh`

## Puerto 8000 ocupado

- **Windows**: doble clic en `START_WAWA.bat` con un argumento: crea un
  acceso directo o ejecuta `START_WAWA.bat 8001`.
- Entra en `http://127.0.0.1:8001`.

## Python no está instalado

- **Windows**: descarga Python 3.10+ de python.org y marca la casilla
  **"Add Python to PATH"** al instalar. Después vuelve a ejecutar
  `START_WAWA.bat`.

---

## Recuperación avanzada (solo si algo falla)

Normalmente no hace falta tocar nada de esto. El botón del panel
**REPARAR Y CONTINUAR AUTOMÁTICAMENTE** (Mission Control) reaparece si la
activación comercial falta o una ejecución quedó en FAILED: lo pulsa y ya
está. Si prefieres la línea de comandos (Windows, dentro de la carpeta de
WAWA, en **PowerShell** con la ruta correcta):

```powershell
.\START_WAWA.bat
```

Y si quieres ver el diagnóstico del bootstrap:

```powershell
.\scripts\startup_bootstrap.py   # o: .venv\Scripts\python.exe scripts\startup_bootstrap.py
```

> **Error típico**: ejecutar `.venv\Scripts\python.exe …` desde otra carpeta
> (p. ej. `C:\Users\j`) da "El módulo '.venv' no pudo cargarse". Ese comando
> solo funciona dentro de la carpeta de WAWA y con la ruta local `.\`.
> Con `START_WAWA.bat` no necesitas hacerlo nunca.

## Notas de seguridad

- WAWA escucha **solo en tu ordenador** (`127.0.0.1`). No la expongas a
  Internet: aún no tiene autenticación, TLS ni rate limiting.
- No compartas `data/abl.db` ni ninguna clave de API. Las credenciales del
  asistente se guardan en el archivo local de credenciales (fuera de Git) y
  nunca aparecen en logs, pantallas ni paquetes.
- La economía es **simulada** y la producción está **bloqueada por diseño**
  hasta que conectes los servicios y autorices el ciclo de 30 días.
