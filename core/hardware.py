"""
core/hardware.py — Perfilador de Hardware Exhaustivo (Fase 1)
=============================================================
Recopila telemetría profunda de la máquina Windows mediante psutil,
platform y consultas WMI nativas vía PowerShell (subprocess puro, sin
DLLs externas ni compiladores).

RETROCOMPATIBILIDAD GARANTIZADA
  El dict retornado siempre incluye las claves legacy:
    nombre_cpu, nucleos, ram_total_mb, ram_disponible_mb, so,
    alerta_ram, alerta_cpu
  Estas clave son usadas por main.py y guardar_reporte_final().
"""

from __future__ import annotations

import platform
import subprocess
import json
import time
import re
import datetime
import psutil
from typing import Any


# ---------------------------------------------------------------------------
# Utilidad interna: ejecutar consulta WMI mediante PowerShell
# ---------------------------------------------------------------------------
def _wmi_query(clase_wmi: str, propiedades: list[str]) -> list[dict[str, Any]]:
    """
    Ejecuta Get-CimInstance <clase_wmi> en PowerShell y devuelve una lista
    de dicts con las propiedades solicitadas.
    Retorna [] ante cualquier fallo para no bloquear el resto del escaneo.
    """
    props_str = ", ".join(propiedades)
    script = (
        f"Get-CimInstance -ClassName {clase_wmi} | "
        f"Select-Object {props_str} | "
        "ConvertTo-Json -Depth 2 -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout.strip())
        # PowerShell devuelve un objeto o un array
        if isinstance(data, dict):
            return [data]
        return data
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Secciones de telemetría
# ---------------------------------------------------------------------------

def _escanear_motherboard_bios() -> dict[str, str]:
    """Fabricante, modelo, versión y fecha de BIOS."""
    mb = _wmi_query("Win32_BaseBoard", ["Manufacturer", "Product"])
    bios = _wmi_query("Win32_BIOS", ["Manufacturer", "SMBIOSBIOSVersion", "ReleaseDate"])

    mb_data = mb[0] if mb else {}
    bios_data = bios[0] if bios else {}

    # La fecha de BIOS puede llegar en dos formatos WMI:
    #   "/Date(1736726400000)/"  → epoch Unix en milisegundos (CIM moderno)
    #   "20250113000000.000000+000" → cadena datetime clásica
    fecha_raw = bios_data.get("ReleaseDate", "") or ""
    fecha_bios = "Desconocida"
    epoch_match = re.search(r"/Date\((\d+)\)/", fecha_raw)
    if epoch_match:
        ts = int(epoch_match.group(1)) / 1000
        d = datetime.datetime.utcfromtimestamp(ts)
        fecha_bios = d.strftime("%d/%m/%Y")
    elif len(fecha_raw) >= 8 and fecha_raw[:8].isdigit():
        fecha_bios = f"{fecha_raw[6:8]}/{fecha_raw[4:6]}/{fecha_raw[:4]}"

    return {
        "mb_fabricante": mb_data.get("Manufacturer", "Desconocido"),
        "mb_modelo": mb_data.get("Product", "Desconocido"),
        "bios_fabricante": bios_data.get("Manufacturer", "Desconocido"),
        "bios_version": bios_data.get("SMBIOSBIOSVersion", "Desconocida"),
        "bios_fecha": fecha_bios,
    }


def _escanear_cpu() -> dict[str, Any]:
    """CPU: modelo, frecuencias, núcleos físicos/lógicos, uso por núcleo."""
    # Nombre del procesador vía WMI (más fiable que platform.processor())
    cpu_wmi = _wmi_query("Win32_Processor", ["Name", "NumberOfCores", "NumberOfLogicalProcessors"])
    cpu_data = cpu_wmi[0] if cpu_wmi else {}

    nombre_cpu = (cpu_data.get("Name") or platform.processor() or "CPU Genérica Detectada").strip()
    nucleos_fisicos = int(cpu_data.get("NumberOfCores") or psutil.cpu_count(logical=False) or 1)
    nucleos_logicos = int(cpu_data.get("NumberOfLogicalProcessors") or psutil.cpu_count(logical=True) or 1)

    # Frecuencias
    freq = psutil.cpu_freq()
    freq_base_ghz = round(freq.max / 1000, 2) if freq and freq.max else 0.0
    freq_actual_ghz = round(freq.current / 1000, 2) if freq and freq.current else 0.0

    # Uso por núcleo (intervalo corto para no bloquear)
    uso_por_nucleo = psutil.cpu_percent(interval=0.5, percpu=True)

    return {
        "nombre_cpu": nombre_cpu,
        "nucleos_fisicos": nucleos_fisicos,
        "nucleos": nucleos_logicos,           # clave legacy
        "frecuencia_base_ghz": freq_base_ghz,
        "frecuencia_actual_ghz": freq_actual_ghz,
        "uso_por_nucleo": uso_por_nucleo,
        "uso_cpu_total": round(sum(uso_por_nucleo) / len(uso_por_nucleo), 1) if uso_por_nucleo else 0.0,
        "alerta_cpu": nucleos_logicos <= 2,    # clave legacy
    }


def _escanear_ram() -> dict[str, Any]:
    """RAM: total/libre (psutil) + velocidad, tipo y ranuras (WMI)."""
    memoria = psutil.virtual_memory()
    ram_total_mb_int = int(memoria.total / (1024 * 1024))
    ram_libre_mb_int = int(memoria.available / (1024 * 1024))

    # Detalles físicos de los módulos
    modulos_wmi = _wmi_query(
        "Win32_PhysicalMemory",
        ["Capacity", "Speed", "SMBIOSMemoryType", "DeviceLocator", "BankLabel"]
    )

    # SMBIOSMemoryType → nombre legible
    tipo_map = {
        20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
        24: "DDR3", 26: "DDR4", 34: "DDR5", 0: "Desconocido"
    }

    modulos = []
    for m in modulos_wmi:
        tipo_num = int(m.get("SMBIOSMemoryType") or 0)
        cap_bytes = int(m.get("Capacity") or 0)
        modulos.append({
            "ranura": m.get("DeviceLocator", "?"),
            "banco": m.get("BankLabel", "?"),
            "capacidad_gb": round(cap_bytes / (1024 ** 3), 1),
            "velocidad_mhz": m.get("Speed", "?"),
            "tipo": tipo_map.get(tipo_num, f"Tipo {tipo_num}"),
        })

    tipo_ram = modulos[0]["tipo"] if modulos else "Desconocido"
    velocidad_ram = modulos[0]["velocidad_mhz"] if modulos else "?"

    return {
        # Claves legacy (en formato string para retrocompatibilidad)
        "ram_total_mb": f"{ram_total_mb_int} MB",
        "ram_disponible_mb": f"{ram_libre_mb_int} MB",
        "alerta_ram": ram_total_mb_int <= 2048,   # clave legacy
        # Claves extendidas
        "ram_total_mb_int": ram_total_mb_int,
        "ram_libre_mb_int": ram_libre_mb_int,
        "ram_uso_pct": round(memoria.percent, 1),
        "ram_tipo": tipo_ram,
        "ram_velocidad_mhz": velocidad_ram,
        "ram_ranuras_ocupadas": len(modulos),
        "ram_modulos": modulos,
    }


def _escanear_gpu() -> dict[str, Any]:
    """GPU(s): modelo, VRAM y versión del driver."""
    gpus_wmi = _wmi_query(
        "Win32_VideoController",
        ["Name", "AdapterRAM", "DriverVersion", "VideoProcessor"]
    )

    gpus = []
    for g in gpus_wmi:
        vram_bytes = int(g.get("AdapterRAM") or 0)
        # AdapterRAM puede ser un entero de 32 bits sin signo — corregir overflow
        if vram_bytes < 0:
            vram_bytes += 2 ** 32
        gpus.append({
            "nombre": g.get("Name", "GPU Desconocida"),
            "procesador": g.get("VideoProcessor", ""),
            "vram_mb": round(vram_bytes / (1024 ** 2), 0),
            "driver_version": g.get("DriverVersion", "Desconocida"),
        })

    gpu_principal = gpus[0]["nombre"] if gpus else "No detectada"

    return {
        "gpu_principal": gpu_principal,
        "gpus": gpus,
    }


def _escanear_almacenamiento() -> dict[str, Any]:
    """Discos físicos (tipo de interfaz) + particiones lógicas."""
    # Discos físicos y tipo de interfaz
    discos_fisicos_wmi = _wmi_query(
        "Win32_DiskDrive",
        ["Model", "MediaType", "InterfaceType", "Size", "SerialNumber"]
    )

    discos_fisicos = []
    for d in discos_fisicos_wmi:
        tam_bytes = int(d.get("Size") or 0)
        interfaz = (d.get("InterfaceType") or "").upper()
        media = (d.get("MediaType") or "").lower()

        # Clasificación simplificada
        if "nvme" in (d.get("Model") or "").lower() or "nvme" in interfaz:
            tipo_disco = "NVMe SSD"
        elif interfaz in ("USB", "1394"):
            tipo_disco = "Externo USB"
        elif "ssd" in media or "solid" in media:
            tipo_disco = "SATA SSD"
        else:
            tipo_disco = "HDD"

        discos_fisicos.append({
            "modelo": d.get("Model", "Disco Desconocido"),
            "tipo": tipo_disco,
            "interfaz": interfaz,
            "capacidad_gb": round(tam_bytes / (1024 ** 3), 1),
        })

    # Particiones lógicas vía psutil
    particiones = []
    for part in psutil.disk_partitions(all=False):
        try:
            uso = psutil.disk_usage(part.mountpoint)
            particiones.append({
                "letra": part.mountpoint,
                "fs": part.fstype,
                "total_gb": round(uso.total / (1024 ** 3), 1),
                "usado_gb": round(uso.used / (1024 ** 3), 1),
                "libre_gb": round(uso.free / (1024 ** 3), 1),
                "uso_pct": uso.percent,
            })
        except PermissionError:
            continue

    return {
        "discos_fisicos": discos_fisicos,
        "particiones": particiones,
    }


def _escanear_red_y_so() -> dict[str, Any]:
    """Adaptador activo, ping a gateway/DNS, uptime y compilación de Windows."""
    # Uptime
    boot_ts = psutil.boot_time()
    uptime_seg = time.time() - boot_ts
    horas = int(uptime_seg // 3600)
    minutos = int((uptime_seg % 3600) // 60)
    uptime_str = f"{horas}h {minutos}m"

    # SO extendido
    so_version = f"{platform.system()} {platform.release()}"
    build_win = platform.version()  # e.g. "10.0.22621"

    # Adaptadores de red activos
    adaptadores = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for iface, stat in stats.items():
        if stat.isup:
            ips = [
                a.address for a in addrs.get(iface, [])
                if ":" not in a.address          # excluye IPv6
                and "-" not in a.address          # excluye MACs (formato Windows AA-BB-CC)
                and not a.address.startswith("127.")  # excluye loopback
            ]
            if ips:
                adaptadores.append({"nombre": iface, "ip": ips[0], "velocidad_mbps": stat.speed})

    adaptador_activo = adaptadores[0]["nombre"] if adaptadores else "Ninguno"
    ip_local = adaptadores[0]["ip"] if adaptadores else "N/A"

    # Latencia: ping a 8.8.8.8 (DNS Google) — fallback a gateway
    latencia_ms = _ping_latencia("8.8.8.8")

    return {
        "so": so_version,                  # clave legacy
        "so_build": build_win,
        "uptime": uptime_str,
        "adaptador_activo": adaptador_activo,
        "ip_local": ip_local,
        "latencia_ms": latencia_ms,
    }


def _ping_latencia(host: str) -> str:
    """Devuelve la latencia en ms como string, o 'N/A' si falla."""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "2000", host],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "tiempo" in line.lower() or "time" in line.lower() or "ms" in line.lower():
                # Buscar patrón "tiempo=XXms" o "time=XXms"
                import re
                m = re.search(r"(?:tiempo|time)[<=](\d+)\s*ms", line, re.IGNORECASE)
                if m:
                    return f"{m.group(1)} ms"
    except Exception:
        pass
    return "N/A"


# ---------------------------------------------------------------------------
# Clase pública
# ---------------------------------------------------------------------------

class LectorHardware:
    """
    API pública del módulo de hardware.

    Uso:
        datos = LectorHardware.escanear_entorno()

    El dict resultante conserva TODAS las claves legacy para no romper
    el código existente en main.py y guardar_reporte_final().
    """

    @staticmethod
    def escanear_entorno() -> dict[str, Any]:
        """
        Recopila telemetría completa de la máquina.
        Garantiza retrocompatibilidad con las claves originales.
        """
        mb = _escanear_motherboard_bios()
        cpu = _escanear_cpu()
        ram = _escanear_ram()
        gpu = _escanear_gpu()
        storage = _escanear_almacenamiento()
        red = _escanear_red_y_so()

        # Combinar todo en un dict plano, preservando claves legacy
        datos: dict[str, Any] = {}
        datos.update(mb)
        datos.update(cpu)
        datos.update(ram)
        datos.update(gpu)
        datos.update(storage)
        datos.update(red)

        return datos


# ---------------------------------------------------------------------------
# Utilidades públicas para persistencia (usadas por cloud_gateway.py)
# ---------------------------------------------------------------------------

def calcular_health_score(hw: dict[str, Any]) -> int:
    """
    Calcula un score de salud del sistema del 0 al 100 basado en reglas de auditoría.

    Penalizaciones aplicadas:
      -20  Disco C: saturado (≥ 90 % de uso)
      -10  Disco C: casi lleno (≥ 80 %)
      -15  RAM muy limitada (< 4 GB)
      -10  RAM escasa (< 8 GB)
      -15  CPU con latencia alta (ping ≥ 200 ms)
      -10  GPU no detectada
      -10  Sin adaptador de red activo
      -5   Frecuencia de CPU muy baja (< 1.5 GHz)
    """
    score = 100

    # Disco sistema (primera partición con letra C:\\ o /)
    for part in hw.get("particiones", []):
        if part.get("letra", "").upper().startswith("C"):
            uso = part.get("uso_pct", 0)
            if uso >= 90:
                score -= 20
            elif uso >= 80:
                score -= 10
            break

    # RAM
    ram_mb = hw.get("ram_total_mb_int", 0)
    if ram_mb < 4096:
        score -= 15
    elif ram_mb < 8192:
        score -= 10

    # Red
    latencia_str = str(hw.get("latencia_ms", "N/A"))
    if latencia_str != "N/A":
        try:
            latencia_num = int(latencia_str.split()[0])
            if latencia_num >= 200:
                score -= 15
        except (ValueError, IndexError):
            pass
    if hw.get("adaptador_activo", "Ninguno") in ("Ninguno", ""):
        score -= 10

    # GPU
    if hw.get("gpu_principal", "No detectada") in ("No detectada", ""):
        score -= 10

    # CPU
    freq_actual = hw.get("frecuencia_actual_ghz", 0.0) or 0.0
    if 0 < freq_actual < 1.5:
        score -= 5

    return max(0, min(100, score))


def _formatear_gpu(hw: dict[str, Any]) -> str:
    """'NVIDIA GeForce RTX 5060 Ti (4095 MB)' o listado de todas las GPUs."""
    gpus = hw.get("gpus", [])
    if not gpus:
        return hw.get("gpu_principal", "No detectada")
    partes = []
    for g in gpus:
        vram = int(g.get("vram_mb", 0))
        vram_str = f"{vram} MB" if vram else "VRAM desconocida"
        partes.append(f"{g.get('nombre', 'GPU desconocida')} ({vram_str})")
    return " | ".join(partes)


def _formatear_almacenamiento(hw: dict[str, Any]) -> str:
    """'NVMe SSD Patriot 240GB / HDD WD 1TB' con estado de saturación."""
    discos = hw.get("discos_fisicos", [])
    if not discos:
        return "Sin discos detectados"
    partes = []
    for d in discos:
        cap = d.get("capacidad_gb", 0)
        cap_str = f"{cap:.0f} GB" if cap else "?"
        partes.append(f"{d.get('tipo', '?')} {d.get('modelo', '?')} {cap_str}")
    return " / ".join(partes)


def _inferir_refrigeracion(hw: dict[str, Any]) -> str:
    """
    Infiere el tipo de refrigeración a partir del nombre de la CPU y la
    telemetría disponible. Sin sensor directo en WMI, usamos heurísticas.
    """
    cpu = (hw.get("nombre_cpu", "") or "").lower()
    # Procesadores de bajo TDP habitualmente usan refrigeración integrada
    if any(x in cpu for x in ("celeron", "pentium", "atom", "n4", "n5", "n3")):
        return "Cooler Integrado (Low-TDP)"
    # Ryzen/i9/i7 sugieren cooler de torre o AIO por TDP alto
    if any(x in cpu for x in ("i9", "ryzen 9", "threadripper", "epyc")):
        return "Cooler Torre Alta Gama / AIO Líquida (inferido)"
    if any(x in cpu for x in ("i7", "ryzen 7", "i5", "ryzen 5")):
        return "Cooler Torre Aire o AIO (inferido)"
    return "Cooler Estándar (inferido)"


def construir_resumen_para_bd(
    ticket_id: str,
    hw: dict[str, Any],
    diag: dict[str, Any],
) -> dict[str, Any]:
    """
    Construye el payload limpio y tipado para la tabla 'reportes_diagnostico'.

    Todas las columnas de texto se coercen a str; health_score a int;
    specs_json es un dict nativo (supabase-py lo serializa a jsonb).
    """
    # Campos de texto simples
    cpu_info   = f"{hw.get('nombre_cpu', '?')} ({hw.get('nucleos_fisicos', '?')}C/{hw.get('nucleos', '?')}T @ {hw.get('frecuencia_actual_ghz', '?')} GHz)"
    ram_info   = f"{hw.get('ram_total_mb', '?')} {hw.get('ram_tipo', '')} @ {hw.get('ram_velocidad_mhz', '?')} MHz ({hw.get('ram_ranuras_ocupadas', '?')} ranuras)"
    gpu_info   = _formatear_gpu(hw)
    storage    = _formatear_almacenamiento(hw)
    placa_base = f"{hw.get('mb_fabricante', '?')} {hw.get('mb_modelo', '?')}"
    refrig     = _inferir_refrigeracion(hw)
    hscore     = calcular_health_score(hw)

    # specs_json: snapshot extendido serializable (excluye listas anidadas complejas)
    specs_json: dict[str, Any] = {
        "bios": {
            "version": hw.get("bios_version"),
            "fecha":   hw.get("bios_fecha"),
        },
        "cpu": {
            "nombre":          hw.get("nombre_cpu"),
            "nucleos_fisicos": hw.get("nucleos_fisicos"),
            "nucleos_logicos": hw.get("nucleos"),
            "freq_base_ghz":   hw.get("frecuencia_base_ghz"),
            "freq_actual_ghz": hw.get("frecuencia_actual_ghz"),
            "uso_total_pct":   hw.get("uso_cpu_total"),
        },
        "ram": {
            "total_mb":    hw.get("ram_total_mb_int"),
            "libre_mb":    hw.get("ram_libre_mb_int"),
            "uso_pct":     hw.get("ram_uso_pct"),
            "tipo":        hw.get("ram_tipo"),
            "velocidad":   hw.get("ram_velocidad_mhz"),
            "ranuras":     hw.get("ram_ranuras_ocupadas"),
            "modulos":     hw.get("ram_modulos", []),
        },
        "gpus": hw.get("gpus", []),
        "discos": {
            "fisicos":     hw.get("discos_fisicos", []),
            "particiones": hw.get("particiones", []),
        },
        "red": {
            "adaptador":  hw.get("adaptador_activo"),
            "ip":         hw.get("ip_local"),
            "latencia_ms":hw.get("latencia_ms"),
        },
        "so": {
            "nombre":  hw.get("so"),
            "build":   hw.get("so_build"),
            "uptime":  hw.get("uptime"),
        },
        "diagnostico_codigo": diag.get("codigo"),
    }

    return {
        "id_ticket":       str(ticket_id),
        "cpu":             str(cpu_info),
        "ram":             str(ram_info),
        "gpu":             str(gpu_info),
        "almacenamiento":  str(storage),
        "placa_base":      str(placa_base),
        "refrigeracion":   str(refrig),
        "health_score":    int(hscore),
        "diagnostico":     str(diag.get("categoria", "") + " — " + diag.get("subcategoria", "")),
        "solucion":        str(diag.get("solucion", "")),
        "specs_json":      specs_json,
    }