# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")
curl_datas, curl_binaries, curl_hiddenimports = collect_all("curl_cffi")
yt_dlp_hiddenimports = collect_submodules("yt_dlp")

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[
        (str(ROOT / "build/windows/ffmpeg.exe"), "."),
        (str(ROOT / "build/windows/node.exe"), "."),
    ] + webview_binaries + curl_binaries,
    datas=[
        (str(ROOT / "frontend/dist"), "frontend/dist"),
        (str(ROOT / "static"), "static"),
    ] + webview_datas + curl_datas,
    hiddenimports=yt_dlp_hiddenimports + webview_hiddenimports + curl_hiddenimports,
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
    icon=str(ROOT / "build/windows/youtube-purple.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
