# -*- mode: python -*-
import os
import mnemonic

spec_root = os.path.abspath(SPECPATH)
print(spec_root)
block_cipher = None
mnemonic_wordlist = os.path.join(os.path.dirname(mnemonic.__file__), 'wordlist', 'english.txt')
if not os.path.isfile(mnemonic_wordlist):
    raise SystemExit('mnemonic wordlist not found: %s' % mnemonic_wordlist)
print(mnemonic_wordlist)

a = Analysis(['app.py'],
             pathex=[spec_root],
	     binaries=[('C:\\Windows\\System32\\msvcp120.dll', 'msvcp120.dll',),
                        ('C:\\Windows\\System32\\msvcr120.dll', 'msvcr120.dll',),
                        ('..\\winlibs\\libeay32.dll', '.',),
                        ('..\\winlibs\\libsecp256k1.dll', 'coincurve',)],
             datas=[
          ('../plugins/yadacoinpool/templates', 'plugins/yadacoinpool/templates'),
          ('../plugins/yadacoinpool/static', 'plugins/yadacoinpool/static'),
		('../static', 'static/'),
		('../templates/', 'templates/'),
		(mnemonic_wordlist, 'mnemonic/wordlist/'),
	     ],
             hiddenimports=['eccsnacks', 'chardet'],
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
          icon='..\\static\\icon.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='YadaCoin')
