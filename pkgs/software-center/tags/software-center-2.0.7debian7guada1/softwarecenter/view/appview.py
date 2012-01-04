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

from __future__ import with_statement


import apt
import gettext
import glib
import gobject
import gtk
import locale
import logging
import math
import os
import pango
import string
import sys
import time
import xapian

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.db.database import StoreDatabase, Application
from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro

from gettext import gettext as _

# cache icons to speed up rendering
_app_icon_cache = {}

class AppStore(gtk.GenericTreeModel):
    """
    A subclass GenericTreeModel that reads its data from a xapian
    database. It can combined with any xapian querry and with
    a generic filter function (that can filter on data not
    available in xapian)
    """

    (COL_APP_NAME,
     COL_TEXT,
     COL_MARKUP,
     COL_ICON,
     COL_INSTALLED,
     COL_AVAILABLE,
     COL_PKGNAME,
     COL_POPCON,
     COL_IS_ACTIVE,
     COL_ACTION_IN_PROGRESS,
     ) = range(10)

    column_type = (str,
                   str,
                   str,
                   gtk.gdk.Pixbuf,
                   bool,
                   bool,
                   str,
                   int,
                   bool,
                   int)

    ICON_SIZE = 24
    MAX_STARS = 5

    (SEARCHES_SORTED_BY_POPCON,
     SEARCHES_SORTED_BY_XAPIAN_RELEVANCE,
     SEARCHES_SORTED_BY_ALPHABETIC) = range(3)

    def __init__(self, cache, db, icons, search_query=None, limit=200,
                 sort=False, filter=None):
        """
        Initalize a AppStore.

        :Parameters:
        - `cache`: apt cache (for stuff like the overlay icon)
        - `db`: a xapian.Database that contians the applications
        - `icons`: a gtk.IconTheme that contains the icons
        - `search_query`: a single search as a xapian.Query or a list
        - `limit`: how many items the search should return (0 == unlimited)
        - `sort`: sort alphabetically after a search
                   (default is to use relevance sort)
        - `filter`: filter functions that can be used to filter the
                    data further. A python function that gets a pkgname
        """
        gtk.GenericTreeModel.__init__(self)
        self.search_query = search_query
        self.cache = cache
        self.db = db
        self.icons = icons
        # invalidate the cache on icon theme changes
        self.icons.connect("changed", lambda theme: _app_icon_cache.clear())
        self._appicon_missing_icon = self.icons.load_icon(MISSING_APP_ICON, self.ICON_SIZE, 0)
        self.apps = []
        # this is used to re-set the cursor
        self.app_index_map = {}
        # this is used to find the in-progress rows
        self.pkgname_index_map = {}
        self.sorted = sort
        self.filter = filter
        self.active = True
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        # rowref of the active app and last active app
        self.active_app = None
        self._prev_active_app = 0
        self._searches_sort_mode = self._get_searches_sort_mode()
        # FIXME: do the sorting/adding in a seperate thread?
        if not search_query:
            # limit to applications
            for m in db.xapiandb.postlist("ATapplication"):
                doc = db.xapiandb.get_document(m.docid)
                if filter and self.is_filtered_out(filter, doc):
                    continue
                appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                pkgname = db.get_pkgname(doc)
                popcon = db.get_popcon(doc)
                self.apps.append(Application(appname, pkgname, popcon))
                # keep the UI going
                while gtk.events_pending():
                    gtk.main_iteration()
            self.apps.sort()
            for (i, app) in enumerate(self.apps):
                self.app_index_map[app] = i
        else:
            # we support single and list search_queries,
            # if list we append them one by one
            if isinstance(search_query, xapian.Query):
                search_query = [search_query]
            already_added = set()
            for q in search_query:
                logging.debug("using query: '%s'" % q)
                enquire = xapian.Enquire(db.xapiandb)
                enquire.set_query(q)
                # set search order mode
                if self._searches_sort_mode == self.SEARCHES_SORTED_BY_POPCON:
                    enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
                elif self._searches_sort_mode == self.SEARCHES_SORTED_BY_ALPHABETIC:
                    self.sorted=sort=True
                if limit == 0:
                    matches = enquire.get_mset(0, len(db))
                else:
                    matches = enquire.get_mset(0, limit)
                logging.debug("found ~%i matches" % matches.get_matches_estimated())
                app_index = 0
                for m in matches:
                    doc = m.document
                    if "APPVIEW_DEBUG_TERMS" in os.environ:
                        print doc.get_value(XAPIAN_VALUE_APPNAME)
                        for t in doc.termlist():
                            print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
                        print "\n"
                    appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                    pkgname = db.get_pkgname(doc)
                    if filter and self.is_filtered_out(filter, doc):
                        continue
                    # when doing multiple queries we need to ensure
                    # we don't add duplicates
                    popcon = db.get_popcon(doc)
                    app = Application(appname, pkgname, popcon)
                    if not app in already_added:
                        self.apps.append(app)
                        already_added.add(app)
                        if not sort:
                            self.app_index_map[app] = app_index
                            app_index = app_index + 1
                    # keep the UI going
                    while gtk.events_pending():
                        gtk.main_iteration()
            if sort:
                self.apps.sort()
                for (i, app) in enumerate(self.apps):
                    self.app_index_map[app] = i
            # build the pkgname map
            for (i, app) in enumerate(self.apps):
                if not app.pkgname in self.pkgname_index_map:
                    self.pkgname_index_map[app.pkgname] = []
                self.pkgname_index_map[app.pkgname].append(i)

    def clear(self):
        self.apps = []
        self.app_index_map.clear()
        self.pkgname_index_map.clear()

    def is_filtered_out(self, filter, doc):
        """ apply filter and return True if the package is filtered out """
        pkgname = self.db.get_pkgname(doc)
        return not filter.filter(doc, pkgname)

    # internal helper
    def _get_searches_sort_mode(self):
        mode = self.SEARCHES_SORTED_BY_POPCON
        if "SOFTWARE_CENTER_SEARCHES_SORT_MODE" in os.environ:
            k = os.environ["SOFTWARE_CENTER_SEARCHES_SORT_MODE"].strip().lower()
            if k == "popcon":
                mode = self.SEARCHES_SORTED_BY_POPCON
            elif k == "alphabetic":
                mode = self.SEARCHES_SORTED_BY_ALPHABETIC
            elif k == "xapian":
                mode = self.SEARCHES_SORTED_BY_XAPIAN_RELEVANCE
        return mode
    def _set_active_app(self, path):
        """ helper that emits row_changed signals for the new
            and previous selected app
        """
        self.active_app = path
        self.row_changed(self._prev_active_app,
                         self.get_iter(self._prev_active_app))
        self._prev_active_app = path
        self.row_changed(path, self.get_iter(path))

    def _calc_normalized_rating(self, raw_rating):
        if raw_rating:
            return int(self.MAX_STARS * math.log(raw_rating)/math.log(self.db.popcon_max+1))
        return 0

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if (not self.apps or
            not self.active or
            not pkgname in self.pkgname_index_map):
            return
        for index in self.pkgname_index_map[pkgname]:
            row = self[index]
            self.row_changed(row.path, row.iter)
    # GtkTreeModel functions
    def on_get_flags(self):
        return (gtk.TREE_MODEL_LIST_ONLY|
                gtk.TREE_MODEL_ITERS_PERSIST)
    def on_get_n_columns(self):
        return len(self.column_type)
    def on_get_column_type(self, index):
        return self.column_type[index]
    def on_get_iter(self, path):
        #logging.debug("on_get_iter: %s" % path)
        if len(self.apps) == 0:
            return None
        index = path[0]
        return index
    def on_get_path(self, rowref):
        logging.debug("on_get_path: %s" % rowref)
        return rowref
    def on_get_value(self, rowref, column):
        #logging.debug("on_get_value: %s %s" % (rowref, column))
        try:
            app = self.apps[rowref]
        except IndexError:
            logging.exception("on_get_value: rowref=%s apps=%s" % (rowref, self.apps))
            return
        doc = self.db.get_xapian_document(app.appname, app.pkgname)
        if column == self.COL_APP_NAME:
            return app.appname
        elif column == self.COL_TEXT:
            appname = app.appname
            summary = self.db.get_summary(doc)
            return "%s\n%s" % (appname, summary)
        elif column == self.COL_MARKUP:
            appname = app.appname
            summary = self.db.get_summary(doc)
            # SPECIAL CASE: the spec says that when there is no appname, 
            #               the summary should be displayed as appname
            if not appname:
                appname = summary
                summary = app.pkgname
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, app.pkgname)
            s = "%s\n<small>%s</small>" % (
                gobject.markup_escape_text(appname),
                gobject.markup_escape_text(summary))
            return s
        elif column == self.COL_ICON:
            try:
                icon_name = doc.get_value(XAPIAN_VALUE_ICON)
                if icon_name:
                    icon_name = os.path.splitext(icon_name)[0]
                    if icon_name in _app_icon_cache:
                        return _app_icon_cache[icon_name]
                    # icons.load_icon takes between 0.001 to 0.01s on my
                    # machine, this is a significant burden because get_value
                    # is called *a lot*. caching is the only option
                    icon = self.icons.load_icon(icon_name, self.ICON_SIZE, 0)
                    _app_icon_cache[icon_name] = icon
                    return icon
            except glib.GError, e:
                logging.debug("get_icon returned '%s'" % e)
                _app_icon_cache[icon_name] = self._appicon_missing_icon
            return self._appicon_missing_icon
        elif column == self.COL_INSTALLED:
            pkgname = app.pkgname
            if pkgname in self.cache and self.cache[pkgname].is_installed:
                return True
            return False
        elif column == self.COL_AVAILABLE:
            pkgname = app.pkgname
            return pkgname in self.cache
        elif column == self.COL_PKGNAME:
            pkgname = app.pkgname
            return pkgname
        elif column == self.COL_POPCON:
            return self._calc_normalized_rating(self.apps[rowref].popcon)
        elif column == self.COL_IS_ACTIVE:
            return (rowref == self.active_app)
        elif column == self.COL_ACTION_IN_PROGRESS:
            if app.pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[app.pkgname]
            else:
                return -1
    def on_iter_next(self, rowref):
        #logging.debug("on_iter_next: %s" % rowref)
        new_rowref = int(rowref) + 1
        if new_rowref >= len(self.apps):
            return None
        return new_rowref
    def on_iter_children(self, parent):
        if parent:
            return None
        # rowref of the first element, so we return zero here
        return 0
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        logging.debug("on_iter_n_children: %s (%i)" % (rowref, len(self.apps)))
        if rowref:
            return 0
        return len(self.apps)
    def on_iter_nth_child(self, parent, n):
        logging.debug("on_iter_nth_child: %s %i" % (parent, n))
        if parent:
            return 0
        if n >= len(self.apps):
            return None
        return n
    def on_iter_parent(self, child):
        return None


