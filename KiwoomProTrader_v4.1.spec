# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kiwoom Pro Algo-Trader v4.1
경량화 + 단일 EXE 빌드 설정

Usage:
    pyinstaller KiwoomProTrader_v4.1.spec

Lightweight build notes:
- PyQt6 기반 (PyQt5 아님)
- numpy/pandas/scipy 제외 (사용 안 함)
- tkinter 제외 (PyQt6만 사용)
- test/unittest/distutils 제외
- UPX 압축 활성화
- 불필요한 Qt 모듈 제외
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 숨겨진 import 수집
hiddenimports = [
    # PyQt6 core
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.sip',
    
    # 내부 모듈
    'config',
    'strategy_manager',
    'notification_manager',
    'risk_manager',
    'stock_screener',
    'backtest_engine',
    'themes',
    
    # API 모듈
    'api',
    'api.auth',
    'api.rest_client',
    'api.websocket_client',
    'api.models',
    
    # 표준 라이브러리
    'json',
    'csv',
    'logging',
    'logging.handlers',
    'threading',
    'queue',
    'pathlib',
    'dataclasses',
    'typing',
    'datetime',
    'enum',
    
    # 외부 라이브러리
    'requests',
    'websockets',
    'keyring',
]

# 제외할 모듈 (경량화)
excludes = [
    # 무거운 과학 라이브러리
    'numpy', 'numpy.core', 'numpy.fft', 'numpy.linalg',
    'pandas', 'scipy', 'sklearn', 'tensorflow', 'torch',
    'matplotlib', 'seaborn', 'plotly',
    
    # GUI 중복 제외
    'tkinter', '_tkinter', 'Tkinter',
    'wx', 'PyQt5', 'PySide2', 'PySide6',
    
    # 개발/테스트 도구
    'test', 'tests', 'unittest', 'pytest',
    'distutils', 'setuptools', 'pip', 'wheel',
    
    # 불필요한 패키지
    'PIL', 'pillow', 'cv2', 'opencv',
    'IPython', 'jupyter', 'notebook', 'nbformat',
    
    # Qt 불필요 모듈
    'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtDesigner', 'PyQt6.QtQuick', 'PyQt6.QtQml',
    'PyQt6.QtMultimedia', 'PyQt6.QtSql', 'PyQt6.QtNetwork',
    'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.QtBluetooth',
    'PyQt6.QtDBus', 'PyQt6.QtNfc', 'PyQt6.QtPositioning',
    'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
    'PyQt6.QtTextToSpeech', 'PyQt6.QtXml',
    
    # 기타
    'email', 'html', 'http.server', 'xmlrpc',
    'multiprocessing.spawn',
]

a = Analysis(
    ['키움증권 자동매매.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 경량화: 불필요한 바이너리 필터링
exclude_binaries = [
    'opengl32sw', 'qt6webengine', 'qt6designer', 'qt6quick',
    'qt6qml', 'qt6multimedia', 'qt6sql', 'qt6network',
    'qt6pdf', 'qt6charts', 'qt6datavisualization',
    'd3dcompiler', 'libcrypto', 'libssl', 
    'qsqlite', 'qminimal', 'qoffscreen',
    'qtwebengine', 'QtWebEngine',
    'api-ms-win',  # Windows API 셋 (불필요한 것들)
]

a.binaries = [x for x in a.binaries if not any(
    excl.lower() in x[0].lower() for excl in exclude_binaries
)]

# 불필요한 데이터 파일 제거
exclude_datas = [
    'tcl', 'tk', 'Include', 'share',
    'translations', 'qtwebengine',
]
a.datas = [x for x in a.datas if not any(
    excl.lower() in x[0].lower() for excl in exclude_datas
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
    strip=True,           # 심볼 제거 (경량화)
    upx=True,             # UPX 압축
    upx_exclude=[
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'python3*.dll',
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,        # GUI 앱 (콘솔 없음)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,            # 아이콘: 'app.ico' 추가 가능
    version=None,
    uac_admin=False,      # 관리자 권한 불필요
)
