# FTD — Scroll CPU/RAM, Marca Propia, Equipos Confiables, Teclado Android y Huella Digital

## Intención
1. Reemplazar los paneles recortados de `CPU / RAM` en Desktop por columnas desplazables completas para ver todas las especificaciones y todos los hilos lógicos sin cajas aplastadas.
2. Eliminar toda referencia visible a `"CPU-Z"` en textos, reportes y tickets de Desktop y Android/Web3D, manteniendo 100% marca propia de IndiServ Analytica.
3. Permitir listar y revocar **Equipos Confiables** (cerrando sus sesiones activas en Supabase) desde `Mi Cuenta` tanto en Desktop como en Android/Web3D.
4. Corregir el error de teclado virtual en el Login APK (espacio negro inferior y recorte superior por doble empuje + `height: 100vh`).
5. Incorporar inicio de sesión rápido con **Huella Digital** en Android APK respaldado por `androidx.biometric:biometric:1.1.0` y cifrado AES-256-GCM en `AndroidKeyStore`.

## Alcance
- Supabase (`IndiServ_Web3D/supabase/`):
  - `migrations/20261126_trusted_devices_management.sql`: RPCs `listar_dispositivos_confiables` y `revocar_dispositivo_confiable` restringidas a `service_role`.
  - `functions/auth-otp/index.ts`: acciones `devices_list` y `device_revoke` protegidas con sesión 15m + aviso por Brevo.
- Desktop (`IndiServ_Python/`):
  - `core/cloud_gateway.py`: `listar_dispositivos_confiables` y `revocar_dispositivo_confiable`.
  - `ui/dashboard_tabs.py`: `_tab_cpu_ram` con `CTkScrollableFrame` completo para CPU (grid de silicio + canvas completo de hilos) y RAM (métricas + todos los slots SMBIOS) y marca propia.
  - `ui/modales.py`: nueva pestaña `Equipos Confiables` en `modal_mi_cuenta`.
  - `core/diagnostico.py`, `ui/stress_y_arbol.py`: textos 100% IndiServ Analytica.
- Android / Web3D (`IndiServ_Web3D/`):
  - `android/app/build.gradle`, `AndroidManifest.xml`, `MainActivity.java`, `BiometricAuthPlugin.java`.
  - `src/index.css`, `src/utils/biometric.js`, `src/components/MobileAuthView.jsx`, `src/components/MobileAccountView.jsx`, `src/components/MobileScannerView.jsx`, `src/components/MobileDiagnosticView.jsx`.

## Checklist
- [x] Migración SQL y endpoints `devices_list` / `device_revoke` en `auth-otp`
- [x] Columnas desplazables en `_tab_cpu_ram` y pestaña `Equipos Confiables` en Desktop
- [x] Eliminación total de menciones visibles `"CPU-Z"` en ambos repositorios
- [x] Corrección de teclado Android (`WindowCompat.setDecorFitsSystemWindows(false)` + `adjustResize` + `height: 100%`)
- [x] Plugin nativo `BiometricAuthPlugin.java` + flujo completo de Huella Digital en Login y Mi Cuenta
- [ ] Verificación automatizada, compilación EXE/APK y push a ambos repositorios
