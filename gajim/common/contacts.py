# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Travis Shirk <travis AT pobox.com>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
#                         Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Tomasz Melcer <liori AT exroot.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
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

from functools import partial

try:
    from gajim.common import app
    from gajim.common.i18n import _
    from gajim.common.account import Account
    from gajim import common
    from gajim.common.const import Chatstate
except ImportError as e:
    if __name__ != "__main__":
        raise ImportError(str(e))


class ContactSettings:
    def __init__(self, account, jid):
        self.get = partial(app.settings.get_contact_setting, account, jid)
        self.set = partial(app.settings.set_contact_setting, account, jid)


class GroupChatSettings:
    def __init__(self, account, jid):
        self.get = partial(app.settings.get_group_chat_setting, account, jid)
        self.set = partial(app.settings.set_group_chat_setting, account, jid)


class XMPPEntity:
    """
    Base representation of entities in XMPP
    """

    def __init__(self, jid, account, resource):
        self.jid = jid
        self.resource = resource
        self.account = account

class CommonContact(XMPPEntity):

    def __init__(self, jid, account, resource, show, presence, status, name,
                 chatstate):

        XMPPEntity.__init__(self, jid, account, resource)

        self._show = show
        self._presence = presence
        self.status = status
        self.name = name

        # this is contact's chatstate
        self._chatstate = chatstate

        self._is_pm_contact = False

    @property
    def show(self):
        return self._show

    @show.setter
    def show(self, value):
        self._show = value

    @property
    def presence(self):
        return self._presence

    @presence.setter
    def presence(self, value):
        self._presence = value

    @property
    def is_available(self):
        return self._presence.is_available

    @property
    def chatstate_enum(self):
        return self._chatstate

    @property
    def chatstate(self):
        if self._chatstate is None:
            return
        return str(self._chatstate)

    @chatstate.setter
    def chatstate(self, value):
        if value is None:
            self._chatstate = value
        else:
            self._chatstate = Chatstate[value.upper()]

    @property
    def is_gc_contact(self):
        return isinstance(self, GC_Contact)

    @property
    def is_pm_contact(self):
        return self._is_pm_contact

    @property
    def is_groupchat(self):
        return False

    def get_full_jid(self):
        raise NotImplementedError

    def get_shown_name(self):
        raise NotImplementedError

    def supports(self, requested_feature):
        """
        Return True if the contact has advertised to support the feature
        identified by the given namespace. False otherwise.
        """
        if self.show == 'offline':
            # Unfortunately, if all resources are offline, the contact
            # includes the last resource that was online. Check for its
            # show, so we can be sure it's existent. Otherwise, we still
            # return caps for a contact that has no resources left.
            return False

        disco_info = app.storage.cache.get_last_disco_info(self.get_full_jid())
        if disco_info is None:
            return False

        return disco_info.supports(requested_feature)

    @property
    def uses_phone(self):
        disco_info = app.storage.cache.get_last_disco_info(self.get_full_jid())
        if disco_info is None:
            return False

        return disco_info.has_category('phone')


