# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['samcli/__main__.py'],
             pathex=['/home/circleci/project'],
             binaries=[],
             datas=[('samcli/lib/generated_sample_events/event-mapping.json', 'samcli/lib/generated_sample_events')],
             hiddenimports=['samcli.commands.publish', 'samcli.commands.logs', 'samcli.commands.deploy', 'samcli.commands.package','samcli.commands.local.local','samcli.commands.build','samcli.commands.validate.validate','samcli.commands.init'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='sam',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
