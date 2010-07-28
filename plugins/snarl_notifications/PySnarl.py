"""
A python version of the main functions to use Snarl
(http://www.fullphat.net/snarl)

Version 1.0

This module can be used in two ways.  One is the normal way
the other snarl interfaces work. This means you can call snShowMessage
and get an ID back for manipulations.

The other way is there is a class this module exposes called SnarlMessage.
This allows you to keep track of the message as a python object.  If you
use the send without specifying False as the argument it will set the ID
to what the return of the last SendMessage was.  This is of course only
useful for the SHOW message.

Requires one of:
    pywin32 extensions from http://pywin32.sourceforge.net
    ctypes (included in Python 2.5, downloadable for earlier versions)

Creator: Sam Listopad II (samlii@users.sourceforge.net)

Copyright 2006-2008 Samuel Listopad II

Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this file except in compliance with the License. You may obtain a copy
of the License at http://www.apache.org/licenses/LICENSE-2.0 Unless required
by applicable law or agreed to in writing, software distributed under the
License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
OF ANY KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.
"""

import array, struct

def LOWORD(dword):
    """Return the low WORD of the passed in integer"""
    return dword & 0x0000ffff
#get the hi word
def HIWORD(dword):
    """Return the high WORD of the passed in integer"""
    return dword >> 16

