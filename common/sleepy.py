#!/usr/bin/env python
"""A Quick class to tell if theres any activity on your machine"""

import time
import idle
from string import find, lower


STATE_UNKNOWN  = "OS probably not supported"
STATE_XAWAY   = "extanted away"
STATE_AWAY   = "away"
STATE_AWAKE    = "awake"

NOT_SUPPORTED = 0

class Sleepy:

    def __init__(self, interval1 = 60, interval2 = 120, devices = ['keyboard', 'mouse', 'ts'] ):

        self.interval1 = interval1
	self.interval2 = interval2
        self.state         = STATE_AWAKE ## assume were awake to stake with
        try:
            idle.init()
        except:
            NOT_SUPPORTED = 1
            self.state = STATE_UNKNOWN

    def poll(self):
        if NOT_SUPPORTED: return -1
        now = time.time()

	idleTime = idle.getIdleSec()
	if idleTime > self.interval2:
		self.state = STATE_XAWAY
	elif idleTime > self.interval1:
		self.state = STATE_AWAY
	else:
		self.state = STATE_AWAKE
        return 1

    def getState(self):
        return self.state

    def setState(self,val):
        self.state = val
            
if __name__ == '__main__':
    s = Sleepy(10)
    while s.poll():
        print "state is %s" % s.getState() 
        time.sleep(5)
