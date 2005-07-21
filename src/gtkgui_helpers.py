from common import gajim

def get_contact_instances_from_jid(account, jid):
	''' we may have two or more resources on that jid '''
	contact_instances = gajim.contacts[account][jid]
	return contact_instances

def get_first_contact_instance_from_jid(account, jid):
	contact_instances = get_contact_instances_from_jid(account, jid)
	return contact_instances[0]

def get_contact_name_from_jid(account, jid):
	contact_instances = get_contact_instances_from_jid(account, jid)
	return contact_instances[0].name
