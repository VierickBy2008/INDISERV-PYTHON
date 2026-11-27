# Autenticación Social OAuth (Google y GitHub) en Escritorio

## Intent
Incorporar inicio de sesión y registro rápido mediante **Google** y **GitHub** (Supabase Auth OAuth PKCE / Implicit) en las vistas **Portal de Seguridad Técnica** (`pantalla_login`) y **Registro de Operador Autorizado** (`pantalla_registro`) de `IndiServ Analytica`, renderizando iconos de alta nitidez con `Pillow` (`Image`, `ImageDraw` -> `CTkImage`) sin depender de archivos `.png`/`.ico` externos y manteniendo la validación obligatoria de DNI de 8 dígitos contra `padron_oficial` en Supabase.

## Scope
- **Incluye:**
  - Generadores vectoriales supersampleados (`6x` LANCZOS) en `core/ui_theme.py` para los iconos de Google (`G` multicolor de 4 tramos) y GitHub (silueta blanca Invertocat de alta nitidez), convertidos a `CTkImage`, más componentes `separador_oauth` y `boton_oauth`.
  - Flujo OAuth de escritorio en `core/cloud_gateway.py`: generador PKCE (`S256` / `s256`), URL de autorización Supabase (`provider="google"` y `provider="github"`), servidor HTTP local efímero (`http.server` en `localhost:54321/auth/callback` con fallback automático a puerto libre en hilo secundario y cierre automático), soporte dual PKCE (`?code=`) e Implicit (`#access_token=`), intercambio sobre HTTPS con pinning SPKI SHA-256 y sincronización de identidad/DNI con Supabase (`auth-otp`, RPC `oauth_sync_operador` y fallback PostgREST).
  - Script SQL `supabase_oauth_setup.sql` (`SECURITY DEFINER` para el rol `authenticated`) para vincular cuentas OAuth con `usuarios_app`, `padron_oficial`, `dispositivos_confiables` y `sesiones_activas` sin abrir RLS a `anon`.
  - Integración UI en `ui/app_core.py`: botones `"Continuar con Google"` y `"Continuar con GitHub"` en Login y Registro, estado visual de espera (`"Esperando autorización en el navegador..."`) con botón de cancelación inmediata, acceso directo al Dashboard para operadores existentes y modal estilizado (`estilizar_toplevel`) de DNI de 8 dígitos para operadores nuevos.
  - Ampliación del arnés de pruebas (`test_supabase_insert.py` y `scripts/test_supabase_insert.py`) y `HIDDEN_IMPORTS` en `build_executable.py`.
- **No incluye:**
  - Modificaciones en el repositorio externo `IndiServ_Web3D` / APK Android.
  - Eliminación del inicio de sesión clásico con DNI + correo + contraseña + OTP.

## Checklist
- [x] Iconos programáticos `icono_google` y `icono_github` (`Pillow` -> `CTkImage`), `separador_oauth` y `boton_oauth` en `core/ui_theme.py`.
- [x] Flujo OAuth PKCE/Implicit, servidor callback `http.server` cancelable y validación de operador/DNI en `core/cloud_gateway.py` + `supabase_oauth_setup.sql`.
- [x] Botones sociales en `pantalla_login` y `pantalla_registro`, estado de espera cancelable y `modal_completar_dni_oauth` (`estilizar_toplevel`) en `ui/app_core.py`.
- [x] Actualización y ejecución completa del arnés de pruebas (`test_supabase_insert.py` y `scripts/test_supabase_insert.py`) + compilación `py_compile` de todo el proyecto.
- [x] Validación obligatoria de DNI (8 dígitos) contra Supabase (`verificar_dni_pre_oauth`) y verificación pre-vuelo de proveedor activo (`/auth/v1/settings`) **antes** de abrir el navegador en Google o GitHub (Login y Registro).
- [x] Compatibilidad multiplataforma Linux (`LD_LIBRARY_PATH_ORIG` + `xdg-open` + `SO_REUSEADDR`), macOS (`/usr/bin/open` + `SO_REUSEADDR`), compilación nativa Cython + PyInstaller (`dist/IndiServ_Analytica.exe`) y sincronización OAuth + deep-link `com.indiserv.analytica://auth-callback` en `IndiServ_Web3D` (Web + Android APK).

## Evidence
- `.\venv\Scripts\python.exe test_supabase_insert.py` → `exit code 0` (`4/4 PASSED`: iconos RGBA HiDPI 36×36 -> `CTkImage` 18×18, bloqueo pre-OAuth cuando falta DNI de 8 dígitos, verificación en Supabase de DNI antes de abrir navegador, chequeo en vivo `/auth/v1/settings` confirmando `Google habilitado=True | GitHub habilitado=True`, URLs PKCE Google/GitHub + servidor `http.server` con cierre automático, y canal HTTPS con pinning SPKI SHA-256 + RLS).
- `.\venv\Scripts\python.exe build_executable.py` → `exit code 0`: `14/14` módulos propios compilados a código máquina C nativo (Cython), `0/14` en bytecode `.pyc` (`[SecurityGate] [OK]`), generado `dist/IndiServ_Analytica.exe`.
- `IndiServ_Web3D` (`npm ci && npm run build && npx cap sync android`) → `0 vulnerabilities`, `vite build` en `1.39 s` y `cap sync android` en `0.167 s` con deep-link `com.indiserv.analytica://auth-callback`, navegador externo seguro en Android (`SessionVault.openExternalAuthUrl`) y soporte cookie HttpOnly en `api/auth-proxy.js`.
- `.\venv\Scripts\python.exe scripts\test_supabase_insert.py` → `exit code 0` (`8/8 PASSED`: Mapa 2D, Telemetría, Gemelo 3D, Micro-Stress Test, Buscador 26/26, Vistas UI + OAuth, y verificación Supabase RLS).
- `py_compile` → `PY_COMPILE_OK: 23 files` sin errores de sintaxis.

## Next
Registrar `http://localhost:54321/auth/callback` (y comodín `http://localhost:*/auth/callback`) en Supabase -> Authentication -> URL Configuration y ejecutar `supabase_oauth_setup.sql` en Supabase SQL Editor.
