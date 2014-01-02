# -*- coding:utf-8 -*-
## src/common/sleepy.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2008 Mateusz Biliński <mateusz AT bilinski.it>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from common import gajim
import os
import sys


STATE_UNKNOWN  = 'OS probably not supported'
STATE_XA   = 'extended away'
STATE_AWAY   = 'away'
STATE_AWAKE     = 'awake'

SUPPORTED = True
try:
    if os.name == 'nt':
        import ctypes

        GetTickCount = ctypes.windll.kernel32.GetTickCount
        GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]

        lastInputInfo = LASTINPUTINFO()
        lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)

        # one or more of these may not be supported before XP.
        OpenInputDesktop = ctypes.windll.user32.OpenInputDesktop
        CloseDesktop = ctypes.windll.user32.CloseDesktop
        SystemParametersInfo = ctypes.windll.user32.SystemParametersInfoW
    else: # unix
        from common import idle
        idle.xss_available
except Exception:
    gajim.log.debug('Unable to load idle module')
    SUPPORTED = False

class SleepyWindows:
    def __init__(self, away_interval = 60, xa_interval = 120):
        self.away_interval = away_interval
        self.xa_interval = xa_interval
        self.state = STATE_AWAKE # assume we are awake

    def getIdleSec(self):
        GetLastInputInfo(ctypes.byref(lastInputInfo))
        idleDelta = float(GetTickCount() - lastInputInfo.dwTime) / 1000
        return idleDelta

    def poll(self):
        """
        Check to see if we should change state
        """
        if not SUPPORTED:
            return False

        # screen saver, in windows >= XP
        saver_runing = ctypes.c_int(0)
        # 0x72 is SPI_GETSCREENSAVERRUNNING
        if SystemParametersInfo(0x72, 0, ctypes.byref(saver_runing), 0) and \
        saver_runing.value:
            self.state = STATE_XA
            return True

        desk = OpenInputDesktop(0, False, 0)
        if not desk:
            # Screen locked
            self.state = STATE_XA
            return True
        CloseDesktop(desk)

        idleTime = self.getIdleSec()

        # xa is stronger than away so check for xa first
        if idleTime > self.xa_interval:
            self.state = STATE_XA
        elif idleTime > self.away_interval:
            self.state = STATE_AWAY
        else:
            self.state = STATE_AWAKE
        return True

    def getState(self):
        return self.state

    def setState(self, val):
        self.state = val

class SleepyUnix:
    def __init__(self, away_interval = 60, xa_interval = 120):
        global SUPPORTED
        self.away_interval = away_interval
        self.xa_interval = xa_interval
        self.state = STATE_AWAKE # assume we are awake

    def getIdleSec(self):
        return idle.getIdleSec()

    def poll(self):
        """
        Check to see if we should change state
        """
        if not SUPPORTED:
            return False

        idleTime = self.getIdleSec()

        # xa is stronger than away so check for xa first
        if idleTime > self.xa_interval:
            self.state = STATE_XA
        elif idleTime > self.away_interval:
            self.state = STATE_AWAY
        else:
            self.state = STATE_AWAKE
        return True

    def getState(self):
        return self.state

    def setState(self, val):
        self.state = val

if os.name == 'nt':
    Sleepy = SleepyWindows
else:
    Sleepy = SleepyUnix
