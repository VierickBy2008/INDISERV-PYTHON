"""
test_supabase_insert.py — Arnés Integral de Evaluación y Pruebas (Test Harness)
===============================================================================
Suite automatizada de validación de IndiServ Analytica (POO I).
Verifica de forma determinista y sin dejar archivos residuales:

  1. Renderizado 2D e integridad geométrica de `core/hardware_map.py`
     (MotherboardMapView, coordenadas de componentes, separación PSU/GPU,
     detección de colisiones/hover y tarjetas emergentes).
  2. Serialización de telemetría (`core/hardware.py`): CPU, GPU, RAM,
     inferencia térmica y cálculo de Health Score.
  3. Generación de tickets y enlaces públicos para el Gemelo Digital 3D
     (`core/gemelo_digital.py` y `core/config.py`).
  4. Inicialización y coherencia visual/estructural de `AppIndiServ` (`main.py`):
     login, registro, dashboard y sus 5 pestañas, árbol inferencial (8 ramas),
     multisíntoma, buscador asistido, stress test, mapa 2D y modales.
  5. Ejecución segura, controlada y cancelable de `MicroStressTest`
     (`core/diagnostico.py`): hilo secundario, terminación limpia de workers,
     cancelación rápida y resiliencia ante errores de callback.
  6. Precisión multi-caso y ejecución directa del `BuscadorAsistido` sobre las
     26 hojas del catálogo (incluyendo acciones directas: Mapa 2D, Gemelo 3D
     y guardado dual TXT + JSON).
  7. Persistencia Cloud en Supabase (`reportes_diagnostico` y `sugerencias_locales`).

Uso:
    .\\venv\\Scripts\\python.exe test_supabase_insert.py

Retorna 0 si todas las suites pasan correctamente, 1 si alguna falla.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import traceback
import webbrowser
from unittest.mock import patch

sys.path.insert(0, ".")

import customtkinter as ctk
from supabase import create_client

from core.config import WEB_VIEWER_URL
from core.hardware import (
    calcular_health_score,
    construir_resumen_para_bd,
    _inferir_refrigeracion,
)
from core.diagnostico import (
    BuscadorAsistido,
    CATALOGO_DICTAMENES,
    MicroStressTest,
    RAMAS_ARBOL,
    acciones_para,
    obtener_dictamen,
    rama_de_codigo,
)
from core.gemelo_digital import abrir_gemelo_digital
from core.hardware_map import MotherboardMapView, DIAG_TO_COMP
from core.cloud_gateway import CloudGateway
from main import AppIndiServ

# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------
SUPABASE_URL = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

# ---------------------------------------------------------------------------
# Datos simulados de telemetría (Mock de hardware real del proyecto)
# ---------------------------------------------------------------------------
HW_MOCK = {
    "mb_fabricante": "ASUSTeK COMPUTER INC.",
    "mb_modelo": "ROG STRIX B550-F GAMING (WI-FI)",
    "bios_fabricante": "American Megatrends Inc.",
    "bios_version": "3621",
    "bios_fecha": "13/01/2025",
    "nombre_cpu": "AMD Ryzen 7 5700X 8-Core Processor",
    "nucleos_fisicos": 8,
    "nucleos": 16,
    "frecuencia_base_ghz": 3.4,
    "frecuencia_actual_ghz": 3.401,
    "uso_por_nucleo": [5.0] * 16,
    "uso_cpu_total": 5.2,
    "alerta_cpu": False,
    "ram_total_mb": "32684 MB",
    "ram_disponible_mb": "18240 MB",
    "alerta_ram": False,
    "ram_total_mb_int": 32684,
    "ram_libre_mb_int": 18240,
    "ram_uso_pct": 44.2,
    "ram_tipo": "DDR4",
    "ram_velocidad_mhz": 2666,
    "ram_ranuras_ocupadas": 2,
    "ram_modulos": [
        {"ranura": "DIMM_A2", "banco": "BANK 1", "capacidad_gb": 16.0, "velocidad_mhz": 2666, "tipo": "DDR4"},
        {"ranura": "DIMM_B2", "banco": "BANK 3", "capacidad_gb": 16.0, "velocidad_mhz": 2666, "tipo": "DDR4"},
    ],
    "gpu_principal": "NVIDIA GeForce RTX 5060 Ti",
    "gpus": [
        {
            "nombre": "NVIDIA GeForce RTX 5060 Ti",
            "procesador": "NVIDIA GeForce RTX 5060 Ti",
            "vram_mb": 4095,
            "driver_version": "32.0.16.1714",
        }
    ],
    "discos_fisicos": [
        {"modelo": "Patriot Memory", "tipo": "NVMe SSD", "interfaz": "NVME", "capacidad_gb": 232.0},
        {"modelo": "WDC WD10SPZX-60Z10T0", "tipo": "HDD", "interfaz": "SATA", "capacidad_gb": 931.5},
    ],
    "particiones": [
        {"letra": "C:\\", "fs": "NTFS", "total_gb": 223.0, "usado_gb": 202.7, "libre_gb": 20.3, "uso_pct": 90.9},
        {"letra": "D:\\", "fs": "NTFS", "total_gb": 931.4, "usado_gb": 695.7, "libre_gb": 235.7, "uso_pct": 74.7},
    ],
    "so": "Windows 11",
    "so_build": "10.0.26300",
    "uptime": "2h 23m",
    "adaptador_activo": "Ethernet 2",
    "ip_local": "192.168.31.160",
    "latencia_ms": "32 ms",
}

DIAG_MOCK = {
    "categoria": "Almacenamiento",
    "subcategoria": "Thermal Throttling",
    "descripcion": "El SSD corta conexión por sobrecalentamiento.",
    "solucion": (
        "1. Instale un disipador pasivo para M.2.\n"
        "2. Mejore el flujo de aire del chasis."
    ),
    "codigo": 501,
}

PAYLOAD_REPORTE = {
    "id_ticket":      "TKT-TEST-EXPANDED",
    "cpu":            "AMD Ryzen 7 5700X (8C/16T @ 3.4 GHz)",
    "ram":            "32684 MB DDR4 @ 2666 MHz (2 ranuras)",
    "gpu":            "NVIDIA GeForce RTX 5060 Ti (4095 MB)",
    "almacenamiento": "HDD Patriot Memory 232 GB / HDD WDC WD10SPZX-60Z10T0 931 GB",
    "placa_base":     "ASUSTeK ROG STRIX B550-F GAMING (WI-FI)",
    "refrigeracion":  "Cooler Torre Aire o AIO (inferido)",
    "health_score":   80,
    "diagnostico":    "Almacenamiento (SSD / HDD) - Disco C: al 90%",
    "solucion": (
        "1. Revise el estado S.M.A.R.T. con CrystalDiskInfo.\n"
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
        "ram": {
            "total_mb": 32684,
            "libre_mb": 18240,
            "uso_pct": 44.2,
            "tipo": "DDR4",
            "velocidad": 2666,
            "ranuras": 2,
            "modulos": [
                {"ranura": "DIMM_A2", "capacidad_gb": 16.0, "tipo": "DDR4"},
                {"ranura": "DIMM_B2", "capacidad_gb": 16.0, "tipo": "DDR4"},
            ],
        },
        "gpus": [{"nombre": "NVIDIA GeForce RTX 5060 Ti", "vram_mb": 4095, "driver_version": "32.0.16.1714"}],
        "discos": {
            "fisicos": [
                {"modelo": "Patriot Memory", "tipo": "HDD", "capacidad_gb": 232.0},
                {"modelo": "WDC WD10SPZX-60Z10T0", "tipo": "HDD", "capacidad_gb": 931.5},
            ],
            "particiones": [
                {"letra": "C:\\", "uso_pct": 90.9, "total_gb": 223.0},
                {"letra": "D:\\", "uso_pct": 74.7, "total_gb": 931.4},
            ],
        },
        "red": {"adaptador": "Ethernet 2", "ip": "192.168.31.160", "latencia_ms": "32 ms"},
        "so": {"nombre": "Windows 11", "build": "10.0.26300", "uptime": "2h 23m"},
        "diagnostico_codigo": 600,
    },
}

PAYLOAD_SUGERENCIA = {
    "id_ticket":  "TKT-TEST-001",
    "sugerencia": "Mantenimiento de prueba exitoso",
}


def _separador(titulo: str):
    print("\n" + "=" * 68)
    print(f"  {titulo}")
    print("=" * 68)


# ===========================================================================
# SUITE 1: INICIALIZACIÓN E INTEGRIDAD 2D DE hardware_map.py
# ===========================================================================
def test_hardware_map_2d(root: ctk.CTk) -> bool:
    _separador("TEST 1: Inicialización e Integridad 2D de hardware_map.py")
    container = None
    try:
        container = ctk.CTkFrame(root, width=920, height=660)

        for cat_prueba, comp_esperado in [
            ("Fuente de Poder", "PSU"),
            ("Memoria RAM", "RAM"),
            ("Tarjeta Gráfica", "GPU"),
            ("Enfriamiento", "CPU"),
            ("Almacenamiento", "M2"),
            ("Adaptador de Red", "IO"),
        ]:
            for w in container.winfo_children():
                w.destroy()
            vista = MotherboardMapView(
                parent=container,
                hw_data=HW_MOCK,
                categoria_diag=cat_prueba,
                cmd_volver=lambda: None,
                cmd_visor_3d=lambda: None,
            )
            assert vista.comp_afectado == comp_esperado, (
                f"Mapeo incorrecto para {cat_prueba}: {vista.comp_afectado} != {comp_esperado}"
            )
            n_items = len(vista.canvas.find_all())
            assert n_items > 50, f"Canvas incompleto ({n_items} elementos)"

        bounds_map = {
            "CPU": vista._cpu_bounds,
            "RAM": vista._ram_bounds,
            "GPU": vista._gpu_bounds,
            "M2":  vista._m2_bounds,
            "IO":  vista._io_bounds,
            "PSU": vista._psu_bounds,
            "BAY": vista._bay_bounds,
        }
        for comp, (x1, y1, x2, y2) in bounds_map.items():
            assert 0 <= x1 < x2 <= MotherboardMapView.CW, f"Bounds X inválidos en {comp}"
            assert 0 <= y1 < y2 <= MotherboardMapView.CH, f"Bounds Y inválidos en {comp}"
            print(f"  [OK] Coordenadas {comp:<3s}: ({x1:3d}, {y1:3d}) -> ({x2:3d}, {y2:3d})")

        gpu_x1, gpu_y1, gpu_x2, gpu_y2 = vista._gpu_bounds
        psu_x1, psu_y1, psu_x2, psu_y2 = vista._psu_bounds
        assert psu_y1 >= gpu_y2, f"Colisión PSU/GPU: {psu_y1} < {gpu_y2}"
        print(f"  [OK] Separación geométrica PSU/GPU verificada (GPU y2={gpu_y2} < PSU y1={psu_y1}).")

        for comp in ("CPU", "RAM", "GPU", "M2", "IO", "PSU"):
            x1, y1, x2, y2 = bounds_map[comp]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            assert vista._hit_test(cx, cy) == comp
            titulo, datos, estado = vista._build_tooltip_data(comp)
            assert titulo and datos and estado
            vista._show_tooltip(comp, cx, cy)
            assert len(vista._tooltip_items) == 5
            vista._clear_tooltip()
            assert len(vista._tooltip_items) == 0

        print("[OK] Renderizado 2D, coordenadas y tooltips validados sin excepciones.")
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_hardware_map_2d: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False
    finally:
        if container is not None:
            try:
                container.destroy()
            except Exception:
                pass


# ===========================================================================
# SUITE 2: SERIALIZACIÓN DE TELEMETRÍA (CPU, GPU, RAM, ESTADO TÉRMICO)
# ===========================================================================
def test_serializacion_telemetria() -> bool:
    _separador("TEST 2: Serialización de Telemetría (CPU, GPU, RAM, Estado Térmico)")
    try:
        payload = construir_resumen_para_bd("7550-TICKET-9999", HW_MOCK, DIAG_MOCK)
        deserializado = json.loads(json.dumps(payload, ensure_ascii=False))

        columnas_esperadas = {
            "id_ticket", "cpu", "ram", "gpu", "almacenamiento",
            "placa_base", "refrigeracion", "health_score",
            "diagnostico", "solucion", "specs_json"
        }
        assert columnas_esperadas.issubset(deserializado.keys())

        specs = deserializado["specs_json"]
        assert specs["cpu"]["nucleos_fisicos"] == 8 and specs["cpu"]["nucleos_logicos"] == 16
        assert specs["ram"]["total_mb"] == 32684 and specs["ram"]["tipo"] == "DDR4"
        assert len(specs["gpus"]) == 1 and specs["gpus"][0]["vram_mb"] == 4095
        print(f"  [OK] CPU serializada : {deserializado['cpu']}")
        print(f"  [OK] RAM serializada : {deserializado['ram']}")
        print(f"  [OK] GPU serializada : {deserializado['gpu']}")

        assert "Torre" in _inferir_refrigeracion(HW_MOCK)
        assert "Low-TDP" in _inferir_refrigeracion({"nombre_cpu": "Intel Celeron N4020"})
        assert "Alta Gama" in _inferir_refrigeracion({"nombre_cpu": "AMD Ryzen 9 7950X"})

        score = calcular_health_score(HW_MOCK)
        assert score == 80, f"Health score inesperado: {score}"
        print(f"  [OK] Health Score calculado: {score}/100")

        stress = MicroStressTest(callback_progreso=lambda m: None, callback_resultado=lambda r: None)
        res_estable = stress._analizar([3400.0, 3380.0, 3390.0], [98.0, 99.5, 100.0])
        res_throttle = stress._analizar([3800.0, 3500.0, 2900.0], [100.0, 100.0, 99.0])
        assert res_estable["throttling"] is False
        assert res_throttle["throttling"] is True
        print(
            f"  [OK] Analizador Térmico: estable ({res_estable['caida_pct']}% caída) "
            f"| throttling ({res_throttle['caida_pct']}% caída)"
        )
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_serializacion_telemetria: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ===========================================================================
# SUITE 3: GENERACIÓN DE TICKETS Y ENLACES DE CONSULTA PÚBLICA
# ===========================================================================
def test_tickets_y_enlaces_publicos() -> bool:
    _separador("TEST 3: Generación de Tickets y Enlaces Públicos (Gemelo Digital 3D)")
    try:
        assert WEB_VIEWER_URL.startswith("https://")
        assert "localhost" not in WEB_VIEWER_URL and "127.0.0.1" not in WEB_VIEWER_URL

        ticket_generado = f"7550-TICKET-{random.randint(1000, 9999)}".strip()
        assert re.match(r"^\d{4}-TICKET-\d{4}$", ticket_generado)

        with patch.object(webbrowser, "open", return_value=True) as mock_open:
            url_generada = abrir_gemelo_digital(f"  {ticket_generado}  ", root_widget=None)
            mock_open.assert_called_once_with(f"{WEB_VIEWER_URL}/?ticket={ticket_generado}")

        assert url_generada == f"{WEB_VIEWER_URL}/?ticket={ticket_generado}"
        print(f"  [OK] Ticket generado y sanitizado : {ticket_generado}")
        print(f"  [OK] Enlace público verificado    : {url_generada}")
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_tickets_y_enlaces_publicos: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ===========================================================================
# SUITE 4: MICRO-STRESS TEST SEGURO, CONTROLADO Y CANCELABLE
# ===========================================================================
def test_micro_stress_test_seguro() -> bool:
    _separador("TEST 4: Micro-Stress Test de CPU Seguro, Multihilo y Cancelable")
    try:
        # 4.1 Ejecución controlada en hilo secundario con muestras en vivo
        progresos: list[str] = []
        muestras: list[dict] = []
        resultado: dict = {}

        test_ok = MicroStressTest(
            callback_progreso=lambda msg: progresos.append(msg),
            callback_resultado=lambda res: resultado.update(res),
            callback_muestra=lambda m: muestras.append(m),
            duracion_seg=2.0,
            max_workers=2,
        )
        t0 = time.perf_counter()
        assert test_ok.iniciar() is True, "No inició el benchmark"
        assert test_ok.iniciar() is False, "Permitió doble inicio simultáneo"
        termino = test_ok.esperar(timeout=8.0)
        elapsed = time.perf_counter() - t0

        assert termino is True, "El hilo secundario de stress test no finalizó a tiempo"
        assert test_ok.activo is False and test_ok.workers_vivos() == 0, "Quedaron workers vivos"
        assert "error" not in resultado, f"Resultado devolvió error: {resultado}"
        assert resultado.get("n_muestras", 0) >= 2, f"Pocas muestras: {resultado}"
        assert len(muestras) >= 2 and len(progresos) >= 2
        assert resultado.get("rendimiento_avg_mops", 0) > 0, "No midió Mops/s reales"
        print(
            f"  [OK] Ejecución acotada ({elapsed:.2f}s) | modo={resultado.get('modo')} "
            f"| muestras={resultado['n_muestras']} | {resultado['rendimiento_avg_mops']} Mops/s"
        )

        # 4.2 Cancelación segura e inmediata sin dejar procesos huérfanos
        res_cancel: dict = {}
        test_cancel = MicroStressTest(
            callback_progreso=lambda m: None,
            callback_resultado=lambda r: res_cancel.update(r),
            duracion_seg=10.0,
            max_workers=2,
        )
        test_cancel.iniciar()
        time.sleep(0.8)
        t_c = time.perf_counter()
        test_cancel.cancelar()
        assert test_cancel.esperar(timeout=4.0) is True, "Cancelación no detuvo el hilo"
        dt_cancel = time.perf_counter() - t_c
        assert dt_cancel < 2.5, f"Cancelación tardó demasiado ({dt_cancel:.2f}s)"
        assert res_cancel.get("cancelado") is True, "No marcó bandera 'cancelado'"
        assert test_cancel.workers_vivos() == 0, "Workers huérfanos tras cancelar"
        print(f"  [OK] Cancelación segura verificada en {dt_cancel:.2f}s (0 workers huérfanos).")

        # 4.3 Resiliencia ante excepción en callback de progreso (no debe abortar)
        res_err_cb: dict = {}

        def _cb_defectuoso(_msg: str):
            raise RuntimeError("Fallo simulado de widget destruido")

        test_resiliente = MicroStressTest(
            callback_progreso=_cb_defectuoso,
            callback_resultado=lambda r: res_err_cb.update(r),
            duracion_seg=1.2,
            modo="hilos",
            max_workers=2,
        )
        test_resiliente.iniciar()
        assert test_resiliente.esperar(timeout=5.0) is True
        assert "error" not in res_err_cb and res_err_cb.get("n_muestras", 0) >= 1
        print("  [OK] Resiliencia ante errores en callbacks de UI verificada.")
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_micro_stress_test_seguro: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ===========================================================================
# SUITE 5: BUSCADOR ASISTIDO MULTI-CASO Y EJECUCIÓN DIRECTA
# ===========================================================================
def test_buscador_asistido_multicaso() -> bool:
    _separador("TEST 5: Buscador Asistido Inteligente (Cobertura de 26 Casos)")
    try:
        # 5.1 Verificar que las 26 hojas del catálogo existen y tienen cobertura
        assert len(CATALOGO_DICTAMENES) == 26, f"Catálogo incompleto: {len(CATALOGO_DICTAMENES)}"
        assert len(RAMAS_ARBOL) == 8, f"Ramas incompletas: {len(RAMAS_ARBOL)}"

        casos_prueba = [
            ("el cable de energía está suelto del tomacorriente", 101),
            ("el interruptor trasero de la fuente estaba en off", 102),
            ("la pc no prende, sin luces ni ventiladores, nada", 103),
            ("el ventilador de la fuente está trabado y huele a quemado", 104),
            ("se apaga sola de golpe, apagados bruscos por voltaje", 105),
            ("los ventiladores giran pero no hace post, clear cmos", 106),
            ("hace pitidos cortos repetitivos al encender", 201),
            ("un pitido largo y dos cortos, la tarjeta gráfica no inicia", 202),
            ("tono continuo de la placa, posible cortocircuito", 203),
            ("pantalla negra sin señal en el monitor por hdmi", 204),
            ("el ventilador del cpu no gira, cooler detenido", 301),
            ("el procesador se calienta mucho, temperatura alta, pasta térmica seca", 302),
            ("la bios avisa calor pero el sensor de temperatura parece falso", 303),
            ("se reinicia antes del logo de la bios en bucle", 401),
            ("no carga windows, bootloader corrupto, bootrec", 402),
            ("se reinicia en el logo de windows tras una actualización de driver", 403),
            ("el ssd nvme desaparece cuando lo uso mucho y se calienta", 501),
            ("quiero revisar la salud smart del disco con crystaldiskinfo", 502),
            ("cpu al 100 en reposo por un proceso, quizás virus", 601),
            ("disco al 100% todo el tiempo, muy lenta", 602),
            ("el arranque es lento, muchos programas de inicio", 603),
            ("la velocidad de la ram en mhz no coincide en la bios", 701),
            ("pantallazo azul jugando con xmp activado", 702),
            ("no tengo internet, el wifi no conecta", 801),
            ("ping alto y lag, pérdida de paquetes", 802),
            ("las paginas no cargan, error de dns en el navegador", 803),
        ]

        aciertos_top1 = 0
        for consulta, codigo_esperado in casos_prueba:
            resultados = BuscadorAsistido.buscar(consulta, top_n=3, hw=HW_MOCK)
            assert resultados, f"Sin resultados para: {consulta}"
            codigos_top3 = [r["codigo"] for r in resultados]
            assert codigo_esperado in codigos_top3, (
                f"Código #{codigo_esperado} no está en top-3 {codigos_top3} para '{consulta}'"
            )
            if resultados[0]["codigo"] == codigo_esperado:
                aciertos_top1 += 1

            # Verificar ejecución directa de diagnóstico para cada caso
            diag = BuscadorAsistido.diagnosticar(consulta, hw=HW_MOCK)
            assert diag is not None and "dictamen" in diag and "acciones" in diag
            for acc_req in ("mapa_2d", "gemelo_3d", "guardar_reporte", "arbol_guiado"):
                assert acc_req in diag["acciones"], f"Falta acción {acc_req} en código #{codigo_esperado}"

        precision = (aciertos_top1 / len(casos_prueba)) * 100.0
        assert precision >= 90.0, f"Precisión top-1 insuficiente: {precision:.1f}%"
        print(
            f"  [OK] Cobertura verificada en los {len(casos_prueba)} casos del árbol "
            f"(Top-1: {aciertos_top1}/{len(casos_prueba)} = {precision:.1f}%)."
        )
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_buscador_asistido_multicaso: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ===========================================================================
# SUITE 6: COHERENCIA VISUAL/ESTRUCTURAL DE VISTAS Y ACCIONES EN AppIndiServ
# ===========================================================================
def test_vistas_y_ejecucion_directa_ui(app: AppIndiServ) -> bool:
    _separador("TEST 6: Vistas UI (Login, Dashboard, Pestañas, Buscador, Stress Test)")
    archivos_creados: list[str] = []
    try:
        app.withdraw()
        app.dni_usuario_activo = "75509123"
        app.hardware_detectado = HW_MOCK

        # 6.1 Login y Registro
        app.pantalla_login()
        app.update_idletasks()
        assert hasattr(app, "entry_dni") and app.entry_dni.winfo_exists()
        assert hasattr(app, "entry_correo") and app.entry_correo.winfo_exists()
        assert hasattr(app, "entry_pass") and app.entry_pass.winfo_exists()

        app.pantalla_registro()
        app.update_idletasks()
        assert hasattr(app, "reg_dni") and app.reg_dni.winfo_exists()
        print("  [OK] Vistas Login y Registro inicializadas correctamente.")

        # 6.2 Dashboard y sus 5 pestañas didácticas
        app.pantalla_dashboard()
        app.update_idletasks()
        assert hasattr(app, "tabs_dashboard") and app.tabs_dashboard.winfo_exists()
        for nombre_tab in ("General", "CPU / RAM", "Gráficos", "Discos", "Red"):
            tab_w = app.tabs_dashboard.tab(nombre_tab)
            assert len(tab_w.winfo_children()) > 0, f"Pestaña '{nombre_tab}' vacía"
        print("  [OK] Dashboard y 5 pestañas (General, CPU/RAM, Gráficos, Discos, Red) verificadas.")

        # 6.3 Árbol de diagnóstico (8 ramas) y Multisíntoma
        app.iniciar_diagnostico()
        app.update_idletasks()
        for r_id in range(len(RAMAS_ARBOL)):
            app.seleccionar_sintoma(r_id)
            app.update_idletasks()
            assert app.arbol_fase == 1 and app.arbol_rama == r_id

        app.pantalla_multisintoma()
        app.update_idletasks()
        app._check_vars[0].set(True)
        app._check_vars[3].set(True)
        app._calcular_multisintoma()
        app.update_idletasks()
        assert len(app._cards_multisintoma.winfo_children()) > 0
        print("  [OK] Árbol Inferencial (8 ramas) y Multisíntoma operativos.")

        # 6.4 Buscador Asistido: búsqueda + ejecución directa + Mapa 2D + Gemelo 3D + Reporte
        app.pantalla_buscador()
        app.update_idletasks()
        app._entry_busqueda.insert(0, "pantalla azul jugando con xmp activado")
        app._ejecutar_busqueda(auto_ejecutar=True)
        app.update_idletasks()

        assert app.dictamen_final is not None and app.dictamen_final["codigo"] == 702, (
            f"Ejecución directa en buscador no seleccionó #702: {app.dictamen_final}"
        )
        assert len(app._scroll_resultados_busq.winfo_children()) > 0
        assert len(app._panel_dictamen_busq.winfo_children()) > 0

        # Probar selector de catálogo directo con otra hoja (ej. #801 Red)
        app._al_elegir_combo_catalogo("#801 · Adaptador de Red — Sin conectividad")
        app.update_idletasks()
        assert app.dictamen_final["codigo"] == 801

        # Acción 1 desde el diagnóstico directo: abrir Mapa 2D
        app._abrir_mapa_desde_vista(app.dictamen_final["categoria"], app.pantalla_buscador)
        app.update_idletasks()
        assert hasattr(app, "mapa_actual") and app.mapa_actual.comp_afectado == "IO"

        # Acción 2: lanzar Gemelo Digital 3D (mockeando navegador y nube)
        with patch.object(webbrowser, "open", return_value=True) as mock_browser, \
             patch.object(CloudGateway, "subir_ticket", return_value=True), \
             patch.object(CloudGateway, "subir_sugerencia", return_value=True):
            url_3d = app.abrir_visor_3d()
            app.update_idletasks()
            assert WEB_VIEWER_URL in url_3d and app.ticket_id_actual in url_3d
            mock_browser.assert_called_once()

        # Acción 3: guardar reporte dual TXT + JSON
        with patch.object(CloudGateway, "subir_ticket", return_value=True), \
             patch.object(CloudGateway, "subir_sugerencia", return_value=True):
            txt_path, json_path = app.guardar_reporte_final(permanecer=True)
            archivos_creados.extend([txt_path, json_path])
            assert os.path.exists(txt_path) and os.path.exists(json_path)
            with open(json_path, "r", encoding="utf-8") as jf:
                data_rep = json.load(jf)
            assert data_rep["diagnostico"]["codigo"] == 801

        print("  [OK] Buscador Asistido: diagnóstico directo, Mapa 2D, Gemelo 3D y Reporte verificados.")

        # 6.5 Vista de Micro-Stress Test en la UI
        app.pantalla_stress_test()
        app.update_idletasks()
        assert hasattr(app, "_btn_stress") and app._btn_stress.winfo_exists()
        assert hasattr(app, "_spark_stress") and app._spark_stress.winfo_exists()
        app._mostrar_resultado_stress({
            "throttling": False,
            "nivel": "ok",
            "freq_max_ghz": 3.4,
            "freq_min_ghz": 3.4,
            "freq_avg_ghz": 3.4,
            "caida_pct": 0.0,
            "caida_rendimiento_pct": 1.2,
            "rendimiento_avg_mops": 42.5,
            "indice_rendimiento": 4250,
            "uso_max_pct": 95.0,
            "uso_avg_pct": 88.0,
            "n_muestras": 6,
            "modo": "procesos",
            "duracion_objetivo_s": 10.0,
            "diagnostico": "✅  RENDIMIENTO ESTABLE — Sin throttling detectado",
        })
        app.update_idletasks()
        contenido_log = app._stress_log.get("0.0", "end").strip()
        assert "RENDIMIENTO ESTABLE" in contenido_log and "42.5 Mops/s" in contenido_log
        print("  [OK] Vista Micro-Stress Test y renderizado de métricas verificados.")
        return True
    except Exception as exc:
        print(f"[ERROR] Fallo en test_vistas_y_ejecucion_directa_ui: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False
    finally:
        for path in archivos_creados:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


# ===========================================================================
# SUITE 7 & 8: PERSISTENCIA CLOUD EN SUPABASE
# ===========================================================================
def test_reportes_diagnostico(client) -> bool:
    _separador("TEST 7: reportes_diagnostico (Supabase Upsert)")
    try:
        response = (
            client.table("reportes_diagnostico")
            .upsert(PAYLOAD_REPORTE, on_conflict="id_ticket")
            .execute()
        )
        if response.data:
            print(f"  [OK] Upsert en reportes_diagnostico exitoso (id_ticket={response.data[0].get('id_ticket')}).")
            return True
        print(f"  [WARN] Upsert sin datos: {response}")
        return False
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def test_sugerencias_locales(client) -> bool:
    _separador("TEST 8: sugerencias_locales (Supabase Upsert)")
    try:
        response = (
            client.table("sugerencias_locales")
            .upsert(PAYLOAD_SUGERENCIA, on_conflict="id_ticket")
            .execute()
        )
        if response.data:
            print(f"  [OK] Upsert en sugerencias_locales exitoso (id_ticket={response.data[0].get('id_ticket')}).")
            return True
        print(f"  [WARN] Upsert sin datos: {response}")
        return False
    except Exception as exc:
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def main() -> int:
    print("=" * 68)
    print("  IndiServ Analytica — Arnés Integral de Pruebas (Test Harness)")
    print("=" * 68)

    app = AppIndiServ()
    app.withdraw()
    try:
        ok_map = test_hardware_map_2d(app)
        ok_tel = test_serializacion_telemetria()
        ok_url = test_tickets_y_enlaces_publicos()
        ok_str = test_micro_stress_test_seguro()
        ok_bus = test_buscador_asistido_multicaso()
        ok_ui  = test_vistas_y_ejecucion_directa_ui(app)
    finally:
        try:
            app._al_cerrar_ventana()
        except Exception:
            pass

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        ok_rep = test_reportes_diagnostico(client)
        ok_sug = test_sugerencias_locales(client)
    except Exception as exc:
        print(f"\n[ERROR] No se pudo crear el cliente Supabase: {exc}")
        ok_rep = False
        ok_sug = False

    resultados = [
        ("1. Mapa Esquemático 2D (hardware_map.py)", ok_map),
        ("2. Serialización de Telemetría y Térmica", ok_tel),
        ("3. Generación de Tickets y Enlace Público", ok_url),
        ("4. Micro-Stress Test Seguro y Cancelable", ok_str),
        ("5. Buscador Asistido (26 Casos + Directo)", ok_bus),
        ("6. Coherencia Visual UI y Flujo de Acciones", ok_ui),
        ("7. Supabase: reportes_diagnostico (upsert)", ok_rep),
        ("8. Supabase: sugerencias_locales (upsert)", ok_sug),
    ]

    print("\n" + "=" * 68)
    print("  RESUMEN DE EJECUCIÓN DEL ARNÉS (HARNESS)")
    print("=" * 68)
    for nombre, estado in resultados:
        print(f"  {nombre:<46s} : {'[OK] PASSED' if estado else '[FAIL] FAILED'}")
    print("=" * 68)

    return 0 if all(est for _, est in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
