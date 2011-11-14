#!/usr/bin/python

import sys
import apt
from random import choice

cache = apt.Cache()
for i in range(int(sys.argv[1])):
    while True:
        pkgname = choice(cache.keys())
        if cache[pkgname].is_installed:
            continue
        try:
            print "Trying to install: '%s'" % pkgname
            cache[pkgname].mark_install()
        except SystemError, e:
            print "Failed to install '%s' (%s)" % (pkgname,e)
            continue
        break
cache.commit(apt.progress.text.AcquireProgress(), 
             apt.progess.base.InstallProgress())
