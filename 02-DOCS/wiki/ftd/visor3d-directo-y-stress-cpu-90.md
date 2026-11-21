# Visor 3D Directo sin Árbol Previo y Corrección de Micro-Stress Test CPU al ~90%

## Intent
1. Permitir que el botón **Visor Gemelo Digital 3D** funcione directamente desde el Dashboard sin obligar al usuario a completar antes el Árbol de Diagnóstico, subiendo la telemetría real del equipo (`laptop` o `desktop`) a Supabase de forma sincrónica antes de abrir el navegador para eliminar la condición de carrera que mostraba la PC de respaldo.
2. Corregir el **Micro-Stress Test de CPU** (`core/diagnostico.py` y `main.py`) para eliminar lecturas falsas ("alucinaciones") en los estados de seguridad y en la bitácora de muestreo, y usar cómputo nativo C libre de GIL (`hashlib.pbkdf2_hmac`) sobre todos los hilos lógicos de cualquier modelo de procesador para llevarlo de forma estable al ~90%+ de carga real.

## Scope
- **Incluido**:
  - `IndiServ_Python/main.py`:
    - `abrir_visor_3d()`: genera un dictamen de inspección general cuando `self.dictamen_final` es `None`, sube el ticket a Supabase y espera confirmación (`join(timeout=4.0)`) antes de invocar `abrir_gemelo_digital()`.
    - Vista `pantalla_stress_test()`: muestra el modelo real del procesador detectado, todos los núcleos/hilos asignados, estados de seguridad precisos (`CARGANDO`, `ÓPTIMO 90%+`, `ESTABLE`, `THROTTLING`) y bitácora de muestreo limpia.
  - `IndiServ_Python/core/diagnostico.py`:
    - `MicroStressTest`: motor multihilo libre de GIL (`hashlib.pbkdf2_hmac` en C + validación FPU) que escala automáticamente a cualquier procesador (`MAX_WORKERS = 128`, `DUTY_CYCLE = 0.90`, todos los hilos lógicos por defecto) para alcanzar ~90%+ de uso de CPU tanto en `.py` como dentro del `.exe`, con línea base estabilizada y suavizado EMA para eliminar falsas alertas de caída/seguridad.
  - `IndiServ_Python/core/hardware.py`: refuerza `_clasificar_tipo_equipo()` con `_tiene_firma_portatil()` (CPU serie `H/HS/HX/U`, GPU `Laptop/Mobile`, placa `LNVNB/FA506/FX505/GU603/G513`, memoria `SODIMM/LPDDR`).
  - `IndiServ_Web3D/src/App.jsx` y `src/utils/hardwareMapper.js`: reintento automático a Supabase si el ticket acaba de crearse y ampliación de firmas de placas de laptop.
  - Recompilación de `dist/IndiServ_Analytica.exe` y ejecución de la suite `test_supabase_insert.py`.

## Checklist
- [x] Actualizar `core/hardware.py` y `main.py` (`abrir_visor_3d`) para subir siempre la telemetría del equipo a Supabase antes de abrir el visor 3D, incluso sin diagnóstico previo.
- [x] Reescribir el kernel de carga y el monitor de estabilidad de `MicroStressTest` en `core/diagnostico.py` y su vista en `main.py` para alcanzar ~90%+ de CPU en cualquier procesador sin falsos estados de seguridad.
- [x] Ejecutar `test_supabase_insert.py` y verificar que las 8 suites pasen con código `0` y que el stress test real alcance ~90%+ de uso de CPU.
- [x] Actualizar `IndiServ_Web3D` (`App.jsx` y `hardwareMapper.js`), hacer push a `origin/main` (`bca70bd`) y recompilar `dist/IndiServ_Analytica.exe`.

## Evidence
- **Stress test real de 16 hilos en `AMD Ryzen 7 7735HS (8C/16T)`**:
  - `1.0s │ 3.20 GHz │ CPU 92.8% │ 16.09 Mops/s │ RAM libre 25.9% │ ÓPTIMO 90%+`
  - `RESULT: {'throttling': False, 'uso_max_pct': 92.8, 'uso_avg_pct': 88.4, 'rendimiento_avg_mops': 16.44, 'detenido_por_seguridad': False, 'workers': 16, 'modo': 'nativo-multihilo'}`
- **Suite de pruebas `test_supabase_insert.py`**:
  - Las 8 suites pasaron con `[OK] PASSED` y código de salida `0`.
- **Push a GitHub (`IndiServ_Web3D`)**:
  - `To https://github.com/sebastopxs/IndiServ_Web3D.git  dc16ea4..bca70bd  main -> main`
- **Recompilación de `dist/IndiServ_Analytica.exe`**:
  - `35067 INFO: Building EXE from EXE-00.toc completed successfully.`

## Next
Entregar el nuevo `dist/IndiServ_Analytica.exe` para pruebas directas desde el Dashboard y en el Micro-Stress Test.
