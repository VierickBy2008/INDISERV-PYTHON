# Rediseño Visual "Obsidian Instrument" y Corrección del Dock Inferior (Desktop + Web + Android)

## Intent
1. Corregir el recorte vertical del panel inferior (`dock`) en el Dashboard de `IndiServ_Python` cuando la ventana está en pantalla completa o resoluciones compactas.
2. Unificar la arquitectura visual, tipografía, jerarquía de color y microinteracciones táctiles de **Windows, Linux, macOS, Web (Vercel) y Android APK** bajo un lenguaje de diseño propio (**Obsidian Telemetry Instrument**) aplicando `emil-design-eng`, `frontend-design` y `ui-ux-pro-max`.

## Scope
- **`IndiServ_Python`**: `core/ui_theme.py`, `main.py` (`pantalla_dashboard`, paleta, fuentes nativas por SO, variantes `modulo`/`util`, feedback táctil en botones e inputs).
- **`IndiServ_Web3D`**: `index.html`, `src/index.css`, `src/App.jsx`, `src/components/TechSidebar.jsx`, `src/components/MobileAuthView.jsx`.

## Checklist
- [x] Empaquetar `dock` con `side="bottom"` ANTES de `tabs_dashboard` (`expand=True`) y reorganizar en grilla simétrica de 2 niveles (4 módulos principales + divisor + 5 utilidades) sin recorte.
- [x] Implementar paleta *Obsidian Instrument* (`#090c12` / `#101521` / `#141b2a`), tipografía nativa (`Segoe UI` / `SF Pro` / `DejaVu Sans`), variantes `modulo`/`util` y respuesta táctil a 60 FPS en `core/ui_theme.py`.
- [x] Implementar curvas `ease-out`, `scale(0.97)` táctil en `:active`, `tabular-nums`, transiciones `.view-enter`, área segura `safe-bottom` y paneles `.instrument-panel` en `IndiServ_Web3D`.
- [x] Verificar geometría en vivo (`dock_clipped: False`, `margin_px: 15`), `vite build`, `npx cap sync android`, push a ambos repositorios y compilación local de `IndiServ_Analytica.exe`.

## Evidence
- `DESKTOP_DOCK_VERIFICATION`: `{'frame_h': 812, 'dock_h': 133, 'dock_clipped': False, 'margin_px': 15}` (`DESKTOP_UI_VERIFIED_OK`).
- `IndiServ_Web3D`: `vite build` (`✓ built in 2.26s`) + `npx cap sync android` (`0.359s`).
- Commits publicados en `origin/main` de ambos repositorios para disparar Vercel + GitHub Actions (Windows, Linux, macOS, Android APK) y compilación local de `dist/IndiServ_Analytica.exe`.

## Next
Probar el ejecutable actualizado en Windows/Linux/macOS y el nuevo APK/Web en producción.
