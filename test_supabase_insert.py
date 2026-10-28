"""
test_supabase_insert.py
=======================
Script de prueba independiente para verificar la conexion a Supabase
y la insercion en dos tablas:

  1. 'reportes_diagnostico' — payload expandido con todas las columnas
  2. 'sugerencias_locales'  — payload estricto de 2 campos (id_ticket, sugerencia)

Uso:
    .\\venv\\Scripts\\python.exe test_supabase_insert.py

Retorna 0 si ambas tablas responden correctamente, 1 si alguna falla.
"""

import sys
import json
import traceback

sys.path.insert(0, ".")

from supabase import create_client

# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------
SUPABASE_URL = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

# ---------------------------------------------------------------------------
# Payload de prueba: reportes_diagnostico
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Payload de prueba: sugerencias_locales
# Esquema exacto: SOLO id_ticket (text PK) y sugerencia (text)
# ---------------------------------------------------------------------------
PAYLOAD_SUGERENCIA = {
    "id_ticket":  "TKT-TEST-001",
    "sugerencia": "Mantenimiento de prueba exitoso",
}


# ---------------------------------------------------------------------------
def _separador(titulo: str):
    print("\n" + "=" * 65)
    print(f"  {titulo}")
    print("=" * 65)


def test_reportes_diagnostico(client) -> bool:
    _separador("TEST 1: reportes_diagnostico (upsert)")
    print(f"  Ticket  : {PAYLOAD_REPORTE['id_ticket']}")
    print(f"  Payload (sin specs_json):")
    p_log = {k: (v if k != "specs_json" else "{...jsonb...}") for k, v in PAYLOAD_REPORTE.items()}
    print(json.dumps(p_log, indent=4, ensure_ascii=False))

    try:
        response = (
            client.table("reportes_diagnostico")
            .upsert(PAYLOAD_REPORTE, on_conflict="id_ticket")
            .execute()
        )
        if response.data:
            print(f"\n[OK] Insercion en reportes_diagnostico exitosa.")
            print(f"     Filas devueltas: {len(response.data)}")
            print(f"     id_ticket: {response.data[0].get('id_ticket')}")
            print(f"     health_score: {response.data[0].get('health_score')}")
            print(f"     fecha_creacion: {response.data[0].get('fecha_creacion')}")
            return True
        else:
            print(f"\n[WARN] Upsert sin datos en response.data. response={response}")
            return False
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def test_sugerencias_locales(client) -> bool:
    _separador("TEST 2: sugerencias_locales (upsert)")
    print(f"  Ticket  : {PAYLOAD_SUGERENCIA['id_ticket']}")
    print(f"  Payload (payload estricto 2 campos):")
    print(json.dumps(PAYLOAD_SUGERENCIA, indent=4, ensure_ascii=False))

    try:
        response = (
            client.table("sugerencias_locales")
            .upsert(PAYLOAD_SUGERENCIA, on_conflict="id_ticket")
            .execute()
        )
        if response.data:
            print(f"\n[OK] Insercion en sugerencias_locales exitosa.")
            print(f"     Filas devueltas: {len(response.data)}")
            print(f"     Datos confirmados por Supabase:")
            print(json.dumps(response.data, indent=4, ensure_ascii=False))
            return True
        else:
            print(f"\n[WARN] Upsert sin datos en response.data. response={response}")
            return False
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}")
        print("  >> Verifica que la tabla solo tenga columnas: id_ticket, sugerencia")
        print("  >> Un campo extra en el payload causaria un error 400 de PostgREST.")
        traceback.print_exc()
        return False


def main() -> int:
    print("=" * 65)
    print("  IndiServ Analytica - Suite de Test de Persistencia en Supabase")
    print("=" * 65)

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Cliente Supabase inicializado.")
    except Exception as exc:
        print(f"[ERROR] No se pudo crear el cliente Supabase: {exc}")
        return 2

    ok1 = test_reportes_diagnostico(client)
    ok2 = test_sugerencias_locales(client)

    print("\n" + "=" * 65)
    print("  RESUMEN")
    print("=" * 65)
    print(f"  reportes_diagnostico : {'[OK] PASSED' if ok1 else '[FAIL] FAILED'}")
    print(f"  sugerencias_locales  : {'[OK] PASSED' if ok2 else '[FAIL] FAILED'}")
    print("=" * 65)

    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