class Contact(CommonContact):
    """
    Information concerning a contact
    """
    def __init__(self, jid, account, name='', groups=None, show='', status='',
    sub='', ask='', resource='', priority=0,
    chatstate=None, idle_time=None, avatar_sha=None, groupchat=False,
    is_pm_contact=False):
        if not isinstance(jid, str):
            print('no str')
        if groups is None:
            groups = []

        CommonContact.__init__(self, jid, account, resource, show,
                               None, status, name, chatstate)

        self.contact_name = '' # nick chosen by contact
        self.groups = [i if i else _('General') for i in set(groups)] # filter duplicate values
        self.avatar_sha = avatar_sha
        self._is_groupchat = groupchat
        self._is_pm_contact = is_pm_contact

        if groupchat:
            self.settings = GroupChatSettings(account.name, jid)
        else:
            self.settings = ContactSettings(account.name, jid)

        self.sub = sub
        self.ask = ask

        self.priority = priority
        self.idle_time = idle_time

        self.pep = {}

    def connect_signal(self, setting, func):
        app.settings.connect_signal(
            setting, func, self.account.name, self.jid)

    def get_full_jid(self):
        if self.resource:
            return self.jid + '/' + self.resource
        return self.jid

    def get_shown_name(self):
        if self._is_groupchat:
            return self._get_groupchat_name()
        if self.name:
            return self.name
        if self.contact_name:
            return self.contact_name
        return self.jid.split('@')[0]

    def _get_groupchat_name(self):
        from gajim.common.helpers import get_groupchat_name
        con = app.connections[self.account.name]
        return get_groupchat_name(con, self.jid)

    def get_shown_groups(self):
        if self.is_observer():
            return [_('Observers')]
        if self.is_groupchat:
            return [_('Group chats')]
        if self.is_transport():
            return [_('Transports')]
        if not self.groups:
            return [_('General')]
        return self.groups

    def is_hidden_from_roster(self):
        """
        If contact should not be visible in roster
        """
        # XEP-0162: http://www.xmpp.org/extensions/xep-0162.html
        if self.is_transport():
            return False
        if self.sub in ('both', 'to'):
            return False
        if self.sub in ('none', 'from') and self.ask == 'subscribe':
            return False
        if self.sub in ('none', 'from') and (self.name or self.groups):
            return False
        if _('Not in contact list') in self.groups:
            return False
        return True

    def is_observer(self):
        # XEP-0162: http://www.xmpp.org/extensions/xep-0162.html
        is_observer = False
        if self.sub == 'from' and not self.is_transport()\
        and self.is_hidden_from_roster():
            is_observer = True
        return is_observer

    @property
    def is_groupchat(self):
        return self._is_groupchat

    @property
    def is_connected(self):
        try:
            return app.gc_connected[self.account.name][self.jid]
        except Exception:
            return False

    def is_transport(self):
        # if not '@' or '@' starts the jid then contact is transport
        return self.jid.find('@') <= 0

    def can_notify(self):
        if not self.is_groupchat:
            raise ValueError

        all_ = app.settings.get('notify_on_all_muc_messages')
        room = self.settings.get('notify_on_all_messages')
        return all_ or room


class GC_Contact(CommonContact):
    """
    Information concerning each groupchat contact
    """

    def __init__(self, room_jid, account, name='', show='', presence=None,
                 status='', role='', affiliation='', jid='', resource='',
                 chatstate=None, avatar_sha=None):

        CommonContact.__init__(self, jid, account, resource, show,
                               presence, status, name, chatstate)

        self.room_jid = room_jid
        self.role = role
        self.affiliation = affiliation
        self.avatar_sha = avatar_sha

        self.settings = ContactSettings(account.name, jid)

    def get_full_jid(self):
        return self.room_jid + '/' + self.name

    def get_shown_name(self):
        return self.name

    def get_avatar(self, *args, **kwargs):
        return common.app.interface.get_avatar(self, *args, **kwargs)

    def as_contact(self):
        """
        Create a Contact instance from this GC_Contact instance
        """
        return Contact(jid=self.get_full_jid(), account=self.account,
            name=self.name, groups=[], show=self.show, status=self.status,
            sub='none', avatar_sha=self.avatar_sha,
            is_pm_contact=True)


