#!/usr/bin/python

import unittest
import tempfile
import shutil
import sys
import os.path
import apt_pkg
sys.path.insert(0,"../")

from DistUpgrade.DistUpgradeController import DistUpgradeController, NoBackportsFoundException
from DistUpgrade.DistUpgradeView import DistUpgradeView

class testPreRequists(unittest.TestCase):
    " this test the prerequists fetching "

    testdir = os.path.abspath("./data-sources-list-test/")

    def setUp(self):
        apt_pkg.config.set("Dir::Etc",self.testdir)
        apt_pkg.config.set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        self.dc = DistUpgradeController(DistUpgradeView(),
                                        datadir=self.testdir)
    def testPreReqSourcesListAddingSimple(self):
        " test adding the prerequists when a mirror is known "
        shutil.copy(os.path.join(self.testdir,"sources.list.in"),
                    os.path.join(self.testdir,"sources.list"))
        template = os.path.join(self.testdir,"prerequists-sources.list.in")
        out = os.path.join(self.testdir,"sources.list.d",
                           "prerequists-sources.list")
        self.dc._addPreRequistsSourcesList(template, out)
        self.assert_(os.path.getsize(out))
        self._verifySources(out, """
deb http://old-releases.ubuntu.com/ubuntu/ feisty-backports main/debian-installer
""")


    def testPreReqSourcesListAddingNoMultipleIdenticalLines(self):
        """ test adding the prerequists and ensure that no multiple
            identical lines are added
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.no_archive_u_c"),
                    os.path.join(self.testdir,"sources.list"))
        template = os.path.join(self.testdir,"prerequists-sources.list.in")
        out = os.path.join(self.testdir,"sources.list.d",
                           "prerequists-sources.list")
        self.dc._addPreRequistsSourcesList(template, out)
        self.assert_(os.path.getsize(out))
        self._verifySources(out, """
deb http://old-releases.ubuntu.com/ubuntu/ feisty-backports main/debian-installer
""")

    def testVerifyBackportsNotFound(self):
        " test the backport verification "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir,"sources.list.minimal"),
                    os.path.join(self.testdir,"sources.list"))
        tmpdir = tempfile.mkdtemp()
        # unset sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        # write empty status file
        open(tmpdir+"/status","w")
        os.makedirs(tmpdir+"/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir+"/status")
        self.dc.openCache(lock=False)
        exp = False
        try:
            res = self.dc._verifyBackports()
            print res
        except NoBackportsFoundException:
            exp = True
        self.assert_(exp == True)

    def disabled__because_of_jaunty_EOL_testVerifyBackportsValid(self):
        " test the backport verification "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir,"sources.list.minimal"),
                    os.path.join(self.testdir,"sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",self.testdir+"/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(self.testdir,"prerequists-sources.list.in")
        out = os.path.join(tmpdir,"prerequists-sources.list")
        # write empty status file
        open(tmpdir+"/status","w")
        os.makedirs(tmpdir+"/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir+"/status")
        self.dc._addPreRequistsSourcesList(template, out)
        self.dc.openCache(lock=False)
        res = self.dc._verifyBackports()
        self.assert_(res == True)

    def disabled__because_of_jaunty_EOL_testVerifyBackportsNoValidMirror(self):
        " test the backport verification with no valid mirror "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir,"sources.list.no_valid_mirror"),
                    os.path.join(self.testdir,"sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",self.testdir+"/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(self.testdir,"prerequists-sources.list.in.no_archive_falllback")
        out = os.path.join(tmpdir,"prerequists-sources.list")
        # write empty status file
        open(tmpdir+"/status","w")
        os.makedirs(tmpdir+"/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir+"/status")
        self.dc._addPreRequistsSourcesList(template, out, dumb=True)
        self.dc.openCache(lock=False)
        res = self.dc._verifyBackports()
        self.assert_(res == True)

    def disabled__because_of_jaunty_EOL_testVerifyBackportsNoValidMirror2(self):
        " test the backport verification with no valid mirror "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir,"sources.list.no_valid_mirror"),
                    os.path.join(self.testdir,"sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",self.testdir+"/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(self.testdir,"prerequists-sources.list.in.broken")
        out = os.path.join(tmpdir,"prerequists-sources.list")
        # write empty status file
        open(tmpdir+"/status","w")
        os.makedirs(tmpdir+"/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir+"/status")
        try:
            self.dc._addPreRequistsSourcesList(template, out, dumb=False)
            self.dc.openCache(lock=False)
            self.dc._verifyBackports()
        except NoBackportsFoundException:
            exp = True
        self.assert_(exp == True)
    
    def _verifySources(self, filename, expected):
        sources_list = open(filename).read()
        for l in expected.split("\n"):
            if l:
                self.assert_(l in sources_list,
                             "expected entry '%s' in '%s' missing, got:\n%s" % (l, filename, open(filename).read()))

if __name__ == "__main__":
    unittest.main()
