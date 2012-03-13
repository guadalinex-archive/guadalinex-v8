#!/usr/bin/python

import glob
import os
import subprocess
import sys

basepath = "/var/lib/dpkg/info/*.md5sums"
ok = True
for f in glob.glob(basepath):
    ret = subprocess.call(["md5sum", "--quiet", "-c", 
                           os.path.join(basepath, f)],
                          cwd="/")
    if ret != 0:
        ok = False

if not ok:
    print "WARNING: at least one md5sum mismatch"
    sys.exit(1)
