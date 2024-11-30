from __future__ import annotations

from typing import Any

from . import constants as constants

class QRCode:
    def __init__(
        self,
        version: int | None,
        error_correction: int,
        box_size: int,
        border: int,
        image_factory: Any = None,
        mask_pattern: Any = None,
    ) -> None: ...
    def add_data(self, data: str) -> None: ...
    def make(self, fit: bool) -> None: ...
    def make_image(self, image_factory: Any = None, **kwargs: Any) -> Any: ...
