# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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
import gettext
import gtk
import logging
import os
import sys
import xapian

from gettext import gettext as _

from softwarecenter.enums import *

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class InstalledPane(SoftwarePane):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        # state
        self.apps_filter = AppViewFilter(db, cache)
        self.apps_filter.set_installed_only(True)
        self.current_appview_selection = None
        # UI
        self._build_ui()
    def _build_ui(self):
        self.navigation_bar.set_size_request(26, -1)
        self.notebook.append_page(self.scroll_app_list, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))
        # initial refresh
        self.search_terms = ""
        self.refresh_apps()

    def _show_installed_overview(self):
        " helper that goes back to the overview page "
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
        
    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear()
        self.navigation_bar.remove_id("search")

    @wait_for_apt_cache_ready
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        if self.search_terms:
            query = self.db.get_query_list_from_search_entry(self.search_terms)
            self.navigation_bar.add_with_id(_("Search Results"),
                                            self.on_navigation_search, 
                                            "search")
        else:
            query = None
        self.navigation_bar.add_with_id(_("Installed Software"), 
                                        self.on_navigation_list,
                                        "list",
                                        animate=False)
        # deactivate the old model, otherwise we have a memleak and
        # a cpu leak
        self.app_view.clear_model()
        # get a new store and attach it to the view
        new_model = AppStore(self.cache,
                             self.db, 
                             self.icons, 
                             query, 
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        self.emit("app-list-changed", len(new_model))
        return False
    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)
        self.search_terms = terms
        if not self.search_terms:
            self._clear_search()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
    def on_db_reopen(self, db):
        self.refresh_apps()
        self._show_installed_overview()
        
    def on_navigation_search(self, pathbar, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()
        
    def on_navigation_list(self, pathbar, part):
        """callback when the navigation button with id 'list' is clicked"""
        if not pathbar.get_active():
            return
        self._clear_search()
        self._show_installed_overview()
        # only emit something if the model is there
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))

    def on_navigation_details(self, pathbar, part):
        """callback when the navigation button with id 'details' is clicked"""
        if not pathbar.get_active():
            return
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
        
    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def display_search(self):
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()
    
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return ""
        # otherwise, show status based on search or not
        model = self.app_view.get_model()
        if not model:
            return ""
        length = len(model)
        if len(self.searchentry.get_text()) > 0:
            return gettext.ngettext("%s matching item",
                                    "%s matching items",
                                    length) % length
        else:
            return gettext.ngettext("%s item installed",
                                    "%s items installed",
                                    length) % length
                                    
    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    db = xapian.Database(pathname)
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    cache = apt.Cache(apt.progress.text.OpProgress())
    cache.ready = True

    w = InstalledPane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(400, 600)
    win.show_all()

    gtk.main()

