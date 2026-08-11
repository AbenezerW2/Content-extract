from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPECPATH).parent
FRONTEND = ROOT / "apps" / "web-extractor" / "frontend" / "dist"
datas = [
    (str(FRONTEND), "apps/web-extractor/frontend/dist"),
    (str(ROOT / "apps" / "web-extractor" / "app.py"), "apps/web-extractor"),
    (str(ROOT / "apps" / "web-extractor" / "crawler.py"), "apps/web-extractor"),
    (str(ROOT / "apps" / "web-extractor" / "app_model.py"), "apps/web-extractor"),
    (str(ROOT / "apps" / "web-extractor" / "history_store.py"), "apps/web-extractor"),
    (
        str(ROOT / "apps" / "youtube-extractor" / "youtube_transcript_extractor.py"),
        "apps/youtube-extractor",
    ),
]

hiddenimports = []
binaries = []
for package in ("webview", "playwright", "youtube_transcript_api", "yt_dlp", "bs4"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

hiddenimports += collect_submodules("webview")
hiddenimports += ["ipaddress", "urllib.robotparser"]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT), str(ROOT / "apps" / "web-extractor")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Content Extract",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Content Extract",
)

app = BUNDLE(
    coll,
    name="Content Extract.app",
    icon=str(ROOT / "assets" / "content-extract-icon.png"),
    bundle_identifier="com.abenezer.contentextract",
    info_plist={
        "CFBundleDisplayName": "Content Extract",
        "CFBundleName": "Content Extract",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Content Extract",
    },
)
