#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import unittest
import shutil
import re

from DistUpgrade.xorg_fix_proprietary import comment_out_driver_from_xorg, replace_driver_from_xorg, is_multiseat

class testOriginMatcher(unittest.TestCase):
    ORIG="test-data/xorg.conf.orig"
    FGLRX="test-data/xorg.conf.fglrx"
    MULTISEAT="test-data/xorg.conf.multiseat"
    NEW="test-data/xorg.conf"


    def testSimple(self):
        shutil.copy(self.ORIG, self.NEW)
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assert_(open(self.ORIG).read() == open(self.NEW).read())
    def testRemove(self):
        shutil.copy(self.FGLRX, self.NEW)
        self.assert_("fglrx" in open(self.NEW).read())
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assert_(not "fglrx" in open(self.NEW).read())
    def testMultiseat(self):
        self.assert_(is_multiseat(self.ORIG) == False)
        self.assert_(is_multiseat(self.FGLRX) == False)
        self.assert_(is_multiseat(self.MULTISEAT) == True)
    def testComment(self):
        shutil.copy(self.FGLRX, self.NEW)
        comment_out_driver_from_xorg("fglrx",self.NEW)
        for line in open(self.NEW):
            if re.match('^#.*Driver.*fglrx',line):
                logging.info("commented out line found")
                break
        else:
            raise Exception("commenting the line did *not* work")
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