class LegacyContactsAPI:
    """
    This is a GOD class for accessing contact and groupchat information.
    The API has several flaws:

            * it mixes concerns because it deals with contacts, groupchats,
              groupchat contacts and metacontacts
            * some methods like get_contact() may return None. This leads to
              a lot of duplication all over Gajim because it is not sure
              if we receive a proper contact or just None.

    It is a long way to cleanup this API. Therefore just stick with it
    and use it as before. We will try to figure out a migration path.
    """
    def __init__(self):
        self._metacontact_manager = MetacontactManager(self)
        self._accounts = {}

    def add_account(self, account_name):
        self._accounts[account_name] = Account(account_name, Contacts(),
                GC_Contacts())
        self._metacontact_manager.add_account(account_name)

    def get_accounts(self, zeroconf=True):
        accounts = list(self._accounts.keys())
        if not zeroconf:
            if 'Local' in accounts:
                accounts.remove('Local')
        return accounts

    def remove_account(self, account):
        del self._accounts[account]
        self._metacontact_manager.remove_account(account)

    def create_contact(self, jid, account, name='', groups=None, show='',
    status='', sub='', ask='', resource='', priority=0,
    chatstate=None, idle_time=None,
    avatar_sha=None, groupchat=False):
        if groups is None:
            groups = []
        # Use Account object if available
        account = self._accounts.get(account, account)
        return Contact(jid=jid, account=account, name=name, groups=groups,
            show=show, status=status, sub=sub, ask=ask, resource=resource,
            priority=priority,
            chatstate=chatstate, idle_time=idle_time, avatar_sha=avatar_sha,
            groupchat=groupchat)

    def create_self_contact(self, jid, account, resource, show, status, priority,
    name=''):
        conn = common.app.connections[account]
        nick = name or common.app.nicks[account]
        account = self._accounts.get(account, account) # Use Account object if available
        self_contact = self.create_contact(jid=jid, account=account,
                name=nick, groups=['self_contact'], show=show, status=status,
                sub='both', ask='none', priority=priority,
                resource=resource)
        self_contact.pep = conn.pep
        return self_contact

    def create_not_in_roster_contact(self, jid, account, resource='', name='',
                                     groupchat=False):
        # Use Account object if available
        account = self._accounts.get(account, account)
        return self.create_contact(jid=jid, account=account, resource=resource,
            name=name, groups=[_('Not in contact list')], show='not in roster',
            status='', sub='none', groupchat=groupchat)

    def copy_contact(self, contact):
        return self.create_contact(contact.jid, contact.account,
            name=contact.name, groups=contact.groups, show=contact.show,
            status=contact.status, sub=contact.sub, ask=contact.ask,
            resource=contact.resource, priority=contact.priority,
            chatstate=contact.chatstate_enum,
            idle_time=contact.idle_time, avatar_sha=contact.avatar_sha)

    def add_contact(self, account, contact):
        if account not in self._accounts:
            self.add_account(account)
        return self._accounts[account].contacts.add_contact(contact)

    def remove_contact(self, account, contact):
        if account not in self._accounts:
            return
        return self._accounts[account].contacts.remove_contact(contact)

    def remove_jid(self, account, jid, remove_meta=True):
        self._accounts[account].contacts.remove_jid(jid)
        if remove_meta:
            self._metacontact_manager.remove_metacontact(account, jid)

    def get_groupchat_contact(self, account, jid):
        return self._accounts[account].contacts.get_groupchat_contact(jid)

    def get_contacts(self, account, jid):
        return self._accounts[account].contacts.get_contacts(jid)

    def get_contact(self, account, jid, resource=None):
        return self._accounts[account].contacts.get_contact(jid, resource=resource)

    def get_contact_strict(self, account, jid, resource):
        return self._accounts[account].contacts.get_contact_strict(jid, resource)

    def get_avatar(self, account, *args, **kwargs):
        return self._accounts[account].contacts.get_avatar(*args, **kwargs)

    def get_avatar_sha(self, account, jid):
        return self._accounts[account].contacts.get_avatar_sha(jid)

    def set_avatar(self, account, jid, sha):
        self._accounts[account].contacts.set_avatar(jid, sha)

    def iter_contacts(self, account):
        for contact in self._accounts[account].contacts.iter_contacts():
            yield contact

    def get_contact_from_full_jid(self, account, fjid):
        return self._accounts[account].contacts.get_contact_from_full_jid(fjid)

    def get_first_contact_from_jid(self, account, jid):
        return self._accounts[account].contacts.get_first_contact_from_jid(jid)

    def get_contacts_from_group(self, account, group):
        return self._accounts[account].contacts.get_contacts_from_group(group)

    def get_contacts_jid_list(self, account):
        return self._accounts[account].contacts.get_contacts_jid_list()

    def get_jid_list(self, account):
        return self._accounts[account].contacts.get_jid_list()

    def change_contact_jid(self, old_jid, new_jid, account):
        return self._accounts[account].change_contact_jid(old_jid, new_jid)

    def get_highest_prio_contact_from_contacts(self, contacts):
        if not contacts:
            return None
        prim_contact = contacts[0]
        for contact in contacts[1:]:
            if int(contact.priority) > int(prim_contact.priority):
                prim_contact = contact
        return prim_contact

    def get_contact_with_highest_priority(self, account, jid):
        contacts = self.get_contacts(account, jid)
        if not contacts and '/' in jid:
            # jid may be a fake jid, try it
            room, nick = jid.split('/', 1)
            contact = self.get_gc_contact(account, room, nick)
            return contact
        return self.get_highest_prio_contact_from_contacts(contacts)

    def get_nb_online_total_contacts(self, accounts=None, groups=None):
        """
        Return the number of online contacts and the total number of contacts
        """
        if not accounts:
            accounts = self.get_accounts()
        if groups is None:
            groups = []
        nbr_online = 0
        nbr_total = 0
        for account in accounts:
            our_jid = common.app.get_jid_from_account(account)
            for jid in self.get_jid_list(account):
                if jid == our_jid:
                    continue
                if (common.app.jid_is_transport(jid) and
                        _('Transports') not in groups):
                    # do not count transports
                    continue
                if self.has_brother(account, jid, accounts) and not \
                self.is_big_brother(account, jid, accounts):
                    # count metacontacts only once
                    continue
                contact = self._accounts[account].contacts._contacts[jid][0]
                if _('Not in contact list') in contact.groups:
                    continue
                in_groups = False
                if groups == []:
                    in_groups = True
                else:
                    for group in groups:
                        if group in contact.get_shown_groups():
                            in_groups = True
                            break

                if in_groups:
                    if contact.show not in ('offline', 'error'):
                        nbr_online += 1
                    nbr_total += 1
        return nbr_online, nbr_total

    def __getattr__(self, attr_name):
        # Only called if self has no attr_name
        if hasattr(self._metacontact_manager, attr_name):
            return getattr(self._metacontact_manager, attr_name)
        raise AttributeError(attr_name)

    def create_gc_contact(self, room_jid, account, name='', show='',
                          presence=None, status='', role='',
                          affiliation='', jid='', resource='', avatar_sha=None):
        account = self._accounts.get(account, account) # Use Account object if available
        return GC_Contact(room_jid, account, name, show, presence, status,
                          role, affiliation, jid, resource, avatar_sha=avatar_sha)

    def add_gc_contact(self, account, gc_contact):
        return self._accounts[account].gc_contacts.add_gc_contact(gc_contact)

    def remove_gc_contact(self, account, gc_contact):
        return self._accounts[account].gc_contacts.remove_gc_contact(gc_contact)

    def remove_room(self, account, room_jid):
        return self._accounts[account].gc_contacts.remove_room(room_jid)

    def get_gc_list(self, account):
        return self._accounts[account].gc_contacts.get_gc_list()

    def get_nick_list(self, account, room_jid):
        return self._accounts[account].gc_contacts.get_nick_list(room_jid)

    def get_gc_contact_list(self, account, room_jid):
        return self._accounts[account].gc_contacts.get_gc_contact_list(room_jid)

    def get_gc_contact(self, account, room_jid, nick):
        return self._accounts[account].gc_contacts.get_gc_contact(room_jid, nick)

    def is_gc_contact(self, account, jid):
        return self._accounts[account].gc_contacts.is_gc_contact(jid)

    def get_nb_role_total_gc_contacts(self, account, room_jid, role):
        return self._accounts[account].gc_contacts.get_nb_role_total_gc_contacts(room_jid, role)

    def set_gc_avatar(self, account, room_jid, nick, sha):
        contact = self.get_gc_contact(account, room_jid, nick)
        if contact is None:
            return
        contact.avatar_sha = sha

    def get_combined_chatstate(self, account, jid):
        return self._accounts[account].contacts.get_combined_chatstate(jid)


