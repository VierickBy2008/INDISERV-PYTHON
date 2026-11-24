# Detección de Modelo Comercial de Laptop / Equipo (Windows, Linux y macOS)

## Intent
Identificar de forma precisa y 100% offline el modelo comercial exacto de laptops y PCs OEM en `IndiServ_Python` (Windows WMI/CIM, Linux `/sys/class/dmi/id/*`, macOS `system_profiler`/`sysctl`), evitando mostrar códigos crudos de placa base (`LNVNB161216`) o MTM aislados (`83S0`) como identidad principal, reflejándolo en `_tab_general` y en `specs_json`.

## Scope
- **Incluido (`IndiServ_Python`)**:
  - `core/hardware.py`: `_limpiar_campo_oem()`, `_resolver_modelo_comercial()`, `_escanear_modelo_equipo()`, actualización de `_tiene_firma_portatil()`, `LectorHardware.escanear_entorno()` y `construir_resumen_para_bd()`.
  - `main.py`: fila prioritaria **"Modelo del Equipo"** en `_tab_general()` debajo de **"Tipo de Equipo"**.
- **Excluido**:
  - `IndiServ_Web3D` y esquema SQL de Supabase.

## Checklist
- [x] Implementar `_resolver_modelo_comercial()` y `_escanear_modelo_equipo()` en `core/hardware.py` (Windows, Linux, macOS).
- [x] Actualizar `_tiene_firma_portatil()`, `escanear_entorno()` y `construir_resumen_para_bd()` en `core/hardware.py`.
- [x] Mostrar **"Modelo del Equipo"** con `Badge` en `_tab_general()` de `main.py`.
- [x] Validar con `py_compile`, prueba en vivo en Windows y mocks multiplataforma (Lenovo, ThinkPad, ASUS TUF, HP Victus, Apple Silicon, Linux DMI, PC armada), y subir a `origin main`.

## Evidence
- `python -m py_compile core/hardware.py main.py`: exit code 0.
- Prueba real en vivo en Windows: `{"equipo_fabricante": "LENOVO", "equipo_modelo_comercial": "LENOVO LOQ 15ARP10E (83S0)", "equipo_es_oem": true}`.
- Suite de pruebas unitarias (Lenovo LOQ, ThinkPad, ASUS TUF sin duplicación, HP Victus, Apple Silicon `Mac15,6`, Linux `/sys/class/dmi/id/*`, PC armada `To be filled by O.E.M.` y `construir_resumen_para_bd`): `ALL_LAPTOP_MODEL_TESTS_OK`.
- `IndiServ_Web3D`: sin modificaciones.

## Next
Esperar ~3 minutos a que termine `Build Multiplataforma` en GitHub Actions y descargar el nuevo ejecutable desde Releases.
