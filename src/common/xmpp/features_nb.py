##   features.py 
##
##   Copyright (C) 2003-2004 Alexey "Snake" Nezhdanov
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

from features import REGISTER_DATA_RECEIVED
from protocol import *

def _on_default_response(disp, iq, cb):
	def _on_response(resp):
		if isResultNode(resp): 
			if cb:
				cb(1)
		elif cb:
			cb(False)
	disp.SendAndCallForResponse(iq, _on_response)

def _discover(disp, ns, jid, node = None, fb2b=0, fb2a=1, cb=None):
	""" Try to obtain info from the remote object.
		If remote object doesn't support disco fall back to browse (if fb2b is true)
		and if it doesnt support browse (or fb2b is not true) fall back to agents protocol
		(if gb2a is true). Returns obtained info. Used internally. """
	iq=Iq(to=jid, typ='get', queryNS=ns)
	if node: 
		iq.setAttr('node',node)
	def _on_resp1(resp):
		if fb2b and not isResultNode(resp): 
			# Fallback to browse
			disp.SendAndCallForResponse(Iq(to=jid,typ='get',queryNS=NS_BROWSE), _on_resp2)   
		else:
			_on_resp2('')
	def _on_resp2(resp):
		if fb2a and not isResultNode(resp): 
			# Fallback to agents
			disp.SendAndCallForResponse(Iq(to=jid,typ='get',queryNS=NS_AGENTS), _on_result)   
		else:
			_on_result('')
	def _on_result(resp):
		if isResultNode(resp): 
			if cb:
				cb(resp.getQueryPayload())
		elif cb:
			cb([])
	disp.SendAndCallForResponse(iq, _on_resp1)

# this function is not used in gajim ???
def discoverItems(disp,jid,node=None, cb=None):
	""" Query remote object about any items that it contains. Return items list. """
	""" According to JEP-0030:
		query MAY have node attribute
		item: MUST HAVE jid attribute and MAY HAVE name, node, action attributes.
		action attribute of item can be either of remove or update value."""
	def _on_response(result_array):
		ret=[]
		for result in result_array:
			if result.getName()=='agent' and result.getTag('name'): 
				result.setAttr('name', result.getTagData('name'))
			ret.append(result.attrs)
		if cb:
			cb(ret)
	_discover(disp, NS_DISCO_ITEMS, jid, node, _on_response)

def discoverInfo(disp,jid,node=None, cb=None):
	""" Query remote object about info that it publishes. Returns identities and features lists."""
	""" According to JEP-0030:
		query MAY have node attribute
		identity: MUST HAVE category and name attributes and MAY HAVE type attribute.
		feature: MUST HAVE var attribute"""
	def _on_response(result):
		identities , features = [] , []
		for i in result:
			if i.getName()=='identity': 
				identities.append(i.attrs)
			elif i.getName()=='feature': 
				features.append(i.getAttr('var'))
			elif i.getName()=='agent':
				if i.getTag('name'): 
					i.setAttr('name',i.getTagData('name'))
				if i.getTag('description'): 
					i.setAttr('name',i.getTagData('description'))
				identities.append(i.attrs)
				if i.getTag('groupchat'): 
					features.append(NS_GROUPCHAT)
				if i.getTag('register'): 
					features.append(NS_REGISTER)
				if i.getTag('search'): 
					features.append(NS_SEARCH)
		if cb:
			cb(identities , features)
	_discover(disp, NS_DISCO_INFO, jid, node, _on_response)
	
### Registration ### jabber:iq:register ### JEP-0077 ###########################
def getRegInfo(disp, host, info={}, sync=True):
	""" Gets registration form from remote host.
		You can pre-fill the info dictionary.
		F.e. if you are requesting info on registering user joey than specify 
		info as {'username':'joey'}. See JEP-0077 for details.
		'disp' must be connected dispatcher instance."""
	iq=Iq('get',NS_REGISTER,to=host)
	for i in info.keys(): 
		iq.setTagData(i,info[i])
	if sync:
		disp.SendAndCallForResponse(iq, lambda resp: _ReceivedRegInfo(disp.Dispatcher,resp, host))
	else: 
		disp.SendAndCallForResponse(iq, _ReceivedRegInfo, {'agent': host })

