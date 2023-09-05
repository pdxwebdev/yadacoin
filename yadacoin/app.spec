# -*- mode: python -*-
import os

spec_root = os.path.abspath(SPECPATH)
print(spec_root)
block_cipher = None
with open('site_packages_path.txt', 'r') as f:
    site_packages_path = f.read().strip()

a = Analysis(['app.py'],
             pathex=[spec_root],
	     binaries=[('C:\\Windows\\System32\\msvcp120.dll', 'msvcp120.dll',),
                        ('C:\\Windows\\System32\\msvcr120.dll', 'msvcr120.dll',),
                        ('..\\winlibs\\libeay32.dll', '.',),
                        ('..\\winlibs\\libsecp256k1.dll', 'coincurve',)],
             datas=[
          ('plugins/yadacoinpool/templates', 'plugins/yadacoinpool/templates'),
          ('plugins/yadacoinpool/static', 'plugins/yadacoinpool/static'),
		('static', 'static/'),
		('templates/app.html', 'templates/'),
		(os.path.join(site_packages_path, 'mnemonic', 'wordlist', 'english.txt'), 'mnemonic/wordlist/'),
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
          name='YadaCoin',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          exclude_binaries=True,
          icon='yadacoin\\static\\icon.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='YadaCoin')