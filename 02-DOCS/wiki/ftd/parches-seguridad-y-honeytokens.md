# Parches de Seguridad y Despliegue de Honeytokens (IndiServ_Python + IndiServ_Web3D)

## Intent
1. Corregir las vulnerabilidades detectadas en la auditoría de seguridad:
   - Hash criptográfico de contraseñas (`SHA-256` con sal por DNI `indiserv_v1$<sha256>`) compatible entre Python y Web/Android, con migración transparente de cuentas existentes al iniciar sesión.
   - Protección contra fuerza bruta en el login (bloqueo temporal tras 5 intentos fallidos).
   - IDs de ticket con entropía criptográfica (`secrets.token_hex(4)` en Python y `crypto.getRandomValues` en JS: 8 caracteres hex = 4,294 millones de combinaciones).
   - Blindaje de `analizar-dispositivo-ia/index.ts` (límite de payload `<= 4096` bytes, sanitización/truncado de campos antes del prompt de Gemini).
   - Protección de `.env` y `.env.*` en `IndiServ_Web3D/.gitignore` + enmascaramiento parcial de IP local en `specs_json`.
2. Desplegar 4 **Honeytokens (trampas de detección de intrusos)** reales que disparen una alerta silenciosa en Supabase (`sugerencias_locales` con prefijo `[ALERTA-HONEYTOKEN]` y `reportes_diagnostico`) y sean visibles en un visor de alertas de seguridad:
   - **Honeytoken 1 (Credencial Señuelo en Base de Datos / Login)**: DNI señuelo de administrador (`00000000` / `99999999` / `admin@indiserv.pe`) que nadie legítimo usa; cualquier intento de login o consulta sobre esas cuentas dispara alerta silenciosa con huella del equipo/navegador y finge error estándar.
   - **Honeytoken 2 (Ticket Señuelo en Buscador 3D / API)**: Tickets trampa (`0000-ADMIN-ROOT`, `TKT-ADMIN-CONFIDENTIAL`, `TKT-BACKUP-MASTER`); si alguien intenta abrirlos por ID o enumerarlos, registra la intrusión en Supabase y devuelve un señuelo inofensivo.
   - **Honeytoken 3 (Variables / Llaves Señuelo en `.env.example` y Honeypot Global `window.__INDISERV_ADMIN_DEBUG_KEY`)**: constante/objeto señuelo en consola DevTools y archivo `.env.example` con token canario (`INDISERV_CANARY_TOKEN_9F8A7B6C`); si un atacante lo invoca o lo usa, registra alerta inmediata.
   - **Honeytoken 4 (Trampa de Ruta / Parámetro URL `?admin=1` / `?debug_dump=1` en Web3D)**: si un atacante prueba parámetros típicos de explotación en la URL de Vercel/APK (`?admin=`, `?debug=`, `?dump=`, `?sql=`), se registra silenciosamente la alerta en Supabase.

## Scope
- **Incluido**:
  - `IndiServ_Python`: `core/security.py` (nuevo módulo de hashing + honeytokens + rate-limit), `core/cloud_gateway.py`, `core/hardware.py`, `main.py`, `.env.example`.
  - `IndiServ_Web3D`: `.gitignore`, `.env.example`, `src/utils/security.js` (nuevo módulo de hashing WebCrypto + honeytokens + rate-limit), `src/utils/cloudHistory.js`, `src/components/MobileAuthView.jsx`, `src/components/TicketLookupBar.jsx`, `src/App.jsx`, `supabase/functions/analizar-dispositivo-ia/index.ts`.

## Checklist
- [x] Crear `IndiServ_Python/core/security.py` y `IndiServ_Web3D/src/utils/security.js` (hashing compatible Python/JS, rate-limit de login, motor de disparo y consulta de Honeytokens).
- [x] Aplicar parches de seguridad en `IndiServ_Python` (`cloud_gateway.py`, `hardware.py`, `main.py`, `.env.example`) y migrar hashes de `usuarios_app` en Supabase.
- [x] Aplicar parches de seguridad y honeytokens en `IndiServ_Web3D` (`.gitignore`, `.env.example`, `MobileAuthView.jsx`, `TicketLookupBar.jsx`, `cloudHistory.js`, `App.jsx`, `analizar-dispositivo-ia/index.ts`).
- [x] Verificar con pruebas reales de login, disparo de honeytokens, `py_compile`, `npm run build` + `npx cap sync android` y `git push` en ambos repositorios.

## Evidence
- `HASH_MIGRATION_OK`: las 7 cuentas existentes en `usuarios_app` fueron migradas de texto plano a `indiserv_v1$<sha256_salted>` y se sembró el ticket canario `0000-ADMIN-ROOT` en `reportes_diagnostico`.
- `IndiServ_Python`: `py_compile` + pruebas unitarias de hash, verificación, rate-limit y honeytokens OK.
- `IndiServ_Web3D`: `vite build` (`✓ built in 3.30s`), `npx cap sync android` y verificación cruzada de hash WebCrypto === Python `hashlib` (`indiserv_v1$baef17bc...`).

## Next
Monitorear las alertas de intrusión desde el botón **🍯 Alertas Honeytoken** dentro de **🔒 Mis Tickets** (Desktop y Android/Web).
