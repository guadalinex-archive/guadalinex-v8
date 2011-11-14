#!/usr/bin/python


import apt
import logging
import sys
import unittest
import urllib2

sys.path.insert(0, "../")
from UpdateManager.Core.MyCache import MyCache

class TestChangelogs(unittest.TestCase):

    def setUp(self):
        self.cache = MyCache(apt.progress.base.OpProgress())

    def test_get_changelogs_uri(self):
        pkgname = "gcc"
        # test binary changelogs
        uri = self.cache._guess_third_party_changelogs_uri_by_binary(pkgname)
        pkg = self.cache[pkgname]
        self.assertEqual(uri,
                         pkg.candidate.uri.replace(".deb", ".changelog"))
        # test source changelogs
        uri = self.cache._guess_third_party_changelogs_uri_by_source(pkgname)
        self.assertTrue("gcc-defaults_" in uri)
        self.assertTrue(uri.endswith(".changelog"))
        # and one without a "Source" entry, we don't find something here
        self.assertEqual(self.cache._guess_third_party_changelogs_uri_by_source("apt"), None)
        # one with srcver == binver
        pkgname = "libgtk2.0-dev"
        uri = self.cache._guess_third_party_changelogs_uri_by_source(pkgname)
        pkg = self.cache[pkgname]
        self.assertTrue(pkg.candidate.version in uri)
        self.assertTrue("gtk+2.0" in uri)

    def test_changelog_not_supported(self):
        def monkey_patched_get_changelogs(name, what, ver, uri):
            raise urllib2.HTTPError(
                "url", "code", "msg", "hdrs", open("/dev/zero"))
        pkgname = "update-manager"
        # patch origin
        real_origin = self.cache.CHANGELOG_ORIGIN
        self.cache.CHANGELOG_ORIGIN = "xxx"
        # monkey patch to raise the right error
        self.cache._get_changelog_or_news = monkey_patched_get_changelogs
        # get changelog
        self.cache.get_changelog(pkgname)
	error = "This update does not come from a source that supports changelogs."
        # verify that we don't have the lines twice
	self.assertEqual(self.cache.all_changes[pkgname].split("\n")[-1], error)
	self.assertEqual(len(self.cache.all_changes[pkgname].split("\n")), 5)
	self.assertEqual(self.cache.all_changes[pkgname].count(error), 1)
        self.cache.CHANGELOG_ORIGIN = real_origin

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        logging.basicConfig(level=logging.DEBUG)
    unittest.main()
    

