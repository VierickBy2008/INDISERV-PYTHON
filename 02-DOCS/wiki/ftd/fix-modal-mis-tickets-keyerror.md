# Fix Modal Mis Tickets en Escritorio (KeyError P["fondo"])

## Intent
Corregir el `KeyError: 'fondo'` en `modal_mis_tickets` de `IndiServ_Python/main.py` que impedía renderizar la lista privada de tickets y los botones de acción en Windows, Linux y macOS.

## Scope
- `IndiServ_Python/main.py` (línea 2530): reemplazar `P["fondo"]` por `P["bg"]` (clave válida en `core/ui_theme.py`) y validar todas las referencias a `P[...]` y el renderizado real del modal.

## Checklist
- [x] Reemplazar `P["fondo"]` por `P["bg"]` en `modal_mis_tickets`.
- [x] Validar estáticamente todas las claves `P[...]` de `main.py` y `core/*.py` contra `core.ui_theme.P`.
- [x] Probar `modal_mis_tickets()` en vivo y compilar/subir `main` para regenerar `.exe`, Linux y macOS.

## Evidence
- Validación estática de paleta: `ALL_PALETTE_KEYS_OK` (cero claves faltantes en `main.py` y `core/*.py`).
- Además del `KeyError: 'fondo'`, se corrigió el dispatch entre hilos en `_cargar_en_hilo` usando `self.after(0, ...)` en lugar de llamar `v.winfo_exists()` desde el hilo secundario.
- Prueba en vivo con `AppIndiServ.mainloop()` y DNI `61303860`: `RENDERED_TICKET_CARDS: 8`, `LIVE_MAINLOOP_TEST_OK` (exit code 0).

## Next
Esperar ~3 minutos a que termine el workflow `Build Multiplataforma` y descargar el nuevo `.exe` / binario desde Releases.