class Contacts():
    """
    This is a breakout of the contact related behavior of the old
    Contacts class (which is not called LegacyContactsAPI)
    """
    def __init__(self):
        # list of contacts  {jid1: [C1, C2]}, } one Contact per resource
        self._contacts = {}

    def add_contact(self, contact):
        if contact.jid not in self._contacts or contact.is_groupchat:
            self._contacts[contact.jid] = [contact]
            return
        contacts = self._contacts[contact.jid]
        # We had only one that was offline, remove it
        if len(contacts) == 1 and contacts[0].show == 'offline':
            # Do not use self.remove_contact: it deletes
            # self._contacts[account][contact.jid]
            contacts.remove(contacts[0])
        # If same JID with same resource already exists, use the new one
        for c in contacts:
            if c.resource == contact.resource:
                self.remove_contact(c)
                break
        contacts.append(contact)

    def remove_contact(self, contact):
        if contact.jid not in self._contacts:
            return
        if contact in self._contacts[contact.jid]:
            self._contacts[contact.jid].remove(contact)
        if not self._contacts[contact.jid]:
            del self._contacts[contact.jid]

    def remove_jid(self, jid):
        """
        Remove all contacts for a given jid
        """
        if jid in self._contacts:
            del self._contacts[jid]

    def get_contacts(self, jid):
        """
        Return the list of contact instances for this jid
        """
        return list(self._contacts.get(jid, []))

    def get_contact(self, jid, resource=None):
        ### WARNING ###
        # This function returns a *RANDOM* resource if resource = None!
        # Do *NOT* use if you need to get the contact to which you
        # send a message for example, as a bare JID in XMPP means
        # highest available resource, which this function ignores!
        """
        Return the contact instance for the given resource if it's given else the
        first contact is no resource is given or None if there is not
        """
        if jid in self._contacts:
            if not resource:
                return self._contacts[jid][0]
            for c in self._contacts[jid]:
                if c.resource == resource:
                    return c
            return self._contacts[jid][0]

    def get_contact_strict(self, jid, resource):
        """
        Return the contact instance for the given resource or None
        """
        if jid in self._contacts:
            for c in self._contacts[jid]:
                if c.resource == resource:
                    return c

    def get_groupchat_contact(self, jid):
        if jid in self._contacts:
            contacts = self._contacts[jid]
            if contacts[0].is_groupchat:
                return contacts[0]

    def get_avatar(self, jid, size, scale, show=None):
        if jid not in self._contacts:
            return None

        for resource in self._contacts[jid]:
            avatar = common.app.interface.get_avatar(
                resource, size, scale, show)
            if avatar is None:
                self.set_avatar(jid, None)
            return avatar

    def get_avatar_sha(self, jid):
        if jid not in self._contacts:
            return None

        for resource in self._contacts[jid]:
            if resource.avatar_sha is not None:
                return resource.avatar_sha
        return None

    def set_avatar(self, jid, sha):
        if jid not in self._contacts:
            return
        for resource in self._contacts[jid]:
            resource.avatar_sha = sha

    def iter_contacts(self):
        for jid in list(self._contacts.keys()):
            for contact in self._contacts[jid][:]:
                yield contact

    def get_jid_list(self):
        return list(self._contacts.keys())

    def get_contacts_jid_list(self):
        return [jid for jid, contact in self._contacts.items() if not
                contact[0].is_groupchat]

    def get_contact_from_full_jid(self, fjid):
        """
        Get Contact object for specific resource of given jid
        """
        barejid, resource = common.app.get_room_and_nick_from_fjid(fjid)
        return self.get_contact_strict(barejid, resource)

    def get_first_contact_from_jid(self, jid):
        if jid in self._contacts:
            return self._contacts[jid][0]

    def get_contacts_from_group(self, group):
        """
        Return all contacts in the given group
        """
        group_contacts = []
        for jid in self._contacts:
            contacts = self.get_contacts(jid)
            if group in contacts[0].groups:
                group_contacts += contacts
        return group_contacts

    def change_contact_jid(self, old_jid, new_jid):
        if old_jid not in self._contacts:
            return
        self._contacts[new_jid] = []
        for _contact in self._contacts[old_jid]:
            _contact.jid = new_jid
            self._contacts[new_jid].append(_contact)
        del self._contacts[old_jid]

    def get_combined_chatstate(self, jid):
        if jid not in self._contacts:
            return
        contacts = self._contacts[jid]
        states = []
        for contact in contacts:
            if contact.chatstate_enum is None:
                continue
            states.append(contact.chatstate_enum)

        return str(min(states)) if states else None


