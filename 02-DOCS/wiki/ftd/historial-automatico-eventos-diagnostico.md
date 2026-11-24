# Historial Automático de Reportes por Evento (Desktop + Android)

## Intent
Registrar automáticamente un reporte privado en `reportes_diagnostico` (vinculado a `specs_json.owner_dni` y etiquetado con `specs_json.tipo_evento`) cada vez que el operador realiza un escaneo de hardware, un re-escaneo, un Micro-Stress Test CPU, una Auditoría IA o un diagnóstico del árbol experto, tanto en `IndiServ_Python` (Windows/Linux/macOS) como en `IndiServ_Web3D` (Android/Web).

## Scope
- **Incluido (`IndiServ_Python`)**:
  - `core/hardware.py`: incluir `tipo_evento` en `specs_json` dentro de `construir_resumen_para_bd`.
  - `main.py`: añadir `_registrar_evento_nube()` y dispararlo automáticamente en escaneo inicial, re-escaneo, finalización de Micro-Stress Test CPU y finalización de Árbol de Diagnóstico; enriquecer `modal_mis_tickets()` con insignia de `tipo_evento`, fecha/hora y resumen de diagnóstico.
- **Incluido (`IndiServ_Web3D`)**:
  - `src/utils/cloudHistory.js`: helper privado para registrar eventos móviles en `reportes_diagnostico` con `owner_dni` y `tipo_evento`.
  - `src/components/MobileScannerView.jsx`: registrar automáticamente escaneos/re-escaneos, Auditoría IA y Micro-Stress Test CPU completado.
  - `src/components/MobileDiagnosticView.jsx`: etiquetar `tipo_evento: "Árbol Diagnóstico"` y registrar automáticamente al llegar al dictamen si el usuario está autenticado.
  - `src/components/TicketLookupBar.jsx`: mostrar `tipo_evento`, fecha/hora y diagnóstico en el historial privado.
- **Excluido**:
  - Cambios al esquema SQL de Supabase (se usa `specs_json` jsonb existente).

## Checklist
- [x] Añadir `tipo_evento` en `IndiServ_Python/core/hardware.py` y registro automático + modal enriquecido en `IndiServ_Python/main.py`.
- [x] Crear `IndiServ_Web3D/src/utils/cloudHistory.js` y conectarlo en `MobileScannerView.jsx`, `MobileDiagnosticView.jsx` y `TicketLookupBar.jsx`.
- [x] Verificar con pruebas reales en Python (`py_compile` + test funcional) y Web3D (`npm run build` + `npx cap sync android`).
- [x] Hacer `git push` en ambos repositorios para regenerar ejecutables y APK.

## Evidence
- `IndiServ_Python`: `py_compile` + test de `construir_resumen_para_bd(..., owner_dni, tipo_evento)` → `OK_PYTHON_AUTO_HISTORY` (exit code 0).
- `IndiServ_Web3D`: `vite build` (`✓ built in 1.86s`) + `npx cap sync android` (`Sync finished in 0.156s`).
- Ambos repositorios subidos a `main` disparando GitHub Actions (Windows/Linux/macOS + Android APK) y Vercel.

## Next
Descargar las compilaciones actualizadas desde Releases y validar que cada escaneo, Micro-Stress Test y diagnóstico aparezca con su etiqueta de evento y fecha en **Mis Tickets**.
