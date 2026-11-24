# Soporte Multiplataforma (Windows, Linux y macOS) y Workflow de Compilación

## Intent
Adaptar el motor de telemetría `core/hardware.py` para que funcione de forma nativa en **Windows**, **Linux** y **macOS**, y crear un empaquetador multiplataforma (`build_executable.py`) junto con un workflow de **GitHub Actions** (`.github/workflows/build_multiplataforma.yml`) que compile automáticamente los ejecutables descargables para los tres sistemas operativos (`Windows .exe`, `Linux ELF` y `macOS .app/.zip`).

## Scope
- **Incluido**:
  - `IndiServ_Python/core/hardware.py`: soporte nativo Windows (WMI PowerShell + `psutil`), Linux (`/sys/class/dmi/id/`, `/proc/cpuinfo`, `lspci`/`nvidia-smi`, `lsblk -J`, `ping -c 1 -W 2`) y macOS (`sysctl`, `system_profiler -json`, `pmset -g batt`, `ping -c 1 -W 2000`).
  - `IndiServ_Python/build_executable.py`: script unificado de compilación PyInstaller multiplataforma (`;` en Windows, `:` en Linux/macOS, `chmod +x` en Unix).
  - `IndiServ_Python/.github/workflows/build_multiplataforma.yml`: pipeline CI/CD que compila en matriz `windows-latest`, `ubuntu-latest` y `macos-latest`.
  - Push a `https://github.com/VierickBy2008/INDISERV-PYTHON.git` (`main`).

## Checklist
- [x] Implementar recolectores multiplataforma (Windows, Linux y macOS) en `core/hardware.py` y actualizar `calcular_health_score()`.
- [x] Crear `build_executable.py` y `.github/workflows/build_multiplataforma.yml`.
- [x] Verificar con pruebas unitarias multiplataforma (`WINDOWS_OK`, `LINUX_OK`, `MACOS_OK`).
- [x] Recompilar `dist/IndiServ_Analytica.exe` mediante `python build_executable.py`.
- [x] Subir cambios a `https://github.com/VierickBy2008/INDISERV-PYTHON.git` (`81f5d42..6a8850a  main -> main`).

## Evidence
- **Verificación de recolectores Windows, Linux y macOS**:
  - `WINDOWS_OK: {'tipo_equipo': 'laptop', 'chassis_types': [10], 'pc_system_type': 2, 'tiene_bateria': True}`
  - `LINUX_OK: ThinkPad T14 laptop AMD Ryzen 7 PRO 7840U AMD Radeon 780M`
  - `MACOS_OK: MacBookPro18,1 laptop Apple M1 Pro Apple M1 Pro GPU`
- **Compilación local (`dist/IndiServ_Analytica.exe`)**:
  - `57944 INFO: Building EXE from EXE-00.toc completed successfully.`
- **Push a GitHub (`VierickBy2008/INDISERV-PYTHON`)**:
  - `To https://github.com/VierickBy2008/INDISERV-PYTHON.git  81f5d42..6a8850a  main -> main`

## Next
Descargar los artefactos compilados (`IndiServ_Analytica-Windows`, `IndiServ_Analytica-Linux` e `IndiServ_Analytica-macOS`) desde `https://github.com/VierickBy2008/INDISERV-PYTHON/actions`.
