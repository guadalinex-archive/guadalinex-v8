#!/usr/bin/python

import apt_pkg
import glob
import os
import sys

current_kernelver = os.uname()[2]

apt_pkg.init()

vers = set()
for k in glob.glob("/boot/vmlinuz-*"):
    ver = "-".join(k.split("-")[1:3])
    vers.add(ver)
    if apt_pkg.VersionCompare(current_kernelver, ver) < 0:
        print "WARNING: there is a kernel version '%s' installed higher than the running kernel" % (ver, current_kernelver)
        sys.exit(1)

print "kernel versions: %s" % ", ".join(vers)
if len(vers) < 2:
    print "WARNING: only one kernel version found '%s'" % vers
    print "expected at least two (new + previous)"
    sys.exit(1)
