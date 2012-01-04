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
from softwarecenter.utils import *

from appview import AppView, AppStore, AppViewFilter
from catview import CategoriesView

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

from widgets.backforward import BackForwardButton

from navhistory import *

class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    DEFAULT_SEARCH_APPS_LIMIT = 200

    (PAGE_CATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(3)

    # define ID values for the various buttons found in the navigation bar
    NAV_BUTTON_ID_CATEGORY = "category"
    NAV_BUTTON_ID_LIST     = "list"
    NAV_BUTTON_ID_SUBCAT   = "subcat"
    NAV_BUTTON_ID_DETAILS  = "details"
    NAV_BUTTON_ID_SEARCH   = "search"

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir)
        # state
        self.apps_category = None
        self.apps_subcategory = None
        self.apps_search_term = ""
        self.apps_sorted = True
        self.apps_limit = 0
        self.apps_filter = AppViewFilter(db, cache)
        self.apps_filter.set_only_packages_without_applications(True)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self._status_text = ""
        self.connect("app-list-changed", self._on_app_list_changed)
        self.current_app_by_category = {}
        self.current_app_by_subcategory = {}
        # track navigation history
        self.nav_history = NavigationHistory(self)
        # UI
        self._build_ui()

    def _build_ui(self):
        # categories, appview and details into the notebook in the bottom
        self.cat_view = CategoriesView(self.datadir, APP_INSTALL_PATH,
                                       self.db,
                                       self.icons)
        scroll_categories = gtk.ScrolledWindow()
        scroll_categories.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_categories.add(self.cat_view)
        self.notebook.append_page(scroll_categories, gtk.Label("categories"))
        # sub-categories view
        self.subcategories_view = CategoriesView(self.datadir,
                                                 APP_INSTALL_PATH,
                                                 self.db,
                                                 self.icons,
                                                 self.cat_view.categories[0])
        self.subcategories_view.connect(
            "category-selected", self.on_subcategory_activated)
        self.scroll_subcategories = gtk.ScrolledWindow()
        self.scroll_subcategories.set_policy(
            gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll_subcategories.add(self.subcategories_view)
        # add nav history back/forward buttons
        self.back_forward = BackForwardButton()
        self.back_forward.left.set_sensitive(False)
        self.back_forward.right.set_sensitive(False)
        self.back_forward.connect("left-clicked", self.on_nav_back_clicked)
        self.back_forward.connect("right-clicked", self.on_nav_forward_clicked)
        self.top_hbox.pack_start(self.back_forward, expand=False, padding=self.PADDING)
        # nav buttons first in the panel
        self.top_hbox.reorder_child(self.back_forward, 0)
        # now a vbox for subcategories and applist
        self.apps_vbox = gtk.VPaned()
        self.apps_vbox.pack1(self.scroll_subcategories, resize=True)
        self.apps_vbox.pack2(self.scroll_app_list)
        # app list
        self.cat_view.connect("category-selected", self.on_category_activated)
        self.notebook.append_page(self.apps_vbox, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label(self.NAV_BUTTON_ID_DETAILS))
        # set status text
        self._update_status_text(len(self.db))
        # home button
        self.navigation_bar.add_with_id(_("Get Software"),
                                        self.on_navigation_category,
                                        self.NAV_BUTTON_ID_CATEGORY,
                                        do_callback=True,
                                        animate=False)

    def _get_query(self):
        """helper that gets the query for the current category/search mode"""
        # NoDisplay is a specal case
        if self._in_no_display_category():
            return xapian.Query()
        # get current sub-category (or category, but sub-category wins)
        cat_query = None
        if self.apps_subcategory:
            cat_query = self.apps_subcategory.query
        elif self.apps_category:
            cat_query = self.apps_category.query
        # mix category with the search terms and return query
        return self.db.get_query_list_from_search_entry(self.apps_search_term,
                                                        cat_query)

    def _in_no_display_category(self):
        """return True if we are in a category with NoDisplay set in the XML"""
        return (self.apps_category and
                self.apps_category.dont_display and
                not self.apps_subcategory and
                not self.apps_search_term)

    def _show_hide_subcategories(self):
        # check if have subcategories and are not in a subcategory
        # view - if so, show it
        if (self.apps_category and
            self.apps_category.subcategories and
            not (self.apps_search_term or self.apps_subcategory)):
            self.scroll_subcategories.show()
            self.subcategories_view.set_subcategory(self.apps_category)
        else:
            self.scroll_subcategories.hide()

    def _show_hide_applist(self):
        # now check if the apps_category view has entries and if
        # not hide it
        model = self.app_view.get_model()
        if (model and
            len(model) == 0 and
            self.apps_category and
            self.apps_category.subcategories and
            not self.apps_subcategory):
            self.scroll_app_list.hide()
        else:
            self.scroll_app_list.show()

    def refresh_apps(self):
        """refresh the applist after search changes and update the
           navigation bar
        """
        #import traceback
        #print "refresh_apps"
        #print traceback.print_stack()
        logging.debug("refresh_apps")
        # mvo: its important to fist show the subcategories and then
        #      the new model, otherwise we run into visual lack
        self._show_hide_subcategories()
        self._refresh_apps_with_apt_cache()

    @wait_for_apt_cache_ready
    def _refresh_apps_with_apt_cache(self):
        self.refresh_seq_nr += 1
        # build query
        query = self._get_query()
        logging.debug("availablepane query: %s" % query)
        # deactivate the old model, otherwise we have a memleak and
        # a cpu leak
        self.app_view.clear_model()
        # create new model and attach it
        seq_nr = self.refresh_seq_nr
        if self.app_view.window:
            self.app_view.window.set_cursor(self.busy_cursor)
        if self.subcategories_view.window:
            self.subcategories_view.window.set_cursor(self.busy_cursor)
        if self.apps_vbox.window:
            self.apps_vbox.window.set_cursor(self.busy_cursor)
        new_model = AppStore(self.cache,
                             self.db,
                             self.icons,
                             query,
                             limit=self.apps_limit,
                             sort=self.apps_sorted,
                             filter=self.apps_filter)
        # between request of the new model and actual delivery other
        # events may have happend
        if seq_nr != self.refresh_seq_nr:
            logging.info("discarding new model (%s != %s)" % (seq_nr, self.refresh_seq_nr))
            return False

        # set model
        self.app_view.set_model(new_model)
        # check if we show subcategoriy
        self._show_hide_applist()
        self.emit("app-list-changed", len(new_model))
        if self.app_view.window:
            self.app_view.window.set_cursor(None)
        if self.subcategories_view.window:
            self.subcategories_view.window.set_cursor(None)
        if self.apps_vbox.window:
            self.apps_vbox.window.set_cursor(None)
        return False

    def update_navigation_button(self):
        """Update the navigation button"""
        if self.apps_category and not self.apps_search_term:
            cat =  self.apps_category.name
            self.navigation_bar.add_with_id(cat,
                                            self.on_navigation_list,
                                            self.NAV_BUTTON_ID_LIST, 
                                            do_callback=True, 
                                            animate=True)

        elif self.apps_search_term:
            self.navigation_bar.add_with_id(_("Search Results"),
                                            self.on_navigation_search,
                                            self.NAV_BUTTON_ID_SEARCH, 
                                            do_callback=True,
                                            animate=True)

    # status text woo
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if (self.notebook.get_current_page() == self.PAGE_APP_DETAILS or
            self._in_no_display_category()):
            return ""
        return self._status_text

    def get_current_app(self):
        """return the current active application object"""
        if self.is_category_view_showing():
            return None
        else:
            if self.apps_subcategory:
                return self.current_app_by_subcategory.get(self.apps_subcategory)
            else:
                return self.current_app_by_category.get(self.apps_category)

    def reset_navigation_history(self):
        """
        reset the navigation history and set the history buttons insensitive
        """
        self.nav_history.reset()
        self.back_forward.left.set_sensitive(False)
        self.back_forward.right.set_sensitive(False)

    def _on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text up-to-date by
           keeping track of the app-list-changed signals
        """
        self._update_status_text(length)

    def _update_status_text(self, length):
        """
        update the text in the status bar
        """
        # SPECIAL CASE: in category page show all items in the DB
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            length = len(self.db)

        if len(self.searchentry.get_text()) > 0:
            self._status_text = gettext.ngettext("%s matching item",
                                                 "%s matching items",
                                                 length) % length
        else:
            self._status_text = gettext.ngettext("%s item available",
                                                 "%s items available",
                                                 length) % length

    def _show_category_overview(self):
        " helper that shows the category overview "
        # reset category query
        self.apps_category = None
        self.apps_subcategory = None
        # remove pathbar stuff
        self.navigation_bar.remove_all()
        self.notebook.set_current_page(self.PAGE_CATEGORY)
        self.emit("app-list-changed", len(self.db))
        self.searchentry.show()

    def _clear_search(self):
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_sorted = True
        self.apps_search_term = ""
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_SEARCH)

    def _check_nav_history(self, display_cb):
        if self.navigation_bar.get_last().label != self.nav_history.get_last_label():
            nav_item = NavigationItem(self, display_cb)
            self.nav_history.navigate_no_cursor_step(nav_item)
        return

    # callbacks
    def on_cache_ready(self, cache):
        """ refresh the application list when the cache is re-opened """
        # just re-draw in the available pane, nothing but the
        # "is-installed" overlay icon will change when something
        # is installed or removed in the available pane
        self.app_view.queue_draw()

    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: %s" % new_text)

        # we got the signal after we already switched to a details
        # page, ignore it
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in any category
        if not self.apps_category and not new_text:
            # category activate will clear search etc
            self.navigation_bar.navigate_up()
            return

        # if the user searches in the "all categories" page, reset the specific
        # category query (to ensure all apps are searched)
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            self.apps_category = None
            self.apps_subcategory = None

        # DTRT if the search is reseted
        if not new_text:
            self._clear_search()
        else:
            self.apps_search_term = new_text
            self.apps_sorted = False
            self.apps_limit = self.DEFAULT_SEARCH_APPS_LIMIT
        self.update_navigation_button()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)

    def on_db_reopen(self, db):
        " called when the database is reopened"
        #print "on_db_open"
        self.refresh_apps()
        self._show_category_overview()

    def display_category(self):
        self._clear_search()
        self._show_category_overview()
        return

    def display_search(self):
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        if self.app_view.get_model():
            list_length = len(self.app_view.get_model())
            self.emit("app-list-changed", list_length)
        self.searchentry.show()
        return

    def display_list(self):
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_SUBCAT)
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)

        if self.apps_subcategory:
            self.apps_subcategory = None
        self.set_category(self.apps_category)
        if self.apps_search_term:
            self._clear_search()
            self.refresh_apps()

        self.notebook.set_current_page(self.PAGE_APPLIST)
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.searchentry.show()
        return

    def display_list_subcat(self):
        if self.apps_search_term:
            self._clear_search()
            self.refresh_apps()
        self.set_category(self.apps_subcategory)
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        model = self.app_view.get_model()
        if model is not None:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()
        return

    def display_details(self):
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
        return

    def on_navigation_category(self, pathbar, part):
        """callback when the navigation button with id 'category' is clicked"""
        # clear the search
        self.display_category()
        nav_item = NavigationItem(self, self.display_category)
        self.nav_history.navigate(nav_item)

    def on_navigation_search(self, pathbar, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()
        nav_item = NavigationItem(self, self.display_search)
        self.nav_history.navigate(nav_item)

    def on_navigation_list(self, pathbar, part):
        """callback when the navigation button with id 'list' is clicked"""
        self.display_list()
        nav_item = NavigationItem(self, self.display_list)
        self.nav_history.navigate(nav_item)

    def on_navigation_list_subcategory(self, pathbar, part):
        self.display_list_subcat()
        nav_item = NavigationItem(self, self.display_list_subcat)
        self.nav_history.navigate(nav_item)

    def on_navigation_details(self, pathbar, part):
        """callback when the navigation button with id 'details' is clicked"""
        self.display_details()
        nav_item = NavigationItem(self, self.display_details)
        self.nav_history.navigate(nav_item)

    def on_subcategory_activated(self, cat_view, category):
        #print cat_view, name, query
        logging.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.apps_subcategory = category
        #self._check_nav_history(self.display_list)
        self.navigation_bar.add_with_id(
            category.name, self.on_navigation_list_subcategory, self.NAV_BUTTON_ID_SUBCAT)

    def on_category_activated(self, cat_view, category):
        """ callback when a category is selected """
        #print cat_view, name, query
        logging.debug("on_category_activated: %s %s" % (
                category.name, category))
        self.apps_category = category
        self.update_navigation_button()

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)

        if self.apps_subcategory:
            #self._check_nav_history(self.display_list_subcat)
            self.current_app_by_subcategory[self.apps_subcategory] = app
        else:
            #self._check_nav_history(self.display_list)
            self.current_app_by_category[self.apps_category] = app

    def on_nav_back_clicked(self, widget, event):
        self.nav_history.nav_back()

    def on_nav_forward_clicked(self, widget, event):
        self.nav_history.nav_forward()

    def is_category_view_showing(self):
        # check if we are in the category page or if we display a
        # sub-category page that has no visible applications
        return (self.notebook.get_current_page() == self.PAGE_CATEGORY or
                not self.scroll_app_list.props.visible)

    def set_category(self, category):
        #print "set_category", category
        #import traceback
        #traceback.print_stack()
        self.update_navigation_button()
        def _cb():
            self.refresh_apps()
            # this is already done earlier
            #self.notebook.set_current_page(self.PAGE_APPLIST)
            return False
        gobject.timeout_add(1, _cb)
        pass

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

    w = AvailablePane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(500,400)
    win.show_all()

    gtk.main()

