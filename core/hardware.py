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

import os
import sys
import platform
import subprocess
import json
import time
import re
import datetime
from pathlib import Path
import psutil
from typing import Any


# ---------------------------------------------------------------------------
# Utilidades internas multiplataforma (Windows WMI / Linux sysfs / macOS)
# ---------------------------------------------------------------------------
def _run_cmd(args: list[str], timeout: int = 5) -> str:
    """Ejecuta un comando nativo del SO y devuelve stdout limpio o '' si falla."""
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creation_flags,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def _read_sys_file(path: str) -> str:
    """Lee un archivo virtual de /sys o /proc en Linux sin lanzar excepciones."""
    try:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        pass
    return ""


def _wmi_query(clase_wmi: str, propiedades: list[str]) -> list[dict[str, Any]]:
    """
    Ejecuta Get-CimInstance <clase_wmi> en PowerShell (solo Windows) y devuelve
    una lista de dicts con las propiedades solicitadas.
    En Linux o macOS retorna [] inmediatamente.
    """
    if sys.platform != "win32":
        return []
    props_str = ", ".join(propiedades)
    script = (
        f"Get-CimInstance -ClassName {clase_wmi} | "
        f"Select-Object {props_str} | "
        "ConvertTo-Json -Depth 2 -Compress"
    )
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=creation_flags,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout.strip())
        if isinstance(data, dict):
            return [data]
        return data
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Secciones de telemetría
# ---------------------------------------------------------------------------

def _escanear_motherboard_bios() -> dict[str, str]:
    """Fabricante, modelo, versión y fecha de BIOS (Windows, Linux y macOS)."""
    if sys.platform.startswith("linux"):
        mb_fab = _read_sys_file("/sys/class/dmi/id/board_vendor") or _read_sys_file("/sys/class/dmi/id/sys_vendor") or "Linux OEM"
        mb_mod = _read_sys_file("/sys/class/dmi/id/board_name") or _read_sys_file("/sys/class/dmi/id/product_name") or _read_sys_file("/proc/device-tree/model") or "Placa Base Linux"
        bios_fab = _read_sys_file("/sys/class/dmi/id/bios_vendor") or mb_fab
        bios_ver = _read_sys_file("/sys/class/dmi/id/bios_version") or "UEFI/Linux"
        bios_fec = _read_sys_file("/sys/class/dmi/id/bios_date") or "Desconocida"
        return {
            "mb_fabricante": mb_fab,
            "mb_modelo": mb_mod,
            "bios_fabricante": bios_fab,
            "bios_version": bios_ver,
            "bios_fecha": bios_fec,
        }

    if sys.platform == "darwin":
        hw_model = _run_cmd(["sysctl", "-n", "hw.model"]) or "Mac"
        boot_rom = "Apple Silicon / EFI"
        sp_out = _run_cmd(["system_profiler", "SPHardwareDataType", "-json"], timeout=6)
        if sp_out:
            try:
                sp_items = json.loads(sp_out).get("SPHardwareDataType", [])
                if sp_items:
                    info = sp_items[0]
                    hw_model = info.get("machine_model") or info.get("machine_name") or hw_model
                    boot_rom = info.get("boot_rom_version") or info.get("os_loader_version") or boot_rom
            except Exception:
                pass
        return {
            "mb_fabricante": "Apple Inc.",
            "mb_modelo": hw_model,
            "bios_fabricante": "Apple Inc.",
            "bios_version": boot_rom,
            "bios_fecha": "Integrado",
        }

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


# Códigos SMBIOS (Win32_SystemEnclosure.ChassisTypes)
_LAPTOP_CHASSIS_TYPES: set[int] = {8, 9, 10, 14, 30, 31, 32}
_DESKTOP_CHASSIS_TYPES: set[int] = {3, 4, 5, 6, 7, 13, 15, 16}


def _clasificar_tipo_equipo(
    chassis_types: list[int],
    pc_system_type: int | None,
    tiene_bateria: bool,
) -> str:
    """
    Determina si el equipo es 'laptop' o 'desktop' priorizando SMBIOS ChassisTypes
    y Win32_ComputerSystem.PCSystemType, con batería (psutil) como fallback.
    """
    chassis_set = set(chassis_types)
    if (chassis_set & _LAPTOP_CHASSIS_TYPES) or pc_system_type == 2:
        return "laptop"
    if (chassis_set & _DESKTOP_CHASSIS_TYPES) or pc_system_type == 1:
        return "desktop"
    if tiene_bateria:
        return "laptop"
    return "desktop"


