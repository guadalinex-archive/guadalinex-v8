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

import dbus
import logging
import gtk
import gobject
import apt
import os
import sys

import aptdaemon.client
from aptdaemon.enums import *

from softwarecenter.enums import *
from softwarecenter.backend.transactionswatcher import TransactionsWatcher

class PendingStore(gtk.ListStore, TransactionsWatcher):

    # column names
    (COL_TID,
     COL_ICON, 
     COL_NAME, 
     COL_STATUS, 
     COL_PROGRESS,
     COL_CANCEL) = range(6)

    # icons
    PENDING_STORE_ICON_CANCEL = gtk.STOCK_CANCEL
    PENDING_STORE_ICON_NO_CANCEL = "" # gtk.STOCK_YES

    ICON_SIZE = 24

    def __init__(self, icons):
        # icon, status, progress
        gtk.ListStore.__init__(self, str, gtk.gdk.Pixbuf, str, str, float, str)
        TransactionsWatcher.__init__(self)
        # data
        self.icons = icons
        # the apt-daemon stuff
        self.apt_client = aptdaemon.client.AptClient()
        self._signals = []

    def clear(self):
        super(PendingStore, self).clear()
        for sig in self._signals:
            gobject.source_remove(sig)
            del sig
        self._signals = []

    def on_transactions_changed(self, current_tid, pending_tids):
        logging.debug("on_transaction_changed %s (%s)" % (current_tid, len(pending_tids)))
        self.clear()
        for tid in [current_tid] + pending_tids:
            if not tid:
                continue
            # we do this synchronous (it used to be a reply_handler)
            # otherwise we run into a race that
            # when we get two on_transaction_changed closely after each
            # other clear() is run before the "_append_transaction" handler
            # is run and we end up with two (or more) _append_transactions
            trans = aptdaemon.client.get_transaction(tid,
                                         error_handler=lambda x: True)
            self._append_transaction(trans)

    def _append_transaction(self, trans):
        """Extract information about the transaction and append it to the
        store.
        """
        logging.debug("_append_transaction %s (%s)" % (trans.tid, trans))
        self._signals.append(
            trans.connect("progress-changed", self._on_progress_changed))
        self._signals.append(
            trans.connect("status-changed", self._on_status_changed))
        self._signals.append(
            trans.connect("cancellable-changed",
                          self._on_cancellable_changed))
        try:
            appname = trans.meta_data["sc_appname"]
        except KeyError:
            #FIXME: Extract information from packages property
            appname = get_role_localised_present_from_enum(trans.role)
            self._signals.append(
                trans.connect("role-changed", self._on_role_changed))
        try:
            iconname = trans.meta_data["sc_iconname"]
        except KeyError:
            icon = self.icons.load_icon(MISSING_APP_ICON, self.ICON_SIZE, 0)
        else:
            try:
                icon = self.icons.load_icon(iconname, self.ICON_SIZE, 0)
            except Exception:
                icon = self.icons.load_icon(MISSING_APP_ICON,
                                            self.ICON_SIZE, 0)
        status_text = self._render_status_text(appname, trans.status)
        cancel_icon = self._get_cancel_icon(trans.cancellable)
        self.append([trans.tid, icon, appname, status_text, trans.progress,
                    cancel_icon])

    def _on_cancellable_changed(self, trans, cancellable):
        #print "_on_allow_cancel: ", trans, allow_cancel
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_CANCEL] = self._get_cancel_icon(cancellable)

    def _get_cancel_icon(self, cancellable):
        if cancellable:
            return self.PENDING_STORE_ICON_CANCEL
        else:
            return self.PENDING_STORE_ICON_NO_CANCEL

    def _on_role_changed(self, trans, role):
        #print "_on_progress_changed: ", trans, role
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_NAME] = get_role_localised_present_from_enum(role)

    def _on_progress_changed(self, trans, progress):
        #print "_on_progress_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_PROGRESS] = progress

    def _on_status_changed(self, trans, status):
        #print "_on_progress_changed: ", trans, status
        for row in self:
            if row[self.COL_TID] == trans.tid:
                # FIXME: the spaces around %s are poor mans padding because
                #        setting xpad on the cell-renderer seems to not work
                name = row[self.COL_NAME]
                row[self.COL_STATUS] = self._render_status_text(name, status)

    def _render_status_text(self, name, status):
        if not name:
            name = ""
        return "%s\n<small>%s</small>" % (name,
                                          get_status_string_from_enum(status))


class PendingView(gtk.TreeView):
    
    CANCEL_XPAD = 6
    CANCEL_YPAD = 6

    def __init__(self, icons):
        gtk.TreeView.__init__(self)
        # customization
        self.set_headers_visible(False)
        self.connect("button-press-event", self._on_button_pressed)
        # icon
        self.icons = icons
        tp = gtk.CellRendererPixbuf()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=PendingStore.COL_ICON)
        self.append_column(column)
        # name
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=PendingStore.COL_STATUS)
        column.set_min_width(200)
        column.set_expand(True)
        self.append_column(column)
        # progress
        tp = gtk.CellRendererProgress()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        column = gtk.TreeViewColumn("Progress", tp, 
                                    value=PendingStore.COL_PROGRESS)
        column.set_min_width(200)
        self.append_column(column)
        # cancel icon
        tpix = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Cancel", tpix, 
                                    stock_id=PendingStore.COL_CANCEL)
        self.append_column(column)
        # fake columns that eats the extra space at the end
        tt = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Cancel", tt)
        self.append_column(column)
        # add it
        store = PendingStore(icons)
        self.set_model(store)
    def _on_button_pressed(self, widget, event):
        """button press handler to capture clicks on the cancel button"""
        #print "_on_clicked: ", event
        if event == None or event.button != 1:
            return
        res = self.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        # no path
        if not path:
            return
        # wrong column
        if column.get_title() != "Cancel":
            return
        # not cancelable (no icon)
        model = self.get_model()
        if model[path][PendingStore.COL_CANCEL] == "":
            return 
        # get tid
        tid = model[path][PendingStore.COL_TID]
        trans = aptdaemon.client.get_transaction(tid)
        try:
            trans.cancel()
        except dbus.exceptions.DBusException, e:
            logging.exception("transaction cancel failed")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    icons = gtk.icon_theme_get_default()
    view = PendingView(icons)

    # gui
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    win = gtk.Window()
    win.add(scroll)
    view.grab_focus()
    win.set_size_request(500,200)
    win.show_all()

    gtk.main()
