# -*- mode: python -*-
import os

spec_root = os.path.abspath(SPECPATH)
print(spec_root)
block_cipher = None


a = Analysis(['app.py'],
             pathex=[spec_root],
	     binaries=[('C:\\Windows\\System32\\msvcp120.dll', 'msvcp120.dll',),
                        ('C:\\Windows\\System32\\msvcr120.dll', 'msvcr120.dll',),
                        ('C:\\Users\\john\\source\\repos\\yadacoin\\libeay32.dll', '.',),
                        ('C:\\Users\\john\\source\\repos\\yadacoin\\libsecp256k1.dll', 'coincurve',)],
             datas=[
		('c:/Users/john/source/repos/yadacoin/static', 'static/'),
		('c:/Users/john/source/repos/yadacoin/templates/app.html', 'templates/'),
		('c:/Python37_64/Lib/site-packages/mnemonic/wordlist/english.txt', 'mnemonic/wordlist/'),
	     ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          
          a.binaries,
          a.zipfiles,
          a.datas,
          name='YadaCoin',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon='c:\\Users\\john\\source\\repos\\yadacoin\\static\\icon.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='YadaCoin')