def _escanear_tipo_equipo() -> dict[str, Any]:
    """
    Detecta el factor de forma ('laptop' | 'desktop') en Windows, Linux y macOS.
    """
    chassis_types: list[int] = []
    pc_system_type: int | None = None

    try:
        tiene_bateria = psutil.sensors_battery() is not None
    except Exception:
        tiene_bateria = False

    if sys.platform.startswith("linux"):
        raw_ct = _read_sys_file("/sys/class/dmi/id/chassis_type")
        if raw_ct.isdigit():
            chassis_types.append(int(raw_ct))
        if not tiene_bateria:
            try:
                ps_dir = Path("/sys/class/power_supply")
                if ps_dir.exists():
                    tiene_bateria = any(p.name.upper().startswith("BAT") for p in ps_dir.iterdir())
            except Exception:
                pass
        pc_system_type = 2 if (set(chassis_types) & _LAPTOP_CHASSIS_TYPES or tiene_bateria) else 1

    elif sys.platform == "darwin":
        hw_model = (_run_cmd(["sysctl", "-n", "hw.model"]) or "").lower()
        batt_info = (_run_cmd(["pmset", "-g", "batt"]) or "").lower()
        if "internalbattery" in batt_info:
            tiene_bateria = True
        if "macbook" in hw_model or tiene_bateria:
            chassis_types = [10]
            pc_system_type = 2
        else:
            chassis_types = [3]
            pc_system_type = 1

    else:
        enclosures = _wmi_query("Win32_SystemEnclosure", ["ChassisTypes"])
        cs = _wmi_query("Win32_ComputerSystem", ["PCSystemType"])
        for enc in enclosures:
            raw_ct = enc.get("ChassisTypes")
            if isinstance(raw_ct, list):
                for val in raw_ct:
                    try:
                        chassis_types.append(int(val))
                    except (TypeError, ValueError):
                        pass
            elif raw_ct is not None:
                try:
                    chassis_types.append(int(raw_ct))
                except (TypeError, ValueError):
                    pass
        if cs:
            raw_pst = cs[0].get("PCSystemType")
            if raw_pst is not None:
                try:
                    pc_system_type = int(raw_pst)
                except (TypeError, ValueError):
                    pc_system_type = None

    tipo_equipo = _clasificar_tipo_equipo(chassis_types, pc_system_type, tiene_bateria)

    return {
        "tipo_equipo": tipo_equipo,
        "chassis_types": chassis_types,
        "pc_system_type": pc_system_type,
        "tiene_bateria": tiene_bateria,
    }


