# -*- coding:utf-8 -*-
## src/common/kwalletbinding.py
##
## Copyright (c) 2009 Thorsten Glaser <t.glaser AT tarent.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only. This file is
## also available under the terms of The MirOS Licence.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

__all__ = ['kwallet_available', 'kwallet_get', 'kwallet_put']

import subprocess


def kwallet_available():
    """
    Return True if kwalletcli can be run, False otherwise
    """
    try:
        p = subprocess.Popen(["kwalletcli", "-qV"])
    except Exception:
        return False
    p.communicate()
    if p.returncode == 0:
        return True
    return False


def kwallet_get(folder, entry):
    """
    Retrieve a passphrase from the KDE Wallet via kwalletcli

    Arguments:
    • folder: The top-level category to use (normally the programme name)
    • entry: The key of the entry to retrieve

    Returns the passphrase, False if it cannot be found,
    or None if an error occured.
    """
    p = subprocess.Popen(["kwalletcli", "-q", "-f", folder.encode('utf-8'),
     "-e", entry.encode('utf-8')], stdout=subprocess.PIPE)
    pw = p.communicate()[0]
    if p.returncode == 0:
        return pw
    if p.returncode == 1 or p.returncode == 4:
        # ENOENT
        return False
    # error
    return None


def kwallet_put(folder, entry, passphrase):
    """
    Store a passphrase into the KDE Wallet via kwalletcli

    Arguments:
    • folder: The top-level category to use (normally the programme name)
    • entry: The key of the entry to store
    • passphrase: The value to store

    Returns True on success, False otherwise.
    """
    p = subprocess.Popen(["kwalletcli", "-q", "-f", folder.encode('utf-8'),
     "-e", entry.encode('utf-8'), "-P"], stdin=subprocess.PIPE)
    p.communicate(passphrase.encode('utf-8'))
    if p.returncode == 0:
        return True
    return False
