# Reintegración Laptop/Desktop y Empaquetado .exe (Versión Rediseñada)

## Intent
Reintegrar la detección automática `laptop` vs. `desktop` (`_escanear_tipo_equipo` y `specs_json.tipo_equipo`), el modo silencioso de subprocesos (`CREATE_NO_WINDOW`) y el soporte de recursos empaquetados (`_resource_path` con `sys._MEIPASS`) sobre la nueva versión rediseñada de `IndiServ_Python` (`main.py` 2,495 líneas + `core/ui_theme.py`), y recompilar `dist/IndiServ_Analytica.exe`.

## Scope
- **Incluido**:
  - `core/hardware.py`: añadir `_clasificar_tipo_equipo()`, `_escanear_tipo_equipo()`, `CREATE_NO_WINDOW` en `_wmi_query()` y `_ping_latencia()`, e incluir `tipo_equipo` y `chassis_types` en `specs_json`.
  - `main.py`: añadir `_resource_path()` para resolver `assets/fondo.jpg` dentro de PyInstaller y mostrar `Tipo de Equipo` (`Laptop / Portátil` o `PC de Escritorio`) en la tarjeta de placa base del nuevo dashboard.
  - Compilación de `dist/IndiServ_Analytica.exe` con PyInstaller (`--onefile --windowed --add-data "assets;assets" --collect-all customtkinter`).
- **Excluido**:
  - Cambios en `IndiServ_Web3D` (ya subido a `origin/main` en `dc16ea4`).

## Checklist
- [x] Reintegrar `_escanear_tipo_equipo()`, `specs_json.tipo_equipo` y `CREATE_NO_WINDOW` en `core/hardware.py`.
- [x] Integrar `_resource_path()` para `assets/fondo.jpg` y mostrar `Tipo de Equipo` en `main.py`.
- [x] Recompilar `dist/IndiServ_Analytica.exe` con PyInstaller y confirmar generación sin errores.

## Evidence
- **Verificación de sintaxis y detección en Python**:
  - `python -m py_compile main.py core/hardware.py` (exit code 0)
  - `OK: {'tipo_equipo': 'laptop', 'chassis_types': [10], 'pc_system_type': 2, 'tiene_bateria': True} laptop`
- **Recompilación de `dist/IndiServ_Analytica.exe` (PyInstaller 6.22.3)**:
  - `62973 INFO: Building EXE from EXE-00.toc completed successfully.`
  - `63012 INFO: Build complete! The results are available in: C:\Users\Lenovo\Desktop\By2002\IndiServ_Python\dist`

## Next
Probar `dist/IndiServ_Analytica.exe` en el escritorio para verificar la nueva interfaz rediseñada junto con la detección de Laptop/PC y el enlace al Gemelo Digital 3D en Vercel.
