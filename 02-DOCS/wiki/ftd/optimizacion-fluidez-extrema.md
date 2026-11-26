# FTD: Optimización Integral de Fluidez (Desktop + Web3D + Android APK)

## Intención y Alcance
Reducir drásticamente el tiempo de arranque, eliminar congelamientos de interfaz y suavizar la interacción en todas las versiones de **IndiServ Analytica** sin sacrificar ninguna funcionalidad (sesiones de 15 min, OTP Brevo, 44 claves de hardware, Gemelo Digital 3D, ni diseño Bento en tablets).

### Archivos modificados
- **IndiServ_Python (Windows / Linux / macOS)**
  - `core/cloud_gateway.py`: importación diferida (*lazy import*) de `supabase` dentro de `_get_client()` + `warm_up_async()` en segundo plano tras mostrar el Login.
  - `core/ui_theme.py`: eliminación de tormentas de redibujado de polígonos a 60 FPS en `boton`, `tarjeta`, `entrada` y `TarjetaMetrica`; `BarraMetrica` acotada a 6 pasos con soporte `animar=False`; `PuntoPulso` optimizado a 100 ms (~10 Hz); `fade_in` en 5 pasos (100 ms); `animar_entrada_panel` instantáneo en paneles grandes (`>= 620 px`).
  - `ui/dashboard_tabs.py`: renderizado diferido (*lazy*) de las 5 pestañas del Dashboard (solo se construye `General` inicialmente; las demás se crean al primer clic y quedan cacheadas); grilla de hilos lógicos en `CPU / RAM` reescrita sobre un único `tk.Canvas` (de ~80 widgets CTk a 1).
  - `main.py`: ocultamiento del fondo `1920×1080` (`place_forget`) en Dashboard y vistas internas opacas; redimensionamiento *debounced* solo cuando el fondo está visible; llamadas HTTP de login, registro, verificación OTP y reenvío 100% asíncronas en hilos *daemon* con helper seguro `_post_ui`.
  - `build_executable.py`: declaración explícita `--hidden-import supabase` para empaquetado seguro en PyInstaller.
- **IndiServ_Web3D (Web Vercel + Android Capacitor APK)**
  - `src/components/ChassisScene.jsx`: sustitución de `<Environment preset="city" />` (descarga HDRI externa) por `<Environment frames={1}>` procedural local con `<Lightformer>`; DPR (`[1, 1.25]`), `shadow-mapSize` (`512×512`) y `ContactShadows` (`256`) adaptados a móvil/tablet.
  - `src/components/HardwareAssembler.jsx`: precarga condicional de `phone-opt.glb` en Android nativo y `pc-opt.glb` solo en navegadores de escritorio.
  - `src/index.css`, `src/App.jsx`, `src/components/TechSidebar.jsx`: eliminación de `backdrop-filter: blur(...)` en tiempo real sobre pantallas táctiles/móviles, `contain: layout style` en `.instrument-card`, `-webkit-overflow-scrolling: touch` + `overscroll-behavior-y: contain` en listas y `React.memo` en botones de navegación.

## Checklist de Verificación y Evidencia Medida

- [x] **Benchmark Desktop Python (antes vs. después, mismo equipo)**
  - `import main`: **5.06 s → 0.45 s** (**−91.1%**, `supabase_at_import=False`)
  - `init + login`: **0.85 s → 0.22 s** (**−74.1%**)
  - `dashboard_render`: **4.32 s → 1.01 s** (**−76.6%**)
  - Widgets creados al abrir Dashboard: **704 → 218** (**−69.0%**)
  - Pestaña `CPU / RAM` (16 hilos): **1,427.5 ms → 392.5 ms** (**−72.5%**)
  - Cambio a pestaña ya cargada: **1.0 ms**
- [x] **Compilación y smoke test Python**: `PY_COMPILE_AND_AST_OK: 17 files`, todas las vistas (Login, OTP, Registro, Dashboard + 5 pestañas, Multisíntoma, Buscador IA, Stress Test, Árbol, Mapa 2D) validadas sin errores.
- [x] **Build Web3D + Capacitor Android**: `vite build` en `3.51 s` (`index.js` `210.77 kB` / `58.90 kB` gzip) y `npx cap sync android` en `0.525 s` sin errores.
- [x] **Compilación local Windows `.exe` y publicación en `origin/main` (Desktop + Web3D/APK)**.

## Siguiente Paso
Verificar la descarga de los nuevos artefactos generados por GitHub Actions (`.exe`, Linux, macOS y `.apk`) y probar el arranque instantáneo en PC y celular.
