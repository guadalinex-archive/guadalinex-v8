# hello_plugin.py - a test plugin for Computer Janitor
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


import logging

import computerjanitor


class HelloPlugin(computerjanitor.Plugin):

    def get_cruft(self):
        cache = self.app.apt_cache
        if cache.has_key("hello"):
            pkg = cache["hello"]
            if pkg.is_installed:
                yield computerjanitor.PackageCruft(cache["hello"],
                                                 "We don't like hello.")

    def post_cleanup(self):
        logging.info("Post-cleanup for HelloPlugin called")