class Win32FuncException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class Win32Funcs:
    """Just a little class to hide the details of finding and using the
correct win32 functions.  The functions may throw a UnicodeEncodeError if
there is not a unicode version and it is sent a unicode string that cannot
be converted to ASCII."""
    WM_USER = 0x400
    WM_COPYDATA = 0x4a
    #Type of String the functions are expecting.
    #Used like function(myWin32Funcs.strType(param)).
    __strType = str
    #FindWindow function to use
    __FindWindow = None
    #FindWindow function to use
    __FindWindowEx = None
    #SendMessage function to use
    __SendMessage = None
    #SendMessageTimeout function to use
    __SendMessageTimeout = None
    #IsWindow function to use
    __IsWindow = None
    #RegisterWindowMessage to use
    __RegisterWindowMessage = None
    #GetWindowText to use
    __GetWindowText = None

    def FindWindow(self, lpClassName, lpWindowName):
        """Wraps the windows API call of FindWindow"""
        if lpClassName is not None:
            lpClassName = self.__strType(lpClassName)
        if lpWindowName is not None:
            lpWindowName = self.__strType(lpWindowName)
        return self.__FindWindow(lpClassName, lpWindowName)

    def FindWindowEx(self, hwndParent, hwndChildAfter, lpClassName, lpWindowName):
        """Wraps the windows API call of FindWindow"""
        if lpClassName is not None:
            lpClassName = self.__strType(lpClassName)
        if lpWindowName is not None:
            lpWindowName = self.__strType(lpWindowName)
        return self.__FindWindowEx(hwndParent, hwndChildAfter, lpClassName, lpWindowName)

    def SendMessage(self, hWnd, Msg, wParam, lParam):
        """Wraps the windows API call of SendMessage"""
        return self.__SendMessage(hWnd, Msg, wParam, lParam)

    def SendMessageTimeout(self, hWnd, Msg,
                           wParam, lParam, fuFlags,
                           uTimeout, lpdwResult = None):
        """Wraps the windows API call of SendMessageTimeout"""
        idToRet = None
        try:
            idFromMsg = array.array('I', [0])
            result = idFromMsg.buffer_info()[0]
            response = self.__SendMessageTimeout(hWnd, Msg, wParam,
                                         lParam, fuFlags,
                                         uTimeout, result)
            if response == 0:
                raise Win32FuncException, "SendMessageTimeout TimedOut"

            idToRet = idFromMsg[0]
        except TypeError:
            idToRet = self.__SendMessageTimeout(hWnd, Msg, wParam,
                                                lParam, fuFlags,
                                                uTimeout)

        if lpdwResult is not None and lpdwResult.typecode == 'I':
            lpdwResult[0] = idToRet

        return idToRet

    def IsWindow(self, hWnd):
        """Wraps the windows API call of IsWindow"""
        return self.__IsWindow(hWnd)

    def RegisterWindowMessage(self, lpString):
        """Wraps the windows API call of RegisterWindowMessage"""
        return self.__RegisterWindowMessage(self.__strType(lpString))

    def GetWindowText(self, hWnd, lpString = None, nMaxCount = None):
        """Wraps the windows API call of SendMessageTimeout"""
        text = ''
        if hWnd == 0:
            return text

        if nMaxCount is None:
            nMaxCount = 1025

        try:
            arrayType = 'c'
            if self.__strType == unicode:
                arrayType = 'u'
            path_string = array.array(arrayType, self.__strType('\x00') * nMaxCount)
            path_buffer = path_string.buffer_info()[0]
            result = self.__GetWindowText(hWnd,
                                          path_buffer,
                                          nMaxCount)
            if result > 0:
                if self.__strType == unicode:
                    text = path_string[0:result].tounicode()
                else:
                    text = path_string[0:result].tostring()
        except TypeError:
            text = self.__GetWindowText(hWnd)

        if lpString is not None and lpString.typecode == 'c':
            lpdwResult[0:len(text)] = array.array('c', str(text));

        if lpString is not None and lpString.typecode == 'u':
            lpdwResult[0:len(text)] = array.array('u', unicode(text));

        return text

    def __init__(self):
        """Load up my needed functions"""
        # First see if they already have win32gui imported.  If so use it.
        # This has to be checked first since the auto check looks for ctypes
        # first.
        try:
            self.__FindWindow = win32gui.FindWindow
            self.__FindWindowEx = win32gui.FindWindowEx
            self.__GetWindowText = win32gui.GetWindowText
            self.__IsWindow = win32gui.IsWindow
            self.__SendMessage = win32gui.SendMessage
            self.__SendMessageTimeout = win32gui.SendMessageTimeout
            self.__RegisterWindowMessage = win32gui.RegisterWindowMessage
            self.__strType = unicode

        #Something threw a NameError,  most likely the win32gui lines
        #so do auto check
        except NameError:
            try:
                from ctypes import windll
                self.__FindWindow            = windll.user32.FindWindowW
                self.__FindWindowEx          = windll.user32.FindWindowExW
                self.__GetWindowText         = windll.user32.GetWindowTextW
                self.__IsWindow              = windll.user32.IsWindow
                self.__SendMessage           = windll.user32.SendMessageW
                self.__SendMessageTimeout    = windll.user32.SendMessageTimeoutW
                self.__RegisterWindowMessage = windll.user32.RegisterWindowMessageW
                self.__strType = unicode

            #FindWindowW wasn't found, look for FindWindowA
            except AttributeError:
                try:
                    self.__FindWindow            = windll.user32.FindWindowA
                    self.__FindWindowEx          = windll.user32.FindWindowExA
                    self.__GetWindowText         = windll.user32.GetWindowTextA
                    self.__IsWindow              = windll.user32.IsWindow
                    self.__SendMessage           = windll.user32.SendMessageA
                    self.__SendMessageTimeout    = windll.user32.SendMessageTimeoutA
                    self.__RegisterWindowMessage = windll.user32.RegisterWindowMessageA
                # Couldn't find either so Die and tell user why.
                except AttributeError:
                    import sys
                    sys.stderr.write("Your Windows TM setup seems to be corrupt."+
                                     "  No FindWindow found in user32.\n")
                    sys.stderr.flush()
                    sys.exit(3)

            except ImportError:
                try:
                    import win32gui
                    self.__FindWindow = win32gui.FindWindow
                    self.__FindWindowEx = win32gui.FindWindowEx
                    self.__GetWindowText = win32gui.GetWindowText
                    self.__IsWindow = win32gui.IsWindow
                    self.__SendMessage = win32gui.SendMessage
                    self.__SendMessageTimeout = win32gui.SendMessageTimeout
                    self.__RegisterWindowMessage = win32gui.RegisterWindowMessage
                    self.__strType = unicode

                except ImportError:
                    import sys
                    sys.stderr.write("You need to have either"+
                                     " ctypes or pywin32 installed.\n")
                    sys.stderr.flush()
                    #sys.exit(2)


myWin32Funcs = Win32Funcs()


SHOW                        = 1
HIDE                        = 2
UPDATE                      = 3
IS_VISIBLE                  = 4
GET_VERSION                 = 5
REGISTER_CONFIG_WINDOW      = 6
REVOKE_CONFIG_WINDOW        = 7
REGISTER_ALERT              = 8
REVOKE_ALERT                = 9
REGISTER_CONFIG_WINDOW_2    = 10
GET_VERSION_EX              = 11
SET_TIMEOUT                 = 12

