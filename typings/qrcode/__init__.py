
from __future__ import annotations

from typing import Any
from typing import Optional

from . import constants as constants


class QRCode:
    def __init__(self, version: Optional[int], error_correction: int, box_size: int, border: int, image_factory: Optional[Any] = None, mask_pattern: Optional[Any] = None) -> None: ...
    def add_data(self, data: str) -> None: ...
    def make(self, fit: bool) -> None: ...
    def make_image(self, image_factory: Optional[Any] = None, fill_color: str, back_color: str) -> Any: ...
