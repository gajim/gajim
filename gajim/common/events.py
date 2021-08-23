# Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import time


class Event:
    def __init__(self, time_=None, show_in_roster=False, show_in_systray=True):
        """
        type_ in chat, normal, file-request, file-error, file-completed,
        file-request-error, file-send-error, file-stopped, gc_msg, pm,
        printed_chat, printed_gc_msg, printed_marked_gc_msg, printed_pm,
        gc-invitation, subscription_request, jingle-incoming

        parameters is (per type_):
            chat, normal, pm: [message, subject, kind, time, encrypted,
            resource, msg_log_id]
                    where kind in error, incoming
            file-*: file_props
            printed_chat: [message, subject, control, msg_log_id]
            printed_*: None
                    messages that are already printed in chat, but not read
            gc-invitation: [room_jid, reason, password, jid_from]
            subscription_request: [text, nick]
            jingle-incoming: (fulljid, sessionid, content_types)
        """
        if time_:
            self.time_ = time_
        else:
            self.time_ = time.time()
        self.show_in_roster = show_in_roster
        self.show_in_systray = show_in_systray
        # Set when adding the event
        self.jid = None
        self.account = None


class ChatEvent(Event):

    type_ = 'chat'

    def __init__(self,
                 message,
                 subject,
                 kind,
                 time_,
                 resource,
                 msg_log_id,
                 correct_id=None,
                 message_id=None,
                 session=None,
                 displaymarking=None,
                 sent_forwarded=False,
                 show_in_roster=False,
                 show_in_systray=True,
                 additional_data=None):
        Event.__init__(self,
                       time_,
                       show_in_roster=show_in_roster,
                       show_in_systray=show_in_systray)
        self.message = message
        self.subject = subject
        self.kind = kind
        self.time = time_
        self.resource = resource
        self.msg_log_id = msg_log_id
        self.message_id = message_id
        self.correct_id = correct_id
        self.session = session
        self.displaymarking = displaymarking
        self.sent_forwarded = sent_forwarded
        if additional_data is None:
            from gajim.common.helpers import AdditionalDataDict
        self.additional_data = AdditionalDataDict()


class PmEvent(ChatEvent):

    type_ = 'pm'


class PrintedChatEvent(Event):

    type_ = 'printed_chat'

    def __init__(self,
                 message,
                 subject,
                 control,
                 msg_log_id,
                 time_=None,
                 message_id=None,
                 stanza_id=None,
                 show_in_roster=False,
                 show_in_systray=True):
        Event.__init__(self,
                       time_,
                       show_in_roster=show_in_roster,
                       show_in_systray=show_in_systray)
        self.message = message
        self.subject = subject
        self.control = control
        self.msg_log_id = msg_log_id
        self.message_id = message_id
        self.stanza_id = stanza_id


class PrintedGcMsgEvent(PrintedChatEvent):

    type_ = 'printed_gc_msg'


class PrintedMarkedGcMsgEvent(PrintedChatEvent):

    type_ = 'printed_marked_gc_msg'


class PrintedPmEvent(PrintedChatEvent):

    type_ = 'printed_pm'


class SubscriptionRequestEvent(Event):

    type_ = 'subscription_request'

    def __init__(self,
                 text,
                 nick,
                 time_=None,
                 show_in_roster=False,
                 show_in_systray=True):
        Event.__init__(self,
                       time_,
                       show_in_roster=show_in_roster,
                       show_in_systray=show_in_systray)
        self.text = text
        self.nick = nick


class GcInvitationEvent(Event):

    type_ = 'gc-invitation'

    def __init__(self, event):
        Event.__init__(self,
                       None,
                       show_in_roster=False,
                       show_in_systray=True)
        for key, value in vars(event).items():
            setattr(self, key, value)


class FileRequestEvent(Event):

    type_ = 'file-request'

    def __init__(self,
                 file_props,
                 time_=None,
                 show_in_roster=False,
                 show_in_systray=True):
        Event.__init__(self,
                       time_,
                       show_in_roster=show_in_roster,
                       show_in_systray=show_in_systray)
        self.file_props = file_props


class FileSendErrorEvent(FileRequestEvent):

    type_ = 'file-send-error'


