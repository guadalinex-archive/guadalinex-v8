#!/usr/bin/python

import unittest

import os
import os.path
import sys
sys.path = [os.path.normpath(os.path.join(os.getcwd(),"../"))] + sys.path

from UpdateManager.GtkProgress import GtkFetchProgress
from UpdateManager.UpdateManager import UpdateManager
from UpdateManager.MetaReleaseGObject import MetaRelease
from UpdateManager.DistUpgradeFetcher import DistUpgradeFetcherGtk

def _(s): return s

# FIXME: use dogtail
# something like (needs to run as a seperate process):
# 
# from dogtail.procedural import *
#         focus.application('displayconfig-gtk')
#        focus.frame('Screen and Graphics Preferences')
#        click("Plug 'n' Play", roleName='push button')
#        focus.window('Choose Screen')
#        select('Flat Panel 1024x768', roleName='table cell')
#        keyCombo("Return")
#        click('OK', roleName='push button')


class TestMetaReleaseGUI(unittest.TestCase):
    def setUp(self):
        self.new_dist = None

    def new_dist_available(self, meta_release, upgradable_to):
        #print "new dist: ", upgradable_to.name
        #print "new dist: ", upgradable_to.version
        #print "meta release: %s" % meta_release
        self.new_dist = upgradable_to

    def testnewdist(self):
        meta = MetaRelease()
        meta.METARELEASE_URI = "http://changelogs.ubuntu.com/meta-release-unit-testing"
        meta._buildMetaReleaseFile()
        meta.connect("new_dist_available", self.new_dist_available)
        meta.download()
        self.assert_(meta.downloading == False)
        no_new_information = meta.check()
        self.assert_(no_new_information == False)
        self.assert_(self.new_dist is not None)

class TestReleaseUpgradeFetcherGUI(unittest.TestCase):
    def _new_dist_available(self, meta_release, upgradable_to):
        self.new_dist = upgradable_to

    def setUp(self):
        meta = MetaRelease()
        meta.METARELEASE_URI = "http://changelogs.ubuntu.com/meta-release-unit-testing"
        meta.connect("new_dist_available", self._new_dist_available)
        meta.download()
        self.assert_(meta.downloading == False)
        no_new_information = meta.check()
        self.assert_(no_new_information == False)
        self.assert_(self.new_dist is not None)
        
    def testdownloading(self):
        parent = UpdateManager("/usr/share/update-manager/")
        progress = GtkFetchProgress(parent,
                                    _("Downloading the upgrade "
                                      "tool"),
                                    _("The upgrade tool will "
                                      "guide you through the "
                                      "upgrade process."))
        fetcher = DistUpgradeFetcherGtk(self.new_dist, parent=parent, progress=progress)
        self.assert_(fetcher.showReleaseNotes())
        self.assert_(fetcher.fetchDistUpgrader())
        self.assert_(fetcher.extractDistUpgrader())
        fetcher.script = fetcher.tmpdir+"/gutsy"
        #fetcher.verifyDistUprader()
        self.assert_(fetcher.authenticate())
        self.assert_(fetcher.runDistUpgrader())


if __name__ == '__main__':
    unittest.main()

