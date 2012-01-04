#!/usr/bin/python
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
import glib
import locale
import logging
import os
import string
import sys
import xapian

from ConfigParser import RawConfigParser, NoOptionError
from glob import glob

from softwarecenter.enums import *

# weights for the different fields
WEIGHT_DESKTOP_NAME = 10
WEIGHT_DESKTOP_KEYWORD = 5
WEIGHT_DESKTOP_GENERICNAME = 3
WEIGHT_DESKTOP_COMMENT = 1

WEIGHT_APT_PKGNAME = 8
WEIGHT_APT_SUMMARY = 5
WEIGHT_APT_DESCRIPTION = 1

from locale import getdefaultlocale
import gettext

class DesktopConfigParser(RawConfigParser):
    " thin wrapper that is tailored for xdg Desktop files "
    DE = "Desktop Entry"
    def get_desktop(self, key):
        " get generic option under 'Desktop Entry'"
        # first try dgettext
        if self.has_option_desktop("X-Ubuntu-Gettext-Domain"):
            value = self.get(self.DE, key)
            if value:
                domain = self.get(self.DE, "X-Ubuntu-Gettext-Domain")
                translated_value = gettext.dgettext(domain, value)
                if value != translated_value:
                    return translated_value
        # then try the i18n version of the key (in [de_DE] or
        # [de]) but ignore errors and return the untranslated one then
        try:
            locale = getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
            if locale:
                if self.has_option_desktop("%s[%s]" % (key, locale)):
                    return self.get(self.DE, "%s[%s]" % (key, locale))
                if "_" in locale:
                    locale_short = locale.split("_")[0]
                    if self.has_option_desktop("%s[%s]" % (key, locale_short)):
                        return self.get(self.DE, "%s[%s]" % (key, locale_short))
        except ValueError,e :
            pass
        # and then the untranslated field
        return self.get(self.DE, key)
    def has_option_desktop(self, key):
        " test if there is the option under 'Desktop Entry'"
        return self.has_option(self.DE, key)
    def get_desktop_categories(self):
        " get the list of categories for the desktop file "
        categories = []
        try:
            categories_str = self.get_desktop("Categories")
            for item in categories_str.split(";"):
                if item:
                    categories.append(item)
        except NoOptionError:
            pass
        return categories

def ascii_upper(key):
    """Translate an ASCII string to uppercase
    in a locale-independent manner."""
    ascii_trans_table = string.maketrans(string.ascii_lowercase,
                                         string.ascii_uppercase)
    return key.translate(ascii_trans_table)

def index_name(doc, name, term_generator):
    """ index the name of the application """
    doc.add_value(XAPIAN_VALUE_APPNAME, name)
    doc.add_term("AA"+name)
    w = globals()["WEIGHT_DESKTOP_NAME"]
    term_generator.index_text_without_positions(name, w)

