#!/usr/bin/python

import glob
import os
import subprocess
import sys
import time

def is_process_running(procname):
    proclist = subprocess.Popen(["ps","-eo","comm"], stdout=subprocess.PIPE).communicate()[0]
    for line in proclist.split("\n"):
        if line == procname:
            return True
    return False
    
if __name__ == "__main__":
    if os.path.exists("/usr/bin/X") or glob.glob("/var/log/Xorg*.log"):
        #print "Checking for running Xorg"
        if not is_process_running("Xorg"):
            print "Xorg not running yet, waiting"
            # wait a bit to and see if it comes up
            time.sleep(20)
            if not is_process_running("Xorg"):
                print "WARNING: /usr/bin/X found but no Xorg running"
                sys.exit(1)

            
    
