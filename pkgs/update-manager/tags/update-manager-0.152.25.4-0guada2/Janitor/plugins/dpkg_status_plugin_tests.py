# dpkg_status.py - compact the dpkg status file
# Copyright (C) 2009  Canonical, Ltd.
#
# Author: Michael Vogt <mvo@ubuntu.com>
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


import os
import tempfile
import unittest

import dpkg_status_plugin


class AutoRemovalPluginTests(unittest.TestCase):

    def setUp(self):
        fd, self.fname = tempfile.mkstemp()
        os.write(fd, "Status: purge ok not-installed\n")
        os.close(fd)
        self.plugin = dpkg_status_plugin.DpkgStatusPlugin(self.fname)

    def tearDown(self):
        os.remove(self.fname)

    def testDpkgStatus(self):
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(sorted(names), sorted([u"dpkg-status:Obsolete entries in dpkg status"]))
