import sys
from pathlib import Path

__version__ = '1.6.0'

IS_FLATPAK = Path('/app/share/run-as-flatpak').exists()

portable_path = Path(sys.executable).parent / 'is_portable'
IS_PORTABLE = portable_path.exists()
