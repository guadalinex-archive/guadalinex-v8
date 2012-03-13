#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import shutil
import subprocess
import apt_pkg
import unittest
from DistUpgrade.DistUpgradeController import DistUpgradeController
from DistUpgrade.DistUpgradeViewNonInteractive import DistUpgradeViewNonInteractive
import logging

class testSourcesListUpdate(unittest.TestCase):

    testdir = os.path.abspath("./data-sources-list-test/")

    def setUp(self):
        apt_pkg.config.set("Dir::Etc",self.testdir)
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        if os.path.exists(os.path.join(self.testdir, "sources.list")):
            os.unlink(os.path.join(self.testdir, "sources.list"))

    def test_sources_list_with_nothing(self):
        """
        test sources.list rewrite with nothing in it
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.nothing"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist","sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu gutsy main restricted
deb http://archive.ubuntu.com/ubuntu gutsy-updates main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
""")

    def test_sources_list_rewrite(self):
        """
        test regular sources.list rewrite
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.in"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist","sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        #print open(os.path.join(self.testdir,"sources.list")).read()
        self._verifySources("""
# main repo
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb http://de.archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted multiverse
deb http://security.ubuntu.com/ubuntu/ gutsy-security universe
""")
        # check that the backup file was created correctly
        self.assert_(subprocess.call(
            ["cmp",
             apt_pkg.config.find_file("Dir::Etc::sourcelist")+".in",
             apt_pkg.config.find_file("Dir::Etc::sourcelist")+".distUpgrade"
            ]) == 0)

    def test_commercial_transition(self):
        """
        test transition of pre-gutsy archive.canonical.com archives
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.commercial-transition"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
deb http://archive.canonical.com/ubuntu gutsy partner
""")
        
    def test_powerpc_transition(self):
        """ 
        test transition of powerpc to ports.ubuntu.com
        """
        arch = apt_pkg.config.find("APT::Architecture")
        apt_pkg.config.set("APT::Architecture","powerpc")
        shutil.copy(os.path.join(self.testdir,"sources.list.powerpc"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)
        # now test the result
        self._verifySources("""
deb http://ports.ubuntu.com/ubuntu-ports/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://ports.ubuntu.com/ubuntu-ports/ gutsy-security main restricted
""")
        apt_pkg.config.set("APT::Architecture",arch)

    def test_sparc_transition(self):
        """ 
        test transition of sparc to ports.ubuntu.com
        """
        arch = apt_pkg.config.find("APT::Architecture")
        apt_pkg.config.set("APT::Architecture","sparc")
        shutil.copy(os.path.join(self.testdir,"sources.list.sparc"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.fromDist = "gutsy"
        d.toDist = "hardy"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)
        # now test the result
        self._verifySources("""
deb http://ports.ubuntu.com/ubuntu-ports/ hardy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ hardy main restricted multiverse

deb http://ports.ubuntu.com/ubuntu-ports/ hardy-security main restricted
""")
        apt_pkg.config.set("APT::Architecture",arch)


    def testVerifySourcesListEntry(self):
        from aptsources.sourceslist import SourceEntry
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        for scheme in ["http"]:
            entry = "deb %s://archive.ubuntu.com/ubuntu/ hardy main universe restricted multiverse" % scheme
            self.assertTrue(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                            "entry '%s' not downloadable" % entry)
            entry = "deb %s://archive.ubuntu.com/ubuntu/ warty main universe restricted multiverse" % scheme
            self.assertFalse(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                            "entry '%s' not downloadable" % entry)
            entry = "deb %s://archive.ubuntu.com/ubuntu/ xxx main" % scheme
            self.assertFalse(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                            "entry '%s' not downloadable" % entry)

    def testEOL2EOLUpgrades(self):
        " test upgrade from EOL release to EOL release "
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir,"sources.list.EOL"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.fromDist = "warty"
        d.toDist = "hoary"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)
        self._verifySources("""
# main repo
deb http://old-releases.ubuntu.com/ubuntu hoary main restricted multiverse universe
deb-src http://old-releases.ubuntu.com/ubuntu hoary main restricted multiverse

deb http://old-releases.ubuntu.com/ubuntu hoary-security main restricted
""")

    def testEOL2SupportedWithMirrorUpgrade(self):
        " test upgrade from a EOL release to a supported release with mirror"
        os.environ["LANG"] = "de_DE.UTF-8"
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir,"sources.list.EOL2Supported"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.fromDist = "gutsy"
        d.toDist = "hardy"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)
        self._verifySources("""
# main repo
deb http://de.archive.ubuntu.com/ubuntu hardy main restricted multiverse universe
deb-src http://de.archive.ubuntu.com/ubuntu hardy main restricted multiverse

deb http://de.archive.ubuntu.com/ubuntu hardy-security main restricted
""")

    def testEOL2SupportedUpgrade(self):
        " test upgrade from a EOL release to a supported release "
        os.environ["LANG"] = "C"
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir,"sources.list.EOL2Supported"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.fromDist = "gutsy"
        d.toDist = "hardy"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)
        self._verifySources("""
# main repo
deb http://archive.ubuntu.com/ubuntu hardy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu hardy main restricted multiverse

deb http://archive.ubuntu.com/ubuntu hardy-security main restricted
""")

    def test_partner_update(self):
        """
        test transition partner repository updates
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.partner"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted universe multiverse

deb http://archive.canonical.com/ubuntu gutsy partner
""")

    def test_apt_cacher_and_apt_bittorent(self):
        """
        test transition of apt-cacher/apt-torrent uris
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.apt-cacher"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v,datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
deb http://localhost:9977/security.ubuntu.com/ubuntu gutsy-security main restricted
deb http://localhost:9977/archive.canonical.com/ubuntu gutsy partner
deb http://localhost:9977/us.archive.ubuntu.com/ubuntu/ gutsy main
deb http://localhost:9977/archive.ubuntu.com/ubuntu/ gutsy main

deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security universe

deb http://archive.canonical.com/ubuntu gutsy partner
""")

        
    def _verifySources(self, expected):
        sources_list = open(apt_pkg.config.find_file("Dir::Etc::sourcelist")).read()
        for l in expected.split("\n"):
            self.assert_(l in sources_list,
                         "expected entry '%s' in sources.list missing. got:\n'''%s'''" % (l, sources_list))
        

if __name__ == "__main__":
    import sys
    for e in sys.argv:
        if e == "-v":
            logging.basicConfig(level=logging.DEBUG)
    unittest.main()
