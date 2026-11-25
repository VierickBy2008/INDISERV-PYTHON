# Plan de Implementación — Sesión Segura de 15 Minutos, Dispositivos Confiables y OTP por Correo

> **Para agentes ejecutores:** Usar `superpowers:executing-plans` o `superpowers:subagent-driven-development` tarea por tarea. Cada paso usa casillas (`- [ ]`) y exige verificación antes de pasar al siguiente.

**Objetivo:** Implementar en todas las versiones de **IndiServ Analytica** (Desktop Windows/Linux/macOS, Web Vercel y Android APK) sesiones persistentes de 15 minutos validadas en servidor, registro de dispositivos confiables (`dispositivos_confiables`) y verificación obligatoria por código OTP de 6 dígitos vía correo electrónico (Brevo API) tanto en registro como en inicio de sesión desde dispositivos nuevos.

**Arquitectura:** Un único punto de entrada en servidor (`supabase/functions/auth-otp/index.ts`) ejecutado con `SUPABASE_SERVICE_ROLE_KEY` orquesta todas las operaciones de identidad, firma HMAC-SHA256 de códigos OTP, consumo atómico en PostgreSQL (`FOR UPDATE`), emisión/validación de tokens opacos de 256 bits (`sesiones_activas`) y envío real de correos vía Brevo HTTPS API. Se revoca el acceso directo del rol `anon` sobre funciones sensibles de registro/login para impedir bypasses por `curl`.

**Stack Tecnológico:** PostgreSQL (Supabase RLS + PL/pgSQL `SECURITY DEFINER`), Supabase Edge Functions (Deno TypeScript), Brevo Transactional Email API v3 (HTTPS), Python 3.13 + CustomTkinter (`IndiServ_Python`), React + Vite 8 + Capacitor 8 (`@capacitor/device`, `IndiServ_Web3D`).

**Especificación de diseño:** [2026-11-25-sesion-15m-otp-dispositivos-design.md](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/02-DOCS/superpowers/specs/2026-11-25-sesion-15m-otp-dispositivos-design.md)

## Restricciones Globales

- Validación 100 % en servidor: nunca confiar en reloj local, `localStorage` ni archivos JSON para decidir expiración de 15 min ni validez de OTP.
- Ventana fija de sesión: `15 minutes` exactos desde emisión (`now() + interval '15 minutes'`) en PostgreSQL; *fail-closed* si no hay conexión al reabrir.
- Caducidad de OTP: `10 minutes`, máximo `5` intentos por desafío, cooldown de reenvío `60 s`, tope de `5` OTPs/hora por DNI/IP.
- Cero exposición del código OTP en respuestas HTTP ni en logs de cliente; solo se almacena `HMAC-SHA256(OTP_PEPPER, ...)` en BD.
- Compatibilidad estricta con el padrón UNMSM (`padron_oficial`), 5 Honeytokens existentes, políticas RLS de `reportes_diagnostico` y `sugerencias_locales`, y compilación multiplataforma (`PyInstaller`, `vite build`, `cap sync android`).
- Secretos requeridos en Supabase Dashboard antes de activar en producción: `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `OTP_PEPPER`.

## Focos de Revisión (5 modos de fallo críticos)

1. **Condición de carrera (*race condition*) en verificación OTP:** dos peticiones simultáneas con el mismo código de 6 dígitos solo pueden aprobarse una vez (`SELECT ... FOR UPDATE` en PostgreSQL).
2. **Fallo de envío en Brevo (401/429/500):** si la API de Brevo rechaza el envío, el desafío recién creado debe marcarse `usado = true` y devolver HTTP `502` sin consumir el cooldown ni dejar el registro bloqueado.
3. **Robo de token de sesión a otro equipo:** un `session_token` copiado desde la PC A a la PC B debe ser rechazado por `session_validate` al no coincidir `device_hash`.
4. **Usuario ya existente antes de la migración:** al iniciar sesión por primera vez en su equipo actual, `dispositivos_confiables` estará vacío para su DNI → recibe 1 OTP al correo guardado en `usuarios_app`, verifica, y el equipo queda registrado como confiable para futuros logins.
5. **Bypass directo por PostgREST (`curl`):** una llamada directa con `anon` key a `/rest/v1/rpc/registrar_usuario_seguro` o `GET /rest/v1/codigos_otp` debe fallar con `401`/`42501` o `0` filas.

---

### Tarea 1: Migración SQL de Tablas, RLS y Funciones Atómicas en PostgreSQL

**Archivos:**
- Crear: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\supabase\migrations\20261125_sessions_devices_otp.sql`
- Crear (copia de referencia): `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\scripts\20261125_sessions_devices_otp.sql`

