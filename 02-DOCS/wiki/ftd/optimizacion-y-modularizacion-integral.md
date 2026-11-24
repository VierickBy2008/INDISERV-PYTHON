# FTD — Optimización y Modularización Integral (Python + Web3D + Android)

- **Fecha:** 2026-11-24
- **Carril:** FTD
- **Repositorios:** `IndiServ_Python`, `IndiServ_Web3D`
- **Objetivo:** Optimizar rendimiento (escaneo de hardware, cliente Supabase, loop 3D y bundle web/móvil), limpiar código muerto/scripts sueltos y modularizar archivos monolíticos sin romper ninguna funcionalidad existente.

---

## Alcance y Cambios Aplicados

### Fase 1 — Rendimiento (Python + Web3D)
1. **Prefetch WMI por lote + escaneo paralelo** ([core/hardware.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/core/hardware.py)):
   - Consolida las 9 clases CIM/WMI (`Win32_BaseBoard`, `Win32_BIOS`, `Win32_ComputerSystem`, `Win32_ComputerSystemProduct`, `Win32_SystemEnclosure`, `Win32_PhysicalMemory`, `Win32_VideoController`, `Win32_DiskDrive`, `Win32_Processor`) en un único subproceso PowerShell (`_wmi_batch_prefetch`) con caché de lectura protegida por `threading.Lock`.
   - Ejecuta `_wmi_batch_prefetch()`, `_escanear_licencia_windows()` y `_escanear_red_y_so()` en paralelo con `ThreadPoolExecutor(max_workers=3)` y limpia el caché en `finally:`.
   - Añade prefijos OEM NVMe (`mtfdk`, `mzvl`, `kbg`, `kxg`, `bc711`, `pc711`, `pc801`, `hfm`, `sn5`, `sn7`, `sn8`) para clasificar discos como `Micron MTFDKCD512QGN` correctamente como `NVMe SSD`.
2. **Singleton thread-safe de Supabase** ([core/cloud_gateway.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/core/cloud_gateway.py)):
   - `_get_client()` reutiliza una sola instancia (`_CLIENT_INSTANCE`) protegida con `_CLIENT_LOCK`, eliminando la reinstanciación del cliente HTTP/SDK por cada operación.
3. **Loop 3D sin `scene.traverse` a 60 FPS en reposo** ([HardwareAssembler.jsx](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/components/HardwareAssembler.jsx)):
   - Pre-cachea las mallas animables en `useMemo`, elimina el import sin usar `HardwarePart` y corta `useFrame` de inmediato mediante `settledRef` cuando los deltas convergen.
4. **Code-splitting + Lazy Loading del visor 3D** ([vite.config.js](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/vite.config.js), [App.jsx](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/App.jsx)):
   - `ChassisScene` cargado con `React.lazy` + `<Suspense>`.
   - Separación de chunks en `manualChunks`: `three-vendor`, `react-vendor`, `supabase-vendor`, `icons-vendor`.

### Fase 2 — Limpieza de Código Muerto y Scripts
- Eliminado `IndiServ_Web3D/Pc.jsx` (160 líneas huérfanas con 0 referencias en `src/`).
- Movidos 4 scripts utilitarios de la raíz de `IndiServ_Python` a `scripts/` (`test_supabase_insert.py`, `create_docx.py`, `create_docx_ms_project.py`, `generar_informe_tecnico.py`) tras confirmar 0 imports en producción.

### Fase 3 — Modularización
- Descompuesto el monolito `IndiServ_Python/main.py` (**3,079 -> 642 líneas**, -79.1%) en 4 mixins bajo `ui/` conservando intacta la API de `AppIndiServ`:
  - `ui/__init__.py` (8 líneas)
  - `ui/dashboard_tabs.py` (`DashboardMixin`, 651 líneas)
  - `ui/diagnostico_views.py` (`DiagnosticoMixin`, 591 líneas)
  - `ui/stress_y_arbol.py` (`StressYArbolMixin`, 725 líneas)
  - `ui/modales.py` (`ModalesMixin`, 577 líneas)
- Actualizado [build_executable.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/build_executable.py) con `--hidden-import` explícitos para `ui` y sus 4 submódulos.
- Extraída la base de conocimiento `DIAGNOSTIC_TREE` (8 ramas, 28 casos clínicos, árboles Sí/No) desde [MobileDiagnosticView.jsx](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/components/MobileDiagnosticView.jsx) (**1,316 -> 723 líneas**, -45.1%) hacia [mobileDiagnosticTree.js](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/data/mobileDiagnosticTree.js) (602 líneas).

---

## Checklist y Evidencia Observada

- [x] **Benchmark `LectorHardware.escanear_entorno()`:** reducido de **9.22 s** (línea base) a **2.18 s – 2.42 s** (~75% más rápido / ~4x) manteniendo las **44 llaves** intactas (`LENOVO LOQ 15ARP10E (83S0)`, `BIOS: LENOVO SUCN16WW 11/11/2025`, `partial_key: 3V66T`, `GPUs: 2`, disco reportado como `NVMe SSD Micron MTFDKCD512QGN-1BN1AABLA 477 GB`).
- [x] **Singleton Supabase:** `_get_client() is _get_client()` verificado en ejecución real.
- [x] **Compilación y auditoría AST Python:** `py_compile` aprobado en los **17 archivos** (`main.py`, `build_executable.py`, `core/*.py`, `ui/*.py`); auditoría AST de nombres indefinidos con **0 errores** en `main.py` y `ui/*.py`.
- [x] **Smoke test GUI en vivo (`AppIndiServ`):** las **8 vistas** (`pantalla_login`, `pantalla_registro`, `pantalla_dashboard`, `pantalla_multisintoma`, `pantalla_buscador`, `pantalla_stress_test`, `pantalla_diagnostico`, `pantalla_hardware_map`) y los **3 modales** (`modal_politica_privacidad`, `modal_sugerencias`, `modal_mis_tickets` con carga real de Supabase y cierre limpio `leak=0`) renderizaron sin excepciones.
- [x] **Build Web3D + Capacitor Android:** `vite build` completado en **1.76 s**; el chunk inicial `dist/assets/index-*.js` bajó de **1,689.4 kB** a **199.74 kB** (`56.41 kB` gzip, **-88.2%**), con `ChassisScene` lazy (`6.47 kB`) y `three-vendor` aislado (`1,068.12 kB`). `npx cap sync android` completado en **0.348 s**.
- [x] **Despliegue multiplataforma:** commits publicados en `origin/main` de ambos repositorios para disparar Vercel + GitHub Actions (Windows, Linux, macOS y Android APK).

---

## Siguiente Paso
Monitorear los pipelines de GitHub Actions y Vercel para confirmar que los nuevos binarios optimizados (`.exe`, Linux, macOS y `.apk`) queden publicados en verde.
