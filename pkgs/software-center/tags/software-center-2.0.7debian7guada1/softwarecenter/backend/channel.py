# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

import xapian
import gettext
from gettext import gettext as _
from softwarecenter.distro import get_distro
from softwarecenter.view.widgets.animatedimage import AnimatedImage

class SoftwareChannel(object):
    """
    class to represent a software channel
    """
    
    ICON_SIZE = 24
    
    def __init__(self, icons, channel_name, channel_origin, channel_component, filter_required=False):
        """
        configure the software channel object based on channel name,
        origin, and component (the latter for detecting the partner
        channel)
        """
        self._channel_name = channel_name
        self._channel_origin = channel_origin
        self._channel_component = channel_component
        self.filter_required = filter_required
        self.icons = icons
        # distro specific stuff
        self.distro = get_distro()
        # configure the channel
        self._channel_display_name = self._get_display_name_for_channel(channel_name, channel_component)
        self._channel_icon = self._get_icon_for_channel(channel_name, channel_origin, channel_component)
        self._channel_query = self._get_channel_query_for_channel(channel_name, channel_component)
        
    def get_channel_name(self):
        """
        return the channel name as represented in the xapian database
        """
        return self._channel_name
        
    def get_channel_origin(self):
        """
        return the channel origin as represented in the xapian database
        """
        return self._channel_origin
        
    def get_channel_component(self):
        """
        return the channel component as represented in the xapian database
        """
        return self._channel_component
       
    def get_channel_display_name(self):
        """
        return the display name for the corresponding channel for use in the UI
        """
        return self._channel_display_name
        
    def get_channel_icon(self):
        """
        return the icon that corresponds to each channel based
        on the channel name, its origin string or its component
        """
        return self._channel_icon

    def get_channel_query(self):
        """
        return the xapian query to be used with this software channel
        """
        return self._channel_query
        
    # TODO:  implement __cmp__ so that sort for channels is encapsulated
    #        here as well
    
    def _get_display_name_for_channel(self, channel_name, channel_component):
        if channel_component == "partner":
            channel_display_name = _("Canonical Partners")
        elif not channel_name:
            channel_display_name = _("Other")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_display_name = self.distro.get_distro_channel_description()
        else:
            channel_display_name = channel_name
        return channel_display_name
    
    def _get_icon_for_channel(self, channel_name, channel_origin, channel_component):
        if channel_component == "partner":
            channel_icon = self._get_icon("guada_icon")
        elif not channel_name:
            channel_icon = self._get_icon("unknown-channel")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_icon = self._get_icon("guada_icon")
        elif channel_origin and channel_origin.startswith("LP-PPA"):
            channel_icon = self._get_icon("ppa")
        # TODO: add check for generic repository source (e.g., Google, Inc.)
        #       self._get_icon("generic-repository")
        else:
            channel_icon = self._get_icon("unknown-channel")
        return channel_icon
    
    def _get_channel_query_for_channel(self, channel_name, channel_component):
    
        if channel_component == "partner":
            q1 = xapian.Query("XOCpartner")
            q2 = xapian.Query("AH%s-partner" % self.distro.get_codename())
            channel_query = xapian.Query(xapian.Query.OP_OR, q1, q2)
        # uncomment the following to limit the distro channel contents to only applications
#        elif channel_name == self.distro.get_distro_channel_name():
#            channel_query = xapian.Query(xapian.Query.OP_AND, 
#                                         xapian.Query("XOL" + channel_name),
#                                         xapian.Query("ATapplication"))
        else:
            channel_query = xapian.Query("XOL" + channel_name)
        return channel_query

    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon
        
    def __str__(self):
        details = []
        details.append("* SoftwareChannel")
        details.append("  get_channel_name(): %s" % self.get_channel_name())
        details.append("  get_channel_origin(): %s" % self.get_channel_origin())
        details.append("  get_channel_component(): %s" % self.get_channel_component())
        details.append("  get_channel_display_name(): %s" % self.get_channel_display_name())
        details.append("  get_channel_icon(): %s" % self.get_channel_icon())
        details.append("  get_channel_query(): %s" % self.get_channel_query())
        details.append("  filter_required: %s" % self.filter_required)
        return '\n'.join(details)
        
if __name__ == "__main__":
    import gtk
    from softwarecenter.enums import *
    icons = gtk.icon_theme_get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(SOFTWARE_CENTER_ICON_PATH)
    distro = get_distro()
    channel = SoftwareChannel(icons, distro.get_distro_channel_name(), None, None, filter_required=True)
    print channel
    channel = SoftwareChannel(icons, distro.get_distro_channel_name(), None, "partner")
    print channel

