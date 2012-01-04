# Copyright (C) 2009-2010 Canonical
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
import gobject
import os
import logging
import subprocess

from aptdaemon import client
from aptdaemon import enums
from aptdaemon.gtkwidgets import AptMediumRequiredDialog, \
                                 AptConfigFileConflictDialog
import gtk

from softwarecenter.backend.transactionswatcher import TransactionsWatcher
from softwarecenter.utils import get_http_proxy_string_from_gconf
from softwarecenter.view import dialogs

from gettext import gettext as _

class AptdaemonBackend(gobject.GObject, TransactionsWatcher):
    """ software center specific code that interacts with aptdaemon """

    __gsignals__ = {'transaction-started':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            ()),
                    'transaction-finished':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (bool,)),
                    'transaction-stopped':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            ()),                    
                    'transactions-changed':(gobject.SIGNAL_RUN_FIRST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT, )),
                    'transaction-progress-changed':(gobject.SIGNAL_RUN_FIRST,
                                                    gobject.TYPE_NONE,
                                                    (str,int,)),
                    # the number/names of the available channels changed
                    'channels-changed':(gobject.SIGNAL_RUN_FIRST,
                                        gobject.TYPE_NONE,
                                        (bool,)),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        TransactionsWatcher.__init__(self)
        self.aptd_client = client.AptClient()
        self.pending_transactions = {}
        self._progress_signal = None
    
    def _axi_finished(self, res):
        self.emit("channels-changed", res)

    # public methods
    def update_xapian_index(self):
        logging.debug("update_xapian_index")
        system_bus = dbus.SystemBus()
        axi = dbus.Interface(
            system_bus.get_object("org.debian.AptXapianIndex","/"),
            "org.debian.AptXapianIndex")
        axi.connect_to_signal("UpdateFinished", self._axi_finished)
        # we don't really care for updates at this point
        #axi.connect_to_signal("UpdateProgress", progress)
        # first arg is force, second update_only
        axi.update_async(True, True)

    def upgrade(self, pkgname, appname, iconname):
        """ upgrade a single package """
        self.emit("transaction-started")
        reply_handler = lambda trans: self._run_transaction(trans, pkgname,
                                                            appname, iconname)
        self.aptd_client.upgrade_packages([pkgname],
                                          reply_handler=reply_handler,
                                          error_handler=self._on_trans_error)

    def remove(self, pkgname, appname, iconname):
        """ remove a single package """
        self.emit("transaction-started")
        reply_handler = lambda trans: self._run_transaction(trans, pkgname,
                                                            appname, iconname)
        self.aptd_client.remove_packages([pkgname], wait=False, 
                                         reply_handler=reply_handler,
                                         error_handler=self._on_trans_error)

    def install(self, pkgname, appname, iconname):
        """ install a single package """
        self.emit("transaction-started")
        reply_handler = lambda trans: self._run_transaction(trans, pkgname,
                                                            appname, iconname)
        self.aptd_client.install_packages([pkgname],
                                          reply_handler=reply_handler,
                                          error_handler=self._on_trans_error)

    def reload(self):
        """ reload package list """
        reply_handler = lambda trans: self._run_transaction(trans, None, None,
                                                            None)
        self.aptd_client.update_cache(reply_handler=reply_handler,
                                      error_handler=self._on_trans_error)

    def enable_component(self, component):
        logging.debug("enable_component: %s" % component)
        try:
            self.aptd_client.enable_distro_component(component)
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                logging.error("enable_component: '%s'" % e)
                return
            raise
        # now update the cache
        self.reload()

    def enable_channel(self, channelfile):
        import aptsources.sourceslist

        # read channel file and add all relevant lines
        for line in open(channelfile):
            line = line.strip()
            if not line:
                continue
            entry = aptsources.sourceslist.SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(channelfile)
            try:
                self.aptd_client.add_repository(
                    entry.type, entry.uri, entry.dist, entry.comps,
                    "Added by software-center", sourcepart)
            except dbus.exceptions.DBusException, e:
                if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                    logging.error("add_repository: '%s'" % e)
                    return
        # now update the cache
        self.reload()

    # internal helpers
    def on_transactions_changed(self, current, pending):
        # cleanup progress signal (to be sure to not leave dbus matchers around)
        if self._progress_signal:
            gobject.source_remove(self._progress_signal)
            self._progress_signal = None
        # attach progress-changed signal for current transaction
        if current:
            trans = client.get_transaction(current, 
                                           error_handler=lambda x: True)
            self._progress_signal = trans.connect("progress-changed", self._on_progress_changed)
        # now update pending transactions
        self.pending_transactions.clear()
        for tid in [current] + pending:
            if not tid:
                continue
            trans = client.get_transaction(tid, error_handler=lambda x: True)
            # FIXME: add a bit more data here
            try:
                pkgname = trans.meta_data["sc_pkgname"]
                self.pending_transactions[pkgname] = trans.progress
            except KeyError:
                # if its not a transaction from us (sc_pkgname) still
                # add it with the tid as key to get accurate results
                # (the key of pending_transactions is never directly
                #  exposed in the UI)
                self.pending_transactions[trans.tid] = trans.progress
        self.emit("transactions-changed", self.pending_transactions)

    def _on_progress_changed(self, trans, progress):
        """ 
        internal helper that gets called on our package transaction progress 
        (only showing pkg progress currently)
        """
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            self.pending_transactions[pkgname] = progress
            self.emit("transaction-progress-changed", pkgname, progress)
        except KeyError:
            pass

    def _on_trans_reply(self):
        # dummy callback for now, but its required, otherwise the aptdaemon
        # client blocks the UI and keeps gtk from refreshing
        logging.debug("_on_trans_reply")

    def _on_trans_error(self, error):
        logging.warn("_on_trans_error: %s" % error)
        # re-enable the action button again if anything went wrong
        if (error._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized" or
            error._dbus_error_name == "org.freedesktop.DBus.Error.NoReply"):
            pass
        else:
            raise error
        self.emit("transaction-stopped")

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        if enum == enums.EXIT_FAILED:
            # daemon died are messages that result from broken
            # cancel handling in aptdaemon (LP: #440941)
            # FIXME: this is not a proper fix, just a workaround
            if trans.error_code == enums.ERROR_DAEMON_DIED:
                logging.warn("daemon dies, ignoring: %s" % excep)
            else:
                msg = "%s: %s\n%s\n\n%s" % (
                    _("Error"),
                    enums.get_error_string_from_enum(trans.error_code),
                    enums.get_error_description_from_enum(trans.error_code),
                    trans.error_details)
                logging.error("error in _on_trans_finished '%s'" % msg)
                # show dialog to the user and exit (no need to reopen
                # the cache)
                dialogs.error(
                    None, 
                    enums.get_error_string_from_enum(trans.error_code),
                    enums.get_error_description_from_enum(trans.error_code),
                    trans.error_details)
        # send finished signal
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            del self.pending_transactions[pkgname]
            self.emit("transaction-progress-changed", pkgname, 100)
        except KeyError:
            pass
        # if it was a cache-reload, trigger a-x-i update
        if trans.role == enums.ROLE_UPDATE_CACHE:
            self.update_xapian_index()
        # send appropriate signals
        self.emit("transactions-changed", self.pending_transactions)
        self.emit("transaction-finished", enum != enums.EXIT_FAILED)

    def _config_file_conflict(self, transaction, old, new):
        dia = AptConfigFileConflictDialog(old, new)
        res = dia.run()
        dia.hide()
        dia.destroy()
        # send result to the daemon
        if res == gtk.RESPONSE_YES:
            transaction.resolve_config_file_conflict(old, "replace")
        else:
            transaction.resolve_config_file_conflict(old, "keep")

    def _medium_required(self, transaction, medium, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == gtk.RESPONSE_OK:
            transaction.provide_medium(medium)
        else:
            transaction.cancel()

    def set_http_proxy(self, trans):
        """ set http proxy based on gconf and attach it to a transaction """
        http_proxy = get_http_proxy_string_from_gconf()
        if http_proxy:
            trans.set_http_proxy(http_proxy, reply_handler=lambda t: True,
                                 error_handler=self._on_trans_error)

    def _run_transaction(self, trans, pkgname, appname, iconname):
        # connect signals
        trans.connect("config-file-conflict", self._config_file_conflict)
        trans.connect("medium-required", self._medium_required)
        trans.connect("finished", self._on_trans_finished)
        # set appname/iconname/pkgname only if we actually have one
        if appname:
            trans.set_meta_data(sc_appname=appname, 
                                reply_handler=lambda t: True,
                                error_handler=self._on_trans_error)
        if iconname:
            trans.set_meta_data(sc_iconname=iconname,
                                reply_handler=lambda t: True,
                                error_handler=self._on_trans_error)
        # we do not always have a pkgname, e.g. "cache_update" does not
        if pkgname:
            trans.set_meta_data(sc_pkgname=pkgname,
                                reply_handler=lambda t: True,
                                error_handler=self._on_trans_error)
            # setup debconf only if we have a pkg
            trans.set_debconf_frontend("gnome", reply_handler=lambda t: True,
                                       error_handler=self._on_trans_error)
            # set this once the new aptdaemon 0.2.x API can be used
            trans.set_remove_obsoleted_depends(True, 
                                               reply_handler=lambda t: True,
                                               error_handler=self._on_trans_error)
            
        # set proxy and run
        self.set_http_proxy(trans)
        trans.run(error_handler=self._on_trans_error,
                  reply_handler=self._on_trans_reply)

if __name__ == "__main__":
    #c = client.AptClient()
    #c.remove_packages(["4g8"], remove_unused_dependencies=True)
    backend = AptdaemonBackend()
    backend.reload()

