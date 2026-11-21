# Empaquetado de IndiServ Analytica como Ejecutable Autónomo (.exe)

## Intent
Convertir `IndiServ_Python` en un ejecutable autónomo de Windows (`dist/IndiServ_Analytica.exe`) mediante PyInstaller para que cualquier usuario pueda descargarlo y ejecutarlo sin instalar Python ni librerías externas, resolviendo correctamente rutas empaquetadas (`sys._MEIPASS`) y evitando que los subprocesos WMI/ping abran ventanas de consola negras.

## Scope
- **Incluido**:
  - `IndiServ_Python/main.py`: helper `_resource_path()` compatible con `sys._MEIPASS` para cargar `assets/fondo.jpg` y visualización de `TIPO DE EQUIPO` en la pestaña General.
  - `IndiServ_Python/core/hardware.py`: uso de `subprocess.CREATE_NO_WINDOW` en `_wmi_query()` y `_ping_latencia()` para que no parpadeen ventanas de consola durante el escaneo en modo `--windowed`, además de `errors="replace"` para evitar `UnicodeDecodeError` con caracteres locales en `ping`.
  - `IndiServ_Python/requirements.txt`: registro de dependencias del proyecto.
  - Compilación con PyInstaller (`--onefile --windowed --name IndiServ_Analytica --add-data "assets;assets" --collect-all customtkinter`) generando `dist/IndiServ_Analytica.exe`.
- **Excluido**:
  - Firma digital Authenticode con certificado EV/OV comercial.

## Checklist
- [x] Actualizar `main.py` con `_resource_path()` para resolver `assets/fondo.jpg` tanto en desarrollo como dentro del ejecutable PyInstaller (`sys._MEIPASS`).
- [x] Actualizar `core/hardware.py` con `CREATE_NO_WINDOW` y `errors="replace"` en las llamadas `subprocess.run` (`_wmi_query` y `_ping_latencia`).
- [x] Poblar `requirements.txt` e instalar `pyinstaller`.
- [x] Compilar `dist/IndiServ_Analytica.exe` con PyInstaller y verificar que el binario se generó sin errores.

## Evidence
- **Compilación con PyInstaller 6.22.3 (Python 3.13.14)**:
  - `61942 INFO: Building EXE from EXE-00.toc completed successfully.`
  - `61973 INFO: Build complete! The results are available in: C:\Users\Lenovo\Desktop\By2002\IndiServ_Python\dist`
- **Archivo generado**:
  - `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\dist\IndiServ_Analytica.exe`

## Next
Distribuir `dist/IndiServ_Analytica.exe` directamente o publicarlo en GitHub Releases para descarga pública.
