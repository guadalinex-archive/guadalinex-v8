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

import gtk
import logging
import os
import xapian

from appview import *
from catview import *

def category_activated(iconview, path, app_view, label):
    (name, pixbuf, query) = iconview.get_model()[path]
    new_model = AppStore(iconview.xapiandb, 
                         iconview.icons, 
                         query, 
                         limit=0,
                         sort=True)
    app_view.set_model(new_model)
    label.set_text("%s items" % len(new_model))

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    datadir = "/usr/share/app-install"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the categories
    cat_view = CategoriesView(datadir, db, icons)
    scroll_cat = gtk.ScrolledWindow()
    scroll_cat.add(cat_view)
    
    # and the apps
    app_store = AppStore(db, icons)
    app_view = AppView(app_store)
    scroll_app = gtk.ScrolledWindow()
    scroll_app.add(app_view)

    # status label
    label = gtk.Label()
    label.set_text("%s items" % len(app_store))

    # and a status label
    
    # pack and show
    box = gtk.VBox()
    box.pack_start(scroll_cat)
    box.pack_start(scroll_app)
    box.pack_start(label, expand=False)

    # setup signals
    cat_view.connect("item-activated", category_activated, app_view, label)

    win = gtk.Window()
    win.add(box)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
