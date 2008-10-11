###
### Internal dbus management. This can go away once native gtk+ is in fink or
### macports and we can require their dbus.
###



import os, sys, commands, signal

if sys.platform != "darwin":
	raise ImportError("System platform is not OS/X")

import osx, osx.nsapp
from common.configpaths import gajimpaths


_GTK_BASE = "/Library/Frameworks/GTK+.framework/Versions/Current"


def readEnv():
	gajimpaths.add_from_root(u'dbus.env', u'dbus.env')
	try:
		dbus_env = open(gajimpaths[u'dbus.env'], "r")
	except Exception:
		return False
	try:
		line1 = dbus_env.readline()
		line2 = dbus_env.readline()
		dbus_env.close()
	except Exception:
		print "Invalid dbus.env file"
		return False
	return parseEnv(line1, line2)


def parseEnv(line1, line2):
	try:
		if not line1 or not line2:
			return False
		if (not line1.startswith("DBUS_SESSION_BUS_ADDRESS=") or
		not line2.startswith("DBUS_SESSION_BUS_PID=")):
			return False
		arr = line2.split("=")
		pid = arr[1].strip().strip('"')
		if not osx.checkPID(int(pid), "dbus-daemon"):
			return False
		line1 = line1.strip()
		loc = line1.find("=")
		address = line1[loc + 1:]
		address = address.strip().strip('"')
		return [address, pid]
	except Exception, e:
		print "Invalid dbus.env file", e
		return False
	return None


def setEnv(env):
	os.environ['DBUS_SESSION_BUS_ADDRESS'] = env[0]
	os.environ['DBUS_SESSION_BUS_PID'] = env[1]
	return


def writeEnv(env):
	gajimpaths.add_from_root(u'dbus.env', u'dbus.env')
	try:
		dbus_env = open(gajimpaths[u'dbus.env'], "w+")
		dbus_env.write("DBUS_SESSION_BUS_ADDRESS=\"" + env[0] + "\"\n")
		dbus_env.write("DBUS_SESSION_BUS_PID=\"" + env[1] + "\"\n")
		dbus_env.close()
	except Exception, e:
		print "Failed to write file: %s" % gajimpaths[u'dbus.env']
		print str(e)
	return


def checkUUID():
	if os.path.exists(_GTK_BASE + "/var/lib/dbus/machine-id"):
		return
	ret = commands.getstatusoutput(_GTK_BASE + "/bin/dbus-uuidgen --ensure")
	if ret[0] != 0:
		print "Failed to initialize dbus machine UUID:", ret[1]
	return


def load(start):
	# Look for existing external session and just use it if it exists
	if (('DBUS_SESSION_BUS_ADDRESS' in os.environ) and
		('DBUS_SESSION_BUS_PID' in os.environ) and
		osx.checkPID(int(os.environ['DBUS_SESSION_BUS_PID']), 'dbus-daemon')):
		return True

	# Look for our own internal session
	env = readEnv()
	if env:
		# We have a valid existing dbus session, yay
		setEnv(env)
		return True

	# Initialize the machine's UUID if not done yet
	checkUUID()

	if start:
		# None found, start a new session
		print "Starting new dbus session"
		#cmd = os.path.join(osx.nsapp.getBundlePath(),
		#		  "Contents/Resources/bin/dbus-launch --exit-with-session")
		cmd = _GTK_BASE + "/bin/dbus-launch --exit-with-session"
		ret = commands.getstatusoutput(cmd)
		arr = ret[1].split("\n")
		if len(arr) != 2:
			print "Failed to start internal dbus session:"
			print ret[1]
			return
		env = parseEnv(arr[0].strip(), arr[1].strip())
		if not env:
			print "Failed to start internal dbus session:"
			print ret[1]
			return
		setEnv(env)
		writeEnv(env)
		return True
	return False


def shutdown():
	env = readEnv()
	if not env:
		return
	os.kill(int(env[1]), signal.SIGINT)
	return

# vim: se ts=3: