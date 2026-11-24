# Auditoría Real de Licencia de Windows (OEM / Retail vs. KMS No Oficial)

## Intent
Incorporar en `IndiServ_Python` (exclusivo para Windows, manteniendo compatibilidad POSIX total en Linux/macOS) un detector nativo de solo lectura que clasifique la licencia de Windows mediante `SoftwareLicensingProduct`, `SoftwareLicensingService` y `winreg` sin exponer claves completas, mostrándolo en la pestaña **General** del Dashboard y registrándolo en `specs_json["so"]["licencia"]`.

## Scope
- **Incluido (`IndiServ_Python`)**:
  - `core/hardware.py`: `_clasificar_licencia_windows(...)` (función pura testeable), `_escanear_licencia_windows()`, integración en `LectorHardware.escanear_entorno()` y `construir_resumen_para_bd()` (`specs_json["so"]["licencia"]`).
  - `core/diagnostico.py`: observación informativa en `EvaluadorTelemetria.evaluar()` si `sospecha_kms` es `True` (sin penalizar el puntaje de hardware).
  - `main.py`: fila **"Licencia Windows"** con `Badge` y nota honesta en `_tab_general()`.
- **Excluido**:
  - `IndiServ_Web3D`, esquema SQL de Supabase y modificación de claves/licencias del sistema (estrictamente solo lectura).

## Checklist
- [x] Implementar `_clasificar_licencia_windows()` y `_escanear_licencia_windows()` en `core/hardware.py` (con `winreg` condicional solo en `win32` y sin exponer `OA3xOriginalProductKey`).
- [x] Integrar `licencia_windows` en `escanear_entorno()`, `construir_resumen_para_bd()` y `EvaluadorTelemetria.evaluar()`.
- [x] Añadir la fila **Licencia Windows** + `Badge` en `_tab_general()` de `main.py`.
- [x] Validar con `py_compile`, prueba real en vivo en Windows y suite de mocks unitarios (`OEM_DM`, `RETAIL`, `VOLUME_KMSCLIENT`, `MAK`, `Sin activar`, `POSIX`), y subir a `origin main`.

## Evidence
- `python -m py_compile main.py core/hardware.py core/diagnostico.py`: exit code 0.
- Prueba real en vivo en Windows: `{"estado": "Original Retail / Digital", "canal": "RETAIL", "etiqueta_badge": "ORIGINAL RETAIL", "permanente": true, "tiene_llave_uefi": false, "sospecha_kms": false, "dias_restantes": null}`.
- Suite de pruebas unitarias (OEM_DM + UEFI, RETAIL, VOLUME_KMSCLIENT público/localhost, KMS corporativo, MAK, Sin activar, POSIX linux/darwin, `specs_json["so"]["licencia"]` y `EvaluadorTelemetria` sin penalizar `health_score`): `ALL_WINDOWS_LICENSE_TESTS_OK`.
- `IndiServ_Web3D`: `git status --short` confirmó cero archivos de código modificados.

## Next
Esperar ~3 minutos a que termine `Build Multiplataforma (Windows, Linux, macOS)` en GitHub Actions y probar el nuevo `IndiServ_Analytica.exe`.
