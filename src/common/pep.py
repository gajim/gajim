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

ACTIVITIES = {
        'doing_chores': {'category':            _('Doing Chores'),
                'buying_groceries':                     _('Buying Groceries'),
                'cleaning':                             _('Cleaning'),
                'cooking':                              _('Cooking'),
                'doing_maintenance':                    _('Doing Maintenance'),
                'doing_the_dishes':                     _('Doing the Dishes'),
                'doing_the_laundry':                    _('Doing the Laundry'),
                'gardening':                            _('Gardening'),
                'running_an_errand':                    _('Running an Errand'),
                'walking_the_dog':                      _('Walking the Dog')},
        'drinking': {'category':                _('Drinking'),
                'having_a_beer':                         _('Having a Beer'),
                'having_coffee':                        _('Having Coffee'),
                'having_tea':                           _('Having Tea')},
        'eating': {'category':                  _('Eating'),
                'having_a_snack':                       _('Having a Snack'),
                'having_breakfast':                     _('Having Breakfast'),
                'having_dinner':                        _('Having Dinner'),
                'having_lunch':                         _('Having Lunch')},
        'exercising': {'category':              _('Exercising'),
                'cycling':                              _('Cycling'),
                'dancing':                              _('Dancing'),
                'hiking':                               _('Hiking'),
                'jogging':                              _('Jogging'),
                'playing_sports':                       _('Playing Sports'),
                'running':                              _('Running'),
                'skiing':                               _('Skiing'),
                'swimming':                             _('Swimming'),
                'working_out':                          _('Working out')},
        'grooming': {'category':                _('Grooming'),
                'at_the_spa':                           _('At the Spa'),
                'brushing_teeth':                       _('Brushing Teeth'),
                'getting_a_haircut':                    _('Getting a Haircut'),
                'shaving':                              _('Shaving'),
                'taking_a_bath':                        _('Taking a Bath'),
                'taking_a_shower':                      _('Taking a Shower')},
        'having_appointment': {'category':      _('Having an Appointment')},
        'inactive': {'category':                _('Inactive'),
                'day_off':                              _('Day Off'),
                'hanging_out':                          _('Hanging out'),
                'hiding':                               _('Hiding'),
                'on_vacation':                          _('On Vacation'),
                'praying':                              _('Praying'),
                'scheduled_holiday':                    _('Scheduled Holiday'),
                'sleeping':                             _('Sleeping'),
                'thinking':                             _('Thinking')},
        'relaxing': {'category':                _('Relaxing'),
                'fishing':                               _('Fishing'),
                'gaming':                                _('Gaming'),
                'going_out':                             _('Going out'),
                'partying':                              _('Partying'),
                'reading':                               _('Reading'),
                'rehearsing':                            _('Rehearsing'),
                'shopping':                              _('Shopping'),
                'smoking':                               _('Smoking'),
                'socializing':                           _('Socializing'),
                'sunbathing':                            _('Sunbathing'),
                'watching_tv':                           _('Watching TV'),
                'watching_a_movie':                      _('Watching a Movie')},
        'talking': {'category':                  _('Talking'),
                'in_real_life':                          _('In Real Life'),
                'on_the_phone':                          _('On the Phone'),
                'on_video_phone':                        _('On Video Phone')},
        'traveling': {'category':                _('Traveling'),
                'commuting':                             _('Commuting'),
                'cycling':                               _('Cycling'),
                'driving':                               _('Driving'),
                'in_a_car':                              _('In a Car'),
                'on_a_bus':                              _('On a Bus'),
                'on_a_plane':                            _('On a Plane'),
                'on_a_train':                            _('On a Train'),
                'on_a_trip':                             _('On a Trip'),
                'walking':                               _('Walking')},
        'working': {'category':                  _('Working'),
                'coding':                                _('Coding'),
                'in_a_meeting':                          _('In a Meeting'),
                'studying':                              _('Studying'),
                'writing':                               _('Writing')}}

TUNE_DATA = ['artist', 'title', 'source', 'track', 'length']

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
        'uri':          _('uri')}

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GdkPixbuf

import logging
log = logging.getLogger('gajim.c.pep')

