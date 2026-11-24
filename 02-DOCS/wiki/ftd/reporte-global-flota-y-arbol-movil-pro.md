# Reporte Global Completo, Gestor de Flota por Fechas y Árbol Móvil Pro (x10)

## Intent
1. Incluir toda la ficha de identidad, BIOS, SO, licencia Windows, integridad Android, red, batería y errores detectados en el reporte global (`TechSidebar.jsx`, `construir_resumen_para_bd`, `cloudHistory.js`) para auditar flotas de 30+ PCs, laptops y teléfonos bajo una misma cuenta.
2. Reconstruir el centro de tickets (`TicketLookupBar.jsx` y `modal_mis_tickets`) con métricas de flota, búsqueda en vivo, filtros por tipo/alertas, agrupación por **Fecha** o **Equipo** y ordenamiento personalizable.
3. Mejorar x10 el Árbol de Diagnóstico Móvil (`MobileDiagnosticView.jsx`) pasando de 6 ramas planas a **8 ramas, 28 casos clínicos, asistente paso a paso Sí/No, diagnóstico Multisíntoma combinado, auto-triaje en vivo y checklist interactivo de reparación**.

## Scope
- **`IndiServ_Python`**: `core/hardware.py` (`_inferir_refrigeracion` para laptops, `construir_resumen_para_bd` con `bios.proveedor`, `mb_fabricante`, `mb_modelo`, `equipo_fabricante`, `errores_detectados`), `core/cloud_gateway.py` (`limite=120`), `main.py` (`modal_mis_tickets` con filtros, agrupación por fecha/equipo y ordenamiento).
- **`IndiServ_Web3D`**: `src/App.jsx`, `src/utils/cloudHistory.js`, `src/components/TechSidebar.jsx`, `src/components/TicketLookupBar.jsx`, `src/components/MobileDiagnosticView.jsx`.

## Checklist
- [x] Enriquecer `specs_json` en `core/hardware.py` y `cloudHistory.js` con identidad completa, BIOS, licencia/integridad y `errores_detectados`.
- [x] Mostrar el reporte global completo (identidad, BIOS, SO, licencia, hardware, red/batería y alertas) en `TechSidebar.jsx`.
- [x] Añadir métricas de flota, filtros, búsqueda en vivo, agrupación por Fecha/Equipo y ordenamiento en `TicketLookupBar.jsx` y `modal_mis_tickets`.
- [x] Reconstruir `MobileDiagnosticView.jsx` con 8 ramas, 28 casos, asistente Sí/No, modo Multisíntoma y checklist interactivo.
- [x] Verificar Python + `vite build` + `npx cap sync android`, subir a ambos repositorios y recompilar ejecutables.

## Evidence
- Verificación de `construir_resumen_para_bd` (`errores_detectados`, `bios.proveedor`, `Sistema Térmico Integrado de Laptop`), `py_compile`, `npm run build` y `npx cap sync android`.
- Push a `origin/main` en ambos repositorios disparando Vercel y GitHub Actions (Windows, Linux, macOS y Android APK) + compilación local de `dist/IndiServ_Analytica.exe`.

## Next
Abrir cualquier reporte desde **Mis Tickets** para ver la ficha completa con modelo, BIOS, licencia y errores, y probar el nuevo Árbol de Diagnóstico Pro en móvil.
