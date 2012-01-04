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
import dbus
import glib
import gobject
import gtk
import logging
import pango
import os
import time
import xapian

import aptdaemon.client

from gettext import gettext as _

from softwarecenter.backend.channel import SoftwareChannel
from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *

from widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage

class ViewSwitcher(gtk.TreeView):

    __gsignals__ = {
        "view-changed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (int, gobject.TYPE_PYOBJECT),
                         ),
    }


    def __init__(self, datadir, db, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.datadir = datadir
        self.icons = icons
        if not store:
            store = ViewSwitcherList(datadir, db, icons)
            # FIXME: this is just set here for app.py, make the
            #        transactions-changed signal part of the view api
            #        instead of the model
            self.model = store
            self.set_model(store)
        gtk.TreeView.__init__(self)
        
        tp = CellRendererAnimatedImage()
        column = gtk.TreeViewColumn("Icon")
        column.pack_start(tp, expand=False)
        column.set_attributes(tp, image=store.COL_ICON)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column.pack_start(tr, expand=True)
        column.set_attributes(tr, markup=store.COL_NAME)
        self.append_column(column)

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))
        
        self.set_model(store)
        self.set_headers_visible(False)
        self.get_selection().set_select_function(self.on_treeview_selected)
        self.set_level_indentation(4)
        self.set_enable_search(False)

        self.selected_channel_name = None
        
        self.connect("row-expanded", self.on_treeview_row_expanded)
        self.connect("row-collapsed", self.on_treeview_row_collapsed)
        self.connect("cursor-changed", self.on_cursor_changed)

        self.get_model().connect("channels-refreshed", self._on_channels_refreshed)
        
    def on_treeview_row_expanded(self, widget, iter, path):
        # do nothing on a node expansion
        pass
        
    def on_treeview_row_collapsed(self, widget, iter, path):
        # on a node collapse, select the node
        self.set_cursor(path)
    
    def on_treeview_selected(self, path):
        if path[0] == ViewSwitcherList.ACTION_ITEM_SEPARATOR_1:
            return False
        return True
        
    def on_cursor_changed(self, widget):
        (path, column) = self.get_cursor()
        model = self.get_model()
        self.selected_channel_name = model[path][ViewSwitcherList.COL_NAME]
        action = model[path][ViewSwitcherList.COL_ACTION]
        channel = model[path][ViewSwitcherList.COL_CHANNEL]
        self.emit("view-changed", action, channel)
        
    def get_view(self):
        """return the current activated view number or None if no
           view is activated (this can happen when a pending view 
           disappeared). Views are:
           
           ViewSwitcherList.ACTION_ITEM_AVAILABLE
           ViewSwitcherList.ACTION_ITEM_CHANNEL
           ViewSwitcherList.ACTION_ITEM_INSTALLED
           ViewSwitcherList.ACTION_ITEM_PENDING
        """
        (path, column) = self.get_cursor()
        if not path:
            return None
        return path[0]
    def set_view(self, action):
        self.set_cursor((action,))
        self.emit("view-changed", action, None)
    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
            
    def expand_available_node(self):
        """ expand the available pane node in the viewswitcher pane """
        model = self.get_model()
        available_path = model.get_path(model.available_iter)
        self.expand_row(available_path, False)
            
    def is_available_node_expanded(self):
        """ return True if the available pane node in the viewswitcher pane is expanded """
        expanded = False
        model = self.get_model()
        if model:
            available_path = model.get_path(model.available_iter)
            expanded = self.row_expanded(available_path)
        return expanded

    def _on_channels_refreshed(self, model):
        """
        when channels are refreshed, the viewswitcher channel is unselected so
        we need to reselect it
        """
        model = self.get_model()
        if model:
            channel_iter_to_select = model.get_channel_iter_for_name(self.selected_channel_name)
            if channel_iter_to_select:
                self.set_cursor(model.get_path(channel_iter_to_select))