def _ReceivedRegInfo(con, resp, agent):
	iq=Iq('get',NS_REGISTER,to=agent)
	if not isResultNode(resp): 
		return
	df=resp.getTag('query',namespace=NS_REGISTER).getTag('x',namespace=NS_DATA)
	if df:
		con.Event(NS_REGISTER,REGISTER_DATA_RECEIVED,(agent,DataForm(node=df),True))
		return
	df=DataForm(typ='form')
	for i in resp.getQueryPayload():
		if type(i)<>type(iq): 
			pass
		elif i.getName()=='instructions': 
			df.addInstructions(i.getData())
		else: 
			df.setField(i.getName()).setValue(i.getData())
	con.Event(NS_REGISTER, REGISTER_DATA_RECEIVED, (agent,df,False))

def register(disp, host, info, cb):
	""" Perform registration on remote server with provided info.
		disp must be connected dispatcher instance.
		Returns true or false depending on registration result.
		If registration fails you can get additional info from the dispatcher's owner
		attributes lastErrNode, lastErr and lastErrCode.
	"""
	iq=Iq('set', NS_REGISTER, to=host)
	if not isinstance(info, dict): 
		info=info.asDict()
	for i in info.keys(): 
		iq.setTag('query').setTagData(i,info[i])
	_on_default_response(disp, iq, cb)

def unregister(disp, host, cb):
	""" Unregisters with host (permanently removes account).
		disp must be connected and authorized dispatcher instance.
		Returns true on success."""
	iq = Iq('set', NS_REGISTER, to=host, payload=[Node('remove')])
	_on_default_response(disp, iq, cb)

def changePasswordTo(disp, newpassword, host=None, cb = None):
	""" Changes password on specified or current (if not specified) server.
		disp must be connected and authorized dispatcher instance.
		Returns true on success."""
	if not host: host=disp._owner.Server
	iq = Iq('set',NS_REGISTER,to=host, payload=[Node('username',
			payload=[disp._owner.Server]),Node('password',payload=[newpassword])])
	_on_default_response(disp, iq, cb)

### Privacy ### jabber:iq:privacy ### draft-ietf-xmpp-im-19 ####################
#type=[jid|group|subscription]
#action=[allow|deny]

def getPrivacyLists(disp, cb):
	""" Requests privacy lists from connected server.
		Returns dictionary of existing lists on success."""
	iq = Iq('get', NS_PRIVACY)
	def _on_response(resp):
		dict = {'lists': []}
		try:
			if not isResultNode(resp): 
				cb(False)
				return
			for list in resp.getQueryPayload():
				if list.getName()=='list': 
					dict['lists'].append(list.getAttr('name'))
				else: 
					dict[list.getName()]=list.getAttr('name')
			cb(dict)
		except: 
			pass
		cb(False)
	disp.SendAndCallForResponse(iq, _on_respons)

def getPrivacyList(disp, listname, cb):
	""" Requests specific privacy list listname. Returns list of XML nodes (rules)
		taken from the server responce."""
	def _on_response(resp):
		try:
			if isResultNode(resp): 
				return cb(resp.getQueryPayload()[0])
		except: 
			pass
		cb(False)
	iq = Iq('get', NS_PRIVACY, payload=[Node('list', {'name': listname})])
	disp.SendAndCallForResponse(iq, _on_response)

def setActivePrivacyList(disp, listname=None, typ='active', cb=None):
	""" Switches privacy list 'listname' to specified type.
		By default the type is 'active'. Returns true on success."""
	if listname: 
		attrs={'name':listname}
	else: 
		attrs={}
	iq = Iq('set',NS_PRIVACY,payload=[Node(typ,attrs)])
	_on_default_response(disp, iq, cb)

def setDefaultPrivacyList(disp, listname=None):
	""" Sets the default privacy list as 'listname'. Returns true on success."""
	return setActivePrivacyList(disp, listname,'default')

def setPrivacyList(disp, list, cb):
	""" Set the ruleset. 'list' should be the simpleXML node formatted
		according to RFC 3921 (XMPP-IM) (I.e. Node('list',{'name':listname},payload=[...]) )
		Returns true on success."""
	iq=Iq('set',NS_PRIVACY,payload=[list])
	_on_default_response(disp, iq, cb)

def delPrivacyList(disp,listname, cb):
	""" Deletes privacy list 'listname'. Returns true on success."""
	iq = Iq('set',NS_PRIVACY,payload=[Node('list',{'name':listname})])
	_on_default_response(disp, iq, cb)
