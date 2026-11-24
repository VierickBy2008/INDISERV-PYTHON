# FTD — Aislamiento de Reportes Locales y Limpieza de Raíz

- **Fecha:** 2026-11-24
- **Carril:** FTD
- **Repositorio:** `IndiServ_Python`
- **Objetivo:** Evitar que la generación local de tickets (`Reporte_Diagnostico_*.txt` y `.json`) ensucie la carpeta principal del código y limpiar los 16 archivos históricos rastreados en la raíz de Git sin alterar la lógica del programa ni la sincronización en Supabase.

---

## Cambios Realizados

1. **Carpeta dedicada para reportes ([ui/modales.py](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/ui/modales.py)):**
   - Añadido `_obtener_carpeta_reportes()`:
     - En ejecución empaquetada (`sys.frozen`): guarda en `~/Documents/IndiServ_Reportes` (con fallback automático a `./reportes` si hubiera restricción de escritura).
     - En desarrollo: guarda en `<repo>/reportes/`.
   - `guardar_reporte_final()` ahora escribe `Reporte_Diagnostico_{ticket_id}.txt` y `.json` dentro de esa carpeta dedicada, manteniendo la misma firma de retorno `(ruta_txt, ruta_json)` y el hilo en segundo plano hacia Supabase.
2. **Limpieza del repositorio y [.gitignore](file:///c:/Users/Lenovo/Desktop/By2002/IndiServ_Python/.gitignore):**
   - Eliminados de Git (`git rm`) los **16 archivos** `Reporte_Diagnostico_*` que llenaban la raíz del repositorio.
   - Agregadas las reglas `reportes/`, `Reporte_Diagnostico_*.txt` y `Reporte_Diagnostico_*.json` a `.gitignore`.

---

## Checklist y Evidencia

- [x] `py_compile` aprobado sobre `ui/modales.py`.
- [x] Prueba en vivo `guardar_reporte_final(permanecer=True)` verificada: `REPORT_ISOLATION_PASS: dir=C:\Users\Lenovo\Desktop\By2002\IndiServ_Python\reportes | root_clean=True | json_ticket=IND-ISO-01`.
- [x] `python build_executable.py` completado con código `0` (`dist/IndiServ_Analytica.exe` actualizado).
- [x] Cambios publicados en `origin/main` con árbol limpio.

---

## Siguiente Paso
Verificar en GitHub que la raíz del repositorio ya no muestre archivos `Reporte_Diagnostico_*`.