class ViewSwitcherList(gtk.TreeStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION,
     COL_CHANNEL) = range(4)

    # items in the treeview
    (ACTION_ITEM_AVAILABLE,
     ACTION_ITEM_INSTALLED,
     ACTION_ITEM_SEPARATOR_1,
     ACTION_ITEM_PENDING,
     ACTION_ITEM_CHANNEL) = range(5)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    __gsignals__ = {'channels-refreshed':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ())}

    def __init__(self, datadir, db, icons):
        gtk.TreeStore.__init__(self, AnimatedImage, str, int, gobject.TYPE_PYOBJECT)
        self.icons = icons
        self.datadir = datadir
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed", self.on_transactions_changed)
        self.backend.connect("channels-changed", self.on_channels_changed)
        self.db = db
        self.distro = get_distro()
        # pending transactions
        self._pending = 0
        # setup the normal stuff
        available_icon = self._get_icon("softwarecenter")
        self.available_iter = self.append(None, [available_icon, _("Get Software"), self.ACTION_ITEM_AVAILABLE, None])

        # do initial channel list update
        self._update_channel_list()
        
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        installed_iter = self.append(None, [icon, _("Installed Software"), self.ACTION_ITEM_INSTALLED, None])
        icon = AnimatedImage(None)
        self.append(None, [icon, "<span size='1'> </span>", self.ACTION_ITEM_SEPARATOR_1, None])
        
        # kick off a background check for changes that may have been made
        # in the channels list
        glib.timeout_add(300, lambda: self._check_for_channel_updates(self.channels))

    def on_channels_changed(self, backend, res):
        logging.debug("on_channels_changed %s" % res)
        if res:
            self.db.open()
            self._update_channel_list()

    def on_transactions_changed(self, backend, total_transactions):
        logging.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        if pending > 0:
            for row in self:
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    row[self.COL_NAME] = _("In Progress (%i)") % pending
                    break
            else:
                icon = AnimatedImage(self.ANIMATION_PATH)
                icon.start()
                self.append(None, [icon, _("In Progress (%i)") % pending, 
                             self.ACTION_ITEM_PENDING, None])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    del self[(i,)]

    def get_channel_iter_for_name(self, channel_name):
        channel_iter_for_name = None
        child = self.iter_children(self.available_iter)
        while child:
            if self.get_value(child, self.COL_NAME) == channel_name:
                channel_iter_for_name = child
                break
            child = self.iter_next(child)
        return channel_iter_for_name
                    
    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon

    def _update_channel_list(self):

        # check what needs to be cleared. we need to append first, kill
        # afterward because otherwise a row without children is collapsed
        # by the view.
        # 
        # normally GtkTreeIters have a limited life-cycle and are no
        # longer valid after the model changed, fortunately with the
        # gtk.TreeStore (that we use) they are persisent
        child = self.iter_children(self.available_iter)
        iters_to_kill = set()
        while child:
            iters_to_kill.add(child)
            child = self.iter_next(child)

        # get list of software channels
        self.channels = self._get_channels()
        
        # iterate the channels and add as subnodes of the available node
        for channel in self.channels:
            self.append(self.available_iter, [channel.get_channel_icon(),
                                              channel.get_channel_display_name(),
                                              self.ACTION_ITEM_CHANNEL,
                                              channel])
        # delete the old ones
        for child in iters_to_kill:
            self.remove(child)

        self.emit("channels-refreshed")

    def _get_channels(self):
        """
        return a list of SoftwareChannel objects in display order
        ordered according to:
            Distribution, Partners, PPAs alphabetically, Other channels alphabetically,
            Unknown channel last
        """
        distro_channel_name = self.distro.get_distro_channel_name()
        
        # gather the set of software channels and order them
        other_channel_list = []
        for channel_iter in self.db.xapiandb.allterms("XOL"):
            if len(channel_iter.term) == 3:
                continue
            channel_name = channel_iter.term[3:]
            
            # get origin information for this channel
            m = self.db.xapiandb.postlist_begin(channel_iter.term)
            doc = self.db.xapiandb.get_document(m.get_docid())
            for term_iter in doc.termlist():
                if term_iter.term.startswith("XOO") and len(term_iter.term) > 3: 
                    channel_origin = term_iter.term[3:]
                    break
            logging.debug("channel_name: %s" % channel_name)
            logging.debug("channel_origin: %s" % channel_origin)
            other_channel_list.append((channel_name, channel_origin))
        
        dist_channel = None
        partner_channel = None
        ppa_channels = []
        other_channels = []
        unknown_channel = []
        
        for (channel_name, channel_origin) in other_channel_list:
            if not channel_name:
                unknown_channel.append(SoftwareChannel(self.icons, 
                                                       channel_name,
                                                       channel_origin,
                                                       None))
            elif channel_name == distro_channel_name:
                dist_channel = (SoftwareChannel(self.icons,
                                                distro_channel_name,
                                                channel_origin,
                                                None,
                                                filter_required=True))
            elif channel_name == "Partner archive":
                partner_channel = SoftwareChannel(self.icons, 
                                                  channel_name,
                                                  channel_origin,
                                                  "partner", 
                                                  filter_required=True)
            elif channel_origin and channel_origin.startswith("LP-PPA"):
                ppa_channels.append(SoftwareChannel(self.icons, 
                                                    channel_name,
                                                    channel_origin,
                                                    None))
            # TODO: detect generic repository source (e.g., Google, Inc.)
            else:
                other_channels.append(SoftwareChannel(self.icons, 
                                                      channel_name,
                                                      channel_origin,
                                                      None))
        # set them in order
        channels = []
        if dist_channel is not None:
            channels.append(dist_channel)
        if partner_channel is not None:
            channels.append(partner_channel)
        channels.extend(ppa_channels)
        channels.extend(other_channels)
        channels.extend(unknown_channel)
        
        return channels
        
    def _check_for_channel_updates(self, channels):
        """ 
        check current set of channel origins in the apt cache to see if anything
        has changed, and refresh the channel list if needed
        """
        if not self.db._aptcache.ready:
            glib.timeout_add(300, lambda: self._check_for_channel_updates(channels))
            return False
        cache_origins = self.db._aptcache.get_origins()
        db_origins = set()
        for channel in channels:
            origin = channel.get_channel_origin()
            if origin:
                db_origins.add(origin)
        logging.debug("cache_origins: %s" % cache_origins)
        logging.debug("db_origins: %s" % cache_origins)
        if cache_origins != db_origins:
            logging.debug("running update_xapian_index")
            self.backend.update_xapian_index()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    scroll = gtk.ScrolledWindow()
    icons = gtk.icon_theme_get_default()

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache(apt.progress.text.OpProgress())
    db = StoreDatabase(pathname, cache)
    db.open()

    view = ViewSwitcher(datadir, db, icons)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