EX_SHOW                     = 32

GLOBAL_MESSAGE = "SnarlGlobalMessage"
GLOBAL_MSG = "SnarlGlobalEvent"

#Messages That may be received from Snarl
SNARL_LAUNCHED                   = 1
SNARL_QUIT                       = 2
SNARL_ASK_APPLET_VER             = 3
SNARL_SHOW_APP_UI                = 4

SNARL_NOTIFICATION_CLICKED       = 32   #notification was right-clicked by user
SNARL_NOTIFICATION_CANCELLED     = SNARL_NOTIFICATION_CLICKED #Name clarified
SNARL_NOTIFICATION_TIMED_OUT     = 33
SNARL_NOTIFICATION_ACK           = 34   #notification was left-clicked by user

#Snarl Test Message
WM_SNARLTEST = myWin32Funcs.WM_USER + 237

M_ABORTED           =   0x80000007L
M_ACCESS_DENIED     =   0x80000009L
M_ALREADY_EXISTS    =   0x8000000CL
M_BAD_HANDLE        =   0x80000006L
M_BAD_POINTER       =   0x80000005L
M_FAILED            =   0x80000008L
M_INVALID_ARGS      =   0x80000003L
M_NO_INTERFACE      =   0x80000004L
M_NOT_FOUND         =   0x8000000BL
M_NOT_IMPLEMENTED   =   0x80000001L
M_OK                =   0x00000000L
M_OUT_OF_MEMORY     =   0x80000002L
M_TIMED_OUT         =   0x8000000AL

ErrorCodeRev = {
                    0x80000007L : "M_ABORTED",
                    0x80000009L : "M_ACCESS_DENIED",
                    0x8000000CL : "M_ALREADY_EXISTS",
                    0x80000006L : "M_BAD_HANDLE",
                    0x80000005L : "M_BAD_POINTER",
                    0x80000008L : "M_FAILED",
                    0x80000003L : "M_INVALID_ARGS",
                    0x80000004L : "M_NO_INTERFACE",
                    0x8000000BL : "M_NOT_FOUND",
                    0x80000001L : "M_NOT_IMPLEMENTED",
                    0x00000000L : "M_OK",
                    0x80000002L : "M_OUT_OF_MEMORY",
                    0x8000000AL : "M_TIMED_OUT"
                }

