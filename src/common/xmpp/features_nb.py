##   features.py
##
##   Copyright (C) 2003-2004 Alexey "Snake" Nezhdanov
##   Copyright (C) 2007 Julien Pivotto <roidelapluie@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

# $Id: features.py,v 1.22 2005/09/30 20:13:04 mikealbon Exp $

"""
Different stuff that wasn't worth separating it into modules
(Registration, Privacy Lists, ...)
"""

from protocol import NS_REGISTER, NS_PRIVACY, NS_DATA, Iq, isResultNode, Node

def _on_default_response(disp, iq, cb):
    def _on_response(resp):
        if isResultNode(resp):
            if cb:
                cb(True)
        elif cb:
            cb(False)
    disp.SendAndCallForResponse(iq, _on_response)

###############################################################################
### Registration
###############################################################################

REGISTER_DATA_RECEIVED = 'REGISTER DATA RECEIVED'

def getRegInfo(disp, host, info={}, sync=True):
    """
    Get registration form from remote host. Info dict can be prefilled
    :param disp: plugged dispatcher instance
    :param info: dict, like {'username':'joey'}.

    See JEP-0077 for details.
    """
    iq=Iq('get', NS_REGISTER, to=host)
    for i in info.keys():
        iq.setTagData(i, info[i])
    if sync:
        disp.SendAndCallForResponse(iq, lambda resp:
                _ReceivedRegInfo(disp.Dispatcher, resp, host))
    else:
        disp.SendAndCallForResponse(iq, _ReceivedRegInfo, {'agent': host })

def _ReceivedRegInfo(con, resp, agent):
    Iq('get', NS_REGISTER, to=agent)
    if not isResultNode(resp):
        error_msg = resp.getErrorMsg()
        con.Event(NS_REGISTER, REGISTER_DATA_RECEIVED, (agent, None, False, error_msg, ''))
        return
    tag=resp.getTag('query', namespace=NS_REGISTER)
    if not tag:
        error_msg = resp.getErrorMsg()
        con.Event(NS_REGISTER, REGISTER_DATA_RECEIVED, (agent, None, False, error_msg, ''))
        return
    df=tag.getTag('x', namespace=NS_DATA)
    if df:
        con.Event(NS_REGISTER, REGISTER_DATA_RECEIVED, (agent, df, True, '',
            tag))
        return
    df={}
    for i in resp.getQueryPayload():
        if not isinstance(i, Node):
            continue
        df[i.getName()] = i.getData()
    con.Event(NS_REGISTER, REGISTER_DATA_RECEIVED, (agent, df, False, '', ''))

def register(disp, host, info, cb, args=None):
    """
    Perform registration on remote server with provided info

    If registration fails you can get additional info from the dispatcher's
    owner   attributes lastErrNode, lastErr and lastErrCode.
    """
    iq=Iq('set', NS_REGISTER, to=host)
    if not isinstance(info, dict):
        info=info.asDict()
    for i in info.keys():
        iq.setTag('query').setTagData(i, info[i])
    disp.SendAndCallForResponse(iq, cb, args)

def unregister(disp, host, cb):
    """
    Unregisters with host (permanently removes account). Returns true on success
    """
    iq = Iq('set', NS_REGISTER, to=host, payload=[Node('remove')])
    _on_default_response(disp, iq, cb)

def changePasswordTo(disp, newpassword, host=None, cb = None):
    """
    Changes password on specified or current (if not specified) server. Returns
    true on success.
    """
    if not host:
        host = disp._owner.Server
    iq = Iq('set', NS_REGISTER, to=host, payload=[Node('username',
                    payload=[disp._owner.Server]), Node('password', payload=[newpassword])])
    _on_default_response(disp, iq, cb)

###############################################################################
### Privacy List
###############################################################################

PL_TYPE_JID = 'jid'
PL_TYPE_GROUP = 'group'
PL_TYPE_SUBC = 'subscription'
PL_ACT_ALLOW = 'allow'
PL_ACT_DENY = 'deny'

