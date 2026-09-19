# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parent.parent
hiddenimports = collect_submodules("yt_dlp") + collect_submodules("webview")
webview_datas = collect_data_files("webview")

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[
        (str(ROOT / "build/windows/ffmpeg.exe"), "."),
        (str(ROOT / "build/windows/node.exe"), "."),
    ],
    datas=[
        (str(ROOT / "frontend/dist"), "frontend/dist"),
        (str(ROOT / "static"), "static"),
    ] + webview_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YouTubeDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
