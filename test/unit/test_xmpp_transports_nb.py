'''
Unit test for tranports classes.
'''

import unittest

import lib
lib.setup_env()

from common.xmpp import transports_nb


class TestModuleLevelFunctions(unittest.TestCase):
	'''
	Test class for functions defined at module level
	'''
	def test_urisplit(self):
		def check_uri(uri, proto, host, port, path):
			_proto, _host, _port, _path = transports_nb.urisplit(uri)
			self.assertEqual(proto, _proto)
			self.assertEqual(host, _host)
			self.assertEqual(path, _path)
			self.assertEqual(port, _port)
			
		check_uri('http://httpcm.jabber.org:5280/webclient', proto='http',
			host='httpcm.jabber.org', port=5280, path='/webclient')
	
		check_uri('http://httpcm.jabber.org/webclient', proto='http',
			host='httpcm.jabber.org', port=80, path='/webclient')
		
		check_uri('https://httpcm.jabber.org/webclient', proto='https',
			host='httpcm.jabber.org', port=443, path='/webclient')

	def test_get_proxy_data_from_dict(self):
		def check_dict(proxy_dict, host, port, user, passwd):
			_host, _port, _user, _passwd = transports_nb.get_proxy_data_from_dict(
				proxy_dict)
			self.assertEqual(_host, host)
			self.assertEqual(_port, port)
			self.assertEqual(_user, user)
			self.assertEqual(_passwd, passwd)

		bosh_dict = {'bosh_content': u'text/xml; charset=utf-8',
 						'bosh_hold': 2,
 						'bosh_http_pipelining': False,
 						'bosh_uri': u'http://gajim.org:5280/http-bind',
						'bosh_useproxy': False,
 						'bosh_wait': 30,
 						'bosh_wait_for_restart_response': False,
 						'host': u'172.16.99.11',
 						'pass': u'pass',
 						'port': 3128,
 						'type': u'bosh',
 						'useauth': True,
 						'user': u'user'}
		check_dict(bosh_dict, host=u'gajim.org', port=5280, user=u'user',
			passwd=u'pass')

		proxy_dict = {'bosh_content': u'text/xml; charset=utf-8',
 						'bosh_hold': 2,
						'bosh_http_pipelining': False,
						'bosh_port': 5280,
						'bosh_uri': u'',
						'bosh_useproxy': True,
						'bosh_wait': 30,
						'bosh_wait_for_restart_response': False,
						'host': u'172.16.99.11',
						'pass': u'pass',
						'port': 3128,
						'type': 'socks5',
						'useauth': True,
						'user': u'user'}
		check_dict(proxy_dict, host=u'172.16.99.11', port=3128, user=u'user',
			passwd=u'pass')
	
	
if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
