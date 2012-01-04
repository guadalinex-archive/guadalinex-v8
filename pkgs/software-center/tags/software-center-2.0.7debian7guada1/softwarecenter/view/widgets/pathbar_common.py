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


import cairo
import colorsys
import gtk
import logging

# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

SHAPE_RECTANGLE = 0
SHAPE_START_ARROW = 1
SHAPE_MID_ARROW = 2
SHAPE_END_CAP = 3


class PathBarStyle:

    def __init__(self, pathbar):
        self.shape_map = self._load_shape_map(pathbar)

        gtk_settings = gtk.settings_get_default()
        self.theme = self._load_theme(gtk_settings)
        self.theme.build_palette(gtk_settings)
        self.properties = self.theme.get_properties(gtk_settings)
        self.gradients = self.theme.get_grad_palette()
        self.dark_line = self.theme.get_dark_line_palette()
        self.light_line = self.theme.get_light_line_palette()
        self.text = self.theme.get_text_palette()
        self.text_states = self.theme.get_text_states()
        self.base_color = None
        return

    def __getitem__(self, item):
        if self.properties.has_key(item):
            return self.properties[item]
        logging.warn('Key does not exist in the style profile: %s' % item)
        return None

    def _load_shape_map(self, pathbar):
        if pathbar.get_direction() != gtk.TEXT_DIR_RTL:
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_ltr,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_ltr,
                     SHAPE_END_CAP:     self._shape_end_cap_ltr}
        else:
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_rtl,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_rtl,
                     SHAPE_END_CAP:     self._shape_end_cap_rtl}
        return shmap

    def _load_theme(self, gtksettings):
        name = gtksettings.get_property("gtk-theme-name")
        r = ThemeRegistry()
        return r.retrieve(name)

    def _shape_rectangle(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_start_arrow_ltr(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_mid_arrow_ltr(self, cr, x, y, w, h, r, aw):
        cr.move_to(0, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.line_to(0, h)
        cr.close_path()
        return

    def _shape_end_cap_ltr(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.move_to(0, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(0, h)
        cr.close_path()
        return

    def _shape_start_arrow_rtl(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_mid_arrow_rtl(self, cr, x, y, w, h, r, aw):
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_end_cap_rtl(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def set_direction(self, direction):
        if direction != gtk.TEXT_DIR_RTL:
            self.shape_map = {SHAPE_RECTANGLE:   self._shape_rectangle,
                              SHAPE_START_ARROW: self._shape_start_arrow_ltr,
                              SHAPE_MID_ARROW:   self._shape_mid_arrow_ltr,
                              SHAPE_END_CAP:     self._shape_end_cap_ltr}
        else:
            self.shape_map = {SHAPE_RECTANGLE:   self._shape_rectangle,
                              SHAPE_START_ARROW: self._shape_start_arrow_rtl,
                              SHAPE_MID_ARROW:   self._shape_mid_arrow_rtl,
                              SHAPE_END_CAP:     self._shape_end_cap_rtl}
        return

    def paint_bg(self, cr, part, x, y, w, h, sxO=0):
        shape = self.shape_map[part.shape]
        state = part.state
        r = self["curvature"]
        aw = self["arrow_width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5-sxO, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape(cr, 0, 0, w, h, r, aw)
        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(0.0, *color1.tofloats())
        lin.add_color_stop_rgb(1.0, *color2.tofloats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # strong outline
        shape(cr, 0, 0, w, h, r, aw)
        cr.set_source_rgb(*self.dark_line[state].tofloats())
        cr.stroke()

        # inner bevel/highlight
        if r == 0: w += 1
        shape(cr, 1, 1, w-1, h-1, r, aw)
        cr.set_source_rgb(*self.light_line[state].tofloats())
        cr.stroke()
        cr.restore()
        return

    def paint_layout(self, widget, part, x, y, sxO=0):
        # draw layout
        layout = part.get_layout()
        widget.style.paint_layout(widget.window,
                                  self.text_states[part.state],
                                  False,
                                  None,   # clip area
                                  widget,
                                  None,
                                  x, y,
                                  layout)
        return

    def paint_focus(self, cr, x, y, w, h):
        self._shape_rectangle(cr, 4, 4, w-4, h-4, self["curvature"], 0)
        cr.set_source_rgb(*self.theme.bg[gtk.STATE_SELECTED].tofloats())
        cr.stroke()
        return


class PathBarColorArray:

    def __init__(self, color_array):
        self.color_array = {}
        for state in (gtk.STATE_NORMAL, gtk.STATE_ACTIVE, gtk.STATE_SELECTED, \
            gtk.STATE_PRELIGHT, gtk.STATE_INSENSITIVE):
            self.color_array[state] = color_from_gdkcolor(color_array[state])
        return

    def __getitem__(self, state):
        return self.color_array[state]


class PathBarColor:

    def __init__(self, red, green, blue):
        self.red = red
        self.green = green
        self.blue = blue
        return

    def set_alpha(self, value):
        self.alpha = value
        return

    def tofloats(self):
        return self.red, self.green, self.blue

    def toclutter(self):
        try:
            from clutter import Color
        except Exception, e:
            logging.exception('Error parsing color: %s' % e)
            raise SystemExit
        r,g,b = self.tofloats()
        return Color(int(r*255), int(g*255), int(b*255))

    def togtkgdk(self):
        r,g,b = self.tofloats()
        return gtk.gdk.Color(int(r*65535), int(g*65535), int(b*65535))

    def lighten(self):
        return self.shade(1.3)

    def darken(self):
        return self.shade(0.7)

    def shade(self, factor):
        # as seen in clutter-color.c
        h,l,s = colorsys.rgb_to_hls(*self.tofloats())

        l *= factor
        if l > 1.0:
            l = 1.0
        elif l < 0:
            l = 0

        s *= factor
        if s > 1.0:
            s = 1.0
        elif s < 0:
            s = 0

        r,g,b = colorsys.hls_to_rgb(h,l,s)
        return PathBarColor(r,g,b)

    def mix(self, color2, mix_factor):
        # as seen in Murrine's cairo-support.c
        r1, g1, b1 = self.tofloats()
        r2, g2, b2 = color2.tofloats()
        r = r1*(1-mix_factor)+r2*mix_factor
        g = g1*(1-mix_factor)+g2*mix_factor
        b = b1*(1-mix_factor)+b2*mix_factor
        return PathBarColor(r,g,b)


class Theme:

    def build_palette(self, gtksettings):
        style = gtk.rc_get_style_by_paths(gtksettings,
                                          'GtkWindow',
                                          'GtkWindow',
                                          gtk.Window)

        style = style or gtk.widget_get_default_style()

        # build pathbar color palette
        self.fg =    PathBarColorArray(style.fg)
        self.bg =    PathBarColorArray(style.bg)
        self.text =  PathBarColorArray(style.text)
        self.base =  PathBarColorArray(style.base)
        self.light = PathBarColorArray(style.base)
        self.mid =   PathBarColorArray(style.base)
        self.dark =  PathBarColorArray(style.base)
        return


class Human(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2.5,
            'min_part_width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow_width': 13,
            'scroll_duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override_base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                       self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:   (self.bg[gtk.STATE_NORMAL].shade(1.00),
                                       self.bg[gtk.STATE_NORMAL].shade(0.75)),

                  gtk.STATE_SELECTED: (self.bg[gtk.STATE_NORMAL].shade(1.11),
                                       self.bg[gtk.STATE_NORMAL]),

                  gtk.STATE_PRELIGHT: (self.bg[gtk.STATE_NORMAL].shade(0.96),
                                       self.bg[gtk.STATE_NORMAL].shade(0.91)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:   self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:   self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED: self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT: self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:   self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT: self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE: self.light[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:   gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:   gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT: gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED: gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class Clearlooks(Human):

    def get_properties(self, gtksettings):
        props = Human.get_properties(self, gtksettings)
        props['curvature'] = 3.5
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients

        selected_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.2)

        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.15),
                                       self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:   (self.bg[gtk.STATE_ACTIVE],
                                       self.bg[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED: (selected_color.shade(1.175),
                                       selected_color),

                  gtk.STATE_PRELIGHT: (self.bg[gtk.STATE_NORMAL].shade(1.3),
                                       selected_color.shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_light_line_palette(self):
        palette = Human.get_light_line_palette(self)
        palette[gtk.STATE_ACTIVE] = self.bg[gtk.STATE_ACTIVE]
        return palette


class InHuman(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2.5,
            'min_part_width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow_width': 13,
            'scroll_duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override_base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                       self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:   (self.bg[gtk.STATE_NORMAL].shade(1.00),
                                       self.bg[gtk.STATE_NORMAL].shade(0.75)),

                  gtk.STATE_SELECTED: (self.bg[gtk.STATE_NORMAL].shade(1.09),
                                       self.bg),

                  gtk.STATE_PRELIGHT: (self.bg[gtk.STATE_SELECTED].shade(1.35),
                                       self.bg[gtk.STATE_SELECTED].shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:   self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:   self.text[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED: self.text[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT: self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:   self.bg[gtk.STATE_ACTIVE].lighten(),
                   gtk.STATE_PRELIGHT: self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:   gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:   gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT: gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED: gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class DustSand(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2.5,
            'min_part_width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow_width': 13,
            'scroll_duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override_base': False
            }
        return props

    def get_grad_palette(self):

        selected_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.4)

        prelight_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.175)

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.42),
                                       self.bg[gtk.STATE_NORMAL].shade(1.1)),

                  gtk.STATE_ACTIVE:      (prelight_color,
                                          prelight_color.shade(1.07)),

                  gtk.STATE_SELECTED:    (selected_color.shade(1.35),
                                          selected_color.shade(1.1)),

                  gtk.STATE_PRELIGHT:    (prelight_color.shade(1.74),
                                          prelight_color.shade(1.42)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:      self.text[gtk.STATE_ACTIVE],
                   gtk.STATE_SELECTED:    self.text[gtk.STATE_SELECTED],
                   gtk.STATE_PRELIGHT:    self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_NORMAL].shade(0.575),
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE].shade(0.5),
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT].shade(0.575),
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_SELECTED].shade(0.575),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_NORMAL].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE].shade(0.95),
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT].lighten(),
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:      gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:      gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT:    gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED:    gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class Dust(DustSand):

    def get_grad_palette(self):

        selected_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.5)

        prelight_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.175)

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.4),
                                       self.bg[gtk.STATE_NORMAL].shade(1.1)),

                  gtk.STATE_ACTIVE:      (self.bg[gtk.STATE_ACTIVE].shade(1.2),
                                          self.bg[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED:    (selected_color.shade(1.5),
                                          selected_color.shade(1.2)),

                  gtk.STATE_PRELIGHT:    (prelight_color.shade(1.74),
                                          prelight_color.shade(1.42)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_dark_line_palette(self):
        palette = DustSand.get_dark_line_palette(self)
        palette[gtk.STATE_SELECTED] = self.bg[gtk.STATE_NORMAL].shade(0.575)
        return palette

    def get_light_line_palette(self):
        palette = DustSand.get_light_line_palette(self)
        palette[gtk.STATE_SELECTED] = self.bg[gtk.STATE_NORMAL].shade(1.15)
        return palette


class Ambiance(DustSand):

    def get_properties(self, gtksettings):
        props = DustSand.get_properties(self, gtksettings)
        props['curvature'] = 4.5
        return props

    def get_grad_palette(self):
        focus_color = color_from_string('#FE765E')
        selected_color = self.bg[gtk.STATE_NORMAL].mix(focus_color,
                                                       0.07)
        prelight_color = self.bg[gtk.STATE_NORMAL].mix(focus_color,
                                                       0.33)

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.2),
                                       self.bg[gtk.STATE_NORMAL].shade(0.85)),

                  gtk.STATE_ACTIVE:   (self.bg[gtk.STATE_NORMAL].shade(0.96),
                                       self.bg[gtk.STATE_NORMAL].shade(0.65)),

                  gtk.STATE_SELECTED: (selected_color.shade(1.075),
                                       selected_color.shade(0.875)),

                  gtk.STATE_PRELIGHT: (prelight_color.shade(1.35),
                                       prelight_color.shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette


class Radiance(Ambiance):

    def get_grad_palette(self):
        palette = Ambiance.get_grad_palette(self)
        palette[gtk.STATE_NORMAL] =  (self.mid[gtk.STATE_NORMAL].shade(1.25),
                                      self.bg[gtk.STATE_NORMAL].shade(0.9))
        return palette


class NewWave(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2,
            'min_part_width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 4,
            'arrow_width': 13,
            'scroll_duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override_base': True
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients

        active_color = self.bg[gtk.STATE_ACTIVE].mix(color_from_string('#FDCF9D'),
                                                     0.45)

        selected_color = self.bg[gtk.STATE_NORMAL].mix(color_from_string('#FDCF9D'),
                                                       0.2)

        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                       self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:   (active_color.shade(1.1),
                                       self.bg[gtk.STATE_ACTIVE].shade(0.95)),

                  gtk.STATE_PRELIGHT: (color_from_string('#FDCF9D'),
                                       color_from_string('#FCAE87')),

                  gtk.STATE_SELECTED: (selected_color.shade(1.2),
                                       selected_color),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:   self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:   self.text[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT: self.text[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED: self.text[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:   self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:   self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:   self.bg[gtk.STATE_ACTIVE].shade(0.97),
                   gtk.STATE_PRELIGHT: color_from_string('#FDCF9D'),
                   gtk.STATE_SELECTED: self.bg[gtk.STATE_SELECTED].lighten(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:   gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:   gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT: gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED: gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class Hicolor(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 0,
            'min_part_width': 48,
            'xpad': 15,
            'ypad': 10,
            'xthickness': 2,
            'ythickness': 2,
            'spacing': 10,
            'arrow_width': 15,
            'scroll_duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override_base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:     (self.mid[gtk.STATE_NORMAL],
                                          self.mid[gtk.STATE_NORMAL]),

                  gtk.STATE_ACTIVE:      (self.mid[gtk.STATE_ACTIVE],
                                          self.mid[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED:    (self.mid[gtk.STATE_SELECTED],
                                          self.mid[gtk.STATE_SELECTED]),

                  gtk.STATE_PRELIGHT:    (self.mid[gtk.STATE_PRELIGHT],
                                          self.mid[gtk.STATE_PRELIGHT]),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:      self.text[gtk.STATE_ACTIVE],
                   gtk.STATE_SELECTED:    self.text[gtk.STATE_SELECTED],
                   gtk.STATE_PRELIGHT:    self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_ACTIVE:      self.dark[gtk.STATE_ACTIVE],
                   gtk.STATE_PRELIGHT:    self.dark[gtk.STATE_PRELIGHT],
                   gtk.STATE_SELECTED:    self.dark[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE: self.dark[gtk.STATE_INSENSITIVE]}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_ACTIVE:      self.light[gtk.STATE_ACTIVE],
                   gtk.STATE_PRELIGHT:    self.light[gtk.STATE_PRELIGHT],
                   gtk.STATE_SELECTED:    self.light[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE: self.light[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:      gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:      gtk.STATE_ACTIVE,
                  gtk.STATE_PRELIGHT:    gtk.STATE_PRELIGHT,
                  gtk.STATE_SELECTED:    gtk.STATE_SELECTED,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class ThemeRegistry:

    REGISTRY = {"Human": Human,
                "Human-Clearlooks": Clearlooks,
                "Clearlooks": Clearlooks,
                "InHuman": InHuman,
                "HighContrastInverse": Hicolor,
                "HighContrastLargePrintInverse": Hicolor,
                "Dust": Dust,
                "Dust Sand": DustSand,
                "New Wave": NewWave,
                "Ambiance": Ambiance,
                "Radiance": Radiance}

    def retrieve(self, theme_name):
        if self.REGISTRY.has_key(theme_name):
            logging.debug("Styling hints found for %s..." % theme_name)
            return self.REGISTRY[theme_name]()
        logging.warn("No styling hints for %s were found... using Human hints." % theme_name)
        return Clearlooks()


def color_from_gdkcolor(gdkcolor):
    return PathBarColor(gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float)


def color_from_string(spec):
    color = gtk.gdk.color_parse(spec)
    return PathBarColor(color.red_float, color.green_float, color.blue_float)




