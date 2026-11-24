# Android Enfriamiento (Monitor Térmico) y Mantenimiento Real (Nivel 1 + Nivel 2)

## Intent
Implementar un módulo completo de Enfriamiento Activo y Mantenimiento Real en `IndiServ_Web3D` (`IndiServ_Analytica.apk`) combinando Nivel 1 (sin permisos invasivos: monitor térmico en tiempo real, caché propia e Intents oficiales del sistema) y Nivel 2 (permisos explícitos en Ajustes: `PACKAGE_USAGE_STATS` para top apps activas y `MANAGE_EXTERNAL_STORAGE` para escáner y limpieza selectiva de archivos en carpetas seguras), con persistencia privada vía `recordMobileEvent`.

## Scope
- **Incluido (`IndiServ_Web3D`)**:
  - `android/app/src/main/AndroidManifest.xml`: permisos Nivel 2 (`PACKAGE_USAGE_STATS`, `MANAGE_EXTERNAL_STORAGE`, `READ_EXTERNAL_STORAGE` `maxSdkVersion="32"`).
  - `android/app/src/main/java/com/indiserv/analytica/MaintenancePlugin.java`: plugin Capacitor nativo con métodos Nivel 1 (`getThermalSnapshot`, `clearAppInternalCache`, `openSystemStorageCleanup`, `openBatterySettings`, `openAppDetailsSettings`) y Nivel 2 (`getPermissionStatus`, `requestUsageStatsPermission`, `requestAllFilesPermission`, `getTopActiveApps`, `scanJunkAndLargeFiles`, `deleteSelectedFiles` con validación estricta de rutas).
  - `android/app/src/main/java/com/indiserv/analytica/MainActivity.java`: registro de `MaintenancePlugin.class`.
  - `src/components/MobileMaintenanceView.jsx`: Bloque A (Monitor Térmico + Sesión 60 s), Bloque B (Caché interna + Top Apps 24 h), Bloque C (Escáner de Descargas/APKs/Archivos Grandes con selección manual + confirmación) y sincronización privada vía `recordMobileEvent`.
  - `src/App.jsx` y `src/components/MobileScannerView.jsx`: integración de la vista y navegación móvil responsive.
- **Excluido**:
  - `IndiServ_Python`, esquema SQL de Supabase y flujo público `/?ticket=...` de Vercel.

## Checklist
- [x] Actualizar `AndroidManifest.xml`, crear `MaintenancePlugin.java` y registrarlo en `MainActivity.java`.
- [x] Crear `src/components/MobileMaintenanceView.jsx` e integrarlo en `src/App.jsx` y `src/components/MobileScannerView.jsx`.
- [x] Ejecutar `npm run build`, limpiar modelos no usados en `dist/models/` y correr `npx cap sync android`.
- [x] Subir a `origin main` en `IndiServ_Web3D` y validar el build de GitHub Actions (`Build Android APK`).

## Evidence
- `npm run build`: `✓ built in 1.84s`; `dist/models/` contiene únicamente `laptop-opt.glb` (124.6 KB), `pc-opt.glb` (17.07 MB) y `phone-opt.glb` (38.6 KB).
- `npx cap sync android`: `Sync finished in 0.312s` con `@capacitor/device@8.0.3` y `@capacitor/network@8.0.1`.
- `IndiServ_Python`: `git status --short` confirmó cero modificaciones de código fuente.

## Next
Confirmar compilación Gradle/Java en verde en GitHub Actions (`Build Android APK`) y probar el nuevo APK en el teléfono real.
