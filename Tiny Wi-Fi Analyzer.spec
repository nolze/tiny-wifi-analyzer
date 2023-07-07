# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["tiny_wifi_analyzer/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[("tiny_wifi_analyzer/view", "view")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Tiny Wi-Fi Analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="universal2",
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name="Tiny Wi-Fi Analyzer.app",
    icon="./assets/twa.icns",
    bundle_identifier="io.github.nolze.tiny-wifi-analyzer",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSHighResolutionCapable": True,
    },
)
