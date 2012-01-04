# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# Parts taken from gnome-app-install:utils.py (also written by Michael Vogt)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import apt
import apt_pkg
import datetime
import locale
import gettext
import gio
import glib
import gobject
import gtk
import os
import subprocess
import time

from gettext import gettext as _

class GtkMainIterationProgress(apt.progress.base.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent):
        while gtk.events_pending():
            gtk.main_iteration()

class AptCache(gobject.GObject):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends")
    RECOMMENDS_TYPES = ("Recommends",)
    SUGGESTS_TYPES = ("Suggests",)

    # stamp file to monitor (provided by update-notifier via
    # APT::Update::Post-Invoke-Success)
    APT_FINISHED_STAMP = "/var/lib/update-notifier/dpkg-run-stamp"

    __gsignals__ = {'cache-ready':  (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-invalid':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self._cache = None
        self._ready = False
        self._timeout_id = None
        # async open cache
        glib.timeout_add(100, self.open)
        # setup monitor watch for install/remove changes
        self.apt_finished_stamp=gio.File(self.APT_FINISHED_STAMP)
        self.apt_finished_monitor = self.apt_finished_stamp.monitor_file(
            gio.FILE_MONITOR_NONE)
        self.apt_finished_monitor.connect(
            "changed", self._on_apt_finished_stamp_changed)
    def _on_apt_finished_stamp_changed(self, monitor, afile, other_file, event):
        if not event == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            return 
        if self._timeout_id:
            glib.source_remove(self._timeout_id)
            self._timeout_id = None
        self._timeout_id = glib.timeout_add_seconds(10, self.open)
    @property
    def ready(self):
        return self._ready
    def open(self):
        self._ready = False
        self.emit("cache-invalid")
        if self._cache == None:
            self._cache = apt.Cache(GtkMainIterationProgress())
        else:
            self._cache.open(GtkMainIterationProgress())
        self._ready = True
        self.emit("cache-ready")
    def __getitem__(self, key):
        return self._cache[key]
    def __iter__(self):
        return self._cache.__iter__()
    def __contains__(self, k):
        return self._cache.__contains__(k)

    def _get_installed_rdepends_by_type(self, pkg, type):
        installed_rdeps = set()
        for rdep in pkg._pkg.rev_depends_list:
            dep_type = rdep.dep_type_untranslated
            if dep_type in type:
                rdep_name = rdep.parent_pkg.name
                if (rdep_name in self._cache and
                    self._cache[rdep_name].is_installed):
                    installed_rdeps.add(rdep.parent_pkg.name)
        return installed_rdeps
    def _installed_dependencies(self, pkg_name, all_deps=None):
        """ recursively return all installed dependencies of a given pkg """
        #print "_installed_dependencies", pkg_name, all_deps
        if not all_deps:
            all_deps = set()
        if pkg_name not in self._cache:
            return all_deps
        cur = self._cache[pkg_name]._pkg.current_ver
        if not cur:
            return all_deps
        for t in self.DEPENDENCY_TYPES+self.RECOMMENDS_TYPES:
            try:
                for dep in cur.depends_list[t]:
                    dep_name = dep[0].target_pkg.name
                    if not dep_name in all_deps:
                        all_deps.add(dep_name)
                        all_deps |= self._installed_dependencies(dep_name, all_deps)
            except KeyError:
                pass
        return all_deps
    def get_installed_automatic_depends_for_pkg(self, pkg):
        """ Get the installed automatic dependencies for this given package
            only.

            Note that the package must be marked for removal already for
            this to work
        """
        installed_auto_deps = set()
        deps = self._installed_dependencies(pkg.name)
        for dep_name in deps:
            try:
                pkg = self._cache[dep_name]
            except KeyError:
                continue
            else:
                if (pkg.is_installed and 
                    pkg.is_auto_removable):
                    installed_auto_deps.add(dep_name)
        return installed_auto_deps
    def get_origins(self):
        """
        return a set of the current channel origins from the apt.Cache itself
        """
        origins = set()
        for pkg in self._cache:
            if not pkg.candidate:
                continue
            for item in pkg.candidate.origins:
                while gtk.events_pending():
                    gtk.main_iteration()
                if item.origin:
                    origins.add(item.origin)
        return origins
    def get_installed_rdepends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.DEPENDENCY_TYPES)
    def get_installed_rrecommends(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.RECOMMENDS_TYPES)
    def get_installed_rsuggests(self, pkg):
        return self._get_installed_rdepends_by_type(pkg, self.SUGGESTS_TYPES)
    def component_available(self, distro_codename, component):
        """ check if the given component is enabled """
        # FIXME: test for more properties here?
        for it in self._cache._cache.file_list:
            if (it.component != "" and 
                it.component == component and
                it.archive != "" and 
                it.archive == distro_codename):
                return True
        return False

if __name__ == "__main__":
    c = AptCache()
    c.open()
    print "deps of unrar"
    print c._installed_dependencies(c["unrar"].name)

    print "unused deps of 4g8"
    pkg = c["4g8"]
    pkg.mark_delete()
    print c.get_installed_automatic_depends_for_pkg(pkg)

    pkg = c["unace"]
    print c.get_installed_automatic_depends_for_pkg(pkg)
    print c.get_installed_rdepends(pkg)
    print c.get_installed_rrecommends(pkg)
    print c.get_installed_rsuggests(pkg)
