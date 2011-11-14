#!/usr/bin/python

import apt_pkg
import glob
import os

(sysname, nodename, krelease, version, machine) = os.uname()

sum = 0
for entry in glob.glob("/boot/*%s*" % krelease):
    sum += os.path.getsize(entry)

print "Sum of kernel releated files: ",sum, apt_pkg.SizeToStr(sum)
