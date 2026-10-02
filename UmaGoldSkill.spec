from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPECPATH)
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")
pydeck_datas, pydeck_binaries, pydeck_hiddenimports = collect_all("pydeck")
opencv_datas, opencv_binaries, opencv_hiddenimports = collect_all("cv2")

datas = (
    streamlit_datas
    + pydeck_datas
    + opencv_datas
    + copy_metadata("streamlit")
    + copy_metadata("pydeck")
    + [
        (str(ROOT / "app.py"), "."),
        (str(ROOT / "data" / "support_cards.json"), "data"),
    ]
)
binaries = streamlit_binaries + pydeck_binaries + opencv_binaries
hiddenimports = sorted(
    set(
        streamlit_hiddenimports
        + pydeck_hiddenimports
        + opencv_hiddenimports
        + [
            "streamlit.web.cli",
            "streamlit.runtime.scriptrunner.magic",
            "streamlit.runtime.scriptrunner.script_runner",
            "event_utils",
            "screen_ocr",
            "mss",
            "numpy",
            "pandas",
            "pytesseract",
            "pygetwindow",
            "win32gui",
            "win32con",
        ]
    )
)

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
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
    name="UmaGoldSkill",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)