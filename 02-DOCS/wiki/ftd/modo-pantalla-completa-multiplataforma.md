# Modo Pantalla Completa Multiplataforma (Windows, Linux y macOS)

## Intent
Habilitar arranque en modo pantalla completa y alternancia fluida entre pantalla completa y ventana en las versiones de escritorio de `IndiServ_Python` para **Windows, Linux y macOS**, con reescalado dinámico del fondo y expansión responsiva del Dashboard.

## Scope
- **Incluido**: `IndiServ_Python/main.py` (`AppIndiServ.__init__`, `_al_redimensionar_ventana`, `_aplicar_pantalla_completa`, `alternar_pantalla_completa`, `salir_pantalla_completa`, `_colocar_boton_fullscreen_flotante`, `pantalla_login`, `pantalla_registro` y `pantalla_dashboard`).
- **Excluido**: `IndiServ_Web3D` (web y Android APK).

## Checklist
- [x] Habilitar `resizable(True, True)` con `minsize(960, 680)` y arranque automático en pantalla completa (`attributes("-fullscreen", True)` con respaldo `zoomed` / geometría de pantalla para Windows, Linux y macOS).
- [x] Añadir atajos de teclado (`F11` en Windows/Linux, `Cmd+Ctrl+F` / `Cmd+Shift+F` en macOS, `Esc` para salir de pantalla completa) y botón visible en Login, Registro y barra superior del Dashboard.
- [x] Reescalar dinámicamente `assets/fondo.jpg` al cambiar el tamaño de ventana y expandir el Dashboard (`relwidth=0.96, relheight=0.94`) y `CTkTabview` (`fill="both", expand=True`).
- [x] Verificar con smoke test en vivo en Windows, subir a `origin/main` (disparando GitHub Actions para Windows, Linux y macOS) y recompilar `dist/IndiServ_Analytica.exe` localmente.

## Evidence
- `FULLSCREEN_SMOKE_TEST`: `{'fullscreen_on': True, 'width_fs': 1536, 'height_fs': 864, 'btn_text_fs': '🗗 Ventana (Esc)', 'fullscreen_off': False, 'btn_text_win': '⛶ Pantalla Completa'}` (`FULLSCREEN_VERIFIED_OK`).
- Recompilación local de `dist/IndiServ_Analytica.exe` y disparo de `.github/workflows/build_multiplataforma.yml` en GitHub Actions.

## Next
Descargar los nuevos binarios desde GitHub Releases (`latest`) o ejecutar localmente `dist/IndiServ_Analytica.exe`.
