# Privacidad de Tickets en la Nube por Cuenta (Web/Android + Desktop)

## Intent
Restringir el listado de tickets en la nube (`reportes_diagnostico`) tanto en `IndiServ_Web3D` (Web/Android) como en `IndiServ_Python` (Windows/Linux/macOS) para que cada cuenta solo vea sus propios reportes (`specs_json->>owner_dni`), evitando exponer equipos de otros usuarios.

## Scope
- **Incluido**:
  - `IndiServ_Web3D/src/components/TicketLookupBar.jsx`: filtrar estrictamente por `specs_json->>owner_dni = user.dni`; si no hay sesión, no listar tickets ajenos y ofrecer inicio de sesión o búsqueda por ID exacto.
  - `IndiServ_Web3D/src/components/MobileDiagnosticView.jsx`: corregir payload de `upsert` (quitar columna inexistente `usuario_nick`) y guardar `owner_dni` y `owner_nick` dentro de `specs_json`.
  - `IndiServ_Web3D/src/App.jsx`: pasar `user={authUser}` y `onRequestLogin` a `TicketLookupBar`.
  - `IndiServ_Python/core/hardware.py`: incluir `owner_dni` dentro de `specs_json` en `construir_resumen_para_bd`.
  - `IndiServ_Python/core/cloud_gateway.py`: propagar `dni` a `construir_resumen_para_bd` en `subir_ticket` y añadir `listar_tickets_usuario(dni)` filtrado estrictamente por `specs_json->>owner_dni`.
  - `IndiServ_Python/main.py`: añadir modal/vista **"Mis Tickets en la Nube"** que muestre únicamente los reportes de `self.dni_usuario_activo` con acceso directo al Visor 3D.
- **Excluido**:
  - Cambios destructivos en el esquema SQL de Supabase (se reutiliza el campo JSONB existente `specs_json`).
  - Enlaces directos `?ticket=<ID>` en Vercel (siguen operando por ID exacto).

## Checklist
- [x] Filtrar `TicketLookupBar.jsx` por `specs_json->>owner_dni` y bloquear listado global sin sesión.
- [x] Corregir `MobileDiagnosticView.jsx` para guardar `owner_dni` en `specs_json` sin columnas inexistentes.
- [x] Propagar `owner_dni` en `IndiServ_Python/core/hardware.py` y `core/cloud_gateway.py` + `listar_tickets_usuario(dni)`.
- [x] Añadir vista privada "Mis Tickets en la Nube" en `IndiServ_Python/main.py`.
- [x] Verificar con pruebas reales contra Supabase, `npm run build` + `npx cap sync android`, y `git push` en ambos repositorios.

## Evidence
- Consulta de esquema `reportes_diagnostico`: columnas reales verificadas (`specs_json` jsonb soporta `.eq("specs_json->>owner_dni", dni)`).
- `IndiServ_Python`: `py_compile` y pruebas unitarias + consulta real Supabase (`OK Python privacy tests passed`, exit code 0). Push en `main`: `64f6b19`.
- `IndiServ_Web3D`: `vite build` (`✓ built in 2.59s`), `npx cap sync android` (`Sync finished in 0.283s`).
- Migración segura en Supabase (`reportes_diagnostico`): 22 tickets históricos asociados unívocamente a su `owner_dni` sin colisiones (`7550`: 11, `6130`: 8, `7059`: 3); los 2 tickets de prueba (`TKT-TEST-01`, `TKT-TEST-EXPANDED`) se mantuvieron excluidos. Verificado con `CloudGateway.listar_tickets_usuario()`.

## Next
Esperar a que finalicen los workflows de GitHub Actions en ambos repositorios para descargar el APK actualizado y los ejecutables Windows/macOS/Linux.
