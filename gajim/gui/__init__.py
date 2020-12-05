
import sys
import importlib
from pathlib import Path


class GUIFinder(importlib.abc.MetaPathFinder):

    def __init__(self, name, fallback=None):
        self._path = Path(__file__).parent.parent / name

        self._fallback_path = None
        if fallback is not None:
            self._fallback_path = Path(__file__).parent.parent / fallback

        self._suffix = 'pyc' if sys.platform == 'win32' else 'py'

    def find_spec(self, fullname, _path, _target=None):
        if not fullname.startswith('gajim.gui'):
            return None

        _namespace, module_name = fullname.rsplit('.', 1)
        module_path = self._path / f'{module_name}.{self._suffix}'

        if not module_path.exists():
            if self._fallback_path is None:
                return None

            module_path = self._fallback_path / f'{module_name}.{self._suffix}'
            if not module_path.exists():
                return None

        spec = importlib.util.spec_from_file_location(fullname, module_path)

        return spec

def init(name, fallback=None):
    sys.meta_path.append(GUIFinder(name, fallback=fallback))
