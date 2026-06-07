# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para Loombit Operator.
Genera: dist/Loombit/Loombit.exe  (onedir — arranque rápido)

Uso:
    pyinstaller loombit.spec
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

# ── Datos a incluir (archivos no-Python) ──────────────────────────────────────
datas = [
    # Assets (icono)
    (str(ROOT / "loombit_operator" / "assets"), "loombit_operator/assets"),
    # Ficheros estáticos de la UI
    (str(ROOT / "loombit_operator" / "static"), "loombit_operator/static"),
    ]

# Skills manifests (opcional — solo si existe el directorio)
_skills = ROOT / "skills"
if _skills.exists():
    datas.append((str(_skills), "skills"))

# Añadir .env si existe (nunca sube a repo, pero en la build local puede estar)
_env = ROOT / ".env"
if _env.exists():
    datas.append((str(_env), "."))

# ── Imports ocultos que PyInstaller no detecta automáticamente ────────────────
hidden_imports = [
    # uvicorn internals
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # FastAPI / Starlette
    "fastapi",
    "fastapi.staticfiles",
    "starlette.staticfiles",
    "starlette.templating",
    "starlette.middleware.cors",
    # Pydantic
    "pydantic",
    "pydantic_settings",
    # httpx
    "httpx",
    "httpx._transports.default",
    # Windows / pywinauto (opcionales en runtime)
    "pynput",
    "pynput.keyboard",
    "pynput.mouse",
    "PIL",
    "PIL.ImageGrab",
    "PIL.Image",
    "PIL.ImageDraw",
    # pystray
    "pystray",
    "pystray._win32",
    # App modules
    "loombit_operator",
    "loombit_operator.main",
    "loombit_operator.config",
    "loombit_operator.llm",
    "loombit_operator.agent",
    "loombit_operator.agent.loop",
    "loombit_operator.agent.memory",
    "loombit_operator.agent.run",
    "loombit_operator.agent.prompts",
    "loombit_operator.tools",
    "loombit_operator.tools.base",
    "loombit_operator.tools.pilot",
    "loombit_operator.tools.computer",
    "loombit_operator.tools.connectors",
    "loombit_operator.tools.registry",
    "loombit_operator.pilot",
    "loombit_operator.pilot.screen",
    "loombit_operator.pilot.input_control",
    "loombit_operator.pilot.windows_control",
    "loombit_operator.routers",
    "loombit_operator.routers.health",
    "loombit_operator.routers.agent",
    "loombit_operator.routers.computer",
    "loombit_operator.routers.pilot",
    "loombit_operator.routers.skill_blanca_oauth",
    "loombit_operator.routers.skill_blanca_actions",
    "loombit_operator.routers.ui",
    "loombit_operator.skill_blanca_gmail",
    "loombit_operator.skill_blanca_calendar",
    "loombit_operator.skill_blanca_oauth",
    "loombit_operator.lm_jobs",
    "loombit_operator.skill_loader",
    "loombit_operator.skills",
    "loombit_operator.docs_intel",
    "loombit_operator.cobros",
    "loombit_operator.pilot.system",
    "loombit_operator.tools.documents",
    "loombit_operator.routers.docs",
    # Cifrado del token (cryptography + keyring backends de Windows)
    "cryptography",
    "cryptography.fernet",
    "keyring",
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.fail",
    "keyring.backends.chainer",
    # Inteligencia documental
    "pypdf",
    # email / mimetypes (para adjuntos)
    "email.mime.multipart",
    "email.mime.text",
    "email.mime.base",
    "email.mime.application",
    "email.encoders",
    "mimetypes",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "loombit_operator" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "black",
        "ruff",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Loombit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # Sin consola visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "loombit_operator" / "assets" / "loombit.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Loombit",
)
