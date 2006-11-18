import os
import sys
import tempfile

# Note on path and filename encodings:
#
# In general it is very difficult to do this correctly.
# We may pull information from environment variables, and what encoding that is
# in is anyone's guess. Any information we request directly from the file
# system will be in filesystemencoding, and (parts of) paths that we write in
# this source code will be in whatever encoding the source is in. (I hereby
# declare this file to be UTF-8 encoded.)
#
# To make things more complicated, modern Windows filesystems use UTF-16, but
# the API tends to hide this from us.
#
# I tried to minimize problems by passing Unicode strings to OS functions as
# much as possible. Hopefully this makes the function return an Unicode string
# as well. If not, we get an 8-bit string in filesystemencoding, which we can
# happily pass to functions that operate on files and directories, so we can
# just leave it as is. Since these paths are meant to be internal to Gajim and
# not displayed to the user, Unicode is not really necessary here.

def fse(s):
	'''Convert from filesystem encoding if not already Unicode'''
	return unicode(s, sys.getfilesystemencoding())

class ConfigPaths:
	def __init__(this, root=None):
		this.root = root
		this.paths = {}

		if this.root is None:
			if os.name == 'nt':
				try:
					# Documents and Settings\[User Name]\Application Data\Gajim

					# How are we supposed to know what encoding the environment
					# variable 'appdata' is in? Assuming it to be in filesystem
					# encoding.
					this.root = os.path.join(fse(os.environ[u'appdata']), u'Gajim')
				except KeyError:
					# win9x, in cwd
					this.root = u''
			else: # Unices
				# Pass in an Unicode string, and hopefully get one back.
				this.root = os.path.expanduser(u'~/.gajim')

	def add_from_root(this, name, path):
		this.paths[name] = (True, path)

	def add(this, name, path):
		this.paths[name] = (False, path)

	def __getitem__(this, key):
		relative, path = this.paths[key]
		if not relative:
			return path
		return os.path.join(this.root, path)

	def get(this, key, default=None):
		try:
			return this[key]
		except KeyError:
			return default

	def iteritems(this):
		for key in this.paths.iterkeys():
			yield (key, this[key])

def windowsify(s):
	if os.name == 'nt':
		return s.capitalize()
	return s

def init():
	paths = ConfigPaths()

	# LOG is deprecated
	k = ( 'LOG',   'LOG_DB',   'VCARD',   'AVATAR',   'MY_EMOTS' )
	v = (u'logs', u'logs.db', u'vcards', u'avatars', u'emoticons')

	if os.name == 'nt':
		v = map(lambda x: x.capitalize(), v)

	for n, p in zip(k, v):
		paths.add_from_root(n, p)

	paths.add('DATA', os.path.join(u'..', windowsify(u'data')))
	paths.add('HOME', os.path.expanduser(u'~'))
	paths.add('TMP', fse(tempfile.gettempdir()))

	try:
		import svn_config
		svn_config.configure(paths)
	except (ImportError, AttributeError):
		pass

	#for k, v in paths.iteritems():
	#	print "%s: %s" % (k, v)

	return paths

gajimpaths = init()

def init_profile(profile, paths=gajimpaths):
	conffile = windowsify(u'config')
	pidfile = windowsify(u'gajim')

	if len(profile) > 0:
		conffile += u'.' + profile
		pidfile += u'.' + profile
	pidfile += u'.pid'
	paths.add_from_root('CONFIG_FILE', conffile)
	paths.add_from_root('PID_FILE', pidfile)
