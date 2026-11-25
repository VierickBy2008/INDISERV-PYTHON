# Diseño Arquitectónico — Sesión Segura de 15 Minutos, Dispositivos Confiables y OTP por Correo (IndiServ Analytica)

- **Fecha:** 2026-11-25
- **Alcance:** `IndiServ_Python` (Desktop Windows/Linux/macOS), `IndiServ_Web3D` (Web Vercel + Android APK Capacitor 8) y Supabase (PostgreSQL RLS + Edge Function `auth-otp`).
- **Estado:** Borrador de diseño para aprobación del usuario (sin código implementado aún).

---

## 1. Intención y Propósito

Blindar el ciclo completo de identidad de **IndiServ Analytica** en todas sus versiones para lograr dos objetivos simultáneos:
1. **Continuidad cómoda y controlada:** que una sesión autenticada siga activa durante **15 minutos** aunque el usuario cierre y vuelva a abrir la aplicación (Desktop, Web o APK), expirando de forma estricta al cumplirse el plazo en el servidor.
2. **Verificación ineludible por correo (OTP de 6 dígitos):** exigir código enviado al correo real tanto al **registrar una nueva cuenta** como al **iniciar sesión desde un dispositivo nuevo o no reconocido**, cerrando toda posibilidad de bypass desde el cliente, manipulación del reloj local, fuerza bruta o condiciones de carrera (*race conditions*).

---

## 2. Metas, No-Metas y Anti-Metas

### Metas
- **Sesión de 15 minutos controlada por servidor:** token opaco de 256 bits emitido por Supabase, almacenado como hash SHA-256 en `sesiones_activas` ligado a `(dni, device_hash)` con `expira_en = now() + interval '15 minutes'`.
- **Huella de dispositivo confiable (`dispositivos_confiables`):** cada equipo físico/instalación genera un `device_hash` estable; un dispositivo ya verificado para ese DNI entra con sus credenciales sin pedir OTP cada vez, mientras que cualquier dispositivo nuevo exige OTP al correo registrado en `usuarios_app`.
- **OTP criptográfico a prueba de fuerza bruta y carreras:** 6 dígitos generados únicamente en servidor, guardados con HMAC-SHA256 + secreto `OTP_PEPPER`, caducidad de 10 minutos, máximo 5 intentos, cooldown de 60 s y consumo atómico en una sola transacción SQL (`FOR UPDATE`).
- **Cero atajos por API directa:** revocar ejecución directa de `anon` sobre la inserción/emisión de cuentas y sesiones; toda creación de cuenta, verificación OTP y emisión de sesión pasa obligatoriamente por la Edge Function `auth-otp` con `service_role`.
- **Paridad total en todas las versiones:** mismo backend `auth-otp` consumido por Desktop Python (`main.py`, `core/cloud_gateway.py`, `core/security.py`), Web Vercel y Android APK (`MobileAuthView.jsx`, `App.jsx`, `security.js`).

### No-Metas
- No migrar a `supabase.auth` (`auth.users`) ni reemplazar la validación contra `padron_oficial` UNMSM por DNI.
- No implementar TOTP por app autenticadora (Google Authenticator) ni SMS en esta fase.
- No construir panel de administración de sesiones remotas desde terceros (solo revocación inmediata al pulsar *Cerrar Sesión*).

### Anti-Metas (qué sería un fallo crítico de seguridad)
- Validar el código OTP o la expiración de 15 minutos en el cliente (Python/JS) o usando la hora local del equipo.
- Devolver el código OTP en la respuesta HTTP o en logs visibles al cliente.
- Permitir que un atacante llame por `curl` directamente a `registrar_usuario_seguro` saltándose la verificación OTP.
- Permitir que un token de sesión copiado desde una PC funcione en otra PC con distinto `device_hash`.

---

## 3. Enfoques Evaluados y Decisión Elegida

