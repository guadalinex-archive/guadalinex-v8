# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt, Gary Lasker
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
import gobject

from gettext import gettext as _

from softwarecenter.enums import *
from softwarecenter.distro import get_distro

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class ChannelPane(SoftwarePane):
    """Widget that represents the channel pane for display of
       individual channels (PPAs, partner repositories, etc.)
       in software-center.
       It contains a search entry and navigation buttons.
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        self.channel = None
        self.apps_filter = None
        self.search_terms = ""
        self.current_appview_selection = None
        self.distro = get_distro()
        # UI
        self._build_ui()
        
    def _build_ui(self):
        self.notebook.append_page(self.scroll_app_list, gtk.Label("channel"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))

    def _show_channel_overview(self):
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
        if not self.channel:
            return
        self.refresh_seq_nr += 1
        channel_query = self.channel.get_channel_query()
        if self.search_terms:
            query = self.db.get_query_list_from_search_entry(self.search_terms,
                                                             channel_query)
            self.navigation_bar.add_with_id(_("Search Results"),
                                            self.on_navigation_search, 
                                            "search")
        else:
            self.navigation_bar.remove_all(keep_first_part=False)
            self.navigation_bar.add_with_id(self.channel.get_channel_display_name(),
                                        self.on_navigation_list,
                                        "list")
            query = xapian.Query(channel_query)

        logging.debug("channelpane query: %s" % query)
        # deactivate the old model, otherwise we have a memleak and
        # a cpu leak
        self.app_view.clear_model()
        gobject.idle_add(self._make_new_model, query, self.refresh_seq_nr)
        return False

    def _make_new_model(self, query, seq_nr):
        # get a new store and attach it to the view
        if self.scroll_app_list.window:
            self.scroll_app_list.window.set_cursor(self.busy_cursor)
        new_model = AppStore(self.cache,
                             self.db, 
                             self.icons, 
                             query, 
                             limit=0,
                             sort=True,
                             filter=self.apps_filter)
        # between request of the new model and actual delivery other
        # events may have happend
        if self.scroll_app_list.window:
            self.scroll_app_list.window.set_cursor(None)
        if seq_nr == self.refresh_seq_nr:
            self.app_view.set_model(new_model)
            self.emit("app-list-changed", len(new_model))
        else:
            logging.debug("discarding new model (%s != %s)" % (seq_nr, self.refresh_seq_nr))
        return False

    def set_channel(self, channel):
        """
        set the current software channel object for display in the channel pane
        and set up the AppViewFilter if required
        """
        self.channel = channel
        if self.channel.filter_required:
            self.apps_filter = AppViewFilter(self.db, self.cache)
            self.apps_filter.set_only_packages_without_applications(True)
        else:
            self.apps_filter = None
        # when displaying a new channel, clear any search in progress
        self.search_terms = ""
        
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
        self._show_channel_overview()

    def on_navigation_search(self, button, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()

    def on_navigation_list(self, button, part):
        """callback when the navigation button with id 'list' is clicked"""
        if not button.get_active():
            return
        self._clear_search()
        self._show_channel_overview()
        # only emit something if the model is there
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))

    def on_navigation_details(self, button, part):
        """callback when the navigation button with id 'details' is clicked"""
        if not button.get_active():
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
            length = len(self.app_view.get_model())
            self.emit("app-list-changed", length)
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
        length = len(self.app_view.get_model())
        if len(self.searchentry.get_text()) > 0:
            return gettext.ngettext("%s matching item",
                                    "%s matching items",
                                    length) % length
        else:
            return gettext.ngettext("%s item available",
                                    "%s items available",
                                    length) % length
                                    
    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the channel pane
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

    w = ChannelPane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(400, 600)
    win.show_all()

    gtk.main()

