# -*- mode: python -*-
import os
import mnemonic
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

spec_root = os.path.abspath(SPECPATH)
print(spec_root)
block_cipher = None
mnemonic_wordlist = os.path.join(os.path.dirname(mnemonic.__file__), 'wordlist', 'english.txt')
if not os.path.isfile(mnemonic_wordlist):
    raise SystemExit('mnemonic wordlist not found: %s' % mnemonic_wordlist)
print(mnemonic_wordlist)

crypto_hidden = collect_submodules('Crypto')
crypto_binaries = collect_dynamic_libs('Crypto')

repo_root = os.path.abspath(os.path.join(spec_root, '..'))
plugins_root = os.path.join(repo_root, 'plugins')
plugin_skip_dirs = {
    'node_modules', '.git', '__pycache__', '.github', '.vscode', 'ui', 'e2e',
}
plugin_hidden = []
plugin_datas = []
if os.path.isdir(plugins_root):
    for plugin_name in sorted(os.listdir(plugins_root)):
        plugin_dir = os.path.join(plugins_root, plugin_name)
        if (
            plugin_name.startswith('.')
            or not os.path.isdir(plugin_dir)
            or not os.path.isfile(os.path.join(plugin_dir, 'handlers.py'))
        ):
            continue
        for root, dirs, files in os.walk(plugin_dir):
            dirs[:] = [d for d in dirs if d not in plugin_skip_dirs and not d.startswith('.')]
            rel = os.path.relpath(root, plugin_dir)
            dest = os.path.join('plugins', plugin_name) if rel == '.' else os.path.join('plugins', plugin_name, rel)
            mod_prefix = 'plugins.' + plugin_name if rel == '.' else 'plugins.' + plugin_name + '.' + rel.replace(os.sep, '.')
            for filename in files:
                if filename.endswith('.py'):
                    plugin_hidden.append(mod_prefix if filename == '__init__.py' else mod_prefix + '.' + filename[:-3])
                elif not filename.endswith(('.pyc', '.pyo')):
                    plugin_datas.append((os.path.join(root, filename), dest))

node_dashboard_hidden = []
if os.path.isdir(os.path.join(repo_root, 'node_dashboard')):
    node_dashboard_hidden = collect_submodules('node_dashboard')

a = Analysis(['app.py'],
             pathex=[spec_root, repo_root],
	     binaries=[('C:\\Windows\\System32\\msvcp120.dll', 'msvcp120.dll',),
                        ('C:\\Windows\\System32\\msvcr120.dll', 'msvcr120.dll',),
                        ('..\\winlibs\\libeay32.dll', '.',),
                        ('..\\winlibs\\libsecp256k1.dll', 'coincurve',)] + crypto_binaries,
             datas=[
		('../static', 'static/'),
		('../templates/', 'templates/'),
		(mnemonic_wordlist, 'mnemonic/wordlist/'),
	     ] + plugin_datas,
             hiddenimports=['eccsnacks', 'chardet', 'Crypto.PublicKey._nist_ecc', 'Crypto.PublicKey.ECC'] + crypto_hidden + plugin_hidden + node_dashboard_hidden,
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