| Enfoque | Pros | Contras | Decisión |
|---|---|---|---|
| **Opción A: Edge Function `auth-otp` + Brevo API (HTTPS)** | Envía a cualquier correo (`@unmsm.edu.pe`, `@gmail.com`) gratis (300 correos/día), HTTPS puro en Deno (sin bloqueos SMTP), 100 % compatible con `padron_oficial` + DNI en Desktop/Web/APK. | Requiere cuenta gratuita en Brevo y 1 secreto `BREVO_API_KEY` + remitente verificado en Supabase Secrets. | **Elegida por el usuario** |
| **Opción B: Edge Function + Resend API** | API HTTPS muy limpia (3,000/mes). | Sin dominio propio comprado, el plan gratis restringe el envío solo al correo del administrador. | Descartada |
| **Opción C: Supabase Auth nativo (`auth.users`)** | OTP integrado. | Límite de ~2 correos/hora en plan gratis y obliga a reescribir todo el esquema DNI + padrón. | Descartada |

---

## 4. Arquitectura Técnica Detallada

### 4.1. Nuevas Tablas en PostgreSQL (RLS estricto: `0` políticas para `anon`)

Todas las tablas nuevas tienen `ENABLE ROW LEVEL SECURITY` y **ninguna política para `anon`/`authenticated`** — solo la Edge Function `auth-otp` (usando `SUPABASE_SERVICE_ROLE_KEY`) opera sobre ellas mediante funciones atómicas:

1. **`public.dispositivos_confiables`**
   - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
   - `dni text NOT NULL REFERENCES public.usuarios_app(dni) ON DELETE CASCADE`
   - `device_hash text NOT NULL` (SHA-256 hex de la huella estable del equipo)
   - `device_label text NOT NULL` (ej. `"Windows · LENOVO LOQ"`, `"Android · SM-P620"`, `"Web · Chrome"`)
   - `plataforma text NOT NULL` (`'desktop' | 'android' | 'web'`)
   - `verificado_en timestamptz NOT NULL DEFAULT now()`
   - `ultimo_uso timestamptz NOT NULL DEFAULT now()`
   - `revocado boolean NOT NULL DEFAULT false`
   - `UNIQUE (dni, device_hash)`
2. **`public.codigos_otp`**
   - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
   - `dni text NOT NULL`
   - `correo text NOT NULL`
   - `proposito text NOT NULL CHECK (proposito IN ('register', 'new_device'))`
   - `device_hash text NOT NULL`
   - `code_hmac text NOT NULL` (`HMAC-SHA256(OTP_PEPPER, id || ':' || dni || ':' || proposito || ':' || codigo)`)
   - `payload_pendiente jsonb` (solo para `register`: `{ nickname, password_hash }`, nunca texto plano)
   - `intentos int NOT NULL DEFAULT 0`
   - `max_intentos int NOT NULL DEFAULT 5`
   - `usado boolean NOT NULL DEFAULT false`
   - `expira_en timestamptz NOT NULL` (`now() + interval '10 minutes'`)
   - `creado_en timestamptz NOT NULL DEFAULT now()`
   - `ip_origen text`
