"""
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
"""

from typing import Any  # pylint: disable=unused-import
from typing import ClassVar  # pylint: disable=unused-import
from typing import Dict  # pylint: disable=unused-import
from typing import Tuple  # pylint: disable=unused-import


class FilesProp:
    _files_props = {}  # type: ClassVar[Dict[Tuple[str, str], Any]]

    def __init__(self):
        raise Exception('this class should not be instantiated')

    @classmethod
    def getNewFileProp(cls, account, sid):
        fp = FileProp(account, sid)
        cls.setFileProp(fp, account, sid)
        return fp

    @classmethod
    def getFileProp(cls, account, sid):
        return cls._files_props.get(account, sid)

    @classmethod
    def getFilePropByAccount(cls, account):
        # Returns a list of file_props in one account
        file_props = []
        for account_, sid in cls._files_props:
            if account_ == account:
                file_props.append(cls._files_props[account, sid])
        return file_props

    @classmethod
    def getFilePropByType(cls, type_, sid):
        # This method should be deleted. Getting fileprop by type and sid is not
        # unique enough. More than one fileprop might have the same type and sid
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.type_ == type_ and fp.sid == sid:
                return fp

    @classmethod
    def getFilePropBySid(cls, sid):
        # This method should be deleted. It is kept to make things compatible
        # This method should be replaced and instead get the file_props by
        # account and sid
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.sid == sid:
                return fp

    @classmethod
    def getFilePropByTransportSid(cls, account, sid):
        files_prop = cls.getAllFileProp()
        for fp in files_prop:
            if fp.account == account and fp.transport_sid == sid:
                return fp

    @classmethod
    def getAllFileProp(cls):
        return list(cls._files_props.values())

    @classmethod
    def setFileProp(cls, fp, account, sid):
        cls._files_props[account, sid] = fp

    @classmethod
    def deleteFileProp(cls, file_prop):
        files_props = cls._files_props
        a = s = None
        for key in files_props:
            account, sid = key
            fp = files_props[account, sid]
            if fp is file_prop:
                a = account
                s = sid
        if a is not None and s is not None:
            del files_props[a, s]


class FileProp:

    def __init__(self, account, sid):
        # Do not instantiate this class directly. Call FilesProp.getNeFileProp
        # instead
        self.streamhosts = []
        self.transfered_size = []
        self.started = False
        self.completed = False
        self.paused = False
        self.stalled = False
        self.connected = False
        self.stopped = False
        self.is_a_proxy = False
        self.proxyhost = None
        self.proxy_sender = None
        self.proxy_receiver = None
        self.streamhost_used = None
        # method callback called in case of transfer failure
        self.failure_cb = None
        # method callback called when disconnecting
        self.disconnect_cb = None
        self.continue_cb = None
        self.sha_str = None
        # transfer type: 's' for sending and 'r' for receiving
        self.type_ = None
        self.error = None
        # Elapsed time of the file transfer
        self.elapsed_time = 0
        self.last_time = None
        self.received_len = None
        # full file path
        self.file_name = None
        self.name = None
        self.date = None
        self.desc = None
        self.offset = None
        self.sender = None
        self.receiver = None
        self.tt_account = None
        self.size = None
        self._sid = sid
        self.transport_sid = None
        self.account = account
        self.mime_type = None
        self.algo = None
        self.direction = None
        self.syn_id = None
        self.seq = None
        self.hash_ = None
        self.fd = None
        self.startexmpp = None
        # Type of the session, if it is 'jingle' or 'si'
        self.session_type = None
        self.request_id = None
        self.proxyhosts = None
        self.dstaddr = None

    def getsid(self):
        # Getter of the property sid
        return self._sid

    def setsid(self, value):
        # The sid value will change
        # we need to change the in _files_props key as well
        del FilesProp._files_props[self.account, self._sid]
        self._sid = value
        FilesProp._files_props[self.account, self._sid] = self

    sid = property(getsid, setsid)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
