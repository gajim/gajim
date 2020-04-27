import os
import subprocess

__version__ = "1.1.99"

IS_FLATPAK = False
if os.path.exists('/app/share/run-as-flatpak'):
    IS_FLATPAK = True

IS_PORTABLE = False
portable_path = os.path.join(os.getcwd(), 'is_portable')
if os.path.exists(portable_path):
    IS_PORTABLE = True

try:
    p = subprocess.Popen('git rev-parse --short=12 HEAD', shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    node = p.communicate()[0]
    if node:
        __version__ += '+' + node.decode('utf-8').strip()
except Exception:
    pass
