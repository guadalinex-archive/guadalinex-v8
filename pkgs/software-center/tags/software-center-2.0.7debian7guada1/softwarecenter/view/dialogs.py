# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
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
from gettext import gettext as _
from pkgview import PkgNamesView

class DetailsMessageDialog(gtk.MessageDialog):
    """Message dialog with optional details expander"""
    def __init__(self,
                 parent=None, 
                 title="", 
                 primary=None, 
                 secondary=None, 
                 details=None,
                 buttons=gtk.BUTTONS_OK, 
                 type=gtk.MESSAGE_INFO):
        gtk.MessageDialog.__init__(self, parent, 0, type, buttons, primary)
        self.set_title(title)
        if secondary:
            self.format_secondary_markup(secondary)
        if details:
            textview = gtk.TextView()
            textview.set_size_request(500, 300)
            textview.get_buffer().set_text(details)
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            scroll.add(textview)
            expand = gtk.Expander(_("Details"))
            expand.add(scroll)
            expand.show_all()
            self.get_content_area().pack_start(expand)
        if parent:
            self.set_modal(True)
            self.set_property("skip-taskbar-hint", True)

def messagedialog(parent=None, 
                  title="", 
                  primary=None, 
                  secondary=None, 
                  details=None,
                  buttons=gtk.BUTTONS_OK, 
                  type=gtk.MESSAGE_INFO):
    """ run a dialog """
    dialog = DetailsMessageDialog(parent=parent, title=title,
                                  primary=primary, secondary=secondary,
                                  details=details, type=type, 
                                  buttons=buttons)
    result = dialog.run()
    dialog.destroy()
    return result

def error(parent, primary, secondary, details=None):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary, 
                         secondary=secondary,
                         details=details,
                         type=gtk.MESSAGE_ERROR)

def confirm_remove(parent, primary, cache, button_text, icon_path, depends=None):
    """Confirm removing of the given app with the given depends"""
    dialog = gtk.MessageDialog(parent=parent, flags=0, 
                               type=gtk.MESSAGE_QUESTION, 
                               message_format=None)
    dialog.set_resizable(True)
    dialog.add_button(_("Cancel"), gtk.RESPONSE_CANCEL)
    dialog.add_button(button_text, gtk.RESPONSE_ACCEPT)

    # fixes launchpad bug #560021
    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 32, 32)
    image = dialog.get_image()
    image.set_from_pixbuf(pixbuf)

    dialog.set_markup(primary)
    # add the dependencies
    if depends:
        vbox = dialog.get_content_area()
        # FIXME: make this a generic pkgview widget
        view = PkgNamesView(_("Dependency"), cache, depends)
        view.set_headers_visible(False)
        scrolled = gtk.ScrolledWindow()
        scrolled.set_size_request(-1, 200)
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        scrolled.add(view)
        scrolled.show_all()
        # FIXME: this needs padding on the left side so 
        # it lines up with the text
        vbox.pack_start(scrolled)
    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_ACCEPT:
        return True
    return False
    

if __name__ == "__main__":
    messagedialog(None, primary="first, no second")
    error(None, "first", "second")
    error(None, "first", "second", "details ......")
    
