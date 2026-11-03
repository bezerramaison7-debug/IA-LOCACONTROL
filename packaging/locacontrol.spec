# ruff: noqa: F821 - Analysis, PYZ, EXE, COLLECT and SPECPATH are injected by PyInstaller.
# PyInstaller spec of LocaControl.exe (P1-B proof, P1-E installer). Build: scripts\package.ps1
# Output: one folder (dist-app\LocaControl\LocaControl.exe + _internal\), ignored by Git.
# Resources keep their project layout under _internal, where app.core.config.resource() finds them.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"

datas = [
    (str(BACKEND / "alembic.ini"), "backend"),
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    # Migration sources only: Alembic loads them from files at runtime, no __pycache__.
    *[
        (str(path), str(Path("backend") / path.parent.relative_to(BACKEND)))
        for path in (BACKEND / "migrations").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ],
    *collect_data_files("reportlab"),  # fonts and metrics used by the PDF documents
]

a = Analysis(
    # One executable, several verbs (abrir, servir, conectar, desconectar, parar): app.launcher.
    [str(BACKEND / "app" / "launcher.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    # Routers and models are imported dynamically by the migrations' env.py.
    hiddenimports=collect_submodules("app"),
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocaControl",
    # Windowed (P1-E): no console window; `servir` writes to <data>\logs\servidor.log.
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="LocaControl")