PRIVACY_LISTS_RECEIVED = 'PRIVACY LISTS RECEIVED'
PRIVACY_LIST_RECEIVED = 'PRIVACY LIST RECEIVED'
PRIVACY_LISTS_ACTIVE_DEFAULT = 'PRIVACY LISTS ACTIVE DEFAULT'

def getPrivacyLists(disp):
    """
    Request privacy lists from connected server. Returns dictionary of existing
    lists on success.
    """
    iq = Iq('get', NS_PRIVACY)
    def _on_response(resp):
        dict_ = {'lists': []}
        if not isResultNode(resp):
            disp.Event(NS_PRIVACY, PRIVACY_LISTS_RECEIVED, (False))
            return
        for list_ in resp.getQueryPayload():
            if list_.getName()=='list':
                dict_['lists'].append(list_.getAttr('name'))
            else:
                dict_[list_.getName()]=list_.getAttr('name')
        disp.Event(NS_PRIVACY, PRIVACY_LISTS_RECEIVED, (dict_))
    disp.SendAndCallForResponse(iq, _on_response)

def getActiveAndDefaultPrivacyLists(disp):
    iq = Iq('get', NS_PRIVACY)
    def _on_response(resp):
        dict_ = {'active': '', 'default': ''}
        if not isResultNode(resp):
            disp.Event(NS_PRIVACY, PRIVACY_LISTS_ACTIVE_DEFAULT, (False))
            return
        for list_ in resp.getQueryPayload():
            if list_.getName() == 'active':
                dict_['active'] = list_.getAttr('name')
            elif list_.getName() == 'default':
                dict_['default'] = list_.getAttr('name')
        disp.Event(NS_PRIVACY, PRIVACY_LISTS_ACTIVE_DEFAULT, (dict_))
    disp.SendAndCallForResponse(iq, _on_response)

def getPrivacyList(disp, listname):
    """
    Request specific privacy list listname. Returns list of XML nodes (rules)
    taken from the server responce.
    """
    def _on_response(resp):
        if not isResultNode(resp):
            disp.Event(NS_PRIVACY, PRIVACY_LIST_RECEIVED, (False))
            return
        disp.Event(NS_PRIVACY, PRIVACY_LIST_RECEIVED, (resp))
    iq = Iq('get', NS_PRIVACY, payload=[Node('list', {'name': listname})])
    disp.SendAndCallForResponse(iq, _on_response)

def setActivePrivacyList(disp, listname=None, typ='active', cb=None):
    """
    Switch privacy list 'listname' to specified type. By default the type is
    'active'. Returns true on success.
    """
    if listname:
        attrs={'name':listname}
    else:
        attrs={}
    iq = Iq('set', NS_PRIVACY, payload=[Node(typ, attrs)])
    _on_default_response(disp, iq, cb)

def setDefaultPrivacyList(disp, listname=None):
    """
    Set the default privacy list as 'listname'. Returns true on success
    """
    return setActivePrivacyList(disp, listname, 'default')

def setPrivacyList(disp, listname, tags):
    """
    Set the ruleset

    'list' should be the simpleXML node formatted according to RFC 3921
    (XMPP-IM) I.e. Node('list',{'name':listname},payload=[...]).

    Returns true on success.
    """
    iq = Iq('set', NS_PRIVACY, xmlns = '')
    list_query = iq.getTag('query').setTag('list', {'name': listname})
    for item in tags:
        if 'type' in item and 'value' in item:
            item_tag = list_query.setTag('item', {'action': item['action'],
                    'order': item['order'], 'type': item['type'],
                    'value': item['value']})
        else:
            item_tag = list_query.setTag('item', {'action': item['action'],
                    'order': item['order']})
        if 'child' in item:
            for child_tag in item['child']:
                item_tag.setTag(child_tag)
    _on_default_response(disp, iq, None)

def delPrivacyList(disp, listname, cb=None):
    ''' Deletes privacy list 'listname'. Returns true on success. '''
    iq = Iq('set', NS_PRIVACY, payload=[Node('list', {'name':listname})])
    _on_default_response(disp, iq, cb)
