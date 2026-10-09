# PyInstaller: сборка JackBOTS.exe одним файлом. Запуск: tools\build_exe.bat
# Ресурсы (web, assets, data) кладутся внутрь exe; config\ и logs\ создаются рядом с exe (см. app/store.py).
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
    console=True,  # окно консоли = сервер работает; закрыл окно — панель остановилась
    upx=False,
)