class SnarlMessage(object):
    """The main Snarl interface object.

    ID = Snarl Message ID for most operations.  See SDK for more info
         as to other values to put here.
    type = Snarl Message Type.  Valid values are : SHOW, HIDE, UPDATE,
           IS_VISIBLE, GET_VERSION, REGISTER_CONFIG_WINDOW, REVOKE_CONFIG_WINDOW
           all which are constants in the PySnarl module.
    timeout = Timeout in seconds for the Snarl Message
    data = Snarl Message data.  This is dependant upon message type.  See SDK
    title = Snarl Message title.
    text = Snarl Message text.
    icon = Path to the icon to display in the Snarl Message.
    """
    __msgType     = 0
    __msgID       = 0
    __msgTimeout  = 0
    __msgData     = 0
    __msgTitle    = ""
    __msgText     = ""
    __msgIcon     = ""
    __msgClass    = ""
    __msgExtra    = ""
    __msgExtra2   = ""
    __msgRsvd1    = 0
    __msgRsvd2    = 0
    __msgHWnd     = 0

    lastKnownHWnd = 0

    def getType(self):
        """Type Attribute getter."""
        return self.__msgType
    def setType(self, value):
        """Type Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgType = value
    type = property(getType, setType, doc="The Snarl Message Type")

    def getID(self):
        """ID Attribute getter."""
        return self.__msgID
    def setID(self, value):
        """ID Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgID = value
    ID = property(getID, setID, doc="The Snarl Message ID")

    def getTimeout(self):
        """Timeout Attribute getter."""
        return self.__msgTimeout
    def updateTimeout(self, value):
        """Timeout Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgTimeout = value
    timeout = property(getTimeout, updateTimeout,
                       doc="The Snarl Message Timeout")

    def getData(self):
        """Data Attribute getter."""
        return self.__msgData
    def setData(self, value):
        """Data Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgData = value
    data = property(getData, setData, doc="The Snarl Message Data")

    def getTitle(self):
        """Title Attribute getter."""
        return self.__msgTitle
    def setTitle(self, value):
        """Title Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgTitle = value
    title = property(getTitle, setTitle, doc="The Snarl Message Title")

    def getText(self):
        """Text Attribute getter."""
        return self.__msgText
    def setText(self, value):
        """Text Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgText = value
    text = property(getText, setText, doc="The Snarl Message Text")

    def getIcon(self):
        """Icon Attribute getter."""
        return self.__msgIcon
    def setIcon(self, value):
        """Icon Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgIcon = value
    icon = property(getIcon, setIcon, doc="The Snarl Message Icon")

    def getClass(self):
        """Class Attribute getter."""
        return self.__msgClass
    def setClass(self, value):
        """Class Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgClass = value
    msgclass = property(getClass, setClass, doc="The Snarl Message Class")

    def getExtra(self):
        """Extra Attribute getter."""
        return self.__msgExtra
    def setExtra(self, value):
        """Extra Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgExtra = value
    extra = property(getExtra, setExtra, doc="Extra Info for the Snarl Message")

    def getExtra2(self):
        """Extra2 Attribute getter."""
        return self.__msgExtra2
    def setExtra2(self, value):
        """Extra2 Attribute setter."""
        if( isinstance(value, basestring) ):
            self.__msgExtra2 = value
    extra2 = property(getExtra2, setExtra2,
                      doc="More Extra Info for the Snarl Message")

    def getRsvd1(self):
        """Rsvd1 Attribute getter."""
        return self.__msgRsvd1
    def setRsvd1(self, value):
        """Rsvd1 Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgRsvd1 = value
    rsvd1 = property(getRsvd1, setRsvd1, doc="The Snarl Message Field Rsvd1")

    def getRsvd2(self):
        """Rsvd2 Attribute getter."""
        return self.__msgRsvd2
    def setRsvd2(self, value):
        """Rsvd2 Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgRsvd2 = value
    rsvd2 = property(getRsvd2, setRsvd2, doc="The Snarl Message Field Rsvd2")

    def getHwnd(self):
        """hWnd Attribute getter."""
        return self.__msgHWnd
    def setHwnd(self, value):
        """hWnd Attribute setter."""
        if( isinstance(value, (int, long)) ):
            self.__msgHWnd = value

    hWnd = property(getHwnd, setHwnd, doc="The hWnd of the window this message is being sent from")


    def __init__(self, title="", text="", icon="", msg_type=1, msg_id=0):
        self.__msgTimeout  = 0
        self.__msgData     = 0
        self.__msgClass    = ""
        self.__msgExtra    = ""
        self.__msgExtra2   = ""
        self.__msgRsvd1    = 0
        self.__msgRsvd2    = 0
        self.__msgType = msg_type
        self.__msgText = text
        self.__msgTitle = title
        self.__msgIcon = icon
        self.__msgID = msg_id

    def createCopyStruct(self):
        """Creates the struct to send as the copyData in the message."""
        return struct.pack("ILLL1024s1024s1024s1024s1024s1024sLL",
                           self.__msgType,
                           self.__msgID,
                           self.__msgTimeout,
                           self.__msgData,
                           self.__msgTitle.encode('utf-8'),
                           self.__msgText.encode('utf-8'),
                           self.__msgIcon.encode('utf-8'),
                           self.__msgClass.encode('utf-8'),
                           self.__msgExtra.encode('utf-8'),
                           self.__msgExtra2.encode('utf-8'),
                           self.__msgRsvd1,
                           self.__msgRsvd2
                           )
    __lpData = None
    __cds = None

    def packData(self, dwData):
        """This packs the data in the necessary format for a
WM_COPYDATA message."""
        self.__lpData = None
        self.__cds = None
        item = self.createCopyStruct()
        self.__lpData = array.array('c', item)
        lpData_ad = self.__lpData.buffer_info()[0]
        cbData = self.__lpData.buffer_info()[1]
        self.__cds = array.array('c',
                                 struct.pack("IIP",
                                             dwData,
                                             cbData,
                                             lpData_ad)
                                 )
        cds_ad = self.__cds.buffer_info()[0]
        return cds_ad

    def reset(self):
        """Reset this SnarlMessage to the default state."""
        self.__msgType     = 0
        self.__msgID       = 0
        self.__msgTimeout  = 0
        self.__msgData     = 0
        self.__msgTitle    = ""
        self.__msgText     = ""
        self.__msgIcon     = ""
        self.__msgClass    = ""
        self.__msgExtra    = ""
        self.__msgExtra2   = ""
        self.__msgRsvd1    = 0
        self.__msgRsvd2    = 0


    def send(self, setid=True):
        """Send this SnarlMessage to the Snarl window.
