# -*- coding:utf-8 -*-
## src/common/pep.py
##
## Copyright (C) 2007 Piotr Gaczkowski <doomhammerng AT gmail.com>
## Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jean-Marie Traissard <jim AT lapin.org>
##                    Jonathan Schleifer <js-common.gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
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

MOODS = {
        'afraid':                       _('Afraid'),
        'amazed':                       _('Amazed'),
        'amorous':                      _('Amorous'),
        'angry':                                _('Angry'),
        'annoyed':                      _('Annoyed'),
        'anxious':                      _('Anxious'),
        'aroused':                      _('Aroused'),
        'ashamed':                      _('Ashamed'),
        'bored':                                _('Bored'),
        'brave':                                _('Brave'),
        'calm':                         _('Calm'),
        'cautious':                     _('Cautious'),
        'cold':                         _('Cold'),
        'confident':            _('Confident'),
        'confused':                     _('Confused'),
        'contemplative':        _('Contemplative'),
        'contented':            _('Contented'),
        'cranky':                       _('Cranky'),
        'crazy':                                _('Crazy'),
        'creative':                     _('Creative'),
        'curious':                      _('Curious'),
        'dejected':                     _('Dejected'),
        'depressed':            _('Depressed'),
        'disappointed': _('Disappointed'),
        'disgusted':            _('Disgusted'),
        'dismayed':                     _('Dismayed'),
        'distracted':           _('Distracted'),
        'embarrassed':          _('Embarrassed'),
        'envious':                      _('Envious'),
        'excited':                      _('Excited'),
        'flirtatious':          _('Flirtatious'),
        'frustrated':           _('Frustrated'),
        'grateful':                     _('Grateful'),
        'grieving':                     _('Grieving'),
        'grumpy':                       _('Grumpy'),
        'guilty':                       _('Guilty'),
        'happy':                                _('Happy'),
        'hopeful':                      _('Hopeful'),
        'hot':                          _('Hot'),
        'humbled':                      _('Humbled'),
        'humiliated':           _('Humiliated'),
        'hungry':                       _('Hungry'),
        'hurt':                         _('Hurt'),
        'impressed':            _('Impressed'),
        'in_awe':                       _('In Awe'),
        'in_love':                      _('In Love'),
        'indignant':            _('Indignant'),
        'interested':           _('Interested'),
        'intoxicated':          _('Intoxicated'),
        'invincible':           _('Invincible'),
        'jealous':                      _('Jealous'),
        'lonely':                       _('Lonely'),
        'lost':                         _('Lost'),
        'lucky':                                _('Lucky'),
        'mean':                         _('Mean'),
        'moody':                                _('Moody'),
        'nervous':                      _('Nervous'),
        'neutral':                      _('Neutral'),
        'offended':                     _('Offended'),
        'outraged':                     _('Outraged'),
        'playful':                      _('Playful'),
        'proud':                                _('Proud'),
        'relaxed':                      _('Relaxed'),
        'relieved':                     _('Relieved'),
        'remorseful':           _('Remorseful'),
        'restless':                     _('Restless'),
        'sad':                          _('Sad'),
        'sarcastic':            _('Sarcastic'),
        'satisfied':            _('Satisfied'),
        'serious':                      _('Serious'),
        'shocked':                      _('Shocked'),
        'shy':                          _('Shy'),
        'sick':                         _('Sick'),
        'sleepy':                       _('Sleepy'),
        'spontaneous':          _('Spontaneous'),
        'stressed':                     _('Stressed'),
        'strong':                       _('Strong'),
        'surprised':            _('Surprised'),
        'thankful':                     _('Thankful'),
        'thirsty':                      _('Thirsty'),
        'tired':                                _('Tired'),
        'undefined':            _('Undefined'),
        'weak':                         _('Weak'),
        'worried':                      _('Worried')}

LOCATION_DATA = {
        'accuracy':     _('accuracy'),
        'alt':          _('alt'),
        'area':         _('area'),
        'bearing':      _('bearing'),
        'building':     _('building'),
        'country':      _('country'),
        'countrycode':  _('countrycode'),
        'datum':        _('datum'),
        'description':  _('description'),
        'error':        _('error'),
        'floor':        _('floor'),
        'lat':          _('lat'),
        'locality':     _('locality'),
        'lon':          _('lon'),
        'postalcode':   _('postalcode'),
        'region':       _('region'),
        'room':         _('room'),
        'speed':        _('speed'),
        'street':       _('street'),
        'text':         _('text'),
        'timestamp':    _('timestamp'),
        'uri':          _('URI')}

from gi.repository import GLib

import logging
log = logging.getLogger('gajim.c.pep')

import nbxmpp
from gajim.common import app


class AbstractPEP(object):

    type_ = ''
    namespace = ''

    @classmethod
    def get_tag_as_PEP(cls, jid, account, event_tag):
        items = event_tag.getTag('items', {'node': cls.namespace})
        if items:
            log.debug("Received PEP 'user %s' from %s" % (cls.type_, jid))
            return cls(jid, account, items)
        else:
            return None

    def __init__(self, jid, account, items):
        self._pep_specific_data, self._retracted = self._extract_info(items)

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

    def asMarkupText(self):
        '''SHOULD be implemented by subclasses'''
        return ''

    def _on_receive(self, jid, account):
        '''SHOULD be implemented by subclasses'''
        pass


