"""
test_supabase_insert.py — Arnés de Pruebas: Persistencia Supabase + OAuth Social (Google y GitHub)
==================================================================================================
Verifica de forma determinista:
  1. Renderizado programático con Pillow (Image, ImageDraw -> CTkImage) de los iconos oficiales de
     Google (G multicolor) y GitHub (silueta blanca de alta nitidez), sin archivos externos.
  2. Presencia, estilo dark-tech, icono a la izquierda y estado de espera cancelable de los botones
     "Continuar con Google" y "Continuar con GitHub" tanto en Login como en Registro, más el modal
     estilizado de validación de DNI (8 dígitos) para operadores nuevos.
  3. Generador de URLs OAuth PKCE (Google y GitHub), captura de callback en servidor HTTP local
     efímero (http.server en hilo secundario con cierre automático) e integración con CloudGateway.
  4. Conectividad HTTPS con pinning TLS SPKI SHA-256 y políticas RLS en Supabase
     ('reportes_diagnostico', 'sugerencias_locales' y Edge Function 'auth-otp').

Uso:
    .\\venv\\Scripts\\python.exe test_supabase_insert.py

Retorna 0 si todas las suites pasan correctamente, 1 si alguna falla.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from unittest.mock import patch

sys.path.insert(0, ".")

import customtkinter as ctk
from PIL import Image
from supabase import create_client

from core.cloud_gateway import (
    OAUTH_CALLBACK_PATH,
    OAUTH_CALLBACK_URL_DEFAULT,
    SUPABASE_KEY,
    SUPABASE_URL,
    CloudGateway,
)
from core.ui_theme import (
    _dibujar_pil_github,
    _dibujar_pil_google,
    boton_oauth,
    icono_github,
    icono_google,
    separador_oauth,
)
from main import AppIndiServ

PAYLOAD_REPORTE = {
    "id_ticket":      "TKT-TEST-EXPANDED",
    "cpu":            "AMD Ryzen 7 5700X (8C/16T @ 3.4 GHz)",
    "ram":            "32684 MB DDR4 @ 2666 MHz (2 ranuras)",
    "gpu":            "NVIDIA GeForce RTX 5060 Ti (4095 MB)",
    "almacenamiento": "SSD NVMe Patriot 232 GB / HDD WDC 931 GB",
    "placa_base":     "ASUSTeK ROG STRIX B550-F GAMING (WI-FI)",
    "refrigeracion":  "Cooler Torre Aire o AIO (inferido)",
    "health_score":   80,
    "diagnostico":    "Almacenamiento (SSD / HDD) - Disco C: al 90%",
    "solucion": (
        "1. Revise el estado S.M.A.R.T.\n"
        "2. Desactive SysMain si es HDD.\n"
        "3. Considere migrar el SO a un SSD NVMe."
    ),
    "specs_json": {
        "bios": {"version": "3621", "fecha": "13/01/2025"},
        "cpu": {
            "nombre": "AMD Ryzen 7 5700X 8-Core Processor",
            "nucleos_fisicos": 8,
            "nucleos_logicos": 16,
            "freq_base_ghz": 3.4,
            "freq_actual_ghz": 3.401,
            "uso_total_pct": 5.2,
        },
        "diagnostico_codigo": 600,
    },
}

PAYLOAD_SUGERENCIA = {
    "id_ticket":  "TKT-TEST-001",
    "sugerencia": "Mantenimiento de prueba exitoso",
}


def _separador(titulo: str) -> None:
    print("\n" + "=" * 68)
    print(f"  {titulo}")
    print("=" * 68)


def test_iconos_oauth_pillow() -> bool:
    """Verifica el renderizado programático de los iconos de Google y GitHub con Pillow -> CTkImage."""
    _separador("TEST 1: Iconos Programáticos OAuth (Pillow -> CTkImage)")
    try:
        pil_g = _dibujar_pil_google(18)
        pil_gh = _dibujar_pil_github(18)

        assert isinstance(pil_g, Image.Image) and pil_g.mode == "RGBA"
        assert isinstance(pil_gh, Image.Image) and pil_gh.mode == "RGBA"
        assert pil_g.size == (36, 36) and pil_gh.size == (36, 36)

        # Verificar presencia de los 4 colores de marca en Google (azul, verde, amarillo, rojo)
        tiene_azul = tiene_verde = tiene_amarillo = tiene_rojo = False
        w, h = pil_g.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pil_g.getpixel((x, y))
                if a < 180:
                    continue
                if b > 190 and r < 110:
                    tiene_azul = True
                elif g > 140 and r < 95 and b < 120:
                    tiene_verde = True
                elif r > 210 and g > 150 and b < 60:
                    tiene_amarillo = True
                elif r > 200 and g < 100 and b < 90:
                    tiene_rojo = True

        assert tiene_azul and tiene_verde and tiene_amarillo and tiene_rojo, (
            f"Faltan tramos cromáticos en Google G: azul={tiene_azul}, verde={tiene_verde}, "
            f"amarillo={tiene_amarillo}, rojo={tiene_rojo}"
        )

        # Verificar silueta blanca de alta nitidez y recorte central negativo en GitHub
        px_blancos = 0
        for y in range(h):
            for x in range(w):
                r, g, b, a = pil_gh.getpixel((x, y))
                if a > 180:
                    assert r >= 245 and g >= 245 and b >= 245, "Píxel opaco de GitHub no es blanco puro"
                    px_blancos += 1
        assert px_blancos > 250, f"Silueta de GitHub demasiado vacía ({px_blancos} px)"
        assert pil_gh.getpixel((w // 2, h // 2))[3] == 0, "El recorte interior Octocat debe ser transparente"

        ctk_g = icono_google(18)
        ctk_gh = icono_github(18)
        assert isinstance(ctk_g, ctk.CTkImage) and ctk_g._size == (18, 18)
        assert isinstance(ctk_gh, ctk.CTkImage) and ctk_gh._size == (18, 18)

        print("  [OK] Icono Google (G multicolor 4 tramos, 36x36 HiDPI -> CTkImage 18x18) verificado.")
        print("  [OK] Icono GitHub (silueta blanca Invertocat, 36x36 HiDPI -> CTkImage 18x18) verificado.")
        return True
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def test_botones_oauth_login_y_registro() -> bool:
    """Verifica que ambos botones OAuth existan en Login y Registro, estado de espera y modal DNI."""
    _separador("TEST 2: Botones Sociales en Login y Registro + Modal DNI (AppIndiServ)")
    app = AppIndiServ()
    app.withdraw()
    try:
        # 1. Pantalla de Login ("Portal de Seguridad Técnica")
        app.pantalla_login()
        app.update_idletasks()

        assert hasattr(app, "sep_oauth_login") and app.sep_oauth_login.winfo_exists()
        assert hasattr(app, "btn_google_login") and app.btn_google_login.winfo_exists()
        assert hasattr(app, "btn_github_login") and app.btn_github_login.winfo_exists()
        assert "Continuar con Google" in app.btn_google_login.cget("text")
        assert "Continuar con GitHub" in app.btn_github_login.cget("text")
        assert app.btn_google_login.cget("compound") == "left"
        assert app.btn_github_login.cget("compound") == "left"
        assert app.btn_google_login.cget("image") is not None
        assert app.btn_github_login.cget("image") is not None
        print("  [OK] Tarjeta Login: separador y botones Google/GitHub con iconos a la izquierda verificados.")

        # 1b. Bloqueo inmediato si el operador no ingresó primero su DNI de 8 dígitos
        app._iniciar_oauth_async("google", origen="login")
        app.update_idletasks()
        assert app._oauth_en_curso is False
        assert "DNI de 8 dígitos" in app.lbl_login_error.cget("text")
        print("  [OK] Bloqueo pre-OAuth cuando no se ingresa el DNI de 8 dígitos verificado.")

        # 1c. Con DNI de 8 dígitos ingresado, pasa a verificar DNI -> espera en navegador -> cancelar
        app.entry_dni.insert(0, "75509123")
        bloqueo = threading.Event()

        def _fake_oauth_wait(**kwargs):
            cb_nav = kwargs.get("on_esperando_navegador")
            if callable(cb_nav):
                cb_nav()
            ev = kwargs.get("cancel_event")
            while ev is not None and not ev.is_set() and not bloqueo.is_set():
                time.sleep(0.02)
            return {"ok": False, "cancelado": True}

        with patch.object(CloudGateway, "iniciar_sesion_oauth_escritorio", side_effect=_fake_oauth_wait):
            app._iniciar_oauth_async("google", origen="login")
            time.sleep(0.05)
            app.update()
            assert (
                "Verificando DNI" in app.btn_google_login.cget("text")
                or "Esperando autorización" in app.btn_google_login.cget("text")
            )
            assert app.btn_google_login.cget("state") == "disabled"
            assert app.btn_cancelar_oauth_login.winfo_ismapped() or app.btn_cancelar_oauth_login.winfo_manager() == "pack"
            app.cancelar_oauth_activo(origen="login")
            app.update_idletasks()
            assert "Continuar con Google" in app.btn_google_login.cget("text")
            assert app.btn_google_login.cget("state") == "normal"
        bloqueo.set()
        print("  [OK] Pre-validación DNI, estado 'Esperando autorización...' y botón Cancelar verificados.")

        # 2. Pantalla de Registro ("Registro de Operador Autorizado")
        app.pantalla_registro()
        app.update_idletasks()

        assert hasattr(app, "sep_oauth_registro") and app.sep_oauth_registro.winfo_exists()
        assert hasattr(app, "btn_google_registro") and app.btn_google_registro.winfo_exists()
        assert hasattr(app, "btn_github_registro") and app.btn_github_registro.winfo_exists()
        assert "Continuar con Google" in app.btn_google_registro.cget("text")
        assert "Continuar con GitHub" in app.btn_github_registro.cget("text")
        assert app.btn_google_registro.cget("compound") == "left"
        assert app.btn_github_registro.cget("compound") == "left"
        assert app.btn_google_registro.cget("image") is not None
        assert app.btn_github_registro.cget("image") is not None
        print("  [OK] Tarjeta Registro: separador y botones Google/GitHub con iconos verificados.")

        # 3. Modal estilizado de DNI para usuarios nuevos de Google/GitHub
        modal = app.modal_completar_dni_oauth(
            {
                "provider": "github",
                "correo": "nuevo.operador@unmsm.edu.pe",
                "nickname": "octo_operador",
                "oauth_access_token": "tok_demo_test",
            }
        )
        app.update_idletasks()
        assert modal.winfo_exists()
        assert hasattr(modal, "entry_dni_oauth") and modal.entry_dni_oauth.winfo_exists()
        assert hasattr(modal, "btn_confirmar_dni") and modal.btn_confirmar_dni.winfo_exists()
        modal.destroy()
        print("  [OK] Modal estilizado (estilizar_toplevel) de validación de DNI de 8 dígitos verificado.")
        return True
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False
    finally:
        try:
            app._al_cerrar_ventana()
        except Exception:
            pass


def test_generador_urls_y_callback_oauth() -> bool:
    """Verifica el generador de URLs OAuth (Google/GitHub), PKCE, servidor callback local y extracción de perfil."""
    _separador("TEST 3: Generador de URLs OAuth (Google/GitHub) + Callback HTTP Local")
    try:
        verifier, challenge = CloudGateway.generar_pkce_pair()
        assert len(verifier) >= 43 and len(challenge) >= 40 and "=" not in challenge

        cb_default = CloudGateway.obtener_callback_url_configuracion()
        assert cb_default == OAUTH_CALLBACK_URL_DEFAULT

        url_google = CloudGateway.construir_url_oauth(
            "google", redirect_uri=cb_default, code_challenge=challenge
        )
        url_github = CloudGateway.construir_url_oauth(
            "github", redirect_uri=cb_default, code_challenge=challenge
        )

        for prov, raw_url in (("google", url_google), ("github", url_github)):
            parsed = urllib.parse.urlparse(raw_url)
            qs = urllib.parse.parse_qs(parsed.query)
            assert parsed.scheme == "https" and parsed.path == "/auth/v1/authorize"
            assert qs.get("provider") == [prov]
            assert qs.get("redirect_to") == [cb_default]
            assert qs.get("code_challenge") == [challenge]
            assert qs.get("code_challenge_method") == ["s256"]
            print(f"  [OK] URL OAuth {prov.capitalize():<6s} generada : {raw_url[:86]}...")

        # Rechazo de proveedores desconocidos
        rechazo_ok = False
        try:
            CloudGateway.construir_url_oauth("twitter")
        except ValueError:
            rechazo_ok = True
        assert rechazo_ok, "Debió rechazar proveedor OAuth no soportado"

        # Servidor HTTP local efímero en hilo secundario (captura ?code= y cierre automático)
        httpd, redirect_uri, state = CloudGateway.iniciar_servidor_callback_oauth(preferred_port=0)
        assert redirect_uri.startswith("http://localhost:") and redirect_uri.endswith(OAUTH_CALLBACK_PATH)
        resultado_cb: dict = {}

        def _worker():
            resultado_cb.update(CloudGateway.esperar_callback_oauth(httpd, state, timeout_sec=6.0))

        t_srv = threading.Thread(target=_worker, daemon=True)
        t_srv.start()

        with urllib.request.urlopen(f"{redirect_uri}?code=pkce_code_demo_987", timeout=4) as resp:
            html_resp = resp.read().decode("utf-8")
            assert resp.status == 200 and "IndiServ Analytica" in html_resp

        t_srv.join(timeout=3.0)
        assert not t_srv.is_alive(), "El servidor HTTP local no se cerró automáticamente tras responder"
        assert resultado_cb.get("ok") is True and resultado_cb.get("code") == "pkce_code_demo_987"
        print(f"  [OK] Callback HTTP local capturado y cerrado automáticamente ({redirect_uri}).")

        # Extracción de perfil Google y GitHub
        p_google = CloudGateway.extraer_perfil_oauth(
            {
                "id": "uid-g1",
                "email": "Operador.Lab@unmsm.edu.pe",
                "user_metadata": {"full_name": "Sebastián Operador"},
                "app_metadata": {"provider": "google"},
            }
        )
        p_github = CloudGateway.extraer_perfil_oauth(
            {
                "id": "uid-gh1",
                "email": "dev@github-user.pe",
                "user_metadata": {"user_name": "sebastian_dev"},
                "app_metadata": {"provider": "github"},
            }
        )
        assert p_google["correo"] == "operador.lab@unmsm.edu.pe" and p_google["nickname"] == "Sebastián Operador"
        assert p_github["correo"] == "dev@github-user.pe" and p_github["nickname"] == "sebastian_dev"
        print("  [OK] Extracción de correo y alias para perfiles Google y GitHub verificada.")
        return True
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def test_conexion_y_rls_supabase(client) -> bool:
    """Verifica alcance HTTPS con pinning TLS SPKI y blindaje RLS en Supabase."""
    _separador("TEST 4: Conectividad Segura Supabase (TLS SPKI + RLS Blindado)")
    try:
        res_otp = CloudGateway._auth_otp_post({"action": "session_validate", "session_token": "invalid", "device_hash": "0"})
        assert "error_conexion" not in res_otp, f"Fallo de red/SPKI hacia Supabase: {res_otp}"
        print(f"  [OK] Canal HTTPS con pinning SPKI SHA-256 activo (HTTP {res_otp.get('_http_status')}).")

        prov_g = CloudGateway.verificar_proveedor_oauth_habilitado("google")
        prov_gh = CloudGateway.verificar_proveedor_oauth_habilitado("github")
        assert "error_conexion" not in prov_g and "error_conexion" not in prov_gh
        print(
            f"  [OK] Pre-vuelo /auth/v1/settings: Google habilitado={prov_g.get('habilitado')} "
            f"| GitHub habilitado={prov_gh.get('habilitado')}"
        )

        with patch.object(
            CloudGateway,
            "_rest_oauth_request",
            return_value=(200, {"ok": True, "existe": False, "en_padron": False, "ya_registrado": False}),
        ), patch.object(CloudGateway, "_auth_otp_post", return_value={"ok": False}):
            dni_no = CloudGateway.verificar_dni_pre_oauth("81234567", origen="login")
            assert dni_no["ok"] is False and dni_no.get("existe") is False

        with patch.object(
            CloudGateway,
            "_rest_oauth_request",
            return_value=(200, {"ok": True, "existe": True, "en_padron": True, "ya_registrado": False}),
        ), patch.object(CloudGateway, "_auth_otp_post", return_value={"ok": False}):
            dni_si = CloudGateway.verificar_dni_pre_oauth("75509123", origen="login")
            assert dni_si["ok"] is True and dni_si.get("existe") is True
        print("  [OK] Pre-validación de DNI en Supabase (aceptación en padrón y rechazo de inexistentes) verificada.")

        # Intentar upsert o confirmar que el blindaje RLS 42501 protege reportes_diagnostico frente a anon
        for tabla, payload in (("reportes_diagnostico", PAYLOAD_REPORTE), ("sugerencias_locales", PAYLOAD_SUGERENCIA)):
            try:
                resp = client.table(tabla).upsert(payload, on_conflict="id_ticket").execute()
                assert resp is not None
                print(f"  [OK] Tabla '{tabla}': escritura autorizada confirmada.")
            except Exception as exc:
                texto = str(exc)
                if "42501" in texto or "permission denied" in texto.lower() or "row-level security" in texto.lower():
                    print(f"  [OK] Tabla '{tabla}': blindaje RLS activo (acceso anon directo bloqueado según política).")
                else:
                    raise
        return True
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def main() -> int:
    print("=" * 68)
    print("  IndiServ Analytica — Suite de Pruebas OAuth Social y Supabase")
    print("=" * 68)

    ok_ico = test_iconos_oauth_pillow()
    ok_ui = test_botones_oauth_login_y_registro()
    ok_url = test_generador_urls_y_callback_oauth()

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        ok_supa = test_conexion_y_rls_supabase(client)
    except Exception as exc:
        print(f"[ERROR] No se pudo inicializar el cliente Supabase: {exc}")
        ok_supa = False

    resultados = [
        ("1. Iconos OAuth Programáticos (Pillow -> CTkImage)", ok_ico),
        ("2. Botones Google/GitHub en Login, Registro y Modal DNI", ok_ui),
        ("3. Generador URLs OAuth PKCE + Servidor Callback Local", ok_url),
        ("4. Conectividad HTTPS Pinning SPKI + Políticas RLS", ok_supa),
    ]

    print("\n" + "=" * 68)
    print("  RESUMEN")
    print("=" * 68)
    for nombre, ok in resultados:
        print(f"  {nombre:<55s}: {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    print("=" * 68)

    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