class FileErrorEvent(FileRequestEvent):

    type_ = 'file-error'


class FileRequestErrorEvent(FileRequestEvent):

    type_ = 'file-request-error'


class FileCompletedEvent(FileRequestEvent):

    type_ = 'file-completed'


class FileStoppedEvent(FileRequestEvent):

    type_ = 'file-stopped'


class FileHashErrorEvent(FileRequestEvent):

    type_ = 'file-hash-error'


class JingleIncomingEvent(Event):

    type_ = 'jingle-incoming'

    def __init__(self,
                 peerjid,
                 sid,
                 content_types,
                 time_=None,
                 show_in_roster=False,
                 show_in_systray=True):
        Event.__init__(self,
                       time_,
                       show_in_roster=show_in_roster,
                       show_in_systray=show_in_systray)
        self.peerjid = peerjid
        self.sid = sid
        self.content_types = content_types


class Events:
    def __init__(self):
        self._events = {}  # list of events {acct: {jid1: [E1, E2]}, }
        self._event_added_listeners = []
        self._event_removed_listeners = []

    def event_added_subscribe(self, listener):
        """
        Add a listener when an event is added to the queue
        """
        if listener not in self._event_added_listeners:
            self._event_added_listeners.append(listener)

    def event_added_unsubscribe(self, listener):
        """
        Remove a listener when an event is added to the queue
        """
        if listener in self._event_added_listeners:
            self._event_added_listeners.remove(listener)

    def event_removed_subscribe(self, listener):
        """
        Add a listener when an event is removed from the queue
        """
        if listener not in self._event_removed_listeners:
            self._event_removed_listeners.append(listener)

    def event_removed_unsubscribe(self, listener):
        """
        Remove a listener when an event is removed from the queue
        """
        if listener in self._event_removed_listeners:
            self._event_removed_listeners.remove(listener)

    def fire_event_added(self, event):
        for listener in self._event_added_listeners:
            listener(event)

    def fire_event_removed(self, event_list):
        for listener in self._event_removed_listeners:
            listener(event_list)

    def add_account(self, account):
        self._events[account] = {}

    def get_accounts(self):
        return self._events.keys()

    def remove_account(self, account):
        del self._events[account]

    def add_event(self, account, jid, event):
        if account not in self._events:
            self._events[account] = {jid: [event]}
        elif jid not in self._events[account]:
            self._events[account][jid] = [event]
        else:
            self._events[account][jid].append(event)

        event.jid = jid
        event.account = account

        self.fire_event_added(event)

    def remove_events(self, account, jid, event=None, types=None):
        """
        If event is not specified, remove all events from this jid, optionally
        only from given type return True if no such event found
        """
        if types is None:
            types = []
        if account not in self._events:
            return True
        if jid not in self._events[account]:
            return True

        if event:  # remove only one event
            if event in self._events[account][jid]:
                if len(self._events[account][jid]) == 1:
                    del self._events[account][jid]
                else:
                    self._events[account][jid].remove(event)
                self.fire_event_removed([event])
                return False
            return True
        if types:
            new_list = []  # list of events to keep
            removed_list = []  # list of removed events
            for ev in self._events[account][jid]:
                if ev.type_ not in types:
                    new_list.append(ev)
                else:
                    removed_list.append(ev)
            if len(new_list) == len(self._events[account][jid]):
                return True

            if new_list:
                self._events[account][jid] = new_list
            else:
                del self._events[account][jid]
            self.fire_event_removed(removed_list)
            return False

        # No event nor type given, remove them all
        removed_list = self._events[account][jid]
        del self._events[account][jid]
        self.fire_event_removed(removed_list)

    def change_jid(self, account, old_jid, new_jid):
        if account not in self._events:
            return
        if old_jid not in self._events[account]:
            return
        if new_jid in self._events[account]:
            self._events[account][new_jid] += self._events[account][old_jid]
        else:
            self._events[account][new_jid] = self._events[account][old_jid]
        del self._events[account][old_jid]

    def get_nb_events(self, types=None, account=None):
        if types is None:
            types = []
        return self._get_nb_events(types=types, account=account)

    def get_events(self, account, jid=None, types=None):
        """
        Return all events from the given account of the form:
        {jid1: [], jid2: []}.
        If jid is given, returns all events from the given jid in a list:
        []
        optionally only from given type
        """
        if types is None:
            types = []
        if account not in self._events:
            return []

        if not jid:
            events_list = {}
            for jid_ in self._events[account]:
                events = []
                for ev in self._events[account][jid_]:
                    if not types or ev.type_ in types:
                        events.append(ev)
                if events:
                    events_list[jid_] = events
            return events_list

        if jid not in self._events[account]:
            return []

        events_list = []
        for ev in self._events[account][jid]:
            if not types or ev.type_ in types:
                events_list.append(ev)
        return events_list

    def get_all_events(self, types=None):
        accounts = self._events.keys()
        events = []
        for account in accounts:
            for jid in self._events[account]:
                for event in self._events[account][jid]:
                    if types is None or event.type_ in types:
                        events.append(event)
        return events

    def get_first_event(self, account=None, jid=None, type_=None):
        """
        Return the first event of type type_ if given
        """
        if not account:
            return self._get_first_event_with_attribute(self._events)

        events_list = self.get_events(account, jid, type_)
        # be sure it's bigger than latest event
        first_event_time = time.time() + 1
        first_event = None
        for event in events_list:
            if event.time_ < first_event_time:
                first_event_time = event.time_
                first_event = event
        return first_event

    def _get_nb_events(self, account=None, jid=None, attribute=None,
                       types=None):
        """
        Return the number of pending events
        """
        if types is None:
            types = []
        nb = 0
        if account:
            accounts = [account]
        else:
            accounts = self._events.keys()
        for acct in accounts:
            if acct not in self._events:
                continue
            if jid:
                jids = [jid]
            else:
                jids = self._events[acct].keys()
            for j in jids:
                if j not in self._events[acct]:
                    continue
                for event in self._events[acct][j]:
                    if types and event.type_ not in types:
                        continue
                    if (not attribute or
                            attribute == 'systray' and event.show_in_systray or
                            attribute == 'roster' and event.show_in_roster):
                        nb += 1
        return nb

    def _get_some_events(self, attribute):
        """
        Attribute in systray, roster
        """
        events = {}
        for account, acc_events in self._events.items():
            events[account] = {}
            for jid in acc_events:
                events[account][jid] = []

                for event in acc_events[jid]:
                    if attribute == 'systray' and event.show_in_systray or \
                    attribute == 'roster' and event.show_in_roster:
                        events[account][jid].append(event)
                if not events[account][jid]:
                    del events[account][jid]
            if not events[account]:
                del events[account]
        return events

    @staticmethod
    def _get_first_event_with_attribute(events):
        """
        Get the first event.
        events is in the form {account1: {jid1: [ev1, ev2], },. }
        """
        # be sure it's bigger than latest event
        first_event_time = time.time() + 1
        first_account = None
        first_jid = None
        first_event = None
        for account in events:
            for jid in events[account]:
                for event in events[account][jid]:
                    if event.time_ < first_event_time:
                        first_event_time = event.time_
                        first_account = account
                        first_jid = jid
                        first_event = event
        return first_account, first_jid, first_event

    def get_nb_systray_events(self, types=None):
        """
        Return the number of events displayed in roster
        """
        if types is None:
            types = []
        return self._get_nb_events(attribute='systray', types=types)

    def get_systray_events(self):
        """
        Return all events that must be displayed in systray:
                {account1: {jid1: [ev1, ev2], },. }
        """
        return self._get_some_events('systray')

    def get_first_systray_event(self):
        events = self.get_systray_events()
        return self._get_first_event_with_attribute(events)

    def get_nb_roster_events(self, account=None, jid=None, types=None):
        """
        Return the number of events displayed in roster
        """
        if types is None:
            types = []
        return self._get_nb_events(attribute='roster',
                                   account=account,
                                   jid=jid,
                                   types=types)

    def get_roster_events(self):
        """
        Return all events that must be displayed in roster:
                {account1: {jid1: [ev1, ev2], },. }
        """
        return self._get_some_events('roster')
