import sys
from pathlib import Path

from .config import *  # noqa: F403

__version__ = "2.2.0"

portable_path = Path(sys.executable).parent / "is_portable"
IS_PORTABLE = portable_path.exists()

# Check for Microsoft app identity by trying to query AppInfo.
# If there is no AppInfo, it's no MS Store install.
has_ms_appinfo = False
try:
    from winrt.windows.applicationmodel import AppInfo

    has_ms_appinfo = AppInfo.current is not None
except Exception:
    pass

IS_MS_STORE = has_ms_appinfo
