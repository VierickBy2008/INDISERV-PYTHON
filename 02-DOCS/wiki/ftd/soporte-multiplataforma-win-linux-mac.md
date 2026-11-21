# Soporte Multiplataforma (Windows, Linux y macOS) y Workflow de Compilación

## Intent
Adaptar el motor de telemetría `core/hardware.py` para que funcione de forma nativa en **Windows**, **Linux** y **macOS** (detectando placa base, BIOS/firmware, factor de forma Laptop vs. Desktop, CPU, RAM, GPU, discos físicos/particiones y red/latencia con las herramientas nativas de cada sistema operativo), y crear un empaquetador multiplataforma (`build_executable.py`) junto con un workflow de **GitHub Actions** (`.github/workflows/build_multiplataforma.yml`) que compile automáticamente los ejecutables descargables para los tres sistemas operativos (`Windows .exe`, `Linux ELF` y `macOS .app/.zip`).

## Scope
- **Incluido**:
  - `IndiServ_Python/core/hardware.py`:
    - Soporte nativo Windows (WMI PowerShell + `psutil`), Linux (`/sys/class/dmi/id/`, `/proc/cpuinfo`, `lspci`/`nvidia-smi`, `lsblk -J`, `ping -c 1 -W 2`) y macOS (`sysctl`, `system_profiler -json`, `pmset -g batt`, `ping -c 1 -W 2000`).
    - Detección de factor de forma (`laptop` vs. `desktop`) en los 3 sistemas operativos.
    - `calcular_health_score()`: soporte tanto para unidad `"C"` (Windows) como para raíz `"/"` (Linux y macOS).
  - `IndiServ_Python/build_executable.py`: script unificado de compilación PyInstaller multiplataforma (`;` en Windows, `:` en Linux/macOS, `chmod +x` en Unix).
  - `IndiServ_Python/.github/workflows/build_multiplataforma.yml`: pipeline CI/CD que compila en matriz `windows-latest`, `ubuntu-latest` y `macos-latest` y publica los artefactos descargables.
  - Verificación multiplataforma y recompilación de `dist/IndiServ_Analytica.exe`.

## Checklist
- [x] Implementar recolectores multiplataforma (Windows, Linux y macOS) en `core/hardware.py` y actualizar `calcular_health_score()` para soportar partición raíz `"/"`.
- [x] Crear `build_executable.py` y `.github/workflows/build_multiplataforma.yml` para compilar ejecutables de Windows, Linux y macOS con PyInstaller.
- [x] Verificar con pruebas unitarias multiplataforma (`WINDOWS_OK`, `LINUX_OK`, `MACOS_OK`).
- [x] Recompilar `dist/IndiServ_Analytica.exe` mediante `python build_executable.py`.

## Evidence
- **Verificación de recolectores Windows, Linux y macOS**:
  - `WINDOWS_OK: {'tipo_equipo': 'laptop', 'chassis_types': [10], 'pc_system_type': 2, 'tiene_bateria': True}`
  - `LINUX_OK: ThinkPad T14 laptop AMD Ryzen 7 PRO 7840U AMD Radeon 780M`
  - `MACOS_OK: MacBookPro18,1 laptop Apple M1 Pro Apple M1 Pro GPU`
- **Compilación con `python build_executable.py`**:
  - `57944 INFO: Building EXE from EXE-00.toc completed successfully.`

## Next
Subir `IndiServ_Python` a un repositorio de GitHub para que `.github/workflows/build_multiplataforma.yml` genere y entregue automáticamente los 3 instaladores (`IndiServ_Analytica-Windows`, `IndiServ_Analytica-Linux` e `IndiServ_Analytica-macOS`).