class GC_Contacts():

    def __init__(self):
        # list of contacts that are in gc {room_jid: {nick: C}}}
        self._rooms = {}

    def add_gc_contact(self, gc_contact):
        if gc_contact.room_jid not in self._rooms:
            self._rooms[gc_contact.room_jid] = {gc_contact.name: gc_contact}
        else:
            self._rooms[gc_contact.room_jid][gc_contact.name] = gc_contact

    def remove_gc_contact(self, gc_contact):
        if gc_contact.room_jid not in self._rooms:
            return
        if gc_contact.name not in self._rooms[gc_contact.room_jid]:
            return
        del self._rooms[gc_contact.room_jid][gc_contact.name]
        # It was the last nick in room ?
        if not self._rooms[gc_contact.room_jid]:
            del self._rooms[gc_contact.room_jid]

    def remove_room(self, room_jid):
        if room_jid in self._rooms:
            del self._rooms[room_jid]

    def get_gc_list(self):
        return self._rooms.keys()

    def get_nick_list(self, room_jid):
        gc_list = self.get_gc_list()
        if not room_jid in gc_list:
            return []
        return list(self._rooms[room_jid].keys())

    def get_gc_contact_list(self, room_jid):
        try:
            return list(self._rooms[room_jid].values())
        except Exception:
            return []

    def get_gc_contact(self, room_jid, nick):
        try:
            return self._rooms[room_jid][nick]
        except KeyError:
            return None

    def is_gc_contact(self, jid):
        """
        >>> gc = GC_Contacts()
        >>> gc._rooms = {'gajim@conference.gajim.org' : {'test' : True}}
        >>> gc.is_gc_contact('gajim@conference.gajim.org/test')
        True
        >>> gc.is_gc_contact('test@jabbim.com')
        False
        """
        jid = jid.split('/')
        if len(jid) != 2:
            return False
        gcc = self.get_gc_contact(jid[0], jid[1])
        return gcc is not None

    def get_nb_role_total_gc_contacts(self, room_jid, role):
        """
        Return the number of group chat contacts for the given role and the total
        number of group chat contacts
        """
        if room_jid not in self._rooms:
            return 0, 0
        nb_role = nb_total = 0
        for nick in self._rooms[room_jid]:
            if self._rooms[room_jid][nick].role == role:
                nb_role += 1
            nb_total += 1
        return nb_role, nb_total


