#!/usr/bin/python

import apt
import apt_pkg
import hashlib
import mock
import unittest
import shutil
import sys
import tempfile

sys.path.insert(0,"../")
from DistUpgrade.DistUpgradeQuirks import DistUpgradeQuirks

class MockController(object):
    def __init__(self):
        self._view = None

class MockConfig(object):
    pass

class TestQuirks(unittest.TestCase):

    def test_enable_recommends_during_upgrade(self):
        controller = mock.Mock()

        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        # server mode
        apt_pkg.config.set("APT::Install-Recommends", "0")
        controller.serverMode = True
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        q.ensure_recommends_are_installed_on_desktops()
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        # desktop mode
        apt_pkg.config.set("APT::Install-Recommends", "0")
        controller.serverMode = False
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        q.ensure_recommends_are_installed_on_desktops()
        self.assertTrue(apt_pkg.config.find_b("APT::Install-Recommends"))

    def test_parse_from_modaliases_header(self):
        pkgrec = { "Package" : "foo",
                   "Modaliases" : "modules1(pci:v00001002d00006700sv*sd*bc03sc*i*, pci:v00001002d00006701sv*sd*bc03sc*i*), module2(pci:v00001002d00006702sv*sd*bc03sc*i*, pci:v00001001d00006702sv*sd*bc03sc*i*)"
                 }
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        self.assertEqual(q._parse_modaliases_from_pkg_header({}), [])
        self.assertEqual(q._parse_modaliases_from_pkg_header(pkgrec),
                         [("modules1",
                           ["pci:v00001002d00006700sv*sd*bc03sc*i*", "pci:v00001002d00006701sv*sd*bc03sc*i*"]),
                         ("module2",
                          ["pci:v00001002d00006702sv*sd*bc03sc*i*", "pci:v00001001d00006702sv*sd*bc03sc*i*"]) ])

    def testFglrx(self):
        mock_lspci_good = set(['1002:9714'])
        mock_lspci_bad = set(['8086:ac56'])
        config = mock.Mock()
        cache = apt.Cache()
        controller = mock.Mock()
        controller.cache = cache
        q = DistUpgradeQuirks(controller, config)
        self.assert_(q._supportInModaliases("fglrx",
                                            mock_lspci_good) == True)
        self.assert_(q._supportInModaliases("fglrx",
                                            mock_lspci_bad) == False)

    def test_cpuHasSSESupport(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-with-sse") == True)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-without-sse") == False)

    def test_cpu_is_i686(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        q.arch = "i386"
        self.assertTrue(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-with-sse"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-without-cmov"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-i586"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-i486"))
        self.assertTrue(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-via-c7m"))

    def _verify_result_checksums(self):
        """ helper for test_patch to verify that we get the expected result """
        # simple case is foo
        self.assertFalse("Hello" in open("./patchdir/foo").read())
        self.assertTrue("Hello" in open("./patchdir/foo_orig").read())
        md5 = hashlib.md5()
        md5.update(open("./patchdir/foo").read())
        self.assertEqual(md5.hexdigest(), "52f83ff6877e42f613bcd2444c22528c")
        # more complex example fstab
        md5 = hashlib.md5()
        md5.update(open("./patchdir/fstab").read())
        self.assertEqual(md5.hexdigest(), "c56d2d038afb651920c83106ec8dfd09")
        # most complex example
        md5 = hashlib.md5()
        md5.update(open("./patchdir/pycompile").read())
        self.assertEqual(md5.hexdigest(), "97c07a02e5951cf68cb3f86534f6f917")
        # with ".\n"
        md5 = hashlib.md5()
        md5.update(open("./patchdir/dotdot").read())
        self.assertEqual(md5.hexdigest(), "cddc4be46bedd91db15ddb9f7ddfa804")
        # test that incorrect md5sum after patching rejects the patch
        self.assertEqual(open("./patchdir/fail").read(),
                         open("./patchdir/fail_orig").read())

    def test_patch(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        # create patch environment
        shutil.copy("./patchdir/foo_orig", "./patchdir/foo")
        shutil.copy("./patchdir/fstab_orig", "./patchdir/fstab")
        shutil.copy("./patchdir/pycompile_orig", "./patchdir/pycompile")
        shutil.copy("./patchdir/dotdot_orig", "./patchdir/dotdot")
        shutil.copy("./patchdir/fail_orig", "./patchdir/fail")
        # apply patches
        q._applyPatches(patchdir="./patchdir")
        self._verify_result_checksums()
        # now apply patches again and ensure we don't patch twice
        q._applyPatches(patchdir="./patchdir")
        self._verify_result_checksums()

    def test_patch_lowlevel(self):
        #test lowlevel too
        from DistUpgrade.DistUpgradePatcher import patch, PatchError
        self.assertRaises(PatchError, patch, "./patchdir/fail", "patchdir/patchdir_fail.ed04abbc6ee688ee7908c9dbb4b9e0a2.deadbeefdeadbeefdeadbeff", "deadbeefdeadbeefdeadbeff")

    def test_ntfs_fstab(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        shutil.copy("./test-data/fstab.ntfs.orig", "./test-data/fstab.ntfs")
        self.assertTrue("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 1" in open("./test-data/fstab.ntfs").read())
        q._ntfsFstabFixup(fstab="./test-data/fstab.ntfs")
        self.assertTrue(open("./test-data/fstab.ntfs").read().endswith("0\n"))
        self.assertTrue("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 0" in open("./test-data/fstab.ntfs").read())
        self.assertFalse("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 1" in open("./test-data/fstab.ntfs").read())

    def test_kde_card_games_transition(self):
        # fake nothing is installed
        empty_status = tempfile.NamedTemporaryFile()
        apt_pkg.config.set("Dir::state::status", empty_status.name)

        # create quirks class
        controller = mock.Mock()
        config = mock.Mock()
        quirks = DistUpgradeQuirks(controller, config)
        # add cache to the quirks class
        cache = quirks.controller.cache = apt.Cache()
        # add mark_install to the cache (this is part of mycache normally)
        cache.mark_install = lambda p, s: cache[p].mark_install()

        # test if the quirks handler works when kdegames-card is not installed
        # does not try to install it
        self.assertFalse(cache["kdegames-card-data-extra"].marked_install)
        quirks._add_kdegames_card_extra_if_installed()
        self.assertFalse(cache["kdegames-card-data-extra"].marked_install)

        # mark it for install
        cache["kdegames-card-data"].mark_install()
        self.assertFalse(cache["kdegames-card-data-extra"].marked_install)
        quirks._add_kdegames_card_extra_if_installed()
        # verify that the quirks handler is now installing it
        self.assertTrue(cache["kdegames-card-data-extra"].marked_install)  

    def test_screensaver_poke(self):
        # fake nothing is installed
        empty_status = tempfile.NamedTemporaryFile()
        apt_pkg.config.set("Dir::state::status", empty_status.name)

        # create quirks class
        controller = mock.Mock()
        config = mock.Mock()
        quirks = DistUpgradeQuirks(controller, config)
        quirks._pokeScreensaver()
        res = quirks._stopPokeScreensaver()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
