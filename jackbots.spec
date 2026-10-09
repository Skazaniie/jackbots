# PyInstaller: builds JackBOTS.exe as a single file. Run: tools\build_exe.bat
# Resources (web, assets, data) go inside the exe; config\ and logs\ are created next to the exe (see app/store.py).
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["app/__main__.py"],
    pathex=["."],
    datas=[("web", "web"), ("assets", "assets"), ("data", "data")],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("app"),
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="JackBOTS",
    icon="branding/jackbots.ico",
    console=True,  # console window = server is running; closing it stops the panel
    upx=False,
)