class UserMoodPEP(AbstractPEP):
    '''XEP-0107: User Mood'''

    type_ = 'mood'
    namespace = nbxmpp.NS_MOOD

    def _extract_info(self, items):
        mood_dict = {}

        for item in items.getTags('item'):
            mood_tag = item.getTag('mood')
            if mood_tag:
                for child in mood_tag.getChildren():
                    name = child.getName().strip()
                    if name == 'text':
                        mood_dict['text'] = child.getData()
                    else:
                        mood_dict['mood'] = name

        retracted = items.getTag('retract') or not 'mood' in mood_dict
        return (mood_dict, retracted)

    def asMarkupText(self):
        assert not self._retracted
        untranslated_mood = self._pep_specific_data['mood']
        mood = self._translate_mood(untranslated_mood)
        markuptext = '<b>%s</b>' % GLib.markup_escape_text(mood)
        if 'text' in self._pep_specific_data:
            text = self._pep_specific_data['text']
            markuptext += ' (%s)' % GLib.markup_escape_text(text)
        return markuptext

    def _translate_mood(self, mood):
        if mood in MOODS:
            return MOODS[mood]
        else:
            return mood


class UserNicknamePEP(AbstractPEP):
    '''XEP-0172: User Nickname'''

    type_ = 'nickname'
    namespace = nbxmpp.NS_NICK

    def _extract_info(self, items):
        nick = ''
        for item in items.getTags('item'):
            child = item.getTag('nick')
            if child:
                nick = child.getData()
                break

        retracted = items.getTag('retract') or not nick
        return (nick, retracted)

    def _update_contacts(self, jid, account):
        nick = '' if self._retracted else self._pep_specific_data
        for contact in app.contacts.get_contacts(account, jid):
            contact.contact_name = nick

    def _update_account(self, account):
        if self._retracted:
            app.nicks[account] = app.config.get_per('accounts', account, 'name')
        else:
            app.nicks[account] = self._pep_specific_data


class UserLocationPEP(AbstractPEP):
    '''XEP-0080: User Location'''

    type_ = 'location'
    namespace = nbxmpp.NS_LOCATION

    def _extract_info(self, items):
        location_dict = {}

        for item in items.getTags('item'):
            location_tag = item.getTag('geoloc')
            if location_tag:
                for child in location_tag.getChildren():
                    name = child.getName().strip()
                    data = child.getData().strip()
                    if child.getName() in LOCATION_DATA:
                        location_dict[name] = data

        retracted = items.getTag('retract') or not location_dict
        return (location_dict, retracted)

    def _update_account(self, account):
        AbstractPEP._update_account(self, account)
        con = app.connections[account].location_info = \
                self._pep_specific_data

    def asMarkupText(self):
        assert not self._retracted
        location = self._pep_specific_data
        location_string = ''

        for entry in location.keys():
            text = location[entry]
            text = GLib.markup_escape_text(text)
            # Translate standard location tag
            tag = LOCATION_DATA.get(entry, entry)
            location_string += '\n<b>%(tag)s</b>: %(text)s' % \
                    {'tag': tag.capitalize(), 'text': text}

        return location_string.strip()


class AvatarNotificationPEP(AbstractPEP):
    '''XEP-0084: Avatars'''

    type_ = 'avatar-notification'
    namespace = 'urn:xmpp:avatar:metadata'

    def _extract_info(self, items):
        self.avatar = None
        for item in items.getTags('item'):
            metadata = item.getTag('metadata')
            if metadata is None:
                app.log('c.m.user_avatar').warning(
                    'Invalid avatar stanza:\n%s', items)
                break
            info = item.getTag('metadata').getTag('info')
            if info is not None:
                self.avatar = info.getAttrs()
            break

        return (None, False)

    def _on_receive(self, jid, account):
        con = app.connections[account]
        if self.avatar is None:
            # Remove avatar
            app.log('c.m.user_avatar').info('Remove: %s', jid)
            app.contacts.set_avatar(account, jid, None)
            own_jid = con.get_own_jid().getStripped()
            app.logger.set_avatar_sha(own_jid, jid, None)
            app.interface.update_avatar(account, jid)
        else:
            sha = app.contacts.get_avatar_sha(account, jid)
            app.log('c.m.user_avatar').info(
                'Update: %s %s', jid, self.avatar['id'])
            if sha == self.avatar['id']:
                app.log('c.m.user_avatar').info(
                    'Avatar already known: %s %s',
                    jid, self.avatar['id'])
                return
            con.get_module('UserAvatar').get_pubsub_avatar(
                jid, self.avatar['id'])


SUPPORTED_PERSONAL_USER_EVENTS = [
    UserMoodPEP,
    UserNicknamePEP, UserLocationPEP, AvatarNotificationPEP]
