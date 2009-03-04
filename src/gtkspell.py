## src/gtkspell.py
##
## (C) 2008 Thorsten P. 'dGhvcnN0ZW5wIEFUIHltYWlsIGNvbQ==\n'.decode("base64")
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

import ctypes
import ctypes.util

import gtk


gboolean = ctypes.c_int
gchar_p = ctypes.c_char_p
gerror_p = ctypes.c_void_p
gobject_p = ctypes.c_void_p
gtkspell_p = ctypes.c_void_p
gtktextview_p = ctypes.c_void_p


class PyGObject(ctypes.Structure):
    _fields_ = [
            ("PyObject_HEAD", ctypes.c_byte * object.__basicsize__),
            ("obj", gobject_p)
    ]


libgtkspell_path = ctypes.util.find_library("gtkspell")
if libgtkspell_path == None:
    raise ImportError("libgtkspell not found")
libgtkspell = ctypes.cdll.LoadLibrary(libgtkspell_path)
libgtkspell.gtkspell_new_attach.restype = gtkspell_p
libgtkspell.gtkspell_new_attach.argtypes = [gtktextview_p, gchar_p, gerror_p]
libgtkspell.gtkspell_set_language.restype = gboolean
libgtkspell.gtkspell_set_language.argtypes = [gtkspell_p, gchar_p, gerror_p]
libgtkspell.gtkspell_recheck_all.argtypes = [gtkspell_p]
libgtkspell.gtkspell_get_from_text_view.restype = gtkspell_p
libgtkspell.gtkspell_get_from_text_view.argtypes = [gtktextview_p]
libgtkspell.gtkspell_detach.argtypes = [gtkspell_p]


def ensure_attached(func):
    def f(self, *args, **kwargs):
        if self.spell:
            func(self, *args, **kwargs)
        else:
            raise RuntimeError("Spell object is already detached")
    return f


class Spell(object):

    def __init__(self, textview, language=None, create=True):
        if not isinstance(textview, gtk.TextView):
            raise TypeError("Textview must be derived from gtk.TextView")
        tv = PyGObject.from_address(id(textview)).obj
        spell = libgtkspell.gtkspell_get_from_text_view(tv)
        if create:
            if spell:
                raise RuntimeError("Textview has already a Spell obj attached")
            self.spell = libgtkspell.gtkspell_new_attach(tv, language, None)
            if not self.spell:
                raise OSError("Unable to attach spell object. "
                              "Language: '%s'" % str(language))
        else:
            if spell:
                self.spell = spell
            else:
                raise RuntimeError("Textview has no Spell object attached")

    @ensure_attached
    def set_language(self, language):
        if libgtkspell.gtkspell_set_language(self.spell, language, None) == 0:
            raise OSError("Unable to set language '%s'" % str(language))

    @ensure_attached
    def recheck_all(self):
        libgtkspell.gtkspell_recheck_all(self.spell)

    @ensure_attached
    def detach(self):
        libgtkspell.gtkspell_detach(self.spell)
        self.spell = None


def get_from_text_view(textview):
    return Spell(textview, create=False)

