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

import datetime
import gettext
import locale
import subprocess

from apt.utils import *
from gettext import gettext as _
from softwarecenter.distro import Distro
from softwarecenter.enums import *

class Ubuntu(Distro):

    # metapackages
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    # screenshot handling
    SCREENSHOT_THUMB_URL =  "http://screenshots.ubuntu.com/thumbnail-404/%s"
    SCREENSHOT_LARGE_URL = "http://screenshots.ubuntu.com/screenshot-404/%s"

    def get_app_name(self):
        return _("Ubuntu Software Center")

    def get_app_description(self):
        return _("Lets you choose from thousands of free applications available for Ubuntu.")
    
    def get_distro_channel_name(self):
        """ The name in the Release file """
        return "Ubuntu"

    def get_distro_channel_description(self):
        """ The description of the main distro channel """
        return _("Provided by Ubuntu")

    def get_removal_warning_text(self, cache, pkg, appname):
        primary = _("To remove %s, these items must be removed "
                    "as well:" % appname)
        button_text = _("Remove All")

        depends = list(cache.get_installed_rdepends(pkg))

        # alter it if a meta-package is affected
        for m in depends:
            if cache[m].section == "metapackages":
                primary = _("If you uninstall %s, future updates will not "
                              "include new items in <b>%s</b> set. "
                              "Are you sure you want to continue?") % (appname, cache[m].installed.summary)
                button_text = _("Remove Anyway")
                depends = []
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in depends:
                primary = _("%s is a core application in Ubuntu. "
                              "Uninstalling it may cause future upgrades "
                              "to be incomplete. Are you sure you want to "
                              "continue?") % appname
                button_text = _("Remove Anyway")
                depends = None
                break
        return (primary, button_text)

    def get_installation_status(self, cache, pkg, appname):
        s = ""
        if pkg.installed:
            # generic message
            s = _("Installed")
            # In future, say "Installed since $date"
        return s

    def get_distro_codename(self):
        if not hasattr(self ,"codename"):
            self.codename = subprocess.Popen(
                ["lsb_release","-c","-s"],
                stdout=subprocess.PIPE).communicate()[0].strip()
        return self.codename

    def get_license_text(self, component):
        li =  _("Unknown")
        if component in ("main", "universe"):
            li = _("Open Source")
        elif component == "restricted":
            li = _("Proprietary")
        s = _("License: %s") % li
        return s

    def is_supported(self, cache, doc, pkgname):
        section = doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        if section == "main" and section == "restricted":
            return True
        if pkgname in cache and cache[pkgname].candidate:
            for origin in cache[pkgname].candidate.origins:
                if (origin.origin == "Ubuntu" and 
                    origin.trusted and 
                    (origin.component == "main" or
                     origin.component == "restricted")):
                    return True
        return False

    def get_price(self, doc):
        # SPECIAL CASE for partner, we don't know the prices there
        # see bug #552830 so we return None
        for term_iter in doc.termlist():
            if (term_iter.term == "XOCpartner" or
                term_iter.term == "AH%s-partner" % self.get_distro_codename()):
                return None
        #TRANSLATORS: This text will be showed as price of the software
        price = _("Free")
        return price

    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        # try to figure out the support dates of the release and make
        # sure to look only for stuff in "Ubuntu" and "distro_codename"
        # (to exclude stuff in ubuntu-updates for the support time 
        # calculation because the "Release" file time for that gets
        # updated regularly)
        releasef = get_release_filename_for_pkg(cache._cache, pkgname, 
                                                "Ubuntu", 
                                                self.get_distro_codename())
        time_t = get_release_date_from_release_file(releasef)
        # check the release date and show support information
        # based on this
        if time_t:
            release_date = datetime.datetime.fromtimestamp(time_t)
            #print "release_date: ", release_date
            now = datetime.datetime.now()
            release_age = (now - release_date).days
            #print "release age: ", release_age

            # init with the default time
            support_month = 18

            # see if we have a "Supported" entry in the pkg record
            if (pkgname in cache and
                cache[pkgname].candidate):
                support_time = cache[pkgname].candidate.record.get("Supported")
                if support_time:
                    if support_time.endswith("y"):
                        support_month = 12*int(support_time.strip("y"))
                    elif support_time.endswith("m"):
                        support_month = int(support_time.strip("m"))
                    else:
                        logging.warning("unsupported 'Supported' string '%s'" % support_time)

            # mvo: we do not define the end date very precisely
            #      currently this is why it will just display a end
            #      range
            (support_end_year, support_end_month) = get_maintenance_end_date(release_date, support_month)
            support_end_month_str = locale.nl_langinfo(getattr(locale,"MON_%d" % support_end_month))
             # check if the support has ended
            support_ended = (now.year >= support_end_year and 
                             now.month > support_end_month)
            if component == "main":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates for "
                             "%(appname)s until %(support_end_month_str)s "
                             "%(support_end_year)s.") % {'appname' : appname,
                                                         'support_end_month_str' : support_end_month_str,
                                                         'support_end_year' : support_end_year}
            elif component == "restricted":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates supplied "
                             "by the developers of %(appname)s until "
                             "%(support_end_month_str)s "
                             "%(support_end_year)s.") % {'appname' : appname,
                                                         'support_end_month_str' : support_end_month_str,
                                                         'support_end_year' : support_end_year}
               
        # if we couldn't fiure a support date, use a generic maintenance
        # string without the date
        if channel or component == "partner":
            return _("Canonical does not provide updates for %s. "
                     "Some updates may be provided by the third party "
                     "vendor.") % appname
        elif component == "main":
            return _("Canonical provides critical updates for %s.") % appname
        elif component == "restricted":
            return _("Canonical provides critical updates supplied by the "
                     "developers of %s.") % appname
        elif component == "universe" or component == "multiverse":
            return _("Canonical does not provide updates for %s. "
                     "Some updates may be provided by the "
                     "Ubuntu community.") % appname
        return _("Application %s has an unknown maintenance status.") % appname


if __name__ == "__main__":
    import apt
    cache = apt.Cache()
    print c.get_maintenance_status(cache, "synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status(cache, "3dchess app", "3dchess", "universe", None)
