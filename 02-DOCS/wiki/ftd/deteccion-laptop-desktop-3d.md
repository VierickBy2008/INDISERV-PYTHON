# Detección Automática Laptop vs. Desktop para el Gemelo Digital 3D

## Intent
Detectar automáticamente el factor de forma del equipo (`laptop` vs. `desktop`) durante el escaneo en `IndiServ_Python`, persistirlo dentro de `specs_json` en Supabase (`reportes_diagnostico`) sin alterar el esquema SQL y hacer que `IndiServ_Web3D` seleccione dinámicamente el modelo `.glb` correspondiente (`/models/laptop-opt.glb` o `/models/pc-opt.glb`) manteniendo retrocompatibilidad con tickets históricos.

## Scope
- **Incluido**:
  - `IndiServ_Python/core/hardware.py`: función `_escanear_tipo_equipo()`, integración en `LectorHardware.escanear_entorno()` y adición de `tipo_equipo` y `chassis_types` en `specs_json` dentro de `construir_resumen_para_bd()`.
  - `IndiServ_Web3D/src/utils/hardwareMapper.js`: extracción de `tipo_equipo` (`"laptop"` | `"desktop"`) desde `specs_json.tipo_equipo` más inferencia por huella de hardware (`7735HS`, `Laptop GPU`, `LNVNB`, `SODIMM`) para tickets previos, y definición de `model_file` y `chassisFile`.
  - `IndiServ_Web3D/src/components/HardwareAssembler.jsx`: carga condicional del `.glb` según `tipo_equipo` con fallback seguro a `/models/pc-opt.glb`, conservando `useMemo` y `useFrame` para `explodedView`.
  - `IndiServ_Web3D/public/models/laptop-opt.glb`: modelo glTF 2.0 binario (124,604 bytes, 16 nodos 3D independientes con materiales PBR).
  - `IndiServ_Web3D/src/App.jsx`: botón indicador/selector `Modo: Laptop / Modo: PC` en la barra superior y soporte para `?tipo=laptop`.
- **Excluido**:
  - Migraciones SQL o nuevas columnas en la tabla `reportes_diagnostico` de Supabase.

## Checklist
- [x] Implementar `_escanear_tipo_equipo()` e integrarlo en `LectorHardware.escanear_entorno()` y `construir_resumen_para_bd()` en `IndiServ_Python/core/hardware.py`.
- [x] Actualizar `mapTelemetryTo3DProfile()` en `IndiServ_Web3D/src/utils/hardwareMapper.js` para exponer `tipo_equipo` y `model_file` con fallback a `/models/pc-opt.glb` e inferencia para tickets existentes de laptop.
- [x] Actualizar `IndiServ_Web3D/src/components/HardwareAssembler.jsx` y `src/App.jsx` para cargar dinámicamente el `.glb` según el perfil/telemetría y permitir alternar el modo en la barra superior.
- [x] Generar `IndiServ_Web3D/public/models/laptop-opt.glb` con 16 nodos 3D separados por categoría y verificar en navegador real con ticket de laptop (`?ticket=6130-TICKET-8241`) tanto en vista ensamblada como en vista explosionada (`Explosión`).
- [x] Subir commit `dc16ea4` a `origin/main` en `IndiServ_Web3D`.

## Evidence
- **Detección Python (`core/hardware.py`)**:
  - `SCAN: {'tipo_equipo': 'laptop', 'chassis_types': [10], 'pc_system_type': 2, 'tiene_bateria': True}` y `BD specs_json: laptop [10]`.
- **Generación de `laptop-opt.glb`**:
  - `[OK] Generado c:\Users\Lenovo\Desktop\By2002\IndiServ_Web3D\public\models\laptop-opt.glb (124,604 bytes, 16 nodos 3D)`
- **Verificación visual en navegador (`http://localhost:5173/?ticket=6130-TICKET-8241`)**:
  - `/models/laptop-opt.glb` cargado con HTTP 200 y renderizado en vista ensamblada y vista explosionada (`Explosión`).
- **Push a GitHub (`IndiServ_Web3D`)**:
  - `git push origin main` → `To https://github.com/sebastopxs/IndiServ_Web3D.git  8d64e72..dc16ea4  main -> main` (exit code 0).

## Next
Feature completada. Cuando Vercel termine el build automático (~30-60 s), `https://indiserv-web3d.vercel.app/?ticket=6130-TICKET-8241` y los nuevos tickets generados desde `IndiServ_Python` mostrarán automáticamente el modelo 3D de laptop o PC.
