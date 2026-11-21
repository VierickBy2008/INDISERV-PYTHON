# Eliminación de Bitácora Local, Política de Privacidad en Registro (UNMSM), Animaciones 60 FPS y Eliminación de Esquinas Negras

## Intent
1. Eliminar la opción **Bitácora Local** del dashboard de `IndiServ_Python`.
2. Exigir la aceptación de la **Política de Privacidad y Términos y Condiciones** (con declaración expresa del Padrón Oficial Público de la UNMSM y Ley N.° 29733) únicamente en la pantalla de **Registro**.
3. Incorporar un motor de **animaciones fluidas a 60 FPS (`16 ms` por frame)** en todos los módulos (`core/ui_theme.py`, `main.py` y `core/hardware_map.py`).
4. Eliminar las esquinas negras triangulares de los paneles principales que flotan sobre el fondo `assets/fondo.jpg`.

## Scope
- **Incluido**:
  - `core/legal.py` y `POLITICA_DE_PRIVACIDAD.md`: Política de Privacidad y Términos completos.
  - `core/ui_theme.py`: motor de interpolación a 60 FPS (`FRAME_MS = 16`, `_lerp_hex`, `animar_entrada_panel`, hover suave a 60 FPS, `BarraMetrica`, `PuntoPulso`, `Sparkline`, `fade_in` y `toast` sin esquinas negras).
  - `core/hardware_map.py`: animación a 60 FPS en el esquema 2D (`MotherboardMapView._start_60fps_schematic_anim`).
  - `main.py`:
    - Casilla obligatoria de términos únicamente en `pantalla_registro()`.
    - `corner_radius=0` en los 9 contenedores principales colocados directamente sobre `self.bg_label` (`fondo.jpg`) para suprimir los triángulos negros exteriores manteniendo los bordes redondeados en las tarjetas internas.
  - Recompilación de `dist/IndiServ_Analytica.exe` y verificación con `test_supabase_insert.py`.

## Checklist
- [x] Dejar la casilla obligatoria de Política de Privacidad únicamente en `pantalla_registro()` (`main.py`).
- [x] Implementar el motor de animaciones a 60 FPS (`16 ms`) en `core/ui_theme.py`, `core/hardware_map.py` y `main.py`.
- [x] Eliminar los triángulos negros de las esquinas en los 9 módulos principales (`main.py`) y `toast` (`core/ui_theme.py`).
- [x] Ejecutar `test_supabase_insert.py` (8 suites) verificando código de salida `0`.
- [x] Recompilar `dist/IndiServ_Analytica.exe`.

## Evidence
- **Suite `test_supabase_insert.py`**: 8/8 suites `[OK] PASSED` (exit code `0`).
- **Compilación de `dist/IndiServ_Analytica.exe` (PyInstaller 6.22.3)**:
  - `63831 INFO: Building EXE from EXE-00.toc completed successfully.`

## Next
Ejecutar `dist/IndiServ_Analytica.exe` y confirmar visualmente que los bordes sobre `fondo.jpg` se ven limpios sin esquinas negras.
