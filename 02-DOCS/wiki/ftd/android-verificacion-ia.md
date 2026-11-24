# Verificación de Modelo Comercial y Autenticidad de Hardware con IA (Android)

## Intent
Ampliar la telemetría nativa Android (`HardwareInfoPlugin.java`) con señales de integridad del sistema y pantalla (`Build.TAGS`, `verifiedbootstate`, detección de root/emulador, resolución física y Hz), crear una Supabase Edge Function segura (`analizar-dispositivo-ia`) conectada a Gemini API sin exponer claves en el APK, e integrar en `MobileScannerView.jsx` el botón **"✨ Verificar Modelo y Piezas con IA"** para identificar el nombre comercial exacto del teléfono y auditar la coherencia de sus componentes.

## Scope
- **Incluido (solo en `IndiServ_Web3D`)**:
  - `android/app/src/main/java/com/indiserv/analytica/HardwareInfoPlugin.java`: `buildTags`, `fingerprint`, `verifiedBootState`, `isRooted`, `isEmulator`, `screenWidthPx`, `screenHeightPx`, `refreshRateHz`.
  - `supabase/functions/analizar-dispositivo-ia/index.ts`: Edge Function Deno/TypeScript con CORS, consulta JSON estructurada a `gemini-3-flash-preview` (`GEMINI_API_KEY` en secreto de Supabase) y fallback heurístico.
  - `src/utils/deviceAuditFallback.js`: motor heurístico de respaldo en cliente.
  - `src/components/MobileScannerView.jsx`: botón y tarjeta de dictamen IA.
- **Excluido**:
  - Cualquier cambio en `IndiServ_Python` o en rutas públicas `/?ticket=...` de Vercel.

## Checklist
- [x] Ampliar `HardwareInfoPlugin.java` con integridad de sistema y tasa de refresco/resolución real.
- [x] Crear y desplegar `supabase/functions/analizar-dispositivo-ia/index.ts` en Supabase con `GEMINI_API_KEY` en Secrets.
- [x] Integrar el botón **"✨ Verificar Modelo y Piezas con IA"** y la tarjeta de auditoría en `src/components/MobileScannerView.jsx`.
- [x] Verificar en vivo el endpoint desplegado (`HTTP 200`, `origen: "gemini-ia"`) y confirmar la publicación de `IndiServ_Analytica.apk` (`20.33 MB`) en GitHub Releases.

## Evidence
- **Prueba en vivo contra Supabase Edge Function (`analizar-dispositivo-ia`)**:
  - `HTTP: 200`
  - `{"origen":"gemini-ia","nombre_comercial":"Samsung Galaxy S25 Ultra","anio_lanzamiento":"2025","veredicto":"Original Coherente","confianza_pct":100,...}`
- **Release Android publicado**:
  - `https://github.com/sebastopxs/IndiServ_Web3D/releases/tag/android-latest` → `IndiServ_Analytica.apk` (`20.33 MB`).

## Next
Instalar `IndiServ_Analytica.apk` en un teléfono Android real y pulsar **"✨ Verificar Modelo y Piezas con IA"** en la pestaña **Mi Android**.