def _escanear_cpu() -> dict[str, Any]:
    """CPU: modelo, frecuencias, núcleos físicos/lógicos, uso por núcleo (Windows, Linux y macOS)."""
    cpu_wmi = _wmi_query("Win32_Processor", ["Name", "NumberOfCores", "NumberOfLogicalProcessors"])
    cpu_data = cpu_wmi[0] if cpu_wmi else {}

    nombre_cpu = (cpu_data.get("Name") or "").strip()
    if not nombre_cpu and sys.platform.startswith("linux"):
        cpuinfo = _read_sys_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if ":" in line and line.split(":", 1)[0].strip().lower() in ("model name", "hardware", "processor"):
                cand = line.split(":", 1)[1].strip()
                if cand and not cand.isdigit():
                    nombre_cpu = cand
                    break
        if not nombre_cpu:
            lscpu_out = _run_cmd(["lscpu"])
            for line in lscpu_out.splitlines():
                if "model name:" in line.lower():
                    nombre_cpu = line.split(":", 1)[1].strip()
                    break
    elif not nombre_cpu and sys.platform == "darwin":
        nombre_cpu = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])

    if not nombre_cpu:
        nombre_cpu = (platform.processor() or "CPU Genérica Detectada").strip()

    nucleos_fisicos = int(cpu_data.get("NumberOfCores") or psutil.cpu_count(logical=False) or 1)
    nucleos_logicos = int(cpu_data.get("NumberOfLogicalProcessors") or psutil.cpu_count(logical=True) or 1)

    # Frecuencias
    try:
        freq = psutil.cpu_freq()
    except Exception:
        freq = None
    freq_base_ghz = round(freq.max / 1000, 2) if freq and freq.max else 0.0
    freq_actual_ghz = round(freq.current / 1000, 2) if freq and freq.current else 0.0
    if freq_actual_ghz <= 0.0 and sys.platform == "darwin":
        # Apple Silicon a veces no expone frecuencia vía sysctl en psutil
        freq_base_ghz = freq_base_ghz or 3.20
        freq_actual_ghz = 3.20

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

    if not modulos and sys.platform != "win32":
        tipo_fb = "Unified LPDDR" if sys.platform == "darwin" else "DDR4/DDR5"
        modulos.append({
            "ranura": "DIMM 0",
            "banco": "System Memory",
            "capacidad_gb": round(memoria.total / (1024 ** 3), 1),
            "velocidad_mhz": "N/A",
            "tipo": tipo_fb,
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

    if not gpus and sys.platform.startswith("linux"):
        nv_out = _run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        if nv_out:
            for line in nv_out.splitlines():
                partes = [p.strip() for p in line.split(",")]
                if len(partes) >= 3:
                    try:
                        vram_mb = float(partes[1])
                    except ValueError:
                        vram_mb = 0.0
                    gpus.append({
                        "nombre": partes[0],
                        "procesador": partes[0],
                        "vram_mb": vram_mb,
                        "driver_version": partes[2],
                    })
        lspci_out = _run_cmd(["lspci"])
        for line in lspci_out.splitlines():
            low = line.lower()
            if any(k in low for k in ("vga compatible controller:", "3d controller:", "display controller:")):
                desc = line.split(":", 2)[-1].strip()
                if desc and not any(desc in g["nombre"] for g in gpus):
                    gpus.append({
                        "nombre": desc,
                        "procesador": desc,
                        "vram_mb": 0.0,
                        "driver_version": "Kernel DRM/Mesa",
                    })

    elif not gpus and sys.platform == "darwin":
        sp_gpu = _run_cmd(["system_profiler", "SPDisplaysDataType", "-json"], timeout=6)
        if sp_gpu:
            try:
                items = json.loads(sp_gpu).get("SPDisplaysDataType", [])
                for it in items:
                    nombre_g = it.get("sppci_model") or it.get("_name") or "Apple Integrated GPU"
                    vram_str = str(it.get("spdisplays_vram") or it.get("spdisplays_vram_shared") or "0")
                    m_vram = re.search(r"(\d+)", vram_str)
                    vram_val = float(m_vram.group(1)) if m_vram else 0.0
                    if "gb" in vram_str.lower():
                        vram_val *= 1024.0
                    gpus.append({
                        "nombre": nombre_g,
                        "procesador": nombre_g,
                        "vram_mb": vram_val,
                        "driver_version": str(it.get("spdisplays_metal") or "Apple Metal"),
                    })
            except Exception:
                pass

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

    if not discos_fisicos and sys.platform.startswith("linux"):
        lsblk_out = _run_cmd(["lsblk", "-J", "-b", "-d", "-o", "NAME,MODEL,SIZE,ROTA,TRAN"])
        if lsblk_out:
            try:
                for bd in json.loads(lsblk_out).get("blockdevices", []):
                    nombre_d = str(bd.get("name") or "")
                    if nombre_d.startswith(("loop", "ram", "zram")):
                        continue
                    tam_b = int(bd.get("size") or 0)
                    if tam_b <= 0:
                        continue
                    tran = str(bd.get("tran") or "").upper()
                    rota = bd.get("rota")
                    es_rot = rota in (True, 1, "1")
                    modelo_d = (bd.get("model") or f"/dev/{nombre_d}").strip()
                    if "NVME" in tran or nombre_d.startswith("nvme"):
                        t_disco = "NVMe SSD"
                    elif tran == "USB":
                        t_disco = "Externo USB"
                    elif not es_rot:
                        t_disco = "SATA SSD"
                    else:
                        t_disco = "HDD"
                    discos_fisicos.append({
                        "modelo": modelo_d,
                        "tipo": t_disco,
                        "interfaz": tran or "BLK",
                        "capacidad_gb": round(tam_b / (1024 ** 3), 1),
                    })
            except Exception:
                pass

    elif not discos_fisicos and sys.platform == "darwin":
        try:
            uso_root = psutil.disk_usage("/")
            discos_fisicos.append({
                "modelo": "Apple Internal SSD",
                "tipo": "NVMe SSD",
                "interfaz": "NVMe",
                "capacidad_gb": round(uso_root.total / (1024 ** 3), 1),
            })
        except Exception:
            pass

    # Particiones lógicas vía psutil
    particiones = []
    for part in psutil.disk_partitions(all=False):
        if sys.platform.startswith("linux") and (
            part.mountpoint.startswith("/snap") or part.fstype in ("squashfs", "tmpfs", "devtmpfs")
        ):
            continue
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
    """Devuelve la latencia en ms como string (Windows, Linux y macOS), o 'N/A' si falla."""
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", "1", "-w", "2000", host]
            enc = "cp850"
        elif sys.platform == "darwin":
            cmd = ["ping", "-c", "1", "-W", "2000", host]
            enc = "utf-8"
        else:
            cmd = ["ping", "-c", "1", "-W", "2", host]
            enc = "utf-8"

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=enc,
            errors="replace",
            timeout=5,
            creationflags=creation_flags,
        )
        for line in result.stdout.splitlines():
            if "tiempo" in line.lower() or "time" in line.lower() or "ms" in line.lower():
                m = re.search(r"(?:tiempo|time)[<=](\d+(?:\.\d+)?)\s*ms", line, re.IGNORECASE)
                if m:
                    val_ms = int(round(float(m.group(1))))
                    return f"{val_ms} ms"
    except Exception:
        pass
    return "N/A"


# ---------------------------------------------------------------------------
# Clase pública
# ---------------------------------------------------------------------------

def _tiene_firma_portatil(hw: dict[str, Any]) -> bool:
    """
    Respaldo por huella de hardware: detecta procesadores móviles (H/HS/HX/U),
    GPUs Laptop/Mobile, memorias SO-DIMM/LPDDR o placas base de portátiles
    (ej. LENOVO LNVNB, ASUS TUF FA506/FX505, ROG GU603/G513, Acer Nitro, HP Victus/Omen)
    por si la tabla SMBIOS del fabricante reporta un ChassisType genérico.
    """
    texto = " ".join(
        str(hw.get(k, "") or "")
        for k in ("nombre_cpu", "gpu_principal", "mb_fabricante", "mb_modelo", "ram_tipo")
    ).lower()
    if any(
        kw in texto
        for kw in (
            "laptop",
            "notebook",
            "portable",
            "mobile",
            "macbook",
            "thinkpad",
            "ideapad",
            "legion",
            "zenbook",
            "vivobook",
            "lnvnb",
            "fa506",
            "fx505",
            "fx506",
            "fa507",
            "gu603",
            "g513",
            "sodimm",
            "so-dimm",
            "lpddr",
        )
    ):
        return True
    if re.search(r"\b(?:i[3579]-|ryzen\s+[3579]\s+|ultra\s+[579]\s+)?\d{4,5}(?:hs|hx|h|u|g[1-7])\b", texto):
        return True
    return False


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
        tipo_eq = _escanear_tipo_equipo()
        cpu = _escanear_cpu()
        ram = _escanear_ram()
        gpu = _escanear_gpu()
        storage = _escanear_almacenamiento()
        red = _escanear_red_y_so()

        # Combinar todo en un dict plano, preservando claves legacy
        datos: dict[str, Any] = {}
        datos.update(mb)
        datos.update(tipo_eq)
        datos.update(cpu)
        datos.update(ram)
        datos.update(gpu)
        datos.update(storage)
        datos.update(red)

        if datos.get("tipo_equipo") != "laptop" and _tiene_firma_portatil(datos):
            datos["tipo_equipo"] = "laptop"

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

    # Disco sistema (primera partición con letra C:\ en Windows o / en Linux/macOS)
    for part in hw.get("particiones", []):
        letra = str(part.get("letra", "")).strip().upper()
        if letra.startswith("C") or letra == "/":
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
    owner_dni: str | None = None,
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
    tipo_final = hw.get("tipo_equipo")
    if tipo_final != "laptop" and _tiene_firma_portatil(hw):
        tipo_final = "laptop"
    clean_dni = str(owner_dni).strip() if owner_dni else ""
    specs_json: dict[str, Any] = {
        "tipo_equipo": tipo_final or "desktop",
        "owner_dni": clean_dni or None,
        "tipo_evento": str(diag.get("tipo_evento") or "Diagnóstico"),
        "chassis_types": hw.get("chassis_types", []),
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