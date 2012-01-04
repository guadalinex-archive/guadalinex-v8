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
import pango

#FIXME: These need to come from the main app
ICON_SIZE = 24
MISSING_APP_ICON = "/usr/share/icons/gnome/scalable/categories/applications-other.svg"

class PkgNamesView(gtk.TreeView):
    """ show a bunch of pkgnames with description """

    (COL_ICON,
     COL_TEXT) = range(2)

    def __init__(self, header, cache, pkgnames):
        super(PkgNamesView, self).__init__()
        model = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn(header, tr, markup=self.COL_TEXT)
        self.append_column(column)
        for pkgname in sorted(pkgnames):
            s = "%s \n<small>%s</small>" % (
                cache[pkgname].installed.summary.capitalize(), pkgname)
            # FIXME: use xapian query here to find a matching icon
            pix = gtk.gdk.pixbuf_new_from_file_at_size(MISSING_APP_ICON, 
                                                       ICON_SIZE, ICON_SIZE)
            row = model.append([pix, s])
