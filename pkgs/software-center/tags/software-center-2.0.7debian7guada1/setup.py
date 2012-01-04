#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

import re
import glob
import os
from subprocess import Popen, PIPE, call
import sys

# update version.py
line = open("debian/changelog").readline()
m = re.match("^[\w-]+ \(([\w\.~\-\+]+)\) ([\w-]+);", line)
VERSION = m.group(1)
open("softwarecenter/version.py","w").write("""
import commands
VERSION='%s'
CODENAME=commands.getoutput("lsb_release -s -c")
DISTRO=commands.getoutput("lsb_release -s -i")
RELEASE=commands.getoutput("lsb_release -s -r")
""" % (VERSION))

# update po4a
if sys.argv[1] == "build":
    call(["po4a", "po/help/po4a.conf"])
    for filename in glob.glob("help/*/*.omf"):
        if 'C' in filename:
            continue

        lang = os.path.basename(os.path.dirname(filename))
        txt = open(filename).read()
        
        txt = txt.replace('<language code="C"/>', '<language code="%s"/>' % lang)
        txt = txt.replace('C/software-center.xml"', '%s/software-center.xml"' % lang)
        f = open(filename, "w")
        try:
            f.write(txt)
        finally:
            f.close()
    

# real setup
setup(name="software-center", version=VERSION,
      scripts=["software-center",
               "utils/update-software-center",
               ],
      packages = ['softwarecenter',
                  'softwarecenter.apt',
                  'softwarecenter.backend',
                  'softwarecenter.db',
                  'softwarecenter.distro',
                  'softwarecenter.view',
                  'softwarecenter.view.widgets',
                 ],
      data_files=[
                  ('share/software-center/ui/',
                   glob.glob("data/ui/*.ui")),
                  ('share/software-center/templates/',
                   glob.glob("data/templates/*.html")),
                  ('../etc/dbus-1/system.d/',
                   ["data/com.ubuntu.SoftwareCenter.conf"]),
                  ('share/software-center/images/',
                   glob.glob("data/images_unbranded/*.png")),
                  ('share/software-center/icons/',
                   glob.glob("data/emblems/*.png")),
                  ('share/apt-xapian-index/plugins',
                   glob.glob("apt-xapian-index-plugin/*.py")),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" : build_help.build_help,
                   "build_icons" : build_icons.build_icons}
      )