Args:
        setid - Boolean defining whether or not to set the ID
                of this SnarlMessage to the return value of
                the SendMessage call.  Default is True to
                make simple case of SHOW easy.
        """
        hwnd = myWin32Funcs.FindWindow(None, "Snarl")
        if myWin32Funcs.IsWindow(hwnd):
            if self.type == REGISTER_CONFIG_WINDOW or self.type == REGISTER_CONFIG_WINDOW_2:
                self.hWnd = self.data
            try:
                response = myWin32Funcs.SendMessageTimeout(hwnd,
                                                           myWin32Funcs.WM_COPYDATA,
                                                           self.hWnd, self.packData(2),
                                                           2, 500)
            except Win32FuncException:
                return False

            idFromMsg = response
            if setid:
                self.ID = idFromMsg
                return True
            else:
                return idFromMsg
        print "No snarl window found"
        return False

    def hide(self):
        """Hide this message.  Type will revert to type before calling hide
to allow for better reuse of object."""
        oldType = self.__msgType
        self.__msgType = HIDE
        retVal = bool(self.send(False))
        self.__msgType = oldType
        return retVal

    def isVisible(self):
        """Is this message visible.  Type will revert to type before calling
hide to allow for better reuse of object."""
        oldType = self.__msgType
        self.__msgType = IS_VISIBLE
        retVal = bool(self.send(False))
        self.__msgType = oldType
        return retVal

    def update(self, title=None, text=None, icon=None):
        """Update this message with given title and text.  Type will revert
to type before calling hide to allow for better reuse of object."""
        oldType = self.__msgType
        self.__msgType = UPDATE
        if text:
            self.__msgText = text
        if title:
            self.__msgTitle = title
        if icon:
            self.__msgIcon = icon
        retVal = self.send(False)
        self.__msgType = oldType
        return retVal

    def setTimeout(self, timeout):
        """Set the timeout in seconds of the message"""
        oldType = self.__msgType
        oldData = self.__msgData
        self.__msgType = SET_TIMEOUT
        #self.timeout = timeout
        #self.__msgData = self.__msgTimeout
        self.__msgData = timeout
        retVal = self.send(False)
        self.__msgType = oldType
        self.__msgData = oldData
        return retVal

    def show(self, timeout=None, title=None,
             text=None, icon=None,
             replyWindow=None, replyMsg=None, msgclass=None, soundPath=None):
        """Show a message"""
        oldType = self.__msgType
        oldTimeout = self.__msgTimeout
        self.__msgType = SHOW
        if text:
            self.__msgText = text
        if title:
            self.__msgTitle = title
        if timeout:
            self.__msgTimeout = timeout
        if icon:
            self.__msgIcon = icon
        if replyWindow:
            self.__msgID = replyMsg
        if replyMsg:
            self.__msgData = replyWindow
        if soundPath:
            self.__msgExtra = soundPath
        if msgclass:
            self.__msgClass = msgclass

        if ((self.__msgClass and self.__msgClass != "") or
           (self.__msgExtra and self.__msgExtra != "")):
            self.__msgType = EX_SHOW


        retVal = bool(self.send())
        self.__msgType = oldType
        self.__msgTimeout = oldTimeout
        return retVal


def snGetVersion():
    """ Get the version of Snarl that is running as a tuple.  (Major, Minor)

If Snarl is not running or there was an error it will
return False."""
    msg = SnarlMessage(msg_type=GET_VERSION)
    version = msg.send(False)
    if not version:
        return False
    return (HIWORD(version), LOWORD(version))

def snGetVersionEx():
    """ Get the internal version of Snarl that is running.

