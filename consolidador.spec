# PyInstaller one-file build for the Windows desktop app.
# Build:  pyinstaller consolidador.spec
# Output: dist/ConsolidadorTextos.exe (windowed, no console)

block_cipher = None

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # easyocr/torch/tensorflow/cv2 son dependencias opcionales (import
    # diferido en src/core/ocr.py) y no deben empaquetarse: añaden GBs.
    excludes=[
        "tkinter", "unittest", "pytest",
        "easyocr", "torch", "tensorflow", "keras", "cv2", "pygame",
        "pandas", "scipy", "sklearn", "matplotlib",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ConsolidadorTextos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
