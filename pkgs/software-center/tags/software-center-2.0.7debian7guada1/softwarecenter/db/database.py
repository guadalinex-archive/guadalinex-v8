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

import gobject
import locale
import logging
import re
import xapian

from softwarecenter import Application

from softwarecenter.utils import *
from softwarecenter.enums import *
from gettext import gettext as _

class StoreDatabase(gobject.GObject):
    """thin abstraction for the xapian database with convenient functions"""

    # TRANSLATORS: List of "grey-listed" words sperated with ";"
    # Do not translate this list directly. Instead,
    # provide a list of words in your language that people are likely
    # to include in a search but that should normally be ignored in
    # the search.
    SEARCH_GREYLIST_STR = _("app;application;package;program;programme;"
                            "suite;tool")

    # signal emited
    __gsignals__ = {"reopen" : (gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                ()),
                    "open" : (gobject.SIGNAL_RUN_FIRST,
                              gobject.TYPE_NONE,
                              (gobject.TYPE_STRING,)),
                    }
    def __init__(self, pathname, cache):
        gobject.GObject.__init__(self)
        self._db_pathname = pathname
        self._aptcache = cache

    def open(self, pathname=None):
        " open the database "
        if pathname:
            self._db_pathname = pathname
        self.xapiandb = xapian.Database(self._db_pathname)
        # add the apt-xapian-database for here (we don't do this
        # for now as we do not have a good way to integrate non-apps
        # with the UI)
        try:
            axi = xapian.Database("/var/lib/apt-xapian-index/index")
            self.xapiandb.add_database(axi)
        except:
            logging.exception("failed to add apt-xapian-index")
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "XP")
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.xapian_parser.add_prefix("pkg_wildcard", "XP")
        self.xapian_parser.add_prefix("pkg_wildcard", "AP")
        self.xapian_parser.set_default_op(xapian.Query.OP_AND)
        self.emit("open", self._db_pathname)

    def reopen(self):
        " reopen the database "
        self.open()
        self.emit("reopen")

    @property
    def popcon_max(self):
        popcon_max = xapian.sortable_unserialise(self.xapiandb.get_metadata("popcon_max_desktop"))
        assert popcon_max > 0
        return popcon_max

    def _comma_expansion(self, search_term):
        """do expansion of "," in a search term, see
        https://wiki.ubuntu.com/SoftwareCenter?action=show&redirect=SoftwareStore#Searching%20for%20multiple%20package%20names
        """
        # expand "," to APpkgname AND
        if "," in search_term:
            query = xapian.Query()
            for pkgname in search_term.split(","):
                # not a pkgname
                if not re.match("[0-9a-z\.\-]+", pkgname):
                    return None
                if pkgname:
                    query = xapian.Query(xapian.Query.OP_OR, query, 
                                         xapian.Query("XP"+pkgname))
            return query
        return None

    def get_query_list_from_search_entry(self, search_term, category_query=None):
        """ get xapian.Query from a search term string and a limit the
            search to the given category
        """
        def _add_category_to_query(query):
            """ helper that adds the current category to the query"""
            if not category_query:
                return query
            return xapian.Query(xapian.Query.OP_AND, 
                                category_query,
                                query)
        # empty query returns a query that matches nothing (for performance
        # reasons)
        if search_term == "" and category_query is None:
            return xapian.Query()
        # we cheat and return a match-all query for single letter searches
        if len(search_term) < 2:
            return _add_category_to_query(xapian.Query(""))

        # filter query by greylist (to avoid overly generic search terms)
        orig_search_term = search_term
        for item in self.SEARCH_GREYLIST_STR.split(";"):
            (search_term, n) = re.subn('\\b%s\\b' % item, '', search_term)
            if n: 
                logging.debug("greylist changed search term: '%s'" % search_term)
        # restore query if it was just greylist words
        if search_term == '':
            logging.debug("grey-list replaced all terms, restoring")
            search_term = orig_search_term
        
        # check if we need to do comma expansion instead of a regular
        # query
        query = self._comma_expansion(search_term)
        if query:
            return _add_category_to_query(query)

        # get a pkg query
        pkg_query = xapian.Query()
        for term in search_term.split():
            pkg_query = xapian.Query(xapian.Query.OP_OR,
                                     xapian.Query("XP"+term),
                                     pkg_query)
        pkg_query = _add_category_to_query(pkg_query)

        # get a search query
        fuzzy_query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL|
                                               xapian.QueryParser.FLAG_BOOLEAN)
        fuzzy_query = _add_category_to_query(fuzzy_query)
        return [pkg_query,fuzzy_query]

    def get_summary(self, doc):
        """ get human readable summary of the given document """
        summary = doc.get_value(XAPIAN_VALUE_SUMMARY)
        channel = doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
        # if we do not have the summary in the xapian db, get it
        # from the apt cache
        if not summary and self._aptcache.ready: 
            pkgname = self.get_pkgname(doc)
            if (pkgname in self._aptcache and 
                self._aptcache[pkgname].candidate):
                return  self._aptcache[pkgname].candidate.summary
            elif channel:
                # FIXME: print something if available for our arch
                pass
            else:
                return _("Sorry, '%s' is not available for this type of computer (%s).") % (pkgname, get_current_arch())
        return summary

    def get_pkgname(self, doc):
        """ Return a packagename from a xapian document """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # if there is no value it means we use the apt-xapian-index 
        # that store the pkgname in the data field directly
        if not pkgname:
            pkgname = doc.get_data()
        return pkgname

    def get_popcon(self, doc):
        """ Return a popcon value from a xapian document """
        popcon_raw = doc.get_value(XAPIAN_VALUE_POPCON)
        if popcon_raw:
            popcon = xapian.sortable_unserialise(popcon_raw)
        else:
            popcon = 0
        return popcon

    def get_xapian_document(self, appname, pkgname):
        """ Get the machting xapian document for appname, pkgname
        
        If no document is found, raise a IndexError
        """
        #logging.debug("get_xapian_document app='%s' pkg='%s'" % (appname,pkgname))
        # first search for appname in the app-install-data namespace
        for m in self.xapiandb.postlist("AA"+appname):
            doc = self.xapiandb.get_document(m.docid)
            if doc.get_value(XAPIAN_VALUE_PKGNAME) == pkgname:
                return doc
        # then look for matching packages from a-x-i
        for m in self.xapiandb.postlist("XP"+pkgname):
            doc = self.xapiandb.get_document(m.docid)
            return doc
        # no matching document found
        raise IndexError("No app '%s' for '%s' in database" % (appname,pkgname))

    def is_appname_duplicated(self, appname):
        """Check if the given appname is stored multiple times in the db
           This can happen for generic names like "Terminal"
        """
        for (i, m) in enumerate(self.xapiandb.postlist("AA"+appname)):
            if i > 0:
                return True
        return False

    def __len__(self):
        """return the doc count of the database"""
        return self.xapiandb.get_doccount()


if __name__ == "__main__":
    import apt
    import sys

    db = StoreDatabase("/var/cache/software-center/xapian", apt.Cache())
    db.open()
    if len(sys.argv) < 2:
        search = "apt,apport"
    else:
        search = sys.argv[1]
    query = db.get_query_list_from_search_entry(search)
    print query
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    for m in matches:
        doc = m.document
        print doc.get_data()

    # test origin
    query = xapian.Query("XOL"+"Ubuntu")
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    print "Ubuntu origin: ", len(matches)
    
