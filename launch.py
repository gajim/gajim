#!/usr/bin/python3 -OO

import os
import sys

if os.geteuid() == 0:
    sys.exit("You must not launch gajim as root, it is insecure.")

import gajim.gajim as g

g.GajimApplication().run(sys.argv)
