'''
This module is in charge of taking care of all the information related to
individual files. Files are identified by the account name and its sid.


>>> print(FilesProp.getFileProp('jabberid', '10'))
None
>>> fp = FilesProp()
Traceback (most recent call last):
    ...
Exception: this class should not be instatiated
>>> print(FilesProp.getAllFileProp())
[]
>>> fp = FilesProp.getNewFileProp('jabberid', '10')
>>> fp2 = FilesProp.getFileProp('jabberid', '10')
>>> fp == fp2
True
'''

from __future__ import annotations

from typing import ClassVar
from typing import Literal

from collections.abc import Callable


class FilesProp:
    _files_props: ClassVar[dict[tuple[str, str], FileProp]] = {}

    def __init__(self):
        raise Exception('this class should not be instantiated')

    @classmethod
    def getNewFileProp(cls, account: str, sid: str) -> FileProp:
        fp = FileProp(account, sid)
        cls.setFileProp(fp, account, sid)
        return fp

    @classmethod
    def getFileProp(cls, account: str, sid: str) -> FileProp | None:
        return cls._files_props.get((account, sid))

    @classmethod
    def getFilePropByAccount(cls, account: str) -> list[FileProp]:
        # Returns a list of file_props in one account
        file_props: list[FileProp] = []
        for account_, sid in cls._files_props:
            if account_ == account:
                file_props.append(cls._files_props[account, sid])
        return file_props

    @classmethod
    def getFilePropByType(cls,
                          type_: Literal['r', 's'],
                          sid: str
                          ) -> FileProp | None:
        # This method should be deleted. Getting fileprop by type and sid is not
        # unique enough. More than one fileprop might have the same type and sid
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.type_ == type_ and fp.sid == sid:
                return fp
        return None

    @classmethod
    def getFilePropBySid(cls, sid: str) -> FileProp | None:
        # This method should be deleted. It is kept to make things compatible
        # This method should be replaced and instead get the file_props by
        # account and sid
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.sid == sid:
                return fp
        return None

    @classmethod
    def getFilePropByTransportSid(cls,
                                  account: str,
                                  sid: str
                                  ) -> FileProp | None:
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.account == account and fp.transport_sid == sid:
                return fp
        return None

    @classmethod
    def getAllFileProp(cls) -> list[FileProp]:
        return list(cls._files_props.values())

    @classmethod
    def setFileProp(cls, fp: FileProp, account: str, sid: str) -> None:
        cls._files_props[account, sid] = fp

    @classmethod
    def deleteFileProp(cls, file_prop: FileProp) -> None:
        files_props = cls._files_props
        acc = sid_ = None
        for key in files_props:
            account, sid = key
            fp = files_props[account, sid]
            if fp is file_prop:
                acc = account
                sid_ = sid
        if acc is not None and sid_ is not None:
            del files_props[acc, sid_]


class FileProp:
    def __init__(self, account: str, sid: str) -> None:
        # Do not instantiate this class directly!
        # Call FilesProp.getNeFileProp instead
        self.streamhosts = []
        self.transferred_size: list[tuple[float, int]] = []
        self.started: bool = False
        self.completed: bool = False
        self.paused: bool = False
        self.stalled: bool = False
        self.connected: bool = False
        self.stopped: bool = False
        self.is_a_proxy: bool = False
        self.proxyhost = None
        self.proxy_sender = None
        self.proxy_receiver = None
        self.streamhost_used = None
        self.failure_cb: Callable[[str], None] | None = None
        self.disconnect_cb = None
        self.continue_cb: Callable[..., None] | None = None
        self.sha_str: str | None = None
        # transfer type: 's' for sending and 'r' for receiving
        self.type_: Literal['r', 's'] | None = None
        self.error: int | None = None
        self.elapsed_time: float = 0  # Elapsed time of the file transfer
        self.last_time: float | None = None
        self.received_len: int | None = None
        self.file_name: str | None = None  # full file path
        self.name: str | None = None
        self.date: str | None = None
        self.desc: str | None = None
        self.offset: int | None = None
        self.sender: str | None = None
        self.receiver: str | None = None
        self.tt_account: str | None = None
        self.size: int | None = None
        self._sid = sid
        self.transport_sid: str | None = None
        self.account = account
        self.mime_type: str | None = None
        self.algo: str | None = None
        self.direction: Literal['<', '>'] | None = None
        self.syn_id: str | None = None
        self.seq: int | None = None
        self.hash_: str | None = None
        self.fd: int | None = None
        # Type of the session, if it is 'jingle' or 'si'
        self.session_type: str | None = None
        self.request_id: str | None = None
        self.proxyhosts = None
        self.dstaddr = None

    def getsid(self) -> str:
        # Getter of the property sid
        return self._sid

    def setsid(self, value: str) -> None:
        # The sid value will change
        # we need to change the in _files_props key as well
        del FilesProp._files_props[self.account, self._sid]
        self._sid = value
        FilesProp._files_props[self.account, self._sid] = self

    sid = property(getsid, setsid)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
