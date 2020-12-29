import subprocess
import sys
from pathlib import Path

__version__ = "1.4.0-dev1"

IS_FLATPAK = Path('/app/share/run-as-flatpak').exists()

portable_path = Path(sys.executable).parent / 'is_portable'
IS_PORTABLE = portable_path.exists()

try:
    p = subprocess.Popen('git rev-parse --short=12 HEAD', shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    node = p.communicate()[0]
    if node:
        __version__ += '+' + node.decode('utf-8').strip()
except Exception:
    pass
