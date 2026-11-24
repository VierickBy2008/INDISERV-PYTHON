# Android Tablet Navigation, Botón Atrás Nativo y Telemetría Comercial estilo CPU-Z

## Intent
1. Corregir la navegación en tablets Android (`>= 768px`), donde la barra `md:hidden` desaparecía, añadiendo barra lateral persistente para tablet/escritorio, pila de navegación (`tabHistory`), botón visible **← Atrás** y soporte nativo al botón/gesto Atrás de Android.
2. Identificar el nombre comercial exacto de teléfonos y tablets usando `getprop` OEM + diccionario local amplio + caché silencioso en `localStorage`.
3. Mostrar el procesador estilo **CPU-Z**: nombre comercial del SoC (Snapdragon, MediaTek Helio/Dimensity, Exynos, Tensor, UNISOC, Kirin), código interno de fábrica y topología real de clústeres ARM Cortex leídos de `/proc/cpuinfo` y `cpufreq`.

## Scope
- **Incluido (`IndiServ_Web3D`)**:
  - `android/app/src/main/java/com/indiserv/analytica/HardwareInfoPlugin.java`
  - `android/app/src/main/java/com/indiserv/analytica/MainActivity.java`
  - `src/utils/hardwareCatalog.js`
  - `src/utils/hardwareMapper.js` y `src/components/HardwareAssembler.jsx`
  - `src/App.jsx` y `src/components/MobileScannerView.jsx`
- **Excluido**:
  - `IndiServ_Python`, esquema SQL de Supabase y flujo público `/?ticket=...` de Vercel.

## Checklist
- [x] Ampliar `HardwareInfoPlugin.java` (OEM `marketName`, `isTablet`, clústeres ARM CPU-Z, `cpuGovernor`) y añadir manejo Back nativo en `MainActivity.java`.
- [x] Crear `src/utils/hardwareCatalog.js` con resolución comercial de dispositivos (teléfono/tablet), SoCs estilo CPU-Z y caché local.
- [x] Actualizar `App.jsx` (barra tablet persistente + `tabHistory` + botón ← Atrás + Back nativo) y `MobileScannerView.jsx` (tarjeta CPU-Z + nombre comercial).
- [x] Probar `hardwareCatalog.js` con Node.js, ejecutar `npm run build` + `npx cap sync android` y subir a `origin main`.

## Evidence
- Test Node.js sobre `src/utils/hardwareCatalog.js` (8 casos: S25 Ultra, Tab S9, Redmi 12/MT6768, Redmi Note 13 Pro 5G, A55/Exynos 1480, Pixel 9 Pro/Tensor G4, Edge 50 Pro, Xiaomi Pad 6): `ALL_8_CATALOG_CASES_OK` (exit code 0).
- `npm run build`: `✓ built in 1.69s`.
- `npx cap sync android`: `Sync finished in 0.129s`.
- `IndiServ_Python`: sin cambios de código.

## Next
Esperar ~2 minutos a que termine el build en GitHub Actions (`Build Android APK`) y descargar el nuevo `IndiServ_Analytica.apk` para probarlo en tablet y teléfono.
