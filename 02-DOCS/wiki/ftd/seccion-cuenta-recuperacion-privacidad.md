# FTD: Sección Mi Cuenta, Recuperación de Contraseña y Política de Privacidad v2.0

## Intención y Alcance
Incorporar autogestión completa de identidad con máxima seguridad en Desktop (`IndiServ_Python`), Web3D y Android APK (`IndiServ_Web3D`), centralizada en la Edge Function `auth-otp` y PostgreSQL `SECURITY DEFINER`:

1. **Foto de perfil (Avatar seguro)**:
   - Compresión cliente a `192×192` WebP/JPEG (`<= 60 KB`).
   - Validación en servidor de *magic bytes* reales (PNG/JPEG/WebP) y tamaño máximo (`75 KB`), guardada en `usuarios_app.avatar_data`.
   - Botón para subir, cambiar o quitar la foto al instante (reflejado en topbar Desktop y navegación móvil/tablet).
2. **Cambio de contraseña (Mi Cuenta)**:
   - Exige sesión activa de 15 min + contraseña actual + código OTP de 6 dígitos vía Brevo (`password_change_init` / `password_change_verify`).
   - Revoca todas las demás sesiones activas y envía alerta de seguridad por correo.
3. **Recuperación de contraseña en Login (“¿Olvidaste tu contraseña?”)**:
   - Disponible en `pantalla_login` (Desktop) y `MobileAuthView.jsx` (Web3D/Android).
   - Exige DNI + correo coincidente + respuesta neutra anti-enumeración + OTP de 6 dígitos vía Brevo (`password_reset_init` / `password_reset_verify`).
   - Al confirmar, actualiza `password_hash`, **revoca el 100% de sesiones activas y dispositivos confiables** y envía alerta de seguridad por correo.
4. **Eliminación total e irreversible de cuenta + tickets (Derecho ARCO)**:
   - Exige sesión activa + contraseña actual + escribir `ELIMINAR` + código OTP irreversible por Brevo (`account_delete_init` / `account_delete_verify`).
   - `eliminar_cuenta_completa(p_dni)` elimina atómicamente en cascada: `sugerencias_locales` asociadas, `reportes_diagnostico` (`owner_dni`), `codigos_otp`, `sesiones_activas`, `dispositivos_confiables` y `usuarios_app`.
5. **Política de Privacidad v2.0**:
   - Actualizada de forma sincronizada en `IndiServ_Python/core/legal.py` e `IndiServ_Web3D/src/utils/legalPolicy.js`.

## Checklist de Verificación y Evidencia Observada
- [x] Migración SQL creada: `IndiServ_Web3D/supabase/migrations/20261126_account_security_profile.sql` (todas las funciones `SECURITY DEFINER` revocadas a `PUBLIC, anon, authenticated` y otorgadas solo a `service_role`).
- [x] Edge Function `auth-otp/index.ts` ampliada con las 8 acciones nuevas + validación de *magic bytes* + avisos Brevo.
- [x] Desktop Python: `PY_COMPILE_OK: 17 files`, compresión de avatar WebP verificada (`138 bytes` en imagen de prueba), smoke test GUI exitoso (`pantalla_recuperar_password`, `pantalla_dashboard` con avatar, `modal_mi_cuenta` con 3 pestañas, `modal_politica_privacidad` v2.0).
- [x] Web3D + Android Capacitor: `vite build` en `2.41 s` (`index.js` `64.74 kB` gzip) y `npx cap sync android` en `0.291 s` sin errores.
- [x] Push a `origin/main` en ambos repositorios + compilación local `dist/IndiServ_Analytica.exe`.

## Acción Manual Requerida en Supabase (1 vez)
1. Ejecutar `supabase/migrations/20261126_account_security_profile.sql` en Supabase SQL Editor.
2. Reemplazar y desplegar el código actualizado de `supabase/functions/auth-otp/index.ts` en Supabase Edge Functions (`auth-otp`, manteniendo desactivado *Verify JWT with legacy secret*).
