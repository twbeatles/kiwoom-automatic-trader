# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['키움증권 자동매매.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'numpy', 
        'IPython', 'notebook', 'tkinter', 'unittest',
        'email', 'html', 'http', 'xml', 'pydoc',
        'distutils', 'multiprocessing', 'lib2to3',
        'pkg_resources'
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
    [],
    exclude_binaries=True,
    name='KiwoomTrader_v4.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 아이콘이 있다면 icon='icon.ico' 추가 가능
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KiwoomTrader_v4.1',
)
