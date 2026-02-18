# -*- mode: python ; coding: utf-8 -*-
"""
Kiwoom Pro Algo-Trader v4.5 - PyInstaller Build Specification
경량화 최적화 빌드 설정 (ONEFILE 모드)
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# ============================================================================
# 데이터 파일 수집
# ============================================================================
datas = [('icon.png', '.')] # 아이콘 파일 포함 (만약 있다면)

# ============================================================================
# 숨겨진 imports (자동 감지 안 되는 모듈)
# ============================================================================
hiddenimports = [
    # PyQt6 필수 모듈
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    
    # 네트워크 모듈
    'websockets.legacy',
    'websockets.legacy.client',
    
    # 보안 모듈
    'keyring.backends',
    'keyring.backends.Windows',
    
    # API 모듈
    'api',
    'api.auth',
    'api.rest_client',
    'api.websocket_client',
    'api.models',
    'dark_theme',
    'telegram_notifier',
    'ui_dialogs',
    
    # 유틸리티
    'dateutil',
    'dateutil.parser',
    
    # 시스템
    'winreg',
]

# ============================================================================
# 제외할 모듈 (확실히 사용하지 않는 모듈만)
# ============================================================================
excludes = [
    # 데이터 과학 라이브러리
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'sklearn',
    'seaborn',
    'plotly',
    
    # 개발/테스트 도구
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'unittest',
    'pdb',
    'pydoc',
    
    # 대체 GUI
    'tkinter',
    'Tkinter',
    'PIL',
    
    # 웹 프레임워크
    'flask',
    'django',
    'tornado',
    'bottle',
    
    # ORM/DB 라이브러리
    'sqlalchemy',
    'pymongo',
    'psycopg2',
    
    # 빌드 도구
    'lib2to3',
    
    # 문서화
    'sphinx',
    'docutils',
]

# ============================================================================
# Analysis 단계
# ============================================================================
a = Analysis(
    ['키움증권 자동매매.py'],
    pathex=[],
    binaries=[],
    datas=datas,
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

# ============================================================================
# PYZ (Python ZIP archive) 단계
# ============================================================================
pyz = PYZ(
    a.pure, 
    a.zipped_data,
    cipher=block_cipher
)

# ============================================================================
# EXE 단계 - ONEFILE 모드
# ============================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KiwoomTrader_v4.5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3*.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

