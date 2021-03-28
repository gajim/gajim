
from __future__ import annotations

from typing import Union
from typing import Sequence
from typing import Optional

import types
import sys
from importlib.abc import MetaPathFinder
from importlib.util import spec_from_file_location
from importlib.machinery import ModuleSpec
from pathlib import Path


class GUIFinder(MetaPathFinder):

    def __init__(self, name: str, fallback: Optional[str] = None) -> None:
        self._path = Path(__file__).parent.parent / name

        self._fallback_path = None
        if fallback is not None:
            self._fallback_path = Path(__file__).parent.parent / fallback

    def find_spec(self,
                  fullname: str,
                  path: Optional[Sequence[Union[bytes, str]]],
                  target: Optional[types.ModuleType] = None) -> Optional[ModuleSpec]:

        if not fullname.startswith('gajim.gui'):
            return None

        _, module_name = fullname.rsplit('.', 1)
        module_path = self._find_module(module_name)
        if module_path is None:
            return None

        spec = spec_from_file_location(fullname, module_path)

        return spec

    def _find_module(self, module_name: str) -> Optional[Path]:
        base_path = Path(self._path)

        fallback_base_path = None
        if self._fallback_path is not None:
            fallback_base_path = Path(self._fallback_path)

        module_path = base_path / module_name
        if module_path.is_dir():
            base_path = module_path
            if fallback_base_path is not None:
                fallback_base_path = fallback_base_path / module_name

            module_name = '__init__'

        module_path = base_path / f'{module_name}.py'
        if module_path.exists():
            return module_path

        module_path = base_path / f'{module_name}.pyc'
        if module_path.exists():
            return module_path

        if fallback_base_path is None:
            return None

        module_path = fallback_base_path / f'{module_name}.py'
        if module_path.exists():
            return module_path

        module_path = fallback_base_path / f'{module_name}.pyc'
        if module_path.exists():
            return module_path

        return None


def init(name: str, fallback: Optional[str] = None) -> None:
    sys.meta_path.append(GUIFinder(name, fallback=fallback))