def update(db, cache, datadir=APP_INSTALL_PATH):
    " index the desktop files in $datadir/desktop/*.desktop "
    term_generator = xapian.TermGenerator()
    seen = set()
    context = glib.main_context_default()
    popcon_max = 0
    for desktopf in glob(datadir+"/desktop/*.desktop"):
        logging.debug("processing %s" % desktopf)
        # process events
        while context.pending():
            context.iteration()
        parser = DesktopConfigParser()
        doc = xapian.Document()
        term_generator.set_document(doc)
        try:
            parser.read(desktopf)
            # app name is the data
            name = parser.get_desktop("Name")
            if name in seen:
                logging.debug("duplicated name '%s' (%s)" % (name, desktopf))
            seen.add(name)
            doc.set_data(name)
            index_name(doc, name, term_generator)
            # check if we should ignore this file
            if parser.has_option_desktop("X-AppInstall-Ignore"):
                ignore = parser.get_desktop("X-AppInstall-Ignore")
                if ignore.strip().lower() == "true":
                    logging.debug(
                        "X-AppInstall-Ignore found for '%s'" % desktopf)
                    continue
            # package name
            pkgname = parser.get_desktop("X-AppInstall-Package")
            doc.add_term("AP"+pkgname)
            doc.add_value(XAPIAN_VALUE_PKGNAME, pkgname)
            doc.add_value(XAPIAN_VALUE_DESKTOP_FILE, desktopf)
            # pocket (main, restricted, ...)
            if parser.has_option_desktop("X-AppInstall-Section"):
                archive_section = parser.get_desktop("X-AppInstall-Section")
                doc.add_term("AS"+archive_section)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_SECTION, archive_section)
            # section (mail, base, ..)
            if pkgname in cache and cache[pkgname].candidate:
                section = cache[pkgname].candidate.section
                doc.add_term("AE"+section)
            # channel (third party stuff)
            if parser.has_option_desktop("X-AppInstall-Channel"):
                archive_channel = parser.get_desktop("X-AppInstall-Channel")
                doc.add_term("AH"+archive_channel)
                doc.add_value(XAPIAN_VALUE_ARCHIVE_CHANNEL, archive_channel)
            # icon
            if parser.has_option_desktop("Icon"):
                icon = parser.get_desktop("Icon")
                doc.add_value(XAPIAN_VALUE_ICON, icon)
            # write out categories
            for cat in parser.get_desktop_categories():
                doc.add_term("AC"+cat.lower())
            # get type (to distinguish between apps and packages
            if parser.has_option_desktop("Type"):
                type = parser.get_desktop("Type")
                doc.add_term("AT"+type.lower())
            # check gettext domain
            if parser.has_option_desktop("X-Ubuntu-Gettext-Domain"):
                domain = parser.get_desktop("X-Ubuntu-Gettext-Domain")
                doc.add_value(XAPIAN_VALUE_GETTEXT_DOMAIN, domain)
            # architecture
            if parser.has_option_desktop("X-AppInstall-Architectures"):
                arches = parser.get_desktop("X-AppInstall-Architectures")
                doc.add_value(XAPIAN_VALUE_ARCHIVE_ARCH, arches)
            # popcon
            # FIXME: popularity not only based on popcon but also
            #        on archive section, third party app etc
            if parser.has_option_desktop("X-AppInstall-Popcon"):
                popcon = float(parser.get_desktop("X-AppInstall-Popcon"))
                # sort_by_value uses string compare, so we need to pad here
                doc.add_value(XAPIAN_VALUE_POPCON, 
                              xapian.sortable_serialise(popcon))
                popcon_max = max(popcon_max, popcon)

            # comment goes into the summary data if there is one,
            # other wise we try GenericName and if nothing else,
            # the summary of the package
            if parser.has_option_desktop("Comment"):
                s = parser.get_desktop("Comment")
                doc.add_value(XAPIAN_VALUE_SUMMARY, s)
            elif parser.has_option_desktop("GenericName"):
                s = parser.get_desktop("GenericName")
                if s != name:
                    doc.add_value(XAPIAN_VALUE_SUMMARY, s)
            elif pkgname in cache and cache[pkgname].candidate:
                s = cache[pkgname].candidate.summary
                doc.add_value(XAPIAN_VALUE_SUMMARY, s)

            # add packagename as meta-data too
            term_generator.index_text_without_positions(pkgname, WEIGHT_APT_PKGNAME)

            # now add search data from the desktop file
            for key in ["GenericName","Comment"]:
                if not parser.has_option_desktop(key):
                    continue
                s = parser.get_desktop(key)
                # we need the ascii_upper here for e.g. turkish locales, see
                # bug #581207
                w = globals()["WEIGHT_DESKTOP_" + ascii_upper(key.replace(" ", ""))]
                term_generator.index_text_without_positions(s, w)
            # add data from the apt cache
            if pkgname in cache and cache[pkgname].candidate:
                s = cache[pkgname].candidate.summary
                term_generator.index_text_without_positions(s, WEIGHT_APT_SUMMARY)
                s = cache[pkgname].candidate.description
                term_generator.index_text_without_positions(s, WEIGHT_APT_DESCRIPTION)
                for origin in cache[pkgname].candidate.origins:
                    doc.add_term("XOA"+origin.archive)
                    doc.add_term("XOC"+origin.component)
                    doc.add_term("XOL"+origin.label)
                    doc.add_term("XOO"+origin.origin)
                    doc.add_term("XOS"+origin.site)

            # add our keywords (with high priority)
            if parser.has_option_desktop("X-AppInstall-Keywords"):
                keywords = parser.get_desktop("X-AppInstall-Keywords")
                for s in keywords.split(";"):
                    if s:
                        term_generator.index_text_without_positions(s, WEIGHT_DESKTOP_KEYWORD)
                
            # FIXME: now do the same for the localizations in the
            #        desktop file
            # FIXME3: add X-AppInstall-Section
        except Exception, e:
            # Print a warning, no error (Debian Bug #568941)
            logging.warning("error processing: %s %s" % (desktopf, e))
            continue
        # now add it
        db.add_document(doc)
    # add db global meta-data
    logging.debug("adding popcon_max_desktop '%s'" % popcon_max)
    db.set_metadata("popcon_max_desktop", xapian.sortable_serialise(float(popcon_max)))
    return True

def rebuild_database(pathname):
    import apt
    cache = apt.Cache(memonly=True)
    # check permission
    if not os.access(pathname, os.W_OK):
        logging.warn("Cannot write to '%s'." % pathname)
        logging.warn("Please check you have the relevant permissions.")
        return False
    # write it
    db = xapian.WritableDatabase(pathname, xapian.DB_CREATE_OR_OVERWRITE)
    update(db, cache)
    # update the mo file stamp for the langpack checks
    mofile = gettext.find("app-install-data")
    if mofile:
        mo_time = os.path.getctime(mofile)
        db.set_metadata("app-install-mo-time", str(mo_time))
    db.flush()
    return True

