# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kiwoom Pro Algo-Trader v3.1
키움증권 자동매매 프로그램 빌드 설정

Usage:
    pyinstaller KiwoomProTrader.spec
"""

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 메인 스크립트
a = Analysis(
    ['키움증권 자동매매.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
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
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'tkinter',
        'test',
        'unittest',
        'distutils',
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
    name='KiwoomProTrader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘이 있으면 'app.ico' 등으로 지정
    version=None,
    uac_admin=False,
)