3. **`public.sesiones_activas`**
   - `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
   - `dni text NOT NULL REFERENCES public.usuarios_app(dni) ON DELETE CASCADE`
   - `device_hash text NOT NULL`
   - `token_hash text NOT NULL UNIQUE` (`SHA-256(session_token)`)
   - `creada_en timestamptz NOT NULL DEFAULT now()`
   - `expira_en timestamptz NOT NULL` (`now() + interval '15 minutes'`)
   - `revocada boolean NOT NULL DEFAULT false`

> **Cierre de bypass SQL:** En la migración SQL se revoca `EXECUTE` del rol `anon` sobre `registrar_usuario_seguro` y `autenticar_usuario` (dejándolas reservadas a `service_role`) para impedir que un atacante cree cuentas o inicie sesión saltándose el flujo OTP de `auth-otp`.

### 4.2. Edge Function Única `supabase/functions/auth-otp/index.ts`

Un único endpoint `POST /functions/v1/auth-otp` con lista blanca CORS, validación de tamaño (`<= 8 KB`), rate limiting por IP y por DNI, y `action` explícita:

| Acción (`action`) | Flujo en Servidor | Respuesta al Cliente |
|---|---|---|
| `register_init` | Valida DNI en `padron_oficial`, verifica que no exista en `usuarios_app`, chequea Honeytokens, rate limit (máx. 5 OTP/hora y cooldown 60 s), genera OTP de 6 dígitos criptográfico, guarda `code_hmac` + `{nickname, password_hash}` en `codigos_otp` y envía correo vía Brevo API. | `{ ok: true, challenge_id, masked_email, expires_in_sec: 600 }` (el código jamás se devuelve). |
| `register_verify` | Bloquea fila con transacción atómica (`SELECT ... FOR UPDATE`), valida `usado = false`, `expira_en > now()`, `intentos < 5` y `device_hash` coincidente. Compara `HMAC` en tiempo constante. Si falla: `intentos += 1` (al 5.º fallo marca `usado = true` y registra alerta Honeytoken). Si acierta: marca `usado = true`, inserta usuario en `usuarios_app`, registra `dispositivos_confiables` y emite sesión de 15 min en `sesiones_activas`. | `{ ok: true, session_token, expires_at, user }` |
| `login_init` | Valida Honeytokens y rate limit; verifica `(dni, correo, password_hash)` contra `usuarios_app`. Si es válido: consulta `dispositivos_confiables` para `(dni, device_hash, revocado = false)`.<br>• **Dispositivo confiable:** emite directamente `session_token` de 15 min en `sesiones_activas`.<br>• **Dispositivo nuevo:** genera OTP `new_device`, lo envía **únicamente al correo registrado en `usuarios_app`** y retorna `requires_otp: true`. | `{ ok: true, requires_otp: false, session_token, expires_at, user }` **o** `{ ok: true, requires_otp: true, challenge_id, masked_email }` |
| `login_verify_otp` | Verifica atómicamente el OTP (`proposito = 'new_device'`, mismo `device_hash`, `FOR UPDATE`, tiempo constante, máx. 5 intentos). Si acierta: registra el dispositivo en `dispositivos_confiables` y emite `session_token` de 15 min. | `{ ok: true, session_token, expires_at, user }` |
| `session_validate` | Recibe `(session_token, device_hash)`. Calcula `SHA-256(session_token)` y verifica en `sesiones_activas` que `revocada = false`, `device_hash` coincida y `now() < expira_en`. | `{ ok: true, user, remaining_sec }` o `{ ok: false }` |
| `session_logout` | Recibe `(session_token, device_hash)` y marca `revocada = true` en `sesiones_activas`. | `{ ok: true }` |

### 4.3. Huella de Dispositivo (`device_hash`) y Almacenamiento Local del Token

- **Desktop (`IndiServ_Python`, `core/security.py`):**
  - `get_device_fingerprint()` construye una huella estable combinando `MachineGuid` (Windows Registry) / `/etc/machine-id` (Linux) / `IOPlatformUUID` (macOS) + nodo hardware + nombre de plataforma, y aplica `SHA-256("INDISERV_DEV_V1::" + raw)`.
  - `save_session_token` / `load_session_token` / `clear_session_token`: guarda `{ token, device_hash }` en un archivo privado del perfil del usuario (`~/.indiserv_session.json` con permisos `0o600` en POSIX / perfil local del usuario en Windows; nunca en la carpeta del repo).
  - Al abrir `AppIndiServ.__init__()`: si existe token local, muestra splash breve y llama a `session_validate` en segundo plano. Si el servidor confirma válido (dentro de los 15 min), entra directo al Dashboard sin pedir contraseña; si expiró o falló la red/validación, borra el token local y abre `pantalla_login()`.
  - Al pulsar **Cerrar Sesión**: llama a `session_logout` y borra el archivo local de inmediato.
- **Web y Android APK (`IndiServ_Web3D`, `src/utils/security.js`, `MobileAuthView.jsx`, `App.jsx`):**
  - `getDeviceFingerprint()`: en Android nativo usa `Device.getId()` (`@capacitor/device`, ya instalado en el proyecto!) + `model`; en Web usa un UUID criptográfico persistido en `localStorage` (`__indiserv_dev_id_v1`) + `userAgent` → `SHA-256`.
  - Guarda `{ token, device_hash }` en `localStorage` (`__indiserv_session_v1`).
  - Al iniciar `App.jsx`: ejecuta `session_validate` contra `auth-otp`; si sigue dentro de los 15 minutos, restaura `authUser` automáticamente (y al pulsar *Salir* llama a `session_logout` y limpia `localStorage`).

### 4.4. Interfaz de Usuario para el Código OTP (Desktop y Móvil/Web)

```text
┌────────────────────────────────────────────────────────┐
│  🔐 Verificación de Seguridad por Correo               │
│  Enviamos un código de 6 dígitos a: j***@unmsm.edu.pe  │
│                                                        │
│  [  4  8  2  9  1  5  ]    Expira en: 09:42            │
│                                                        │
│  [ Verificar y Entrar ]    [ Reenviar código (58s) ]   │
│  ← Cancelar y volver                                   │
└────────────────────────────────────────────────────────┘
```

---

## 5. Decisiones Propuestas por el Diseñador (para tu visto bueno)

Para avanzar sin bloquearnos en micro-detalles, propongo estas decisiones concretas — dime si quieres cambiar cualquiera antes de pasar al plan de implementación:

1. **Duración fija de 15 minutos desde la autenticación (no deslizante):** si cierras y abres la app dentro de los 15 min entras directo; a los 15 min exactos en el reloj de PostgreSQL la sesión caduca (ideal para PCs compartidas de laboratorio). *(Si prefieres que se renueve otros 15 min cada vez que la abres, se cambia con 1 línea en `session_validate`).*
2. **Usuarios ya registrados antes de esta actualización:** la primera vez que inicien sesión en un equipo tras desplegar el cambio, ese equipo aún no estará en `dispositivos_confiables`, así que les pedirá 1 código OTP al correo para registrar ese equipo como confiable; a partir de ahí entran directo desde ese equipo y solo vuelven a recibir OTP si inician sesión en un equipo distinto.
3. **Secretos en Supabase Dashboard (necesarios para el envío real de correos):** deberás configurar 3 secretos en `Supabase → Edge Functions → Secrets`:
   - `BREVO_API_KEY` (tu clave gratuita de Brevo)
   - `BREVO_SENDER_EMAIL` (el correo remitente verificado en Brevo, ej. tu correo Gmail/institucional)
   - `OTP_PEPPER` (cadena aleatoria larga generada por nosotros para firmar los HMAC-SHA256)
4. **Sin internet al reabrir:** si no hay conexión a Supabase para validar el token de 15 min, por seguridad **no se confía en la caché local** y se muestra la pantalla de login (principio *fail-closed*).

---

## 6. Alcance del Trabajo y Pruebas Planificadas

- **Tamaño:** Proyecto multi-capa (4 tareas independientes y verificables):
  1. Migración SQL (`20261125_sessions_devices_otp.sql`): tablas + RLS estricto + funciones atómicas `FOR UPDATE` + cierre de bypass directo.
  2. Edge Function `supabase/functions/auth-otp/index.ts`: acciones `register_init`, `register_verify`, `login_init`, `login_verify_otp`, `session_validate`, `session_logout` + integración Brevo + pruebas unitarias/HTTP.
  3. Cliente Desktop (`IndiServ_Python`): huella de dispositivo, almacén de token, cliente `auth-otp` en `CloudGateway`, auto-restauración de sesión 15 min y vista/modal de código OTP en Login y Registro.
  4. Cliente Web3D y Android APK (`IndiServ_Web3D`): huella Capacitor/Web, auto-restauración 15 min en `App.jsx`, flujo OTP en `MobileAuthView.jsx`, `vite build` + `cap sync android`.
