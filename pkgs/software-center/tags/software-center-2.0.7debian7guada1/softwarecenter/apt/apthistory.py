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
import apt_pkg
import glob
import gzip
import string

from debian_bundle import deb822

class Transaction(object):
    
    PKGACTIONS=["Install", "Upgrade", "Downgrade" "Remove", "Purge"]

    def __init__(self, sec):
        self.start_date = sec["Start-Date"]
        for k in self.PKGACTIONS+["Error"]:
            if k in sec:
                setattr(self, k.lower(), map(string.strip, sec[k].split(",")))
            else:
                setattr(self, k.lower(), [])
    def __len__(self):
        count=0
        for k in self.PKGACTIONS:
            count += len(getattr(self, k.lower()))
        return count
               
class AptHistory(object):

    # FIXME: add full history file reading
    def __init__(self, history_file=None):
        self.history_file = history_file
        if not history_file:
            self.history_file = apt_pkg.config.find_file("Dir::Log::History")
            #self.history_file = "/var/log/apt/history.log.1.gz"
        if self.history_file.endswith(".gz"):
            f = gzip.open(self.history_file)
        else:
            f = open(self.history_file)
        self.rescan(f)
    def rescan(self, f):
        self.transactions = []
        for stanza in deb822.Deb822.iter_paragraphs(f):
            trans = Transaction(stanza)
            self.transactions.append(trans)
    @property
    def older_parts(self):
        return glob.glob(self.history_file+".*.gz")

    def _find_in_terminal_log(self, date, term_file):
        found = False
        term_lines = []
        for line in term_file:
            if line.startswith("Log started: %s" % date):
                found = True
            elif line.endswith("Log ended") or line.startswith("Log started"):
                found = False
            if found:
                term_lines.append(line)
        return term_lines

    def find_terminal_log(self, date):
        """Find the terminal log part for the given transaction
           (this can be rather slow)
        """
        # FIXME: try to be more clever here with date/file timestamps
        term = apt_pkg.config.find_file("Dir::Log::Terminal")
        term_lines = self._find_in_terminal_log(date, open(term))
        # now search the older history
        if not term_lines:
            for f in glob.glob(term+".*.gz"):
                term_lines = self._find_in_terminal_log(date, gzip.open(f))
                if term_lines:
                    return term_lines
        return term_lines

    # TODO:
    #  def find_terminal_log(self, date)
    #  def rescan(self, scan_all_parts=True)
