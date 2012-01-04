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
import cairo
import gobject
import gtk
import pango
import pathbar_common

from gettext import gettext as _


class PathBar(gtk.HBox):

    ANIMATE_FPS = 50
    ANIMATE_DELAY = 150
    ANIMATE_DURATION = 150

    def __init__(self, group=None):
        gtk.HBox.__init__(self)
        self.set_redraw_on_allocate(False)

        self._width = 0
        self._queue = []
        self._active_part = None
        self._out_of_width = False
        self._button_press_origin = None

        self._animate = False, None
        self._scroll_xO = 0
        self._no_draw = False
        self._scroller = None

        self.theme = pathbar_common.PathBarStyle(self)

        # Accessibility info
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("You are here:"))
        atk_desc.set_role(atk.ROLE_PANEL)

        self.set_events(gtk.gdk.EXPOSURE_MASK)
        self.connect('expose-event', self._on_expose_event)
        self.connect('size-allocate', self._on_size_allocate)
        self.connect('style-set', self._on_style_set)
        self.connect('realize', self._append_on_realize)
        return

    def _shrink_check(self, allocation):
        path_w = self._width
        overhang = path_w - allocation.width
        self._width -= overhang
        mpw = self.theme['min_part_width']
        for part in self.get_children():
            w = part.get_size_request()[0]
            dw = 0
            if w - overhang <= mpw:
                overhang -= w-mpw
                part.set_width(mpw)
            else:
                part.set_width(w-overhang)
                break
        self._out_of_width = True
        self.queue_draw()
        return

    def _grow_check(self, allocation):
        w_freed = allocation.width - self._width
        parts = self.get_children()
        parts.reverse()
        for part in parts:
            bw = part.get_best_width()
            w = part.get_size_request()[0]
            if w < bw:
                dw = bw - w
                if dw <= w_freed:
                    w_freed -= dw
                    part.restore_best_width()
                else:
                    part.set_width(w + w_freed)
                    w_freed = 0
                    break

        self._width = allocation.width - w_freed
        if self._width < allocation.width:
            self._out_of_width = False
        self.queue_draw()
        return

    def _compose_on_append(self, last_part):
        parts = self.get_children()
        if len(parts) == 0:
            last_part.set_shape(pathbar_common.SHAPE_RECTANGLE)
        elif len(parts) == 1:
            root_part = parts[0]
            root_part.set_shape(pathbar_common.SHAPE_START_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        else:
            tail_part = parts[-1]
            tail_part.set_shape(pathbar_common.SHAPE_MID_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        return

    def _compose_on_remove(self, last_part):
        parts = self.get_children()
        if len(parts) == 1:
            last_part.set_shape(pathbar_common.SHAPE_RECTANGLE)
        elif len(parts) == 2:
            root_part = parts[0]
            root_part.set_shape(pathbar_common.SHAPE_START_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        else:
            tail_part = parts[-1]
            tail_part.set_shape(pathbar_common.SHAPE_MID_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        return

    def _part_enter_notify(self, part, event):
        if part == self._button_press_origin:
            part.set_state(gtk.STATE_ACTIVE)
        else:
            part.set_state(gtk.STATE_PRELIGHT)
        self._part_queue_draw(part)
        return

    def _part_leave_notify(self, part, event):
        if part == self._active_part:
            part.set_state(gtk.STATE_SELECTED)
        else:
            part.set_state(gtk.STATE_NORMAL)
        self._part_queue_draw(part)
        return

    def _part_button_press(self, part, event):
        if event.button != 1: return
        self._button_press_origin = part
        part.set_state(gtk.STATE_ACTIVE)
        self._part_queue_draw(part)
        return

    def _part_button_release(self, part, event):
        if event.button != 1: return

        part_region = gtk.gdk.region_rectangle(part.allocation)
        if not part_region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            return
        if part != self._button_press_origin: return
        if self._active_part:
            self._active_part.set_state(gtk.STATE_NORMAL)
            self._part_queue_draw(self._active_part)

        self.set_active(part)
        part.set_state(gtk.STATE_PRELIGHT)
        self._button_press_origin = None
        self._part_queue_draw(part)
        return

    def _part_key_press(self, part, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            part.set_state(gtk.STATE_ACTIVE)
            self._part_queue_draw(part)
        return

    def _part_key_release(self, part, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self.set_active(part)
            part.set_state(gtk.STATE_SELECTED)
            self._part_queue_draw(part)
        return

    def _part_focus_in(self, part, event):
        self._part_queue_draw(part)
        return

    def _part_focus_out(self, part, event):
        self._part_queue_draw(part)
        return

    def _part_connect_signals(self, part):
        part.connect('enter-notify-event', self._part_enter_notify)
        part.connect('leave-notify-event', self._part_leave_notify)
        part.connect("button-press-event", self._part_button_press)
        part.connect("button-release-event", self._part_button_release)
        part.connect("key-press-event", self._part_key_press)
        part.connect("key-release-event", self._part_key_release)
        part.connect('focus-in-event', self._part_focus_in)
        part.connect('focus-out-event', self._part_focus_out)
        return

    def _part_queue_draw(self, part):
        a = part.get_allocation()
        x, y, h = a.x, a.y, a.height
        w = part.get_draw_width()
        xo = part.get_draw_xoffset()
        self.queue_draw_area(x+xo, y, w, h)
        return

    def _on_expose_event(self, widget, event):
        if self._scroll_xO:
            self._expose_scroll(widget, event)
        else:
            self._expose_normal(widget, event)
        return

    def _expose_normal(self, widget, event):
        theme = self.theme
        parts = self.get_children()
        parts.reverse()
        region = gtk.gdk.region_rectangle(event.area)

        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        for part in parts:
            if not part.invisible:
                a = part.get_allocation()
                xo = part.get_draw_xoffset()
                x, y, w, h = a.x, a.y, a.width, a.height
                w = part.get_draw_width()
                theme.paint_bg(cr, part, x+xo, y, w, h)

                x, y, w, h = part.get_layout_points()

                if part.has_focus():
                    self.style.paint_focus(self.window,
                                           part.state,
                                           (a.x+x-4, a.y+y-2, w+8, h+4),
                                           self,
                                           'button',
                                           a.x+x-4, a.y+y-2, w+8, h+4)

                theme.paint_layout(widget, part, a.x+x, a.y+y)
            else:
                part.invisible = False
        del cr
        return

    def _expose_scroll(self, widget, event):
        parts = self.get_children()
        if len(parts) < 2: return
        static_tail, scroller = parts[-2:]

        if self.get_direction() != gtk.TEXT_DIR_RTL:
            sxO = self._scroll_xO
        else:
            sxO = -self._scroll_xO

        theme = self.theme

        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        a = scroller.get_allocation()
        x, y, w, h = a.x, a.y, a.width, a.height
        w = scroller.get_draw_width()
        xo = scroller.get_draw_xoffset()
        theme.paint_bg(cr, scroller, x+xo-sxO, y, w, h)
        x, y, w, h = scroller.get_layout_points()
        theme.paint_layout(widget, scroller, a.x+x-int(sxO), a.y+y)

        a = static_tail.get_allocation()
        x, y, w, h = a.x, a.y, a.width, a.height
        w = static_tail.get_draw_width()
        xo = static_tail.get_draw_xoffset()
        theme.paint_bg(cr, static_tail, x+xo, y, w, h)
        del cr
        return

    def _on_size_allocate(self, widget, allocation):
        if self._width < allocation.width and self._out_of_width:
            self._grow_check(allocation)
        elif self._width >= allocation.width:
            self._shrink_check(allocation)

        if self._animate[0] and self.theme['enable-animations']:
            part = self._animate[1]
            part.invisible = True
            self._animate = False, None
            gobject.timeout_add(self.ANIMATE_DELAY, self._scroll_out_init, part)
        else:
            self.queue_draw()
        return

    def _on_style_set(self, widget, old_style):
        self.theme = pathbar_common.PathBarStyle(self)
        self.set_size_request(-1, -1)
        for part in self.get_children():
            part.recalc_dimensions()
        self.queue_draw()
        return

    def _append_on_realize(self, widget):
        for part, do_callback, animate in self._queue:
            self.append(part, do_callback, animate)
        return

    def _scroll_out_init(self, part):
        draw_area = part.get_allocation()
        self._scroller = gobject.timeout_add(
            max(int(1000.0 / self.ANIMATE_FPS), 10),  # interval
            self._scroll_out_cb,
            part.get_size_request()[0],
            self.ANIMATE_DURATION*0.001,   # 1 over duration (converted to seconds)
            gobject.get_current_time(),
            (draw_area.x, draw_area.y,
            draw_area.width, draw_area.height))
        return False

    def _scroll_out_cb(self, distance, duration, start_t, draw_area):
        cur_t = gobject.get_current_time()
        xO = distance - distance*((cur_t - start_t) / duration)

        if xO > 0:
            self._scroll_xO = xO
            self.queue_draw_area(*draw_area)

        else:   # final frame
            self._scroll_xO = 0
            # redraw the entire widget
            # incase some timeouts are skipped due to high system load
            self.queue_draw()
            self._scroller = None
            return False
        return True

    def has_parts(self):
        return self.get_children() == True

    def get_parts(self):
        return self.get_children()

    def get_last(self):
        if self.get_children():
            return self.get_children()[-1]
        return None

    def set_active(self, part, do_callback=True):
        if part == self._active_part: return
        if self._active_part:
            self._active_part.set_state(gtk.STATE_NORMAL)
            self._part_queue_draw(self._active_part)

        part.set_state(gtk.STATE_SELECTED)
        self._part_queue_draw(part)
        self._active_part = part
        if do_callback and part.callback:
            part.callback(self, part)
        return

    def get_active(self):
        return self._active_part

    def set_active_no_callback(self, part):
        self.set_active(part, False)
        return

    def append(self, part, do_callback=True, animate=True):
        if not self.get_property('visible'):
            self._queue.append([part, do_callback, animate])
            return

        if self._scroller:
            gobject.source_remove(self._scroller)
        self._scroll_xO = 0

        self._compose_on_append(part)
        self._width += part.get_size_request()[0]

        self.pack_start(part, False)
        self._part_connect_signals(part)
        self._animate = animate, part
        part.show()

        if do_callback:
            self.set_active(part)
        else:
            self.set_active_no_callback(part)
        return

    def append_no_callback(self, part):
        self.append(part, do_callback=False)

    def remove(self, part):
        parts = self.get_children()
        if len(parts) <= 1: return  # protect last part
        self._width -= part.get_size_request()[0]
        part.destroy()
        self._compose_on_remove(parts[-2])
        return

    def remove_all(self, keep_first_part=True, do_callback=True):
        parts = self.get_children()
        if len(parts) < 1: return
        if keep_first_part:
            if len(parts) <= 1: return
            parts = parts[1:]
        for part in parts:
            part.destroy()

        self._width = 0
        if keep_first_part:
            root = self.get_parts()[0]
            root.set_shape(pathbar_common.SHAPE_RECTANGLE)
            self._width = root.get_size_request()[0]
            if do_callback: root.callback(self, root)
        return

    def navigate_up(self):
        parts = self.get_children()
        if len(parts) > 1:
            nav_part = parts[len(parts) - 2]
            self.set_active(nav_part)
        return


class PathPart(gtk.EventBox):

    def __init__(self, parent, label, callback=None):
        gtk.EventBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_visible_window(False)

        part_atk = self.get_accessible()
        part_atk.set_name(label)
        part_atk.set_description(_('Navigates to the %s page.' % label))
        part_atk.set_role(atk.ROLE_PUSH_BUTTON)

        self.invisible = False
        self._parent = parent
        self._draw_shift = 0
        self._draw_width = 0
        self._best_width = 0
        self._layout_points = 0,0,0,0
        self._size_requisition = 0,0

        self.label = None
        self.shape = pathbar_common.SHAPE_RECTANGLE
        self.layout = None
        self.callback = callback
        self.set_label(label)

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)
        return

    def __repr__(self):
        return self.label

    def _make_layout(self):
        pc = self._parent.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.label)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        self.layout = layout
        return

    def _set_best_width(self, best_width):
        self._best_width = best_width
        return

    def _calc_layout_points(self):
        if not self.layout: self._make_layout()
        x = self._parent.theme['xpad']
        y = self._parent.theme['ypad']
        w, h = self.layout.get_pixel_extents()[1][2:]
        self._layout_points = [x, y, w, h]
        return

    def _adjust_width(self, shape, w):
        self._draw_xoffset = 0
        self._draw_width = w

        arrow_width = self._parent.theme['arrow_width']
        if shape == pathbar_common.SHAPE_RECTANGLE:
            return w

        elif shape == pathbar_common.SHAPE_START_ARROW:
            self._draw_width += arrow_width
            if self.get_direction() == gtk.TEXT_DIR_RTL:
                self._draw_xoffset -= arrow_width

        elif shape == pathbar_common.SHAPE_END_CAP:
            w += arrow_width
            self._draw_width += arrow_width
            if self.get_direction() != gtk.TEXT_DIR_RTL:
                self._layout_points[0] += arrow_width

        elif shape == pathbar_common.SHAPE_MID_ARROW:
            w += arrow_width
            self._draw_width += 2*arrow_width
            if self.get_direction() == gtk.TEXT_DIR_RTL:
                self._draw_xoffset -= arrow_width
            else:
                self._layout_points[0] += arrow_width
        return w

    def _calc_size(self, shape):
        lx, ly, w, h = self.layout.get_pixel_extents()[1]
        w += 2*self._parent.theme['xpad']
        h += 2*self._parent.theme['ypad'] + 2   # plus 2, so height is same as gtk.Entry at given font size

        w = self._adjust_width(shape, w)
        if not self.get_best_width():
            self._set_best_width(w)
        self.set_size_request(w, h)
        return

    def do_callback(self):
        self.callback(self._parent, self)
        return

    def set_label(self, label):
        if label == self.label: return
        self.label = gobject.markup_escape_text(label.strip())
        if not self.layout:
            self._make_layout()
        else:
            self.layout.set_markup(self.label)

        self._calc_layout_points()
        self._calc_size(self.shape)
        return

    def set_shape(self, shape):
        self.shape = shape
        self._calc_layout_points()
        self._calc_size(shape)
        return

    def set_width(self, w):
        theme = self._parent.theme
        lw = w-theme['arrow_width']
        if self.shape != pathbar_common.SHAPE_START_ARROW:
            lw -= theme['xpad']
        if self.shape == pathbar_common.SHAPE_MID_ARROW:
            lw -= theme['arrow_width']
        self.layout.set_width(lw*pango.SCALE)

        self._draw_width = w+theme['arrow_width']
        self.set_size_request(w, -1)
        return

    def restore_best_width(self):
        w = self.get_best_width()
        arrow_width = self._parent.theme['arrow_width']

        if self.shape == pathbar_common.SHAPE_MID_ARROW:
            w += arrow_width
        if self.shape == pathbar_common.SHAPE_END_CAP and \
            self.get_direction() == gtk.TEXT_DIR_RTL:
            self._draw_xoffset -= arrow_width
            self._layout_points[0] -= arrow_width

        self.layout.set_width(-1)
        self._draw_width = w+arrow_width
        self.set_size_request(w, -1)
        return

    def get_draw_width(self):
        return self._draw_width

    def get_draw_xoffset(self):
        return self._draw_xoffset

    def get_best_width(self):
        return self._best_width

    def get_layout_points(self):
        x, y, w, h = self._layout_points
        y = int(max((self.allocation.height-h)*0.5+0.5, y))
        return x, y, w, h

    def get_layout(self):
        return self.layout

    def recalc_dimensions(self):
        self.layout = None
        self.set_size_request(-1, -1)
        self._calc_layout_points()
        self._calc_size(self.shape)
        return

class NavigationBar(PathBar):

    APPEND_DELAY = 150

    def __init__(self, group=None):
        PathBar.__init__(self)
        self.id_to_part = {}
        return

    def add_with_id(self, label, callback, id, do_callback=True, animate=True):
        """
        Add a new button with the given label/callback

        If there is the same id already, replace the existing one
        with the new one
        """
        # check if we have the button of that id or need a new one
        if id in self.id_to_part:
            part = self.id_to_part[id]
            part.set_label(label)
        else:
            part = PathPart(parent=self, label=label, callback=callback)
            part.set_name(id)
            self.id_to_part[id] = part
            self.append(part, do_callback, animate)
        return

    def remove_id(self, id):
        if not id in self.id_to_part:
            return
        part = self.id_to_part[id]
        del self.id_to_part[id]
        self.remove(part)
        return

    def remove_all(self, keep_first_part=True, do_callback=True):
        if len(self.get_parts()) <= 1: return
        root = self.get_children()[0]
        self.id_to_part = {root.get_name(): root}
        PathBar.remove_all(self, do_callback=do_callback)
        return

    def get_button_from_id(self, id):
        """
        return the button for the given id (or None)
        """
        if not id in self.id_to_part:
            return None
        return self.id_to_part[id]


class Test:

    def __init__(self):
        self.counter = 0
        w = gtk.Window()
        w.connect("destroy", gtk.main_quit)
        w.set_size_request(384, -1)
        w.set_default_size(512, -1)
        w.set_border_width(3)

        vb = gtk.VBox()
        w.add(vb)

        pb = PathBar()
        vb.pack_start(pb, False)
        part = PathPart(pb, 'Get Free Software?')
        pb.append(part)

        add = gtk.Button(stock=gtk.STOCK_ADD)
        rem = gtk.Button(stock=gtk.STOCK_REMOVE)
        self.entry = gtk.Entry()

        vb.pack_start(add, False)
        vb.pack_start(self.entry, False)
        vb.pack_start(rem, False)
        add.connect('clicked', self.add_cb, pb)
        rem.connect('clicked', self.rem_cb, pb)

        w.show_all()
        gtk.main()
        return

    def add_cb(self, widget, pb):
        text = self.entry.get_text() or ('unnammed%s' % self.counter)
        part = PathPart(pb, text)
        pb.append(part)
        self.counter += 1
        return

    def rem_cb(self, widget, pb):
        last = pb.get_children()[-1]
        pb.remove(last)
        return

if __name__ == '__main__':
    Test()
