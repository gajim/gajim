from __future__ import annotations

import typing

@typing.final
class ApplicationData_Static(type):
    @property
    def current(cls) -> typing.Optional[ApplicationData]: ...

@typing.final
class ApplicationData(metaclass=ApplicationData_Static):
    @property
    def local_cache_folder(self) -> typing.Optional[StorageFolder]: ...

@typing.final
class StorageFolder_Static(type): ...

@typing.final
class StorageFolder(metaclass=StorageFolder_Static):
    @property
    def path(self) -> str: ...
