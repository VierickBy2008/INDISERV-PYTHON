# Empaquetado Android (.apk) con Capacitor sobre IndiServ_Web3D

## Intent
Convertir `IndiServ_Web3D` en una aplicación híbrida compilable a `.apk` nativo de Android mediante Capacitor (`@capacitor/android`), incorporando Login/Registro con Política de Privacidad UNMSM (solo en Registro), escáner de hardware móvil + benchmark CPU con Web Workers, búsqueda de tickets de Supabase y visor 3D táctil responsive, preservando intactos los enlaces públicos de Vercel (`/?ticket=...`) y sin tocar `IndiServ_Python`.

## Scope
- **Incluido (solo en `IndiServ_Web3D`)**:
  - Instalación de `@capacitor/core`, `@capacitor/cli`, `@capacitor/android`, `@capacitor/device` y `@capacitor/network`, creación de `capacitor.config.json` y generación del proyecto nativo `android/` con permisos `INTERNET` y `ACCESS_NETWORK_STATE`.
  - `src/utils/legalPolicy.js`: Política de Privacidad y Términos UNMSM (Ley N.° 29733).
  - `src/components/MobileAuthView.jsx`: Login y Registro contra `padron_oficial` y `usuarios_app`, exigiendo aceptación de términos exclusivamente en Registro.
  - `src/components/MobileScannerView.jsx`: telemetría Android/WebView (Device plugin, Network plugin, núcleos, RAM, batería, GPU WebGL, pantalla) y Micro-Stress Test CPU con Web Workers.
  - `src/components/TicketLookupBar.jsx` e integración responsive en `src/App.jsx` y `src/components/TechSidebar.jsx`.
  - `.github/workflows/build_android_apk.yml`: pipeline GitHub Actions (Node 20 + Java 21 + Gradle) que optimiza `dist/models/`, compila y publica `IndiServ_Analytica.apk` en Artifacts y Releases.
- **Excluido**:
  - Cualquier cambio en `IndiServ_Python` o en el esquema SQL de Supabase.

## Checklist
- [x] Instalar Capacitor y generar el proyecto nativo `android/` con `capacitor.config.json` en `IndiServ_Web3D`.
- [x] Implementar `MobileAuthView.jsx`, `MobileScannerView.jsx`, `TicketLookupBar.jsx` y la integración responsive en `App.jsx` y `TechSidebar.jsx` (preservando enlaces públicos `/?ticket=...` sin login).
- [x] Crear `.github/workflows/build_android_apk.yml` para compilar y publicar `IndiServ_Analytica.apk`.
- [x] Verificar con `npm run build`, `npx cap sync android` y `git push origin main` (`7721e0f`).

## Evidence
- **Build web Vite**: `✓ 2508 modules transformed. ✓ built in 2.80s`.
- **Capacitor Android**:
  - `Found 2 Capacitor plugins for android: @capacitor/device@8.0.3, @capacitor/network@8.0.1`
  - `Sync finished in 0.175s`
- **Push a GitHub (`sebastopxs/IndiServ_Web3D`)**:
  - `To https://github.com/sebastopxs/IndiServ_Web3D.git  bca70bd..7721e0f  main -> main`

## Next
Verificar la finalización de `.github/workflows/build_android_apk.yml` en `https://github.com/sebastopxs/IndiServ_Web3D/actions` y descargar `IndiServ_Analytica.apk` desde `https://github.com/sebastopxs/IndiServ_Web3D/releases/latest`.
