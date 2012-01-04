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

import gettext
import glib
import glob
import gobject
import gtk
import locale
import logging
import os
import xapian


from ConfigParser import ConfigParser
from gettext import gettext as _
from widgets.wkwidget import WebkitWidget
from xml.etree import ElementTree as ET

from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.utils import *
from softwarecenter.distro import get_distro

(COL_CAT_NAME,
 COL_CAT_PIXBUF,
 COL_CAT_QUERY,
 COL_CAT_MARKUP) = range(4)

class Category(object):
    """represents a menu category"""
    def __init__(self, untranslated_name, name, iconname, query,
                 only_unallocated, dont_display, subcategories):
        self.name = name
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        self.query = query
        self.only_unallocated = only_unallocated
        self.subcategories = subcategories
        self.dont_display = dont_display

class CategoriesView(WebkitWidget):

    CATEGORY_ICON_SIZE = 64
    SUB_CATEGORY_ICON_SIZE = 48

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (gobject.TYPE_PYOBJECT,
                               ),
                              )
        }

    def __init__(self, datadir, desktopdir, db, icons, root_category=None):
        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        db - a Database object
        icons - a gtk.IconTheme
        root_category - a Category class with subcategories or None
        """
        super(CategoriesView, self).__init__(datadir)
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))
        self.categories = []
        self.header = ""
        self.db = db
        self.icons = icons
        if not root_category:
            self.header = _("Departments")
            self.categories = self.parse_applications_menu(desktopdir)
            self.in_subsection = False
        else:
            self.in_subsection = True
            self.set_subcategory(root_category)
        self.connect("load-finished", self._on_load_finished)

    def set_subcategory(self, root_category, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name
        self.categories = root_category.subcategories
        self.refresh_html()
        # wait until html is ready
        while gtk.events_pending():
            gtk.main_iteration()

    def on_category_clicked(self, name):
        """emit the category-selected signal when a category was clicked"""
        logging.debug("on_category_changed: %s" % name)
        for cat in self.categories:
            if cat.name == name:
                self.emit("category-selected", cat)

    # run javascript inside the html
    def _on_load_finished(self, view, frame):
        """
        helper for the webkit widget that injects the categories into
        the page when it has finished loading
        """
        if self.in_subsection:
            self.execute_script("hide_header();")
        else:
            self.execute_script("show_header();")
        for cat in sorted(self.categories, cmp=self._cat_sort_cmp):
            iconpath = ""
            if cat.iconname:
                if self.in_subsection:
                    size = self.SUB_CATEGORY_ICON_SIZE
                else:
                    size = self.CATEGORY_ICON_SIZE
                iconinfo = self.icons.lookup_icon(cat.iconname, size, 0)
                # Bug-Debian: http://bugs.debian.org/592289
                # Use applications-other as a fallback for missing icons
                if not iconinfo:
                    cat.iconname = "applications-other"
                    iconinfo = self.icons.lookup_icon(cat.iconname, size, 0)
                if iconinfo:
                    iconpath = iconinfo.get_filename()
                    logging.debug("icon: %s %s" % (iconinfo, iconpath))
            s = 'addCategory("%s","%s", "%s")' % (cat.name, 
                                                  cat.untranslated_name,
                                                  iconpath)
            logging.debug("running script '%s'" % s)
            self.execute_script(s)


    # substitute stuff
    def wksub_ubuntu_software_center(self):
        return get_distro().get_app_name()
    def wksub_icon_size(self):
        if self.in_subsection:
            return self.SUB_CATEGORY_ICON_SIZE
        else:
            return self.CATEGORY_ICON_SIZE
    def wksub_header(self):
        return self.header
    def wksub_text_direction(self):
        direction = gtk.widget_get_default_direction()
        if direction ==  gtk.TEXT_DIR_RTL:
            return 'DIR="RTL"'
        elif direction ==  gtk.TEXT_DIR_LTR:
            return 'DIR="LTR"'
    def wksub_font_family(self):
        return self._get_font_description_property("family")
        
    def wksub_font_weight(self):
        try:
            return self._get_font_description_property("weight").real
        except AttributeError:
            return int(self._get_font_description_property("weight"))
             
    def wksub_font_style(self):
        return self._get_font_description_property("style").value_nick
    def wksub_font_size(self):
        return self._get_font_description_property("size")/1024

    def wksub_featured_applications_image(self):
        return self._image_path("featured_applications_background")
    def wksub_button_background_left(self):
        return self._image_path("button_background_left")
    def wksub_button_background_right(self):
        return self._image_path("button_background_right")
    def wksub_heading_background_image(self):
        return self._image_path("heading_background_image")
    def wksub_basket_image(self):
        return self._image_path("basket")
    def wksub_arrow_image(self):
        return self._image_path("arrow")
    

    # helper code for menu parsing etc
    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name)) 

    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "System":
            return 1
        elif b.untranslated_name == "System":
            return -1
        elif a.untranslated_name == "Developer Tools":
            return 1
        elif b.untranslated_name == "Developer Tools":
            return -1
        return locale.strcoll(a.name, b.name)

    def _parse_directory_tag(self, element):
        cp = ConfigParser()
        fname = "/usr/share/desktop-directories/%s" % element.text
        logging.debug("reading '%s'" % fname)
        cp.read(fname)
        try:
            untranslated_name = name = cp.get("Desktop Entry","Name")
        except Exception, e:
            logging.warn("'%s' has no name" % fname)
            return None
        try:
            gettext_domain = cp.get("Desktop Entry", "X-Ubuntu-Gettext-Domain")
        except:
            gettext_domain = None
        try:
            icon = cp.get("Desktop Entry","Icon")
        except Exception, e:
            icon = "applications-other"
        if gettext_domain:
            name = gettext.dgettext(gettext_domain, untranslated_name)
        if name == untranslated_name:
            name = gettext.gettext(untranslated_name)
        return (untranslated_name, name, gettext_domain, icon)

    def _parse_and_or_not_tag(self, element, query, xapian_op):
        """parse a <And>, <Or>, <Not> tag """
        for and_elem in element.getchildren():
            if and_elem.tag == "Not":
                query = self._parse_and_or_not_tag(and_elem, query, xapian.Query.OP_AND_NOT)
            elif and_elem.tag == "Category":
                logging.debug("adding: %s" % and_elem.text)
                q = xapian.Query("AC"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCSection":
                logging.debug("adding section: %s" % and_elem.text)
                # we have the section once in apt-xapian-index and once
                # in our own DB this is why we need two prefixes
                # FIXME: ponder if it makes sense to simply write
                #        out XS in update-software-center instead of AE?
                q = xapian.Query(xapian.Query.OP_OR,
                                 xapian.Query("XS"+and_elem.text.lower()),
                                 xapian.Query("AE"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCType":
                logging.debug("adding type: %s" % and_elem.text)
                q = xapian.Query("AT"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCChannel":
                logging.debug("adding channel: %s" % and_elem.text)
                q = xapian.Query("AH"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgname":
                logging.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                q1 = xapian.Query("AP"+and_elem.text.lower())
                q = xapian.Query(xapian.Query.OP_OR, q1,
                                 xapian.Query("XP"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgnameWildcard":
                logging.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                s = "pkg_wildcard:%s" % and_elem.text.lower()
                q = self.db.xapian_parser.parse_query(s, xapian.QueryParser.FLAG_WILDCARD)
                query = xapian.Query(xapian_op, query, q)
            else: 
                print "UNHANDLED: ", and_elem.tag, and_elem.text
        return query

    def _parse_include_tag(self, element):
        for include in element.getchildren():
            if include.tag == "Or":
                query = xapian.Query()
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_OR)
            if include.tag == "And":
                query = xapian.Query("")
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_AND)
            # without "and" tag we take the first entry
            elif include.tag == "Category":
                return xapian.Query("AC"+include.text.lower())
            else:
                logging.warn("UNHANDLED: _parse_include_tag: %s" % include.tag)
        # empty query matches all
        return xapian.Query("")

    def _parse_menu_tag(self, item):
        name = None
        untranslated_name = None
        query = None
        icon = None
        only_unallocated = False
        dont_display = False
        subcategories = []
        for element in item.getchildren():
            # ignore inline translations, we use gettext for this
            if (element.tag == "Name" and 
                '{http://www.w3.org/XML/1998/namespace}lang' in element.attrib):
                continue
            if element.tag == "Name":
                untranslated_name = element.text
                # gettext/xml writes stuff from software-center.menu
                # out into the pot as escaped xml, so we need to escape
                # the name first, get the translation and unscape it again
                escaped_name = xml_escape(untranslated_name)
                name = xml_unescape(gettext.gettext(escaped_name))
            elif element.tag == "SCIcon":
                icon = element.text
            elif element.tag == "Directory":
                (untranslated_name, name, gettext_domain, icon) = self._parse_directory_tag(element)
            elif element.tag == "Include":
                query = self._parse_include_tag(element)
            elif element.tag == "OnlyUnallocated":
                only_unallocated = True
            elif element.tag == "SCDontDisplay":
                dont_display = True
            elif element.tag == "Menu":
                subcat = self._parse_menu_tag(element)
                if subcat:
                    subcategories.append(subcat)
            else:
                print "UNHANDLED tag in _parse_menu_tag: ", element.tag
                
        if untranslated_name and query:
            return Category(untranslated_name, name, icon, query,  only_unallocated, dont_display, subcategories)
        else:
            print "UNHANDLED entry: ", name, untranslated_name, icon, query
        return None

    def _build_unallocated_queries(self, categories):
        for cat_unalloc in categories:
            if not cat_unalloc.only_unallocated:
                continue
            for cat in categories:
                if cat.name != cat_unalloc.name:
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT, cat_unalloc.query, cat.query)
            #print cat_unalloc.name, cat_unalloc.query

    def parse_applications_menu(self, datadir):
        " parse a application menu and return a list of Category objects"""
        categories = []
        # we support multiple menu files and menu drop ins
        menu_files = [datadir+"/desktop/software-center.menu"]
        menu_files += glob.glob(datadir+"/menu.d/*.menu")
        for f in menu_files:
            tree = ET.parse(f)
            root = tree.getroot()
            for child in root.getchildren():
                category = None
                if child.tag == "Menu":
                    category = self._parse_menu_tag(child)
                if category:
                    categories.append(category)
        # post processing for <OnlyUnallocated>
        # now build the unallocated queries, once for top-level,
        # and for the subcategories. this means that subcategories
        # can have a "OnlyUnallocated/" that applies only to 
        # unallocated entries in their sublevel
        for cat in categories:
            self._build_unallocated_queries(cat.subcategories)
        self._build_unallocated_queries(categories)

        # debug print
        for cat in categories:
            logging.debug("%s %s %s" % (cat.name, cat.iconname, cat.query))
        return categories
        
    def _get_pango_font_description(self):
        return gtk.Label("pango").get_pango_context().get_font_description()
        
    def _get_font_description_property(self, property):
        description = self._get_pango_font_description()
        return getattr(description, "get_%s" % property)()




