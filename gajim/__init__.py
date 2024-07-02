import sys
from pathlib import Path

__version__ = '1.9.1'

IS_FLATPAK = Path('/app/share/run-as-flatpak').exists()

portable_path = Path(sys.executable).parent / 'is_portable'
IS_PORTABLE = portable_path.exists()

# Check for Microsoft app identity by trying to query AppInfo.
# If there is no AppInfo, it's no MS Store install.
has_ms_appinfo = False
try:
    from winrt.windows.applicationmodel import AppInfo
    _current_appinfo = AppInfo.current()  # type: ignore
    has_ms_appinfo = True
except (AttributeError, ImportError, OSError):
    pass

IS_MS_STORE = has_ms_appinfo