**Interfaces:**
- Produce tablas con RLS activado y `0` políticas para `anon`: `public.dispositivos_confiables`, `public.codigos_otp`, `public.sesiones_activas`.
- Produce funciones SQL `SECURITY DEFINER` (solo `GRANT EXECUTE` a `service_role`):
  - `public.consumir_otp_atomico(p_challenge_id uuid, p_device_hash text, p_code_hmac text) -> jsonb`
  - `public.emitir_sesion_15m(p_dni text, p_device_hash text, p_token_hash text) -> jsonb`
  - `public.validar_sesion_15m(p_token_hash text, p_device_hash text) -> jsonb`
  - `public.revocar_sesion_15m(p_token_hash text, p_device_hash text) -> jsonb`
- Revoca `EXECUTE` de `anon` y `authenticated` sobre `autenticar_usuario` y `registrar_usuario_seguro`.

- [ ] **Paso 1:** Redactar `20261125_sessions_devices_otp.sql` con las 3 tablas, índices (`(dni, device_hash)`, `(token_hash)`, `(dni, creado_en)`), `ENABLE ROW LEVEL SECURITY`, `REVOKE ALL FROM anon, authenticated` y las 4 funciones atómicas con `SELECT ... FOR UPDATE`.
- [ ] **Paso 2:** Validar sintaxis SQL y ausencia de políticas permisivas para `anon` en las 3 tablas nuevas.
- [ ] **Paso 3:** Documentar el comando de ejecución en Supabase Dashboard (SQL Editor) para aplicar en producción en la Tarea 5.

---

### Tarea 2: Supabase Edge Function `auth-otp` + Envío de Correos vía Brevo

**Archivos:**
- Crear: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\supabase\functions\auth-otp\index.ts`
- Test: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\supabase\functions\auth-otp\index.test.ts` (pruebas unitarias de lógica HMAC, enmascarado de correo, comparación en tiempo constante y validación de acciones).