# test code
def category_activated(iconview, category, db):
    #(name, pixbuf, query) = iconview.get_model()[path]
    name = category.name
    query = category.query
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, 2000)
    for m in matches:
        doc = m.document
        appname = doc.get_value(XAPIAN_VALUE_APPNAME)
        print "appname: ", appname,
            #for t in doc.termlist():
            #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
            #print "\n"
    print len(matches)

if __name__ == "__main__":
    import apt
    from softwarecenter.enums import *
    from softwarecenter.db.database import StoreDatabase
    logging.basicConfig(level=logging.DEBUG)

    appdir = "/usr/share/app-install"
    datadir = "./data"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache()
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the category view
    view = CategoriesView(datadir, appdir, db, icons)
    view.connect("category-selected", category_activated, db)
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    # now a sub-category view
    for cat in view.categories:
        if cat.untranslated_name == "Games":
            games_category = cat
    subview = CategoriesView(datadir, appdir, db, icons, games_category)
    subview.connect("category-selected", category_activated, db)
    scroll2 = gtk.ScrolledWindow()
    scroll2.add(subview)

    # pack and show
    vbox = gtk.VBox()
    vbox.pack_start(scroll, padding=6)
    vbox.pack_start(scroll2, padding=6)

    win = gtk.Window()
    win.add(vbox)
    view.grab_focus()
    win.set_size_request(700,600)
    win.show_all()

    gtk.main()