class CellRendererButton:

    def __init__(self, layout, markup, alt_markup=None, xpad=14, ypad=4):
        if not alt_markup:
            w, h, mx, amx = self._calc_markup_params(layout, markup, xpad, ypad)
        else:
            w, h, mx, amx = self._calc_markup_params_alt(layout, markup, alt_markup, xpad, ypad)

        self.params = {
            'label': markup,
            'markup': markup,
            'alt_markup': alt_markup,
            'width': w,
            'height': h,
            'y_offset_const': 0,
            'region_rect': gtk.gdk.region_rectangle(gtk.gdk.Rectangle(0,0,0,0)),
            'xpad': xpad,
            'ypad': ypad,
            'state': gtk.STATE_NORMAL,
            'shadow': gtk.SHADOW_OUT,
            'layout_x': mx,
            'markup_x': mx,
            'alt_markup_x': amx
            }
        self.use_alt = False
        return

    def _calc_markup_params(self, layout, markup, xpad, ypad):
        layout.set_markup(markup)
        w = self._get_layout_pixel_width(layout) + 2*xpad
        h = self._get_layout_pixel_height(layout) + 2*ypad
        return w, h, xpad, 0

    def _calc_markup_params_alt(self, layout, markup, alt_markup, xpad, ypad):
        layout.set_markup(markup)
        mw = self._get_layout_pixel_width(layout)
        layout.set_markup(alt_markup)
        amw = self._get_layout_pixel_width(layout)

        if amw > mw:
            w = amw + 2*xpad
            mx = xpad + (amw - mw)/2
            amx = xpad
        else:
            w = mw + 2*xpad
            mx = xpad
            amx = xpad + (mw - amw)/2

        # assume text height is the same for markups.
        h = self._get_layout_pixel_height(layout) + 2*ypad
        return w, h, mx, amx

    def _get_layout_pixel_width(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[2]

    def _get_layout_pixel_height(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[3]

    def set_state(self, state_type):
        self.params['state'] = state_type
        return

    def set_shadow(self, shadow_type):
        self.params['shadow'] = shadow_type

    def set_sensitive(self, is_sensitive):
        if not is_sensitive:
            self.set_state(gtk.STATE_INSENSITIVE)
            self.set_shadow(gtk.SHADOW_OUT)
        else:
            self.set_state(gtk.STATE_NORMAL)
            self.set_shadow(gtk.SHADOW_OUT)
        return

    def set_use_alt_markup(self, use_alt):
        if self.use_alt == use_alt: 
            return
        self.use_alt = use_alt
        p = self.params
        if use_alt:
            p['label'] = p['alt_markup']
            p['layout_x'] = p['alt_markup_x']
        else:
            p['label'] = p['markup']
            p['layout_x'] = p['markup_x']
        return

    def get_use_alt_markup(self):
        return self.use_alt

    def set_param(self, key, value):
        self.params[key] = value
        return

    def get_param(self, key):
        return self.params[key]

    def get_params(self, *keys):
        r = []
        for k in keys:
            r.append(self.params[k])
        return r

    def draw(self, window, widget, layout, dst_x, cell_yO):
        p = self.params
        w, h, yO = self.get_params('width', 'height', 'y_offset_const')
        dst_y = yO+cell_yO
        state = p['state']

        # backgound "button" rect
        widget.style.paint_box(window,
                               state,
                               p['shadow'],
                               (dst_x, dst_y, w, h),
                               widget,
                               "button",
                               dst_x,
                               dst_y,
                               w,
                               h)

        # cache region_rectangle for event checks
        p['region_rect'] = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(dst_x, dst_y, w, h))

#        # if btn_has_focus:
#        # draw focal rect
#        widget.style.paint_focus(window,
#                                 state,
#                                 (dst_x, dst_y, w, h),
#                                 widget,
#                                 "button",
#                                 dst_x-2,       # x
#                                 dst_y-2,       # y
#                                 w-4,          # width
#                                 h-4)          # height

        # draw button label
        dst_x += p['layout_x']
        dst_y += p['ypad']
        layout.set_markup(p['label'])
        widget.style.paint_layout(window,
                            state,
                            True,
                            (dst_x, dst_y, w, h),
                            widget,
                            None,
                            dst_x,
                            dst_y,
                            layout)
        return


# custom cell renderer to support dynamic grow
class CellRendererAppView(gtk.GenericCellRenderer):

    __gproperties__ = {
        'markup': (gobject.TYPE_STRING, 'Markup', 'Pango markup', '',
                    gobject.PARAM_READWRITE),

#        'addons': (bool, 'AddOns', 'Has add-ons?', False,
#                   gobject.PARAM_READWRITE),

        # numbers mean: min: 0, max: 5, default: 0
        'rating': (gobject.TYPE_INT, 'Rating', 'Popcon rating', 0, 5, 0,
            gobject.PARAM_READWRITE),

#        'reviews': (gobject.TYPE_INT, 'Reviews', 'Number of reviews', 0, 100, 0,
#            gobject.PARAM_READWRITE),

        'isactive': (bool, 'IsActive', 'Is active?', False,
                    gobject.PARAM_READWRITE),

        'installed': (bool, 'installed', 'Is the app installed', False,
                     gobject.PARAM_READWRITE),

        'available': (bool, 'available', 'Is the app available for install', False,
                     gobject.PARAM_READWRITE),

        'action_in_progress': (gobject.TYPE_INT, 'Action Progress', 'Action progress', -1, 100, -1,
                     gobject.PARAM_READWRITE),
        }

    def __init__(self, show_ratings):
        self.__gobject_init__()

        # height defaults
        self.base_height = 0
        self.button_height = 0

        self.markup = None
        self.rating = 0
        self.reviews = 0
        self.isactive = False
        self.installed = False
        self.show_ratings = show_ratings

        # get rating icons
        icons = gtk.icon_theme_get_default()
        self.star_pixbuf = icons.load_icon("sc-emblem-favorite", 12, 0)
        self.star_not_pixbuf = icons.load_icon("sc-emblem-favorite-not", 12, 0)

        # specify the func that calc's distance from margin, based on text dir
        self._calc_x = self._calc_x_ltr
        return

    def set_direction(self, text_direction):
        self.text_direction = text_direction
        if text_direction != gtk.TEXT_DIR_RTL:
            self._calc_x = self._calc_x_ltr
        else:
            self._calc_x = self._calc_x_rtl
        return

    def set_base_height(self, base_height):
        self.base_height = base_height
        return

    def set_button_height(self, button_height):
        self.button_height = button_height
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def _get_layout_pixel_width(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[2]

    def _get_layout_pixel_height(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[3]

    def _calc_x_ltr(self, cell_area, aspect_width, margin_xO):
        return cell_area.x + margin_xO

    def _calc_x_rtl(self, cell_area, aspect_width, margin_xO):
        return cell_area.x + cell_area.width - aspect_width - margin_xO

    def draw_appname_summary(self, window, widget, cell_area, layout, xpad, ypad, flags):
        w = self.star_pixbuf.get_width()
        h = self.star_pixbuf.get_height()
        # total 5star width + 1 px spacing per star
        max_star_width = AppStore.MAX_STARS*(w+1)

        # work out layouts max width
        lw = self._get_layout_pixel_width(layout)
        max_layout_width = cell_area.width - 4*xpad - max_star_width

        if lw >= max_layout_width:
            layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            layout.set_width((max_layout_width)*pango.SCALE)
            lw = max_layout_width

        # work out where to draw layout
        dst_x = self._calc_x(cell_area, lw, xpad)
        dst_y = cell_area.y + ypad

        # important! ensures correct text rendering, esp. when using hicolor theme
        if (flags & gtk.CELL_RENDERER_SELECTED) != 0:
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL

        widget.style.paint_layout(window,
                                  state,
                                  True,
                                  cell_area,
                                  widget,
                                  None,
                                  dst_x,
                                  dst_y,
                                  layout)
        # remove layout size constraints
        layout.set_width(-1)
        return w, h, max_star_width

    def draw_appname_activity_state(self, window, widget, cell_area, layout, xpad, ypad, flags, activity):
        # stub.  in the spec mpt has it so that when an app is being installed is has:
        # Audacity
        # Installing ...

        #or, for removal:
        # Audacity
        # Removing ...
        return

    def draw_rating_and_reviews(self, window, widget, cell_area, layout, xpad, ypad, w, h, max_star_width, flags):
        dst_y = cell_area.y+ypad + ( 0 if self.reviews > 0 else 10) # unnamed constant because I can't see a place to put these 
        
        # draw star rating
        self.draw_rating(window, cell_area, dst_y, max_star_width, xpad, self.rating)

        if self.reviews == 0: return
        # draw number of reviews
        nr_reviews_str = gettext.ngettext("%s review",
                                          "%s reviews",
                                          self.reviews) % self.reviews
        
        layout.set_markup("<small>%s</small>" % nr_reviews_str)
        lw = self._get_layout_pixel_width(layout)
        dst_x = self._calc_x(cell_area, lw, cell_area.width-xpad-max_star_width+(max_star_width-lw)/2)

        widget.style.paint_layout(window,
                                  flags,
                                  True,
                                  cell_area,
                                  widget,
                                  None,
                                  dst_x,
                                  cell_area.y+ypad+h+1,
                                  layout)
        return

    def draw_rating(self, window, cell_area, dst_y, max_star_width, xpad, r):
        w = self.star_pixbuf.get_width()
        for i in range(AppStore.MAX_STARS):
            # special case.  not only do we want to shift the x offset, but we want to reverse the order in which
            # the gold stars are presented.
            if self.text_direction != gtk.TEXT_DIR_RTL:
                dst_x = cell_area.x + cell_area.width - xpad - max_star_width + i*(w+1)
            else:
                dst_x = cell_area.x + xpad + max_star_width - w - i*(w+1)

            if i < r:
                window.draw_pixbuf(None,
                                   self.star_pixbuf,                        # icon
                                   0, 0,                                    # src pixbuf
                                   dst_x,                                   # x
                                   dst_y,                                   # y
                                   -1, -1,                                  # size
                                   0, 0, 0)                                 # dither
            else:
                window.draw_pixbuf(None,
                                   self.star_not_pixbuf,                    # icon
                                   0, 0,                                    # src pixbuf
                                   dst_x,                                   # x
                                   dst_y,                                   # y
                                   -1, -1,                                  # size
                                   0, 0, 0)                                 # dither
        return

    def draw_progress(self, window, widget, cell_area, layout, dst_x, ypad, flags):
        percent = self.props.action_in_progress * 0.01
        w = widget.buttons['action'].get_param('width')
        h = 22  # pixel height. should be the same height of CellRendererProgress progressbar
        dst_y = cell_area.y + (self.base_height-h)/2

        # progress trough border
        widget.style.paint_flat_box(window, gtk.STATE_ACTIVE, gtk.SHADOW_IN,
                               (dst_x, dst_y, w, h),
                               widget, 
                               None,
                               dst_x,
                               dst_y,
                               w,
                               h)

        # progress trough inner
        widget.style.paint_flat_box(window, gtk.STATE_NORMAL, gtk.SHADOW_IN,
                               (dst_x+1, dst_y+1, w-2, h-2),
                               widget, 
                               None,
                               dst_x+1,
                               dst_y+1,
                               w-2,
                               h-2)

        # progress bar
        if self.text_direction != gtk.TEXT_DIR_RTL:
            widget.style.paint_box(window, flags, gtk.SHADOW_OUT,
                                   (dst_x, dst_y, percent*w, h),
                                   widget, 
                                   "bar",
                                   dst_x,
                                   dst_y,
                                   percent*w,
                                   h)
        else:
            widget.style.paint_box(window, flags, gtk.SHADOW_OUT,
                                   (dst_x + w+1-percent*w, dst_y, percent*w, h),
                                   widget, 
                                   "bar",
                                   dst_x + w+1-percent*w,
                                   dst_y,
                                   percent*w,
                                   h)
        return

    def on_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')

        # create pango layout with markup
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.markup)

        w, h, max_star_width = self.draw_appname_summary(window, widget, cell_area, layout, xpad, ypad, flags)

        if not self.isactive:
            if self.show_ratings:
                # draw star rating only
                dst_y = cell_area.y + (cell_area.height-h)/2
                self.draw_rating(window, cell_area, dst_y, max_star_width, xpad, self.rating)
            return

        # Install/Remove button
        # only draw a install/remove button if the app is actually available
        if self.available:
            btn = widget.get_button('action')
            btn.set_use_alt_markup(self.installed)
            dst_x = self._calc_x(cell_area, btn.get_param('width'), cell_area.width-xpad-btn.get_param('width'))
            btn.draw(window, widget, layout, dst_x, cell_area.y)
            # check if the current app has an action that is in progress
            if self.props.action_in_progress < 0:
                # draw rating with the number of reviews
                if self.show_ratings:
                    self.draw_rating_and_reviews(window, widget, cell_area, layout, xpad, ypad, w, h, max_star_width, flags)
            else:
                self.draw_progress(window, widget, cell_area, layout, dst_x, ypad, flags)

        # More Info button
        btn = widget.buttons['info']
        dst_x = self._calc_x(cell_area, btn.get_param('width'), xpad)
        btn.draw(window, widget, layout, dst_x, cell_area.y)
        return

    def on_get_size(self, widget, cell_area):
        h = self.base_height
        if self.isactive:
            h += self.button_height
        return -1, -1, -1, h

gobject.type_register(CellRendererAppView)


# custom renderer for the arrow thing that mpt wants
class CellRendererPixbufWithOverlay(gtk.CellRendererPixbuf):

    # offset of the install overlay icon
    OFFSET_X = 14
    OFFSET_Y = 16

    # size of the install overlay icon
    OVERLAY_SIZE = 16

    __gproperties__ = {
        'overlay' : (bool, 'overlay', 'show an overlay icon', False,
                     gobject.PARAM_READWRITE),
   }

    def __init__(self, overlay_icon_name):
        gtk.CellRendererPixbuf.__init__(self)
        icons = gtk.icon_theme_get_default()
        self.overlay = False
        try:
            self._installed = icons.load_icon(overlay_icon_name,
                                          self.OVERLAY_SIZE, 0)
        except glib.GError:
            # icon not present in theme, probably because running uninstalled
            self._installed = icons.load_icon('emblem-system',
                                          self.OVERLAY_SIZE, 0)
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def do_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):

        # always render icon app icon centered with respect to an unexpanded CellRendererAppView
        ypad = self.get_property('ypad')

        area = (cell_area.x,
                cell_area.y+ypad,
                AppStore.ICON_SIZE,
                AppStore.ICON_SIZE)

        gtk.CellRendererPixbuf.do_render(self, window, widget, background_area,
                                         area, area, flags)
        overlay = self.overlay
        if overlay:
            dest_x = cell_area.x + self.OFFSET_X
            dest_y = cell_area.y + self.OFFSET_Y
            window.draw_pixbuf(None,
                               self._installed, # icon
                               0, 0,            # src pixbuf
                               dest_x, dest_y,  # dest in window
                               -1, -1,          # size
                               0, 0, 0)         # dither

gobject.type_register(CellRendererPixbufWithOverlay)


class AppView(gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, str),
                                       ),
    }

    def __init__(self, show_ratings, store=None):
        gtk.TreeView.__init__(self)
        self.buttons = {}
        self.focal_btn = None

        # if this hacked mode is available everything will be fast
        # and we can set fixed_height mode and still have growing rows
        # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            logging.warn("ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # a11y: this is a fake cell renderer with a zero size
        # we use it so that orca and other a11y tools get proper text to read
        # it needs to be the first one, because that is what the tools look
        # at by default
        tt = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tt, text=AppStore.COL_TEXT)
        column.set_fixed_width(1)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        # the columns that are actually visible
        tp = CellRendererPixbufWithOverlay("software-center-installed")
        tp.set_property('ypad', 2)

        column = gtk.TreeViewColumn("Icon", tp,
                                    pixbuf=AppStore.COL_ICON,
                                    overlay=AppStore.COL_INSTALLED)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        tr = CellRendererAppView(show_ratings)
        tr.set_property('xpad', 3)
        tr.set_property('ypad', 2)

        column = gtk.TreeViewColumn("Apps", tr, 
                                    markup=AppStore.COL_MARKUP,
                                    rating=AppStore.COL_POPCON,
                                    isactive=AppStore.COL_IS_ACTIVE,
                                    installed=AppStore.COL_INSTALLED, 
                                    available=AppStore.COL_AVAILABLE,
                                    action_in_progress=AppStore.COL_ACTION_IN_PROGRESS)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        if store is None:
            store = gtk.ListStore(str, gtk.gdk.Pixbuf)
        self.set_model(store)

        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated)

        # button and motion are "special"
        self.connect("style-set", self._on_style_set, tr)
        self.connect("button-press-event", self._on_button_press_event, column)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("motion-notify-event", self._on_motion, tr, column)

        self.backend = get_install_backend()
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)

    def clear_model(self):
        """ clear the model by deleting the old model """
        # clear the model harder, we have a memleak otherwise
        # if we don't do a explicit del
        old_model = self.get_model()
        self.set_model(None)
        if old_model is None:
            return
        # *ugh* deactivate the old model because otherwise it keeps
        # getting progress_changed events and eats CPU time until its
        # garbage collected
        old_model.active = False
        old_model.clear()
        del old_model


    def is_action_in_progress_for_selected_app(self):
        """
        return True if an install or remove of the current package
        is in progress
        """
        (path, column) = self.get_cursor()
        model = self.get_model()
        action_in_progress = False
        if path:
            action_in_progress = (model[path][AppStore.COL_ACTION_IN_PROGRESS] != -1)
        return action_in_progress

    def get_button(self, key):
        return self.buttons[key]

    def _get_default_font_size(self):
        raw_font_name = gtk.settings_get_default().get_property("gtk-font-name")
        (font_name, font_size) = string.rsplit(raw_font_name, maxsplit=1)
        try:
            return int(font_size)
        except:
            logging.warn("could not parse font size for font description: %s" % font_name)
        #default size of default gtk font_name ("Sans 10")
        return 10

    def _on_style_set(self, widget, old_style, tr):
        self._configure_cell_and_button_geometry(tr)
        return

    def _on_motion(self, tree, event, tr, col):
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y) or not self.buttons:
            self.window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path: return

        self.window.set_cursor(None)
        for id, btn in self.buttons.iteritems():
            rr = btn.get_param('region_rect')
            if btn.get_param('state') != gtk.STATE_INSENSITIVE:
                if rr.point_in(x, y):
                    self.window.set_cursor(self._cursor_hand)
                    if btn.get_param('state') != gtk.STATE_PRELIGHT:
                        btn.set_state(gtk.STATE_PRELIGHT)
                else:
                    if btn.get_param('state') != gtk.STATE_NORMAL:
                        btn.set_state(gtk.STATE_NORMAL)

        store = tree.get_model()
        store.row_changed(path[0], store.get_iter(path[0]))
        return

    def _on_cursor_changed(self, view):
        # trigger callback, if we do it here get_selection() returns
        # the previous selected row for some reason
        #   without the timeout a row gets multiple times selected
        #   and "wobbles" when switching between categories
        gobject.timeout_add(1, self._app_selected_timeout_cb, view)

    def _app_selected_timeout_cb(self, view):
        selection = view.get_selection()
        if not selection:
            return False
        model, it = selection.get_selected()
        model, rows = selection.get_selected_rows()
        if not rows: 
            return False
        row = rows[0][0]
        # update active app, use row-ref as argument
        model._set_active_app(row)
        #self.queue_draw()
        # emit selected signal
        name = model[row][AppStore.COL_APP_NAME]
        pkgname = model[row][AppStore.COL_PKGNAME]
        #print name, pkgname
        popcon = model[row][AppStore.COL_POPCON]
        if self.buttons.has_key('action'):
            action_button = self.buttons['action']
            if self.is_action_in_progress_for_selected_app():
                action_button.set_sensitive(False)
            else:
                action_button.set_sensitive(True)
        self.emit("application-selected", Application(name, pkgname, popcon))
        return False

    def _on_row_activated(self, view, path, column):
        model = view.get_model()
        name = model[path][AppStore.COL_APP_NAME]
        pkgname = model[path][AppStore.COL_PKGNAME]
        popcon = model[path][AppStore.COL_POPCON]
        self.emit("application-activated", Application(name, pkgname, popcon))

    def _on_button_press_event(self, view, event, col):
        if event.button != 1:
            return
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        for btn_id, btn in self.buttons.iteritems():
            rr = btn.get_param('region_rect')
            if rr.point_in(x, y) and (btn.get_param('state') != gtk.STATE_INSENSITIVE):
                self.focal_btn = btn_id
                btn.set_state(gtk.STATE_ACTIVE)
                btn.set_shadow(gtk.SHADOW_IN)

                model = view.get_model()
                appname = model[path][AppStore.COL_APP_NAME]
                pkgname = model[path][AppStore.COL_PKGNAME]
                installed = model[path][AppStore.COL_INSTALLED]
                popcon = model[path][AppStore.COL_POPCON]

                s = gtk.settings_get_default()
                gobject.timeout_add(s.get_property("gtk-timeout-initial"),
                                    self._app_activated_cb,
                                    btn,
                                    btn_id,
                                    appname,
                                    pkgname,
                                    popcon,
                                    installed,
                                    view.get_model(),
                                    path)
                break

    def _app_activated_cb(self, btn, btn_id, appname, pkgname, popcon, installed, store, path):
        if btn_id == 'info':
            btn.set_state(gtk.STATE_NORMAL)
            btn.set_shadow(gtk.SHADOW_OUT)
            self.emit("application-activated", Application(appname, pkgname, popcon))
        elif btn_id == 'action':
            btn.set_sensitive(False)
            store.row_changed(path[0], store.get_iter(path[0]))
            if installed:
                perform_action = "remove"
            else:
                perform_action = "install"
            self.emit("application-request-action", Application(appname, pkgname, popcon), perform_action)
        return False
        
    def _on_transaction_started(self, backend):
        """ callback when an application install/remove transaction has started """
        if self.buttons.has_key('action'):
            self.buttons['action'].set_sensitive(False)
        
    def _on_transaction_finished(self, backend, success):
        """ callback when an application install/remove transaction has finished """
        if self.buttons.has_key('action'):
            self.buttons['action'].set_sensitive(True)

    def _on_transaction_stopped(self, backend):
        """ callback when an application install/remove transaction has stopped """
        if self.buttons.has_key('action'):
            self.buttons['action'].set_sensitive(True)

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]

    def _configure_cell_and_button_geometry(self, tr):
        # tell the cellrenderer the text direction for renderering purposes
        tr.set_direction(self.get_direction())

        pc = self.get_pango_context()
        layout = pango.Layout(pc)

        font_size = self._get_default_font_size()
        tr.set_base_height(max(int(3.5*font_size), 32))    # 32, the pixbufoverlay height

        action_btn = CellRendererButton(layout, markup=_("Install"), alt_markup=_("Remove"))
        info_btn = CellRendererButton(layout, _("More Info"))

        max_h = max(action_btn.get_param('height'), info_btn.get_param('height'))
        tr.set_button_height(max_h+tr.get_property('ypad')*2)

        yO = tr.base_height+tr.get_property('ypad')
        action_btn.set_param('y_offset_const', yO)
        info_btn.set_param('y_offset_const', yO)

        self.buttons['action'] = action_btn
        self.buttons['info'] = info_btn
        return