**Interfaces:**
- Consumes: Tablas y funciones SQL de Tarea 1 vía `createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)` + secretos `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `OTP_PEPPER`.
- Produces: Endpoint `POST /functions/v1/auth-otp` aceptando JSON `{ action, ... }`:
  - `register_init({ dni, nickname, correo, password_hash, device_hash, device_label, plataforma })`
  - `register_verify({ challenge_id, code, device_hash, device_label, plataforma })`
  - `login_init({ dni, correo, password_hash, device_hash, device_label, plataforma })`
  - `login_verify_otp({ challenge_id, code, device_hash, device_label, plataforma })`
  - `session_validate({ session_token, device_hash })`
  - `session_logout({ session_token, device_hash })`

- [ ] **Paso 1:** Implementar utilidades criptográficas WebCrypto (`generateOtp6`, `computeOtpHmac`, `timingSafeEqualHex`, `generateSessionToken256`, `sha256Hex`, `maskEmail`) y cliente HTTPS Brevo (`sendBrevoOtpEmail`) con plantilla HTML limpia en español.
- [ ] **Paso 2:** Implementar los 6 handlers (`register_init`, `register_verify`, `login_init`, `login_verify_otp`, `session_validate`, `session_logout`), incluyendo rate limit por IP/DNI, cooldown de 60 s, invalidación de OTPs previos no usados, rollback si Brevo falla y registro de alertas Honeytoken al 5.º intento fallido.
- [ ] **Paso 3:** Escribir y ejecutar pruebas unitarias (Node/Deno o script de verificación) cubriendo: generación de 6 dígitos, verificación HMAC en tiempo constante, detección de código incorrecto y enmascarado de correo.

---

### Tarea 3: Integración en Cliente Desktop (`IndiServ_Python`)

**Archivos:**
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\core\security.py`
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\core\cloud_gateway.py`
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\main.py`
- Test: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Python\tests\test_auth_session_otp.py`

**Interfaces:**
- Produces en `core/security.py`:
  - `get_device_fingerprint() -> tuple[str, str]` (retorna `(device_hash, device_label)` estable por equipo)
  - `save_session_token(token: str, device_hash: str) -> None`
  - `load_session_token() -> tuple[str, str] | None`
  - `clear_session_token() -> None`
- Produces en `core/cloud_gateway.py`:
  - `CloudGateway.auth_otp_request(payload: dict) -> dict`
  - `CloudGateway.iniciar_login_seguro(...)`, `CloudGateway.verificar_otp_login(...)`, `CloudGateway.iniciar_registro_otp(...)`, `CloudGateway.verificar_otp_registro(...)`, `CloudGateway.validar_sesion_guardada(...)`, `CloudGateway.cerrar_sesion_servidor(...)`

- [ ] **Paso 1:** Escribir pruebas unitarias en `tests/test_auth_session_otp.py` para `get_device_fingerprint()` (estabilidad determinista) y persistencia/borrado de token (`save`/`load`/`clear` con aislamiento en `tmp_path`).
- [ ] **Paso 2:** Implementar huella de dispositivo y almacenamiento seguro de sesión (`~/.indiserv_session.json`) en `core/security.py`, y cliente HTTPS hacia `/functions/v1/auth-otp` en `core/cloud_gateway.py`.
- [ ] **Paso 3:** Integrar en `main.py`:
  - Auto-restauración de sesión al iniciar (`_intentar_restaurar_sesion_async` con splash breve; si `session_validate` devuelve `ok: true` entra al Dashboard; si falla o expiró los 15 min, borra token y muestra Login).
  - Pantalla/modal `pantalla_verificacion_otp(challenge_id, masked_email, proposito, on_success)` con campo de 6 dígitos, contador regresivo de expiración y botón *Reenviar código* con cooldown de 60 s.
  - Revocación remota en `cerrar_sesion()` llamando a `session_logout` + `clear_session_token()`.
- [ ] **Paso 4:** Ejecutar `pytest` / pruebas unitarias, `py_compile`, auditoría AST y smoke test GUI en vivo (`pantalla_login`, `pantalla_registro`, `pantalla_verificacion_otp`, `pantalla_dashboard`).

---

### Tarea 4: Integración en Web3D y Android APK (`IndiServ_Web3D`)

**Archivos:**
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\src\utils\security.js`
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\src\components\MobileAuthView.jsx`
- Modificar: `c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\src\App.jsx`

**Interfaces:**
- Produces en `src/utils/security.js`:
  - `getDeviceFingerprint() -> Promise<{ deviceHash, deviceLabel, plataforma }>` (usa `Device.getId()` en Android nativo y UUID persistente en Web)
  - `saveSessionToken(token, deviceHash)`, `loadSessionToken()`, `clearSessionToken()`
  - `callAuthOtp(payload) -> Promise<object>` (llama a `${SUPABASE_URL}/functions/v1/auth-otp`)

- [ ] **Paso 1:** Implementar `getDeviceFingerprint`, manejo de token en `localStorage` y cliente `callAuthOtp` en `src/utils/security.js`.
- [ ] **Paso 2:** Actualizar `MobileAuthView.jsx` para soportar el paso de código OTP de 6 dígitos tanto en Registro (`register_init` → `register_verify`) como en Login desde dispositivo nuevo (`login_init` → `login_verify_otp`), con contador regresivo y botón de reenvío (`60 s`).
- [ ] **Paso 3:** Actualizar `App.jsx` para validar sesión guardada al arranque (`session_validate` dentro de los 15 min) y revocar en servidor (`session_logout`) al pulsar *Salir*.
- [ ] **Paso 4:** Ejecutar `npm run build` y `npx cap sync android` verificando 0 errores y tamaño óptimo de chunks.

---

### Tarea 5: Despliegue en Supabase, Push Multiplataforma y Verificación End-to-End

- [ ] **Paso 1:** Aplicar `20261125_sessions_devices_otp.sql` en Supabase SQL Editor.
- [ ] **Paso 2:** Configurar los 3 secretos en Supabase (`BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `OTP_PEPPER`) y desplegar `supabase functions deploy auth-otp --no-verify-jwt`.
- [ ] **Paso 3:** Ejecutar prueba de seguridad en vivo:
  - Verificar que `GET /rest/v1/codigos_otp` y `GET /rest/v1/sesiones_activas` devuelven `0` filas.
  - Verificar que el registro envía un correo real de 6 dígitos y crea la cuenta solo tras ingresar el código.
  - Verificar que cerrar y reabrir la app dentro de 15 min restaura la sesión automáticamente y que *Cerrar Sesión* la revoca al instante.
  - Verificar que un login con otro `device_hash` exige OTP al correo.
- [ ] **Paso 4:** Commit y `git push origin main` en `IndiServ_Python` e `IndiServ_Web3D` (disparando Vercel + GitHub Actions para Windows, Linux, macOS y Android APK) y compilar `dist/IndiServ_Analytica.exe` local.
