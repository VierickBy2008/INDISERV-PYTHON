"""
build_executable.py — Compilador Nativo Anti-Ingeniería Inversa (Cython -> C -> PyInstaller)
===========================================================================================
Compila TODOS los módulos propietarios (core/*.py y ui/*.py) a código máquina C nativo
(.pyd en Windows, .so en Linux/macOS) sin docstrings, sin comentarios, sin bindings Python
y con símbolos depurados, luego empaqueta desde un directorio aislado sin ningún archivo .py
propietario y verifica automáticamente que 0 módulos propios queden en bytecode (.pyc).

Uso:
    python build_executable.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE_DIR = ROOT / "build" / "native_stage"
CYTHON_SRC_DIR = ROOT / "build" / "cython_src"
PYI_WORK_DIR = ROOT / "build" / "pyi_work"
PYI_SPEC_DIR = ROOT / "build" / "pyi_spec"

PROPRIETARY_PACKAGES = ("core", "ui")

# Dependencias usadas dentro de las extensiones compiladas (.pyd/.so) que PyInstaller
# no puede descubrir por análisis AST al estar compiladas en código máquina nativo.
HIDDEN_IMPORTS = [
    # Módulos propios compilados a C nativo
    "core",
    "core.config",
    "core.security",
    "core.cloud_gateway",
    "core.diagnostico",
    "core.gemelo_digital",
    "core.hardware",
    "core.hardware_map",
    "core.legal",
    "core.ui_theme",
    "ui",
    "ui.app_core",
    "ui.dashboard_tabs",
    "ui.diagnostico_views",
    "ui.modales",
    "ui.stress_y_arbol",
    # Librerías de terceros y stdlib usadas dentro de los .pyd/.so
    "customtkinter",
    "darkdetect",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageOps",
    "PIL.ImageTk",
    "psutil",
    "supabase",
    "postgrest",
    "gotrue",
    "supabase_auth",
    "supabase_functions",
    "storage3",
    "realtime",
    "httpx",
    "httpcore",
    "h2",
    "anyio",
    "sniffio",
    "certifi",
    "idna",
    "pydantic",
    "websockets",
    "dotenv",
    "pyperclip",
    "cryptography",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.hashes",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "urllib.request",
    "urllib.error",
    "urllib.parse",
    "webbrowser",
    "concurrent.futures",
    "ctypes",
    "ctypes.wintypes",
    "platform",
    "uuid",
    "secrets",
    "hashlib",
    "base64",
    "json",
    "datetime",
    "math",
    "random",
    "re",
    "tempfile",
    "threading",
    "subprocess",
    "warnings",
    "traceback",
]


def _discover_proprietary_modules() -> list[tuple[str, Path]]:
    mods: list[tuple[str, Path]] = []
    for pkg in PROPRIETARY_PACKAGES:
        pkg_dir = ROOT / pkg
        for py_file in sorted(pkg_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            mod_name = f"{pkg}.{py_file.stem}"
            mods.append((mod_name, py_file))
    return mods


def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=False)
    path.mkdir(parents=True, exist_ok=True)


def _compile_with_setuptools(modules: list[tuple[str, Path]]) -> bool:
    """Compila todos los módulos Cython usando setuptools (MSVC en Windows, gcc/clang en POSIX)."""
    setup_code = f'''
import os, sys
from setuptools import Extension, setup
from Cython.Build import cythonize
from Cython.Compiler import Options

Options.docstrings = False

extra_compile = ["/O2", "/DNDEBUG"] if sys.platform == "win32" else ["-O2", "-DNDEBUG", "-fvisibility=hidden"]
extra_link = [] if sys.platform == "win32" else (["-s"] if sys.platform.startswith("linux") else [])

exts = [
    Extension(
        name,
        [rel_path],
        extra_compile_args=extra_compile,
        extra_link_args=extra_link,
        define_macros=[("CYTHON_WITHOUT_ASSERTIONS", "1")],
    )
    for name, rel_path in {[(m, f"{m.replace('.', '/')}.py") for m, _ in modules]!r}
]

if __name__ == "__main__":
    setup(
        name="indiserv_native_core",
        ext_modules=cythonize(
            exts,
            compiler_directives={{
                "language_level": "3",
                "embedsignature": False,
                "emit_code_comments": False,
                "linetrace": False,
                "binding": False,
                "annotation_typing": False,
            }},
            nthreads=0 if sys.platform == "win32" else max(1, min(4, os.cpu_count() or 1)),
            quiet=False,
        ),
    )
'''
    setup_file = CYTHON_SRC_DIR / "_setup_native.py"
    setup_file.write_text(setup_code, encoding="utf-8")

    res = subprocess.run(
        [sys.executable, str(setup_file), "build_ext", "--inplace"],
        cwd=str(CYTHON_SRC_DIR),
    )
    return res.returncode == 0


def _compile_windows_gcc_fallback(modules: list[tuple[str, Path]]) -> bool:
    """Respaldo nativo Windows con UCRT64/MinGW gcc si MSVC no está disponible en el host local."""
    gcc = shutil.which("gcc")
    if not gcc:
        return False

    from Cython.Build import cythonize
    from Cython.Compiler import Options

    Options.docstrings = False

    print(f"[Native] Usando respaldo GCC en Windows: {gcc}")
    inc_dir = sysconfig.get_paths()["include"]
    base_prefix = Path(sys.base_prefix)
    libs_dir = base_prefix / "libs"
    py_ver = f"{sys.version_info.major}{sys.version_info.minor}"
    py_lib = libs_dir / f"python{py_ver}.lib"
    py_dll = base_prefix / f"python{py_ver}.dll"
    link_target = str(py_lib) if py_lib.is_file() else str(py_dll)
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".pyd"

    rel_files = [str(CYTHON_SRC_DIR / f"{m.replace('.', os.sep)}.py") for m, _ in modules]
    cythonize(
        rel_files,
        compiler_directives={
            "language_level": "3",
            "embedsignature": False,
            "emit_code_comments": False,
            "linetrace": False,
            "binding": False,
            "annotation_typing": False,
        },
        quiet=False,
    )

    for mod_name, _ in modules:
        c_file = CYTHON_SRC_DIR / f"{mod_name.replace('.', os.sep)}.c"
        out_pyd = CYTHON_SRC_DIR / f"{mod_name.replace('.', os.sep)}{ext_suffix}"
        cmd = [
            gcc,
            "-shared",
            "-O2",
            "-s",
            "-DNDEBUG",
            "-DCYTHON_WITHOUT_ASSERTIONS=1",
            f"-I{inc_dir}",
            str(c_file),
            link_target,
            "-o",
            str(out_pyd),
        ]
        res = subprocess.run(cmd, cwd=str(CYTHON_SRC_DIR))
        if res.returncode != 0 or not out_pyd.is_file():
            print(f"[Native] ERROR compilando {mod_name} con GCC.")
            return False
    return True


def _build_native_stage(modules: list[tuple[str, Path]]) -> list[str]:
    """Compila los 14 módulos propietarios a binarios C nativos en build/native_stage."""
    _clean_dir(CYTHON_SRC_DIR)
    _clean_dir(STAGE_DIR)

    # Preparar copia temporal de fuentes para compilar sin ensuciar el repo
    for pkg in PROPRIETARY_PACKAGES:
        (CYTHON_SRC_DIR / pkg).mkdir(parents=True, exist_ok=True)
        (STAGE_DIR / pkg).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / pkg / "__init__.py", CYTHON_SRC_DIR / pkg / "__init__.py")
        shutil.copy2(ROOT / pkg / "__init__.py", STAGE_DIR / pkg / "__init__.py")

    for mod_name, src_path in modules:
        dst_src = CYTHON_SRC_DIR / f"{mod_name.replace('.', os.sep)}.py"
        shutil.copy2(src_path, dst_src)

    shutil.copy2(ROOT / "main.py", STAGE_DIR / "main.py")
    if (ROOT / "assets").exists():
        shutil.copytree(ROOT / "assets", STAGE_DIR / "assets")

    print(f"[Native] Compilando {len(modules)} módulos Python a código máquina C nativo (Cython)...")
    ok = _compile_with_setuptools(modules)
    if not ok and sys.platform == "win32":
        ok = _compile_windows_gcc_fallback(modules)
    if not ok:
        raise RuntimeError("Falló la compilación nativa Cython. Verifique compilador C (MSVC/gcc/clang).")

    ext_glob = "*.pyd" if sys.platform == "win32" else "*.so"
    compiled_names: list[str] = []
    strip_bin = shutil.which("strip")

    for mod_name, _ in modules:
        pkg, stem = mod_name.split(".", 1)
        matches = list((CYTHON_SRC_DIR / pkg).glob(f"{stem}.*{ext_glob[1:]}")) + list(
            (CYTHON_SRC_DIR / pkg).glob(f"{stem}{ext_glob[1:]}")
        )
        if not matches:
            raise RuntimeError(f"No se generó el binario nativo para {mod_name}")
        bin_path = matches[0]
        dst_bin = STAGE_DIR / pkg / bin_path.name
        shutil.copy2(bin_path, dst_bin)
        if sys.platform == "darwin" and strip_bin:
            subprocess.run([strip_bin, "-x", str(dst_bin)], check=False)
        elif sys.platform.startswith("linux") and strip_bin:
            subprocess.run([strip_bin, "--strip-unneeded", str(dst_bin)], check=False)
        compiled_names.append(mod_name)

    # Doble garantía: verificar que NO exista ningún .py propietario en STAGE_DIR
    leaked = [
        p for pkg in PROPRIETARY_PACKAGES for p in (STAGE_DIR / pkg).glob("*.py") if p.name != "__init__.py"
    ]
    if leaked:
        raise RuntimeError(f"Se filtraron fuentes .py en native_stage: {leaked}")

    print(f"[Native] [OK] {len(compiled_names)} binarios nativos listos en {STAGE_DIR}")
    return compiled_names


def _verify_no_proprietary_bytecode(exe_name: str, compiled_modules: list[str]) -> None:
    """
    Puerta anti-ingeniería inversa: verifica en PYZ-00.toc y Analysis-00.toc que
    0 módulos propietarios estén en bytecode (.pyc) y todos sean binarios nativos (.pyd/.so).
    """
    pyz_toc = PYI_WORK_DIR / exe_name / "PYZ-00.toc"
    pkg_toc = PYI_WORK_DIR / exe_name / "PKG-00.toc"
    if not pyz_toc.is_file() or not pkg_toc.is_file():
        raise RuntimeError(f"No se encontraron TOCs de verificación en {PYI_WORK_DIR / exe_name}")

    pyz_text = pyz_toc.read_text(encoding="utf-8", errors="replace")
    pkg_text = pkg_toc.read_text(encoding="utf-8", errors="replace")

    leaked_pyz = [m for m in compiled_modules if f"'{m}'" in pyz_text or f'"{m}"' in pyz_text]
    if leaked_pyz:
        raise RuntimeError(
            f"[SECURITY-FAIL] Módulos propietarios detectados en bytecode PYZ: {leaked_pyz}"
        )

    missing_bin = []
    for m in compiled_modules:
        pkg, stem = m.split(".", 1)
        marker_a = f"{pkg}/{stem}."
        marker_b = f"{pkg}\\\\{stem}."
        if marker_a not in pkg_text and marker_b not in pkg_text:
            missing_bin.append(m)
    if missing_bin:
        raise RuntimeError(
            f"[SECURITY-FAIL] Módulos nativos ausentes en el empaquetado binario: {missing_bin}"
        )

    print(
        f"[SecurityGate] [OK] Verificado: 0/{len(compiled_modules)} módulos propios en bytecode .pyc; "
        f"{len(compiled_modules)}/{len(compiled_modules)} empaquetados como código máquina nativo."
    )


def main() -> int:
    sep = ";" if sys.platform == "win32" else ":"

    if sys.platform == "win32":
        exe_name = "IndiServ_Analytica"
    elif sys.platform == "darwin":
        exe_name = "IndiServ_Analytica-macOS"
    else:
        exe_name = "IndiServ_Analytica-Linux"

    modules = _discover_proprietary_modules()
    compiled_modules = _build_native_stage(modules)

    _clean_dir(PYI_WORK_DIR)
    _clean_dir(PYI_SPEC_DIR)

    hidden = list(HIDDEN_IMPORTS)
    if sys.platform == "win32":
        hidden.append("winreg")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--optimize",
        "2",
        "--name",
        exe_name,
        "--paths",
        str(STAGE_DIR),
        "--workpath",
        str(PYI_WORK_DIR),
        "--specpath",
        str(PYI_SPEC_DIR),
        "--distpath",
        str(ROOT / "dist"),
        "--add-data",
        f"{STAGE_DIR / 'assets'}{sep}assets",
        "--collect-all",
        "customtkinter",
        "--collect-data",
        "certifi",
    ]
    if sys.platform != "win32" and shutil.which("strip"):
        cmd.append("--strip")

    for mod in hidden:
        cmd.extend(["--hidden-import", mod])

    cmd.append(str(STAGE_DIR / "main.py"))

    print(f"[Build] Empaquetando ejecutable nativo para '{sys.platform}' -> dist/{exe_name}")
    # Ejecutar desde STAGE_DIR para que PyInstaller nunca resuelva core/*.py o ui/*.py del árbol raíz
    res = subprocess.run(cmd, cwd=str(STAGE_DIR))
    if res.returncode != 0:
        return res.returncode

    _verify_no_proprietary_bytecode(exe_name, compiled_modules)

    if sys.platform != "win32":
        out_bin = ROOT / "dist" / exe_name
        if out_bin.exists():
            os.chmod(out_bin, 0o755)
            print(f"[Build] Permisos de ejecución (+x) aplicados a {out_bin}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
