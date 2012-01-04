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
import aptdaemon

class TransactionsWatcher(object):
    """ 
    base class for objects that need to watch the aptdaemon 
    for transaction changes. it registers a handler for the daemon
    going away and reconnects when it appears again

    it also provides a "on_transaction_changed()" method
    """

    def __init__(self):
        # watch the daemon exit and (re)register the signal
        bus = dbus.SystemBus()
        self._owner_watcher = bus.watch_name_owner(
            "org.debian.apt", self._register_active_transactions_watch)

    def _register_active_transactions_watch(self, connection):
        #print "_register_active_transactions_watch", connection
        apt_daemon = aptdaemon.client.get_aptdaemon()
        apt_daemon.connect_to_signal("ActiveTransactionsChanged", 
                                     self.on_transactions_changed)
        current, queued = apt_daemon.GetActiveTransactions()
        self.on_transactions_changed(current, queued)
    
    def on_transactions_changed(self, current, queue):
        " stub implementation "
        pass
