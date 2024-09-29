from __future__ import annotations

import typing

@typing.final
class AppInfo_Static(type):
    @property
    def current(cls) -> typing.Optional[AppInfo]: ...

@typing.final
class AppInfo(metaclass=AppInfo_Static):
    @property
    def app_user_model_id(self) -> str: ...
