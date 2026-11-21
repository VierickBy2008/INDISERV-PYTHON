"""
build_executable.py — Empaquetador Multiplataforma (Windows, Linux y macOS)
===========================================================================
Detecta automáticamente el sistema operativo actual y ejecuta PyInstaller
con los separadores y banderas apropiados para generar el binario autónomo:
  • Windows : dist/IndiServ_Analytica.exe
  • Linux   : dist/IndiServ_Analytica-Linux
  • macOS   : dist/IndiServ_Analytica.app (y binario dist/IndiServ_Analytica-macOS)

Uso en cualquier sistema operativo:
    python build_executable.py
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    # En Windows el separador de --add-data es ';', en Linux y macOS es ':'
    sep = ";" if sys.platform == "win32" else ":"

    if sys.platform == "win32":
        exe_name = "IndiServ_Analytica"
    elif sys.platform == "darwin":
        exe_name = "IndiServ_Analytica-macOS"
    else:
        exe_name = "IndiServ_Analytica-Linux"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        exe_name,
        "--add-data",
        f"assets{sep}assets",
        "--collect-all",
        "customtkinter",
        "main.py",
    ]

    print(f"[Build] Compilando para plataforma '{sys.platform}' -> dist/{exe_name}")
    print("[Build] Comando:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0 and sys.platform != "win32":
        out_bin = os.path.join("dist", exe_name)
        if os.path.exists(out_bin):
            os.chmod(out_bin, 0o755)
            print(f"[Build] Permisos de ejecución (+x) aplicados a {out_bin}")
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
