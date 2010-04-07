import sys, commands
from network_manager_listener import device_now_active, device_no_longer_active


if sys.platform != 'darwin':
    raise ImportError('System platform is not OS X')

net_device_active = True

###
### Utility functions
###

def checkPID(pid, procname):
    out = commands.getstatusoutput("ps -wwp %d" % pid)
    arr = out[1].split("\n")
    if ((len(arr) == 2) and (arr[1].find(procname) >= 0)):
        return True
    return False

import nsapp

def init():
    nsapp.init()
    nsapp.setNetworkCB(netDeviceChanged)
    return


def shutdown():
    import dbus
    dbus.shutdown()
    return


def netDeviceChanged():
    global net_device_active
    if net_device_active:
        net_device_active = False
        device_no_longer_active(None)
    else:
        net_device_active = True
        device_now_active(None)
    return