# XXX should we use a xapian.MatchDecider instead?
class AppViewFilter(object):
    """
    Filter that can be hooked into AppStore to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        self.distro = get_distro()
        self.db = db
        self.cache = cache
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
        self.only_packages_without_applications = False
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def get_supported_only(self):
        return self.supported_only
    def set_only_packages_without_applications(self, v):
        """
        only show packages that are not displayed as applications

        e.g. abiword (the package document) will not be displayed
             because there is a abiword application already
        """
        self.only_packages_without_applications = v
    def get_only_packages_without_applications(self, v):
        return self.only_packages_without_applications
    def filter(self, doc, pkgname):
        """return True if the package should be displayed"""
        #logging.debug("filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.only_packages_without_applications:
            if not doc.get_value(XAPIAN_VALUE_PKGNAME):
                # "if not self.db.xapiandb.postlist("AP"+pkgname):"
                # does not work for some reason
                for m in self.db.xapiandb.postlist("AP"+pkgname):
                    return False
        if self.installed_only:
            if (not pkgname in self.cache or
                not self.cache[pkgname].is_installed):
                return False
        if self.not_installed_only:
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                return False
        if self.supported_only:
            if not self.distro.is_supported(self.cache, doc, pkgname):
                return False
        return True

def get_query_from_search_entry(search_term):
    # now build a query
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    # ensure that we only search for applicatins here, even
    # when a-x-i is loaded
    app_query =  xapian.Query("ATapplication")
    query = xapian.Query(xapian.Query.OP_AND, app_query, user_query)
    return query

def on_entry_changed(widget, data):
    new_text = widget.get_text()
    print "on_entry_changed: ", new_text
    #if len(new_text) < 3:
    #    return
    (cache, db, view) = data
    query = get_query_from_search_entry(new_text)
    view.set_model(AppStore(cache, db, icons, query))
    with ExecutionTime("model settle"):
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    # the store
    cache = apt.Cache(apt.progress.text.OpProgress())
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.prepend_search_path("/usr/share/app-install/icons/")
    icons.prepend_search_path("/usr/share/software-center/icons/")

    # now the store
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(False)
    store = AppStore(cache, db, icons, sort=True, filter=filter)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (cache, db, view))
    entry.set_text("f")

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400, 400)
    win.show_all()

    gtk.main()

