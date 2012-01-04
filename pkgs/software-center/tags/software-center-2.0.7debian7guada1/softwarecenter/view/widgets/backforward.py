# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import atk
import gtk
import cairo
import gobject
import pathbar_common

from gettext import gettext as _


# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295


class BackForwardButton(gtk.HBox):

    __gsignals__ = {'left-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,)),

                    'right-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,))}

    def __init__(self):
        gtk.HBox.__init__(self)
        self.theme = pathbar_common.PathBarStyle(self)
        sep = SeparatorPart()

        if self.get_direction() != gtk.TEXT_DIR_RTL:
            # ltr
            self.left = ButtonPartLeft('left-clicked')
            self.right = ButtonPartRight('right-clicked')
            self.set_button_atk_info_ltr()
        else:
            # rtl
            self.left = ButtonPartRight('left-clicked')
            self.right = ButtonPartLeft('right-clicked')
            self.set_button_atk_info_rtl()

        atk_obj = self.get_accessible()
        atk_obj.set_name(_('History Navigation'))
        atk_obj.set_description(_('Navigate forwards and backwards.'))
        atk_obj.set_role(atk.ROLE_PANEL)

        self.pack_start(self.left)
        self.pack_start(sep, False)
        self.pack_end(self.right)

        sep.connect_after("style-set", self._on_style_set)
        self.connect_after('size-allocate', self._on_size_allocate)
        return

    def set_button_atk_info_ltr(self):
        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        return

    def set_button_atk_info_rtl(self):
        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        return

    def _on_style_set(self, widget, oldstyle):
        # when alloc.width == 1, this is typical of an unallocated widget,
        # lets not break a sweat for nothing...
        if self.allocation.width == 1:
            return

        old_xthickness = self.theme['xthickness']
        self.theme = pathbar_common.PathBarStyle(self)
        if old_xthickness > self.theme['xthickness']:
            a = self.allocation
            self.queue_draw_area(a.x, a.y,
                                 a.width+self.theme['xthickness'], a.height)
        else:
            self.queue_draw()
        return

    def _on_size_allocate(self, widget, allocation):
        self.queue_draw()
        return

class SeparatorPart(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.theme = pathbar_common.PathBarStyle(self)
        self.set_size_request(self.theme['xthickness'], -1)

        atk_obj = self.get_accessible()
        atk_obj.set_role(atk.ROLE_SEPARATOR)

        self.connect("expose-event", self._on_expose)
        self.connect("style-set", self._on_style_set)
        return

    def _on_expose(self, widget, event):
        parent = self.get_parent()
        if not parent: return
        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.set_source_rgb(*self.theme.dark_line[self.state].tofloats())
        cr.fill()
        del cr
        return

    def _on_style_set(self, widget, old_style):
        self.theme = pathbar_common.PathBarStyle(self)
        self.set_size_request(self.theme['xthickness'], -1)
        return


class ButtonPart(gtk.DrawingArea):

    ARROW_SIZE = (12,12)
    DEFAULT_SIZE = (31, 27)

    def __init__(self, arrow_type, signal_name):
        gtk.DrawingArea.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_size_request(*self.DEFAULT_SIZE)
        self.shape = pathbar_common.SHAPE_RECTANGLE
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        self.arrow_type = arrow_type

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK|
                        gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK)

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_press)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release, signal_name)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect("button-release-event", self._on_release, signal_name)
        return

    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            self.set_state(gtk.STATE_NORMAL)
        super(ButtonPart, self).set_sensitive(is_sensitive)
        return

    def set_active(self, is_active):
        if is_active:
            self.shadow_type = gtk.SHADOW_IN
            self.set_state(gtk.STATE_ACTIVE)
        else:
            self.shadow_type = gtk.SHADOW_OUT
            self.set_state(gtk.STATE_NORMAL)
        return

    def _on_enter(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        if not self.button_down:
            self.set_state(gtk.STATE_PRELIGHT)
        else:
            self.set_active(True)
        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, widget, event, signal_name):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self.set_state(gtk.STATE_SELECTED)
            self.get_parent().emit(signal_name, event)
        return

    def _on_leave(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.set_active(False)
        return

    def _on_focus_in(self, widget, event):
        self.queue_draw()
        return

    def _on_focus_out(self, widget, event):
        self.queue_draw()
        return

    def _on_press(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.button_down = True
        self.set_active(True)
        return

    def _on_release(self, widget, event, signal_name):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        p = gtk.gdk.device_get_core_pointer()
        x, y = p.get_state(widget.window)[0]
        rr = gtk.gdk.region_rectangle(widget.allocation)
        if rr.point_in(int(x+widget.allocation.x), int(y+widget.allocation.y)):
            self.set_state(gtk.STATE_PRELIGHT)
            self.get_parent().emit(signal_name, event)
        else:
            self.set_state(gtk.STATE_NORMAL)
        return

    def expose_pathbar(self, widget, area, x, y, w, h, xo=0, wo=0):
        if not self.parent: return
        # background
        cr = widget.window.cairo_create()
        cr.rectangle(area)
        cr.clip()

        self.parent.theme.paint_bg(cr,
                                   self,
                                   x, y, w, h)
        del cr

        # arrow
        if self.has_focus():
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x+4+xo, y+4, w-8+wo, h-8),
                                   self,
                                   'button',
                                   x+4+xo, y+4,
                                   w-8+wo, h-8)

        aw, ah = self.ARROW_SIZE
        ax, ay = (area.width - aw)/2, (area.height - ah)/2,

        self.style.paint_arrow(self.window,
                               self.state,
                               self.shadow_type,
                               (ax, ay, aw, ah),
                               self,
                               "button",
                               self.arrow_type,
                               True,
                               ax, ay,
                               aw, ah)
        return


class ButtonPartLeft(ButtonPart):

    def __init__(self, sig_name):
        ButtonPart.__init__(self, gtk.ARROW_LEFT, sig_name)
        self.connect("expose-event", self._on_expose, self.expose_pathbar)
        return

    def _on_expose(self, widget, event, expose_func):
        area = event.area
        expose_func(widget,
                    area,
                    area.x,
                    area.y,
                    area.width + 10,
                    area.height,
                    wo=-10)
        return


class ButtonPartRight(ButtonPart):

    def __init__(self, sig_name):
        ButtonPart.__init__(self, gtk.ARROW_RIGHT, sig_name)
        self.connect("expose-event", self._on_expose, self.expose_pathbar)
        return

    def _on_expose(self, widget, event, expose_func):
        area = event.area
        expose_func(widget,
                    area,
                    area.x-10,
                    area.y,
                    area.width+10,
                    area.height,
                    xo=10,
                    wo=-10)
        return