class MetacontactManager():

    def __init__(self, contacts):
        self._metacontacts_tags = {}
        self._contacts = contacts

    def add_account(self, account):
        if account not in self._metacontacts_tags:
            self._metacontacts_tags[account] = {}

    def remove_account(self, account):
        del self._metacontacts_tags[account]

    def define_metacontacts(self, account, tags_list):
        self._metacontacts_tags[account] = tags_list

    def _get_new_metacontacts_tag(self, jid):
        if not jid in self._metacontacts_tags:
            return jid
        #FIXME: can this append ?
        assert False

    def iter_metacontacts_families(self, account):
        for tag in self._metacontacts_tags[account]:
            family = self._get_metacontacts_family_from_tag(account, tag)
            yield family

    def _get_metacontacts_tag(self, account, jid):
        """
        Return the tag of a jid
        """
        if not account in self._metacontacts_tags:
            return None
        for tag in self._metacontacts_tags[account]:
            for data in self._metacontacts_tags[account][tag]:
                if data['jid'] == jid:
                    return tag
        return None

    def add_metacontact(self, brother_account, brother_jid, account, jid, order=None):
        tag = self._get_metacontacts_tag(brother_account, brother_jid)
        if not tag:
            tag = self._get_new_metacontacts_tag(brother_jid)
            self._metacontacts_tags[brother_account][tag] = [{'jid': brother_jid,
                    'tag': tag}]
            if brother_account != account:
                con = common.app.connections[brother_account]
                con.get_module('MetaContacts').store_metacontacts(
                    self._metacontacts_tags[brother_account])
        # be sure jid has no other tag
        old_tag = self._get_metacontacts_tag(account, jid)
        while old_tag:
            self.remove_metacontact(account, jid)
            old_tag = self._get_metacontacts_tag(account, jid)
        if tag not in self._metacontacts_tags[account]:
            self._metacontacts_tags[account][tag] = [{'jid': jid, 'tag': tag}]
        else:
            if order:
                self._metacontacts_tags[account][tag].append({'jid': jid,
                        'tag': tag, 'order': order})
            else:
                self._metacontacts_tags[account][tag].append({'jid': jid,
                        'tag': tag})
        con = common.app.connections[account]
        con.get_module('MetaContacts').store_metacontacts(
            self._metacontacts_tags[account])

    def remove_metacontact(self, account, jid):
        if account not in self._metacontacts_tags:
            return

        found = None
        for tag in self._metacontacts_tags[account]:
            for data in self._metacontacts_tags[account][tag]:
                if data['jid'] == jid:
                    found = data
                    break
            if found:
                self._metacontacts_tags[account][tag].remove(found)
                con = common.app.connections[account]
                con.get_module('MetaContacts').store_metacontacts(
                    self._metacontacts_tags[account])
                break

    def has_brother(self, account, jid, accounts):
        tag = self._get_metacontacts_tag(account, jid)
        if not tag:
            return False
        meta_jids = self._get_metacontacts_jids(tag, accounts)
        return len(meta_jids) > 1 or len(meta_jids[account]) > 1

    def is_big_brother(self, account, jid, accounts):
        family = self.get_metacontacts_family(account, jid)
        if family:
            nearby_family = [data for data in family
                    if account in accounts]
            bb_data = self._get_metacontacts_big_brother(nearby_family)
            if bb_data['jid'] == jid and bb_data['account'] == account:
                return True
        return False

    def _get_metacontacts_jids(self, tag, accounts):
        """
        Return all jid for the given tag in the form {acct: [jid1, jid2],.}
        """
        answers = {}
        for account, tags in self._metacontacts_tags.items():
            if tag in tags:
                if account not in accounts:
                    continue
                answers[account] = []
                for data in tags[tag]:
                    answers[account].append(data['jid'])
        return answers

    def get_metacontacts_family(self, account, jid):
        """
        Return the family of the given jid, including jid in the form:
        [{'account': acct, 'jid': jid, 'order': order}, ] 'order' is optional
        """
        tag = self._get_metacontacts_tag(account, jid)
        return self._get_metacontacts_family_from_tag(account, tag)

    def _get_metacontacts_family_from_tag(self, account, tag):
        if not tag:
            return []
        answers = []
        if tag in self._metacontacts_tags[account]:
            for data in self._metacontacts_tags[account][tag]:
                data['account'] = account
                answers.append(data)
        return answers

    def _metacontact_key(self, data):
        """
        Data is {'jid': jid, 'account': account, 'order': order} order is
        optional
        """
        show_list = ['not in roster', 'error', 'offline', 'dnd',
                     'xa', 'away', 'chat', 'online', 'requested', 'message']

        jid = data['jid']
        account = data['account']
        # contact can be null when a jid listed in the metacontact data
        # is not in our roster
        contact = self._contacts.get_contact_with_highest_priority(
            account, jid)
        show = show_list.index(contact.show) if contact else 0
        priority = contact.priority if contact else 0
        has_order = 'order' in data
        order = data.get('order', 0)
        transport = common.app.get_transport_name_from_jid(jid)
        server = common.app.get_server_from_jid(jid)
        myserver = app.settings.get_account_setting(account, 'hostname')
        return (bool(contact), show > 2, has_order, order, bool(transport),
                show, priority, server == myserver, jid, account)

    def get_nearby_family_and_big_brother(self, family, account):
        """
        Return the nearby family and its Big Brother

        Nearby family is the part of the family that is grouped with the
        metacontact.  A metacontact may be over different accounts. If accounts
        are not merged then the given family is split account wise.

        (nearby_family, big_brother_jid, big_brother_account)
        """
        if app.settings.get('mergeaccounts'):
            # group all together
            nearby_family = family
        else:
            # we want one nearby_family per account
            nearby_family = [data for data in family if account == data['account']]

        if not nearby_family:
            return (None, None, None)
        big_brother_data = self._get_metacontacts_big_brother(nearby_family)
        big_brother_jid = big_brother_data['jid']
        big_brother_account = big_brother_data['account']

        return (nearby_family, big_brother_jid, big_brother_account)

    def _get_metacontacts_big_brother(self, family):
        """
        Which of the family will be the big brother under which all others will be
        ?
        """
        return max(family, key=self._metacontact_key)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
