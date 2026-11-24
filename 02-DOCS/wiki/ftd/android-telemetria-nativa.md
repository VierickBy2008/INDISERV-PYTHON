# Plugin Nativo Android de Telemetría Completa (SoC, Arquitectura, RAM, Almacenamiento y Batería)

## Intent
Implementar un plugin nativo de Capacitor en Java (`HardwareInfoPlugin.java`) dentro de `IndiServ_Web3D/android/` y conectarlo con `MobileScannerView.jsx` para leer directamente del sistema operativo Android la información real del dispositivo: marca y modelo exacto, SoC/procesador (`Build.SOC_MODEL` + `/proc/cpuinfo` + frecuencias `cpufreq`), arquitectura ABI (`arm64-v8a`), memoria RAM exacta (`ActivityManager.MemoryInfo`), almacenamiento interno total/usado/libre (`StatFs`) y salud/temperatura/voltaje de batería.

## Scope
- **Incluido (solo en `IndiServ_Web3D`)**:
  - `android/app/src/main/java/com/indiserv/analytica/HardwareInfoPlugin.java`: plugin Capacitor `@CapacitorPlugin(name = "HardwareInfo")` con `@PluginMethod getFullHardwareInfo()`.
  - `android/app/src/main/java/com/indiserv/analytica/MainActivity.java`: registro de `HardwareInfoPlugin.class` antes de `super.onCreate()`.
  - `src/components/MobileScannerView.jsx`: consumo del plugin nativo `registerPlugin('HardwareInfo')` con barras de uso para RAM y almacenamiento, SoC/frecuencia/ABI, modelo/marca/board, temperatura/voltaje/salud de batería, GPU WebGL y Micro-Stress Test CPU.
- **Excluido**:
  - Cualquier cambio en `IndiServ_Python` o en Supabase.

## Checklist
- [x] Crear `HardwareInfoPlugin.java` y registrarlo en `MainActivity.java`.
- [x] Actualizar `MobileScannerView.jsx` para mostrar modelo, marca, procesador/SoC, arquitectura ABI, frecuencias, RAM exacta, almacenamiento total/usado/libre y temperatura/salud de batería.
- [x] Verificar con `npm run build`, `npx cap sync android` y `git push origin main` (`a989405`).

## Evidence
- `npm run build` + `npx cap sync android` → `Sync finished in 0.211s`.
- `git push origin main` → `To https://github.com/sebastopxs/IndiServ_Web3D.git  7f79877..a989405  main -> main`.

## Next
Esperar ~3 minutos a que termine el workflow `Build Android APK (Capacitor)` en `https://github.com/sebastopxs/IndiServ_Web3D/actions` y descargar el nuevo `IndiServ_Analytica.apk` desde `https://github.com/sebastopxs/IndiServ_Web3D/releases/latest`.
