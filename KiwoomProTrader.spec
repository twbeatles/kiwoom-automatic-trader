# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kiwoom Pro Algo-Trader v4.0
경량화 빌드 설정

Usage:
    pyinstaller KiwoomProTrader.spec

Lightweight build notes:
- numpy/pandas/scipy excluded (not used)
- tkinter excluded (PyQt5 only)
- test/unittest/distutils excluded
- UPX compression enabled
"""

block_cipher = None

a = Analysis(
    ['키움증권 자동매매.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt5 core
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QAxContainer',
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 무거운 과학 라이브러리 제외
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        # GUI 중복 제외
        'tkinter',
        '_tkinter',
        'Tkinter',
        # 개발/테스트 도구 제외
        'test',
        'unittest',
        'distutils',
        'setuptools',
        'pip',
        # 불필요한 패키지 제외
        'PIL',
        'cv2',
        'IPython',
        'jupyter',
        'notebook',
        # matplotlib backends 불필요한 것들 제외 (Qt5만 사용)
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_gtk3',
        'matplotlib.backends.backend_wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 경량화: 불필요한 바이너리 필터링
a.binaries = [x for x in a.binaries if not any(
    excl in x[0].lower() for excl in [
        'opengl', 'qt5webengine', 'qt5designer', 'qt5quick',
        'qt5qml', 'qt5multimedia', 'qt5sql', 'qt5network',
        'libcrypto', 'libssl', 'qsqlite', 'qminimal'
    ]
)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KiwoomProTrader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # 심볼 제거로 경량화
    upx=True,    # UPX 압축
    upx_exclude=[
        'vcruntime140.dll',
        'python3*.dll',
        'Qt5Core.dll',
        'Qt5Gui.dll',
        'Qt5Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # GUI 앱
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 필요시: 'app.ico'
    version=None,
    uac_admin=False,
)
