# Copyright (C) 2007 Piotr Gaczkowski <doomhammerng AT gmail.com>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jean-Marie Traissard <jim AT lapin.org>
#                    Jonathan Schleifer <js-common.gajim AT webkeks.org>
#                    Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
log = logging.getLogger('gajim.c.pep')

from gajim.common import app


class AbstractPEP:

    type_ = ''
    namespace = ''

    @classmethod
    def get_tag_as_PEP(cls, jid, account, event_tag):
        items = event_tag.getTag('items', {'node': cls.namespace})
        if items:
            log.debug('Received PEP "user %s" from %s', cls.type_, jid)
            return cls(jid, account, items)
        return None

    def __init__(self, jid, account, items):
        self.data, self._retracted = self._extract_info(items)

        self._update_contacts(jid, account)
        if jid == app.get_jid_from_account(account):
            self._update_account(account)
        self._on_receive(jid, account)

    def _extract_info(self, items):
        '''To be implemented by subclasses'''
        raise NotImplementedError

    def _update_contacts(self, jid, account):
        for contact in app.contacts.get_contacts(account, jid):
            if self._retracted:
                if self.type_ in contact.pep:
                    del contact.pep[self.type_]
            else:
                contact.pep[self.type_] = self

    def _update_account(self, account):
        acc = app.connections[account]
        if self._retracted:
            if self.type_ in acc.pep:
                del acc.pep[self.type_]
        else:
            acc.pep[self.type_] = self

    def as_markup_text(self):
        '''SHOULD be implemented by subclasses'''
        return ''

    def _on_receive(self, jid, account):
        '''SHOULD be implemented by subclasses'''
        pass


SUPPORTED_PERSONAL_USER_EVENTS = []