If Snarl is not running or there was an error it will
return False."""
    sm = SnarlMessage(msg_type=GET_VERSION_EX)
    verNum = sm.send(False)
    if not verNum:
        return False
    return verNum

def snGetGlobalMessage():
    """Get the Snarl global message id from windows."""
    return myWin32Funcs.RegisterWindowMessage(GLOBAL_MSG)

def snShowMessage(title, text, timeout=0, iconPath="",
                  replyWindow=0, replyMsg=0):
    """Show a message using Snarl and return its ID.  See SDK for arguments."""
    sm = SnarlMessage( title, text, iconPath, msg_id=replyMsg)
    sm.data = replyWindow
    if sm.show(timeout):
        return sm.ID
    else:
        return False

def snShowMessageEx(msgClass, title, text, timeout=0, iconPath="",
                  replyWindow=0, replyMsg=0, soundFile=None, hWndFrom=None):
    """Show a message using Snarl and return its ID.  See SDK for arguments.
    One added argument is hWndFrom that allows one to make the messages appear
    to come from a specific window.  This window should be the one you registered
    earlier with RegisterConfig"""
    sm = SnarlMessage( title, text, iconPath, msg_id=replyMsg)
    sm.data = replyWindow
    if hWndFrom is not None:
        sm.hWnd = hWndFrom
    else:
        sm.hWnd = SnarlMessage.lastKnownHWnd
    if sm.show(timeout, msgclass=msgClass, soundPath=soundFile):
        return sm.ID
    else:
        return False

def snUpdateMessage(msgId, msgTitle, msgText, icon=None):
    """Update a message"""
    sm = SnarlMessage(msg_id=msgId)
    if icon:
        sm.icon = icon
    return sm.update(msgTitle, msgText)

def snHideMessage(msgId):
    """Hide a message"""
    return SnarlMessage(msg_id=msgId).hide()

def snSetTimeout(msgId, timeout):
    """Update the timeout of a message already shown."""
    sm = SnarlMessage(msg_id=msgId)
    return sm.setTimeout(timeout)

def snIsMessageVisible(msgId):
    """Returns True if the message is visible False otherwise."""
    return SnarlMessage(msg_id=msgId).isVisible()

def snRegisterConfig(replyWnd, appName, replyMsg):
    """Register a config window.  See SDK for more info."""
    global lastRegisteredSnarlMsg
    sm = SnarlMessage(msg_type=REGISTER_CONFIG_WINDOW,
                      title=appName,
                      msg_id=replyMsg)
    sm.data = replyWnd
    SnarlMessage.lastKnownHWnd = replyWnd

    return sm.send(False)

def snRegisterConfig2(replyWnd, appName, replyMsg, icon):
    """Register a config window.  See SDK for more info."""
    global lastRegisteredSnarlMsg
    sm = SnarlMessage(msg_type=REGISTER_CONFIG_WINDOW_2,
                      title=appName,
                      msg_id=replyMsg,
                      icon=icon)
    sm.data = replyWnd
    SnarlMessage.lastKnownHWnd = replyWnd
    return sm.send(False)

def snRegisterAlert(appName, classStr) :
    """Register an alert for an already registered config.  See SDK for more info."""
    sm = SnarlMessage(msg_type=REGISTER_ALERT,
                      title=appName,
                      text=classStr)
    return sm.send(False)

def snRevokeConfig(replyWnd):
    """Revoke a config window"""
    sm = SnarlMessage(msg_type=REVOKE_CONFIG_WINDOW)
    sm.data = replyWnd
    if replyWnd == SnarlMessage.lastKnownHWnd:
        SnarlMessage.lastKnownHWnd = 0
    return sm.send(False)

def snGetSnarlWindow():
    """Returns the hWnd of the snarl window"""
    return myWin32Funcs.FindWindow(None, "Snarl")

def snGetAppPath():
    """Returns the application path of the currently running snarl window"""
    app_path = None
    snarl_handle = snGetSnarlWindow()
    if snarl_handle != 0:
        pathwin_handle = myWin32Funcs.FindWindowEx(snarl_handle,
                                                   0,
                                                   "static",
                                                   None)
        if pathwin_handle != 0:
            try:
                result = myWin32Funcs.GetWindowText(pathwin_handle)
                app_path = result
            except Win32FuncException:
                pass


    return app_path

def snGetIconsPath():
    """Returns the path to the icons of the program"""
    s = snGetAppPath()
    if s is None:
        return ""
    else:
        return s + "etc\\icons\\"

def snSendTestMessage(data=None):
    """Sends a test message to Snarl.  Used to make sure the
api is connecting"""
    param = 0
    command = 0
    if data:
        param = struct.pack("I", data)
        command = 1
    myWin32Funcs.SendMessage(snGetSnarlWindow(), WM_SNARLTEST, command, param)
