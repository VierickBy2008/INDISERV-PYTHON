# FTD — Sesión Segura de 15 Minutos, Dispositivos Confiables y OTP por Correo

- **Fecha:** 2026-11-25
- **Carril:** FTD (con diseño previo en `02-DOCS/superpowers/specs/` y plan en `02-DOCS/superpowers/plans/`)
- **Repositorios:** `IndiServ_Python`, `IndiServ_Web3D`

## Cambios Implementados

1. **PostgreSQL RLS + Funciones Atómicas ([20261125_sessions_devices_otp.sql](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/supabase/migrations/20261125_sessions_devices_otp.sql)):**
   - Tablas `dispositivos_confiables`, `codigos_otp` y `sesiones_activas` con `ENABLE ROW LEVEL SECURITY` y `0` políticas para `anon`/`authenticated`.
   - Funciones atómicas (`service_role` exclusivamente): `consumir_otp_atomico` (`SELECT ... FOR UPDATE`, máx. 5 intentos, caducidad 10 min), `emitir_sesion_15m`, `validar_sesion_15m` (reloj PostgreSQL + `device_hash`) y `revocar_sesion_15m`.
   - Cierre de bypass directo: `REVOKE EXECUTE` de `anon`/`authenticated` sobre `autenticar_usuario` y `registrar_usuario_seguro`.
2. **Supabase Edge Function ([auth-otp/index.ts](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/supabase/functions/auth-otp/index.ts)):**
   - 6 acciones (`register_init`, `register_verify`, `login_init`, `login_verify_otp`, `session_validate`, `session_logout`), OTP 6 dígitos criptográfico sin sesgo, `HMAC-SHA256` con `OTP_PEPPER`, rate limit por IP y por DNI (`5 OTP/h`, cooldown `60 s`), envío real vía **Brevo API v3** (rollback automático si falla) y alertas `HONEY-OTP-*` al 5.º intento fallido.
3. **Desktop Python (`IndiServ_Python`):**
   - [core/security.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/core/security.py): `get_device_fingerprint()` (`MachineGuid`/`machine-id`), `save_session_token`, `load_session_token`, `clear_session_token`.
   - [core/cloud_gateway.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/core/cloud_gateway.py): cliente HTTPS a `/functions/v1/auth-otp` con respaldo temporal 404 previo al despliegue.
   - [main.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/main.py) y [ui/dashboard_tabs.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/ui/dashboard_tabs.py): auto-restauración de sesión 15 min al abrir, `pantalla_verificacion_otp()` con contador y reenvío 60 s, y `cerrar_sesion()` con revocación remota.
4. **Web3D y Android APK (`IndiServ_Web3D`):**
   - [src/utils/security.js](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/utils/security.js): `getDeviceFingerprint()` (`Device.getId()` en Capacitor Android / UUID en Web), almacén de token y `callAuthOtp()`.
   - [src/components/MobileAuthView.jsx](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/components/MobileAuthView.jsx) y [src/App.jsx](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Web3D/src/App.jsx): auto-restauración 15 min, pantalla OTP 6 dígitos en registro y nuevo dispositivo, y `handleLogout()` con revocación remota.

## Evidencia Verificada
- [x] `PYTHON_OTP_SESSION_PASS`: `py_compile=17`, huella estable `fea3c991bd4c...`, persistencia de token, `pantalla_verificacion_otp` (`register` y `new_device`) y `cerrar_sesion` verificados en vivo.
- [x] `vite build` (`1.88 s`, `index-*.js: 210.72 kB`) y `npx cap sync android` (`0.331 s`) aprobados sin errores.
- [ ] Activación en Supabase por el titular: ejecutar SQL + cargar secretos Brevo + `OTP_PEPPER` + desplegar `auth-otp`.
