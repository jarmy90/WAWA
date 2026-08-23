# Cómo abrir WAWA (Autonomous Business Lab)

WAWA es una **web local** (no una página pública de GitHub). Se abre en tu
propio ordenador en `http://127.0.0.1:8000`. Sigue estos pasos.

---

## 1. Descargar el paquete

1. Descarga el archivo `.zip.txt` más reciente de la carpeta
   `deliverables/packages/` del repositorio (o el que te haya pasado el
   supervisor).
2. **Importante**: el repositorio es **privado**, así que los enlaces RAW de
   GitHub no funcionan. Descarga desde la interfaz web de GitHub (con tu
   cuenta), desde el workspace de Freebuff, o por el canal que te indique el
   supervisor.
3. Guarda el archivo donde quieras, por ejemplo en `Documentos/WAWA`.

> **¿Cómo saber que estás viendo la versión correcta?**
> El topbar de la web muestra un chip con la versión (p. ej. `v0.11`).
> Si aparece un **banner rojo** "Frontend desactualizado", pulsa
> **Ctrl+F5** (recarga forzada) o reinicia WAWA. La interfaz de la
> iteración 011 incluye las pestañas **Campaña real** e **Ideas**, el botón
> **INICIAR CAMPAÑA REAL** y la franja de estado con **PRE_CYCLE** en la
> parte superior.

## 2. Extraerlo

- **Windows**: clic derecho sobre el archivo → **Extraer todo**.
  El `.zip.txt` es un ZIP normal; si Windows no lo reconoce, cambia el nombre
  a `wawa.zip` y vuelve a intentarlo.
- **Linux/macOS**: doble clic o `unzip archivo.zip.txt`.

Obtendrás una carpeta con `start_wawa.sh`, `START_WAWA.bat`, `app/`,
`frontend/`, etc.

## 3. Iniciar la web

Abre una terminal dentro de la carpeta extraída:

- **Windows**: haz doble clic en `START_WAWA.bat` (o en la terminal:
  `START_WAWA.bat`).
- **Linux/macOS**: `sh start_wawa.sh`

La primera vez tardará un poco (crea el entorno virtual e instala
dependencias). Al final se abrirá el navegador solo.

## 4. URL de acceso

```
http://127.0.0.1:8000
```

Si no se abre el navegador solo, escríbela a mano.

## 5. Detenerla

- **Windows**: doble clic en `STOP_WAWA.bat`.
- **Linux/macOS**: `sh stop_wawa.sh`

También puedes cerrar la ventana de la terminal, pero mejor usa los scripts.

## 6. Dónde están los archivos de ideas

- En la web: pestaña **Campaña real** → pulsa **INICIAR CAMPAÑA REAL**.
- En la pestaña **Ideas**: filtra y descarga **CSV**, **JSON**, **Markdown**,
  **Finalistas** o el **paquete de investigación (.zip)**.
- En disco: dentro de la carpeta de la web, `data/` (base de datos SQLite
  `data/abl.db`) y `logs/wawa.log` (registro del servidor).

## 7. Cómo iniciar una campaña

1. Abre la web.
2. Ve a la pestaña **Campaña real**.
3. Pulsa **INICIAR CAMPAÑA REAL**.
4. El sistema genera conceptos, los filtra, hace el torneo y llega solo hasta
   el punto donde necesita **investigación externa** (se detiene ahí
   honestamente: no inventa evidencia).

## 8. Cómo copiar misiones

Cuando la campaña esté en "Investigación externa necesaria":

1. Pulsa **Copiar misión** en cada misión.
2. Pega la misión en Freebuff (o en el modelo que prefieras).
3. Copia la respuesta.

## 9. Cómo importar respuestas

1. Vuelve a la web, pestaña **Campaña real**.
2. Pega la respuesta completa en el cuadro **Pegar investigación**.
3. Pulsa **Pegar investigación**.
4. El sistema la asocia a la misión, guarda lo que tenga fuentes verificables
   y continúa automáticamente. Si la respuesta no tiene URL + fecha +
   fragmento, se guarda como nota **sin** convertirse en evidencia.

## 10. El puerto 8000 está ocupado

- **Windows**: `START_WAWA.bat 8001` (o cualquier otro puerto).
- **Linux/macOS**: `sh start_wawa.sh 8001`
- Entonces entra en `http://127.0.0.1:8001`.

## 11. Python no está instalado

- **Windows**: descarga Python 3.10+ de python.org y marca la casilla
  **"Add Python to PATH"** al instalar.
- **macOS**: `brew install python` o instala desde python.org.
- **Linux**: `sudo apt install python3 python3-venv python3-pip` (o el
  gestor de paquetes de tu distribución).

## Notas de seguridad

- WAWA escucha **solo en tu ordenador** (`127.0.0.1`). No la expongas a
  Internet: aún no tiene autenticación, TLS ni rate limiting.
- No comparta el archivo `data/abl.db` ni ninguna clave de API que pueda
  existir en tu `.env` local.
- La economía es **simulada**: nunca mueve dinero real.
