# Android Completo: Batería Avanzada, Modelo 3D de Smartphone y Árbol de Diagnóstico

## Intent
Completar la experiencia de diagnóstico experto en la versión Android (`IndiServ_Web3D`) añadiendo:
1. Telemetría avanzada de batería en `HardwareInfoPlugin.java` (porcentaje, salud, temperatura °C, voltaje mV, tecnología Li-ion/Li-poly, tipo de cargador AC/USB/Wireless y corriente mA).
2. Modelo 3D propio de smartphone (`public/models/phone-opt.glb`) con 12 nodos internos separados para vista ensamblada, explosión 3D y selección por componente, junto con soporte para los 3 factores de forma (`phone` | `laptop` | `desktop`) en `hardwareMapper.js`, `HardwareAssembler.jsx` y `App.jsx`.
3. Módulo de **Árbol de Diagnóstico y Solución de Problemas** (`MobileDiagnosticView.jsx`) con 6 ramas guiadas + buscador de síntomas, generación de ticket en Supabase (`tipo_equipo: "phone"`) y enlace directo al Gemelo Digital 3D del teléfono.

## Scope
- **Incluido (solo en `IndiServ_Web3D`)**:
  - `public/models/phone-opt.glb`: modelo glTF 2.0 binario de smartphone con piezas internas nombradas.
  - `android/app/src/main/java/com/indiserv/analytica/HardwareInfoPlugin.java`: datos detallados de batería (tecnología, fuente de carga, corriente, salud y estado).
  - `src/utils/hardwareMapper.js` y `src/components/HardwareAssembler.jsx`: soporte de `tipo_equipo === 'phone'` → `/models/phone-opt.glb`.
  - `src/components/MobileDiagnosticView.jsx`: árbol de decisión interactivo (6 ramas) + buscador + soluciones paso a paso + sincronización de ticket a Supabase + apertura en Visor 3D del teléfono.
  - `src/components/MobileScannerView.jsx` y `src/App.jsx`: tarjeta de batería detallada, botón para ver el propio teléfono en 3D y nueva pestaña **Diagnóstico** en la barra inferior.
- **Excluido**:
  - Cualquier cambio en `IndiServ_Python` o en el esquema SQL de Supabase.

## Checklist
- [x] Generar `public/models/phone-opt.glb` con nodos separados para vista explosionada y clic por componente.
- [x] Ampliar `HardwareInfoPlugin.java` con métricas completas de batería (tecnología, fuente de carga, corriente mA, voltaje, temperatura y salud).
- [x] Añadir soporte `'phone'` → `/models/phone-opt.glb` en `hardwareMapper.js`, `HardwareAssembler.jsx` y `App.jsx`.
- [x] Implementar `MobileDiagnosticView.jsx` (Árbol de Diagnóstico + Buscador + Soluciones + Ticket Supabase + Visor 3D del teléfono) e integrarlo en `App.jsx`.
- [x] Verificar con Node.js, `npm run build`, `npx cap sync android` y `git push origin main` para compilar `IndiServ_Analytica.apk`.

## Evidence
- `generate_phone_glb.py`: `[OK] Generado c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\public\models\phone-opt.glb (38,592 bytes, 11 nodos 3D)`.
- Prueba Node.js sobre `hardwareMapper.js`: `{"phoneExplicit":"/models/phone-opt.glb","phoneAuto":"/models/phone-opt.glb","laptop":"/models/laptop-opt.glb","desktop":"/models/pc-opt.glb"}` (exit code 0).
- `npm run build`: `✓ built in 2.08s`; `dist/models/` contiene `phone-opt.glb` (38.5 KB), `laptop-opt.glb` (124.6 KB) y `pc-opt.glb` (17.07 MB).
- `npx cap sync android`: `Sync finished in 0.179s` con `@capacitor/device@8.0.3` y `@capacitor/network@8.0.1`.
- `IndiServ_Python`: sin modificaciones de código.

## Next
Descargar el nuevo `IndiServ_Analytica.apk` desde GitHub Releases una vez finalice el workflow `build_android_apk.yml` y validar en el teléfono real.