from common import helpers
import nbxmpp
from common import gajim


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
        if jid == gajim.get_jid_from_account(account):
            self._update_account(account)

    def _extract_info(self, items):
        '''To be implemented by subclasses'''
        raise NotImplementedError

    def _update_contacts(self, jid, account):
        for contact in gajim.contacts.get_contacts(account, jid):
            if self._retracted:
                if self.type_ in contact.pep:
                    del contact.pep[self.type_]
            else:
                contact.pep[self.type_] = self

    def _update_account(self, account):
        acc = gajim.connections[account]
        if self._retracted:
            if self.type_ in acc.pep:
                del acc.pep[self.type_]
        else:
            acc.pep[self.type_] = self

    def asMarkupText(self):
        '''SHOULD be implemented by subclasses'''
        return ''


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


class UserTunePEP(AbstractPEP):
    '''XEP-0118: User Tune'''

    type_ = 'tune'
    namespace = nbxmpp.NS_TUNE

    def _extract_info(self, items):
        tune_dict = {}

        for item in items.getTags('item'):
            tune_tag = item.getTag('tune')
            if tune_tag:
                for child in tune_tag.getChildren():
                    name = child.getName().strip()
                    data = child.getData().strip()
                    if child.getName() in TUNE_DATA:
                        tune_dict[name] = data

        retracted = items.getTag('retract') or not ('artist' in tune_dict or
            'title' in tune_dict)
        return (tune_dict, retracted)

    def asMarkupText(self):
        assert not self._retracted
        tune = self._pep_specific_data

        artist = tune.get('artist', _('Unknown Artist'))
        artist = GLib.markup_escape_text(artist)

        title = tune.get('title', _('Unknown Title'))
        title = GLib.markup_escape_text(title)

        source = tune.get('source', _('Unknown Source'))
        source = GLib.markup_escape_text(source)

        tune_string =  _('<b>"%(title)s"</b> by <i>%(artist)s</i>\n'
                'from <i>%(source)s</i>') % {'title': title,
                'artist': artist, 'source': source}
        return tune_string


class UserActivityPEP(AbstractPEP):
    '''XEP-0108: User Activity'''

    type_ = 'activity'
    namespace = nbxmpp.NS_ACTIVITY

    def _extract_info(self, items):
        activity_dict = {}

        for item in items.getTags('item'):
            activity_tag = item.getTag('activity')
            if activity_tag:
                for child in activity_tag.getChildren():
                    name = child.getName().strip()
                    data = child.getData().strip()
                    if name == 'text':
                        activity_dict['text'] = data
                    else:
                        activity_dict['activity'] = name
                        for subactivity in child.getChildren():
                            subactivity_name = subactivity.getName().strip()
                            activity_dict['subactivity'] = subactivity_name

        retracted = items.getTag('retract') or not 'activity' in activity_dict
        return (activity_dict, retracted)

    def asMarkupText(self):
        assert not self._retracted
        pep = self._pep_specific_data
        activity = pep['activity']
        subactivity = pep['subactivity'] if 'subactivity' in pep else None
        text = pep['text'] if 'text' in pep else None

        if activity in ACTIVITIES:
            # Translate standard activities
            if subactivity in ACTIVITIES[activity]:
                subactivity = ACTIVITIES[activity][subactivity]
            activity = ACTIVITIES[activity]['category']

        markuptext = '<b>' + GLib.markup_escape_text(activity)
        if subactivity:
            markuptext += ': ' + GLib.markup_escape_text(subactivity)
        markuptext += '</b>'
        if text:
            markuptext += ' (%s)' % GLib.markup_escape_text(text)
        return markuptext


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
        for contact in gajim.contacts.get_contacts(account, jid):
            contact.contact_name = nick

    def _update_account(self, account):
        if self._retracted:
            gajim.nicks[account] = gajim.config.get_per('accounts', account, 'name')
        else:
            gajim.nicks[account] = self._pep_specific_data


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
        con = gajim.connections[account].location_info = \
                self._pep_specific_data

    def asMarkupText(self):
        assert not self._retracted
        location = self._pep_specific_data
        location_string = ''

        for entry in location.keys():
            text = location[entry]
            text = GLib.markup_escape_text(text)
            # Translate standart location tag
            tag = LOCATION_DATA.get(entry, entry)
            location_string += '\n<b>%(tag)s</b>: %(text)s' % \
                    {'tag': tag.capitalize(), 'text': text}

        return location_string.strip()


SUPPORTED_PERSONAL_USER_EVENTS = [UserMoodPEP, UserTunePEP, UserActivityPEP,
    UserNicknamePEP, UserLocationPEP]
