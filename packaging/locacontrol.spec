# ruff: noqa: F821 - Analysis, PYZ, EXE, COLLECT and SPECPATH are injected by PyInstaller.
# PyInstaller spec of the LocaControl server (P1-B packaging proof). Build: scripts\package.ps1
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
    [str(BACKEND / "app" / "server.py")],
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
    # shortcut: console window kept for the proof; the installer (P1-E) needs a windowed build
    # with its own log file, because uvicorn writes to stdout/stderr.
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="LocaControl")
