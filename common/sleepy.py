#!/usr/bin/env python
"""A Quick class to tell if theres any activity on your machine"""

import time
from string import find, lower


STATE_UNKNOWN  = "OS probably not supported"
STATE_XAWAY   = "extanted away"
STATE_AWAY   = "away"
STATE_AWAKE    = "awake"

NOT_SUPPORTED = 0

class Sleepy:

    def __init__(self, interval1 = 60, interval2 = 120, devices = ['keyboard', 'mouse', 'ts'] ):

        self.devices       = devices
        self.time_marker   = time.time()
        self.interval = self.interval_orig = interval1
	self.interval_orig2 = interval2
        self.last_proc_vals = {}
        for dev in self.devices: self.last_proc_vals[dev] = 0
        
        self.state         = STATE_AWAKE ## assume were awake to stake with
        try:
            self.proc_int_fh = open("/proc/interrupts",'r')
        except:
            NOT_SUPPORTED = 1
            self.state = STATE_UNKNOWN
        self.proc_int_fh.close()
        

    def poll(self):
        if NOT_SUPPORTED: return -1
        now = time.time()

        changed = 0         ## figure out if we have recieved interupts
        for dev in self.devices: ## any of the selected devices  
            proc_val = self._read_proc(dev)
            changed = changed or ( self.last_proc_vals[dev] != proc_val )
            self.last_proc_vals[dev] = proc_val
	
        if changed:
            ## we are awake :)
	    self.time_marker = time.time() ## reset marker
            self.state = STATE_AWAKE
            self.interval = self.interval_orig
        else:
            if (now - self.time_marker >= self.interval):
                ## we are asleep 
                if self.state == STATE_AWAKE:
                    self.state = STATE_AWAY
                    self.interval = self.interval_orig2 #second interval
                else:
                    self.state = STATE_XAWAY
        return 1

    def getState(self):
        return self.state

    def setState(self,val):
        self.state = val
            
    def _read_proc(self, device = 'mouse'):
        proc_int_fh = open("/proc/interrupts",'r')
        info = proc_int_fh.readlines()
        ## ignore first line
        for line in info[1:]:
            cols = line.strip().split()
            if (find(lower(cols[-1]),device) != -1):
                proc_int_fh.close()
                return int(cols[1])
        proc_int_fh.close()
        return 1

if __name__ == '__main__':
    s = Sleepy(10)
    while s.poll():
        print "state is %s" % s.getState() 
        time.sleep(10)
