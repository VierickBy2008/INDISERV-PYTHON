# FTD: Reinicio de Tickets, Guardado Manual Bajo Demanda, Mi Cuenta Desplegable y Diagnóstico Profundo Estilo CPU-Z

## Intención y Alcance
1. **Reinicio de tickets acumulados**: script SQL `IndiServ_Web3D/supabase/migrations/20261126_reset_all_tickets.sql` para vaciar `reportes_diagnostico` y `sugerencias_locales` (conservando alertas `HONEY-%` y cuentas de usuario).
2. **Guardado 100% manual bajo demanda (Desktop + Android/Web3D)**:
   - Se eliminó todo autoguardado al iniciar sesión, reescanear, finalizar el Árbol de Diagnóstico, ejecutar Micro-Stress Test, auditar con IA o limpiar caché/enfriar en Android.
   - Se incorporaron botones explícitos **«Guardar Ticket / Guardar en Nube»** (con bloqueo anti-duplicados) en Dashboard, Árbol de Diagnóstico, Buscador IA, Stress Test y Escáner/Diagnóstico Android.
3. **Mi Cuenta con secciones desplegables (`MobileAccountView.jsx`)**:
   - *Cambiar Contraseña* y *Eliminar Cuenta Permanentemente* quedaron colapsados por defecto detrás de filas desplegables limpias con chevron (`openSection`), dejando visible el perfil/avatar y el menú ordenado de Seguridad y Privacidad.
4. **Telemetría profunda tipo CPU-Z y diagnóstico específico (PC + Android)**:
   - **Desktop (`core/hardware.py`, `core/diagnostico.py`, `ui/dashboard_tabs.py`, `ui/stress_y_arbol.py`, `ui/diagnostico_views.py`)**: extracción real de *Code Name*, *Socket*, *Tecnología (nm)*, *Max TDP*, *Core Voltage*, *Bus Speed* y *Multiplicador*, *Family/Model/Stepping*, cachés *L1/L2/L3* (`Win32_CacheMemory`), instrucciones reales *ISA* (`IsProcessorFeaturePresent` / `/proc/cpuinfo` / `sysctl`), *Virtualización BIOS*, SPD completo por módulo RAM (fabricante, *PartNumber*, velocidad nominal vs configurada, voltaje, formato DIMM/SO-DIMM, Single vs Dual-Channel) y resolución/Hz de pantalla.
   - **Android (`HardwareInfoPlugin.java`, `MobileScannerView.jsx`, `MobileDiagnosticView.jsx`, `cloudHistory.js`)**: frecuencias en vivo por clúster (`scaling_cur_freq`), instrucciones *ISA ARM* (`/proc/cpuinfo Features`), cachés *L1d/L1i/L2/L3* (`/sys/devices/system/cpu/cpu0/cache`), estado térmico nativo (`PowerManager.getCurrentThermalStatus`), *revision/variant* y *bootloader*.
   - Todos los dictámenes en PC y Android integran ahora un bloque **«Perfil Técnico CPU-Z Verificado en Este Equipo»** y alertas específicas sobre el hardware real detectado.

## Checklist de Verificación y Evidencia
- [x] SQL de reinicio de tickets creado (`20261126_reset_all_tickets.sql`).
- [x] Cero autoguardados en Desktop y Web3D/Android; guardado estrictamente bajo demanda.
- [x] Acordeón desplegable en `MobileAccountView.jsx` para *Cambiar Contraseña* y *Eliminar Cuenta*.
- [x] Escaneo CPU-Z real verificado en Windows (`core/hardware.py`) + compilación/smoke test Python + build Vite/Capacitor Android + recompilación local `dist/IndiServ_Analytica.exe`.
