# Rediseño Visual/Didáctico, Micro-Stress Test Seguro, Buscador con Ejecución Directa y Harness

## Intent
Elevar la calidad visual y didáctica de **IndiServ Analytica** en todas las pantallas (`main.py` y `core/ui_theme.py`), resolver y asegurar el **Micro-Stress Test de CPU** en hilo secundario con cancelación limpia (`core/diagnostico.py`), dotar al **Buscador Asistido** de coincidencia multi-caso sobre las 26 hojas del árbol con ejecución directa de diagnóstico y acciones (Mapa 2D, Gemelo Digital 3D, Reporte dual), y actualizar el arnés automatizado (`test_supabase_insert.py`).

## Scope
- **`core/ui_theme.py`**: Sistema de diseño dark-tech unificado (`Badge`, `BarraMetrica`, `TarjetaMetrica`, `PuntoPulso`, `Sparkline`, `toast`, `estilizar_toplevel` y estilos de controles).
- **`core/diagnostico.py`**:
  - `CATALOGO_DICTAMENES` (26 casos en 8 ramas, incluyendo Red `#801`–`#803`) y `RAMAS_ARBOL`.
  - `BuscadorAsistido.buscar` y `BuscadorAsistido.diagnosticar` con normalización, sinónimos, stemming en español, tolerancia a errores de tipeo y refuerzo por telemetría (`EvaluadorTelemetria`).
  - `MicroStressTest` con aislamiento de callbacks (`_aislar`), ejecución en hilo secundario (`threading.Thread`), workers de prioridad baja (`BELOW_NORMAL_PRIORITY_CLASS`) con ciclo de trabajo al 85 %, cancelación segura (`cancelar()`) y detección combinada de throttling (frecuencia y Mops/s).
- **`main.py`**: Rediseño integral de Login, Registro, Dashboard (5 pestañas con KPIs y barras animadas), Árbol Inferencial (8 ramas), Multisíntoma con filtro, Buscador Asistido con ejecución directa y Micro-Stress Test con curva `Sparkline` en vivo.
- **`test_supabase_insert.py`**: 8 suites automatizadas que cubren Mapa 2D, Telemetría, Tickets/URL 3D, Stress Test seguro/cancelable, Buscador (26 casos), Vistas/Acciones UI y Supabase.

## Checklist
- [x] Sistema de diseño cohesivo y componentes didácticos (`core/ui_theme.py`).
- [x] Micro-Stress Test de CPU seguro, multihilo, cancelable y resiliente a errores (`core/diagnostico.py` y `main.py`).
- [x] Buscador Asistido con cobertura de los 26 casos y ejecución directa de diagnósticos y acciones (`core/diagnostico.py` y `main.py`).
- [x] Rediseño de Login, Dashboard (General, CPU/RAM, Gráficos, Discos, Red), Multisíntoma, Árbol y Modales (`main.py`).
- [x] Actualización y verificación del harness (`test_supabase_insert.py`).

## Evidence
- Ejecución completa de `test_supabase_insert.py` validando las 8 suites con código de salida `0`.

## Next
Ejecutar la aplicación con `.\venv\Scripts\python.exe main.py` o correr el arnés `.\venv\Scripts\python.exe test_supabase_insert.py` antes de la sustentación.
