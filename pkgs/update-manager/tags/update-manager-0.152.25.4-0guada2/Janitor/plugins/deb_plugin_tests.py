# deb_plugin_tests.py - unittests for deb_plugin.py
# Copyright (C) 2008  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import unittest

import deb_plugin


class MockApplication(object):

    def __init__(self):
        self.commit_called = False
        self.refresh_called = False
        self.apt_cache = self
        
    def commit(self, foo, bar):
        self.commit_called = True
        
    def refresh_apt_cache(self):
        self.refresh_called = True


class DebPluginTests(unittest.TestCase):

    def setUp(self):
        self.plugin = deb_plugin.DebPlugin()
        self.app = MockApplication()
        self.plugin.set_application(self.app)

    def testReturnsEmptyListOfCruft(self):
        self.assertEqual(self.plugin.get_cruft(), [])

    def testPostCleanupCallsCommit(self):
        self.plugin.post_cleanup()
        self.assert_(self.app.commit_called)
        
    def testPostCleanupCallsRefresh(self):
        self.plugin.post_cleanup()
        self.assert_(self.app.refresh_called)
