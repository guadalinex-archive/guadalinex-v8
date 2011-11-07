# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-
#
# «gtk_ui» - GTK user interface
#
# Copyright (C) 2005 Junta de Andalucía
# Copyright (C) 2005, 2006, 2007, 2008, 2009 Canonical Ltd.
#
# Authors:
#
# - Javier Carranza <javier.carranza#interactors._coop>
# - Juan Jesús Ojeda Croissier <juanje#interactors._coop>
# - Antonio Olmo Titos <aolmo#emergya._info>
# - Gumer Coronel Pérez <gcoronel#emergya._info>
# - Colin Watson <cjwatson@ubuntu.com>
# - Evan Dandrea <ev@ubuntu.com>
# - Mario Limonciello <superm1@ubuntu.com>
#
# This file is part of Ubiquity.
#
# Ubiquity is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or at your option)
# any later version.
#
# Ubiquity is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with Ubiquity; if not, write to the Free Software Foundation, Inc., 51
# Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import sys
import os
import subprocess
import traceback
import syslog
import atexit
import gettext
import ConfigParser

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

#in query mode we won't be in X, but import needs to pass
if 'DISPLAY' in os.environ:
    from gi.repository import Gtk, Gdk, GObject
    GObject.threads_init()
    from ubiquity import gtkwidgets

from ubiquity import filteredcommand, gconftool, gsettings, i18n, validation, misc
from ubiquity.plugin import Plugin
from ubiquity.components import install, plugininstall, partman_commit
import ubiquity.progressposition
import ubiquity.frontend.base
from ubiquity.frontend.base import BaseFrontend

# We create class attributes dynamically from UI files, and it's far too
# tedious to list them all.
__pychecker__ = 'no-classattr'

# Define global path
PATH = os.environ.get('UBIQUITY_PATH', False) or '/usr/share/ubiquity'

# Define global pixmaps location
PIXMAPS = os.environ.get('PIXMAPS', False) or '/usr/share/pixmaps'
 
# Define ui path
UIDIR = os.environ.get('UBIQUITY_GLADE', False) or os.path.join(PATH, 'gtk')
os.environ['UBIQUITY_GLADE'] = UIDIR


# Define locale path
LOCALEDIR = "/usr/share/locale"

def set_root_cursor(cursor=None):
    if cursor is None:
        cursor = Gdk.Cursor.new(Gdk.CursorType.ARROW)
    win = Gdk.get_default_root_window()
    if win:
        win.set_cursor(cursor)
    while Gtk.events_pending():
        Gtk.main_iteration()

class Controller(ubiquity.frontend.base.Controller):
    def add_builder(self, builder):
        self._wizard.builders.append(builder)

    def translate(self, lang=None, just_me=True, not_me=False, reget=False):
        if lang:
            self._wizard.locale = lang
        self._wizard.translate_pages(lang, just_me, not_me, reget)

    def allow_go_forward(self, allowed):
        try:
            self._wizard.allow_go_forward(allowed)
        except AttributeError:
            pass

    def allow_go_backward(self, allowed):
        try:
            self._wizard.allow_go_backward(allowed)
        except AttributeError:
            pass

    def allow_change_step(self, allowed):
        try:
            self._wizard.allow_change_step(allowed)
        except AttributeError:
            pass

    def allowed_change_step(self):
        return self._wizard.allowed_change_step

    def go_forward(self):
        self._wizard.next.activate()

    def go_backward(self):
        self._wizard.back.activate()

    def go_to_page(self, widget):
        self._wizard.set_current_page(self._wizard.steps.page_num(widget))

    def toggle_top_level(self):
        if self._wizard.live_installer.get_property('visible'):
            self._wizard.live_installer.hide()
        else:
            self._wizard.live_installer.show()
        self._wizard.refresh()

    def toggle_progress_section(self):
        if self._wizard.progress_section.get_property('visible'):
            self._wizard.progress_section.hide()
        else:
            self._wizard.progress_section.show()
        self._wizard.refresh()

    def get_string(self, name, lang=None, prefix=None):
        return self._wizard.get_string(name, lang, prefix)

    def toggle_navigation_control(self,hideFlag):
        if hideFlag:
            self._wizard.navigation_control.show()
        else:
            self._wizard.navigation_control.hide()
        self._wizard.refresh()

    def toggle_next_button(self, label='gtk-go-forward'):
        self._wizard.toggle_next_button(label)

    def switch_to_install_interface(self):
        self._wizard.switch_to_install_interface()

class Wizard(BaseFrontend):

    def __init__(self, distro):
        def add_subpage(self, steps, name):
            """Inserts a subpage into the notebook.  This assumes the file
            shares the same base name as the page you are looking for."""
            widget = None
            uifile = UIDIR + '/' + name + '.ui'
            if os.path.exists(uifile):
                self.builder.add_from_file(uifile)
                widget = self.builder.get_object(name)
                steps.append_page(widget, None)
            else:
                print >>sys.stderr, 'Could not find ui file %s' % name
            return widget

        def add_widget(self, widget):
            """Make a widget callable by the toplevel."""
            if not isinstance(widget, Gtk.Widget):
                return
            name = Gtk.Buildable.get_name(widget)
            widget.set_name(name)
            if 'UBIQUITY_LDTP' in os.environ:
                atk_desc = widget.get_accessible()
                atk_desc.set_name(name)
            self.all_widgets.add(widget)
            setattr(self, widget.get_name(), widget)
            # We generally want labels to be selectable so that people can
            # easily report problems in them
            # (https://launchpad.net/bugs/41618), but GTK+ likes to put
            # selectable labels in the focus chain, and I can't seem to turn
            # this off in glade and have it stick. Accordingly, make sure
            # labels are unfocusable here.
            label = None
            if isinstance(widget, Gtk.Label):
                label = widget
            elif isinstance(widget, gtkwidgets.StateBox):
                label = widget.label

            # If we're runing Orca, we want to be able to read labels.
            if label:
                label.set_property('can-focus', self.screen_reader)
                label.set_selectable(self.screen_reader)

        BaseFrontend.__init__(self, distro)
        self.previous_excepthook = sys.excepthook
        sys.excepthook = self.excepthook

        # declare attributes
        self.all_widgets = set()
        self.gconf_previous = {}
        self.gsettings_previous = {}
        self.thunar_previous = {}
        self.language_questions = ('live_installer', 'quit', 'back', 'next',
                                   'warning_dialog', 'warning_dialog_label',
                                   'cancelbutton', 'exitbutton',
                                   'install_button', 'restart_to_continue')
        self.current_page = None
        self.backup = None
        self.allowed_change_step = True
        self.allowed_go_backward = True
        self.allowed_go_forward = True
        self.stay_on_page = False
        self.progress_position = ubiquity.progressposition.ProgressPosition()
        self.progress_cancelled = False
        self.installing = False
        self.installing_no_return = False
        self.returncode = 0
        self.history = []
        self.builder = Gtk.Builder()
        self.grub_options = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        self.finished_installing = False
        self.finished_pages = False
        self.parallel_db = None
        self.timeout_id = None
        self.screen_reader = False

        # To get a "busy mouse":
        self.watch = Gdk.Cursor.new(Gdk.CursorType.WATCH)
        set_root_cursor(self.watch)
        atexit.register(set_root_cursor)

        self.laptop = misc.execute("laptop-detect")

        # Are we running alongside Orca?
        with open('/proc/cmdline') as fp:
            if 'access=v3' in fp.read():
                self.screen_reader = True

        # set default language
        self.locale = i18n.reset_locale(self)

        GObject.timeout_add_seconds(30, self.poke_screensaver)

        # set custom language
        self.set_locales()

        # Thin progress bar
        provider = Gtk.CssProvider()
        provider.load_from_data(
            '''GtkProgressBar {
              -GtkProgressBar-min-horizontal-bar-height : 10
              }''')

        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
            provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # load the main interface
        self.builder.add_from_file('%s/ubiquity.ui' % UIDIR)
        
        self.builders = [self.builder]
        self.pages = []
        self.pagesindex = 0
        self.pageslen = 0
        steps = self.builder.get_object("steps")
        found_install = False
        for mod in self.modules:
            if hasattr(mod.module, 'PageGtk'):
                mod.ui_class = mod.module.PageGtk
                mod.controller = Controller(self)
                mod.ui = mod.ui_class(mod.controller)
                mod.title = mod.ui.get('plugin_title')
                widgets = mod.ui.get('plugin_widgets')
                optional_widgets = mod.ui.get('plugin_optional_widgets')
                if not found_install:
                    found_install = mod.ui.get('plugin_is_install')
                if widgets or optional_widgets:
                    def fill_out(widget_list):
                        rv = []
                        if not isinstance(widget_list, list):
                            widget_list = [widget_list]
                        for w in widget_list:
                            if not w:
                                continue
                            if isinstance(w, str):
                                w = add_subpage(self, steps, w)
                            else:
                                steps.append_page(w, None)
                            rv.append(w)
                        return rv
                    mod.widgets = fill_out(widgets)
                    mod.optional_widgets = fill_out(optional_widgets)
                    mod.all_widgets = mod.widgets + mod.optional_widgets
                    self.pageslen += 1
                    self.pages.append(mod)

        # If no plugins declare they are install, then we'll say the last one
        # is
        if not found_install:
            self.pages[self.pageslen - 1].ui.plugin_is_install = True

        self.toplevels = set()
        for builder in self.builders:
            for widget in builder.get_objects():
                add_widget(self, widget)
                if isinstance(widget, Gtk.Window):
                    self.toplevels.add(widget)
        self.builder.connect_signals(self)

        self.stop_debconf()
        self.translate_widgets(reget=True)

        self.customize_installer()
        misc.add_connection_watch(self.network_change)

        # Put up the a11y indicator in maybe-ubiquity mode
        if ('UBIQUITY_GREETER' in os.environ and os.path.exists('/usr/bin/casper-a11y-enable')):
            try:
                from gi.repository import AppIndicator3 as AppIndicator
                self.indicator = AppIndicator.Indicator.new('ubiquity', 'accessibility-directory',
                    AppIndicator.IndicatorCategory.OTHER)
                self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
                self.indicator.set_menu(self.builder.get_object('a11y_indicator_menu'))
                self.live_installer.connect('key-press-event', self.a11y_profile_keys)
                if os.path.exists('/usr/bin/canberra-gtk-play'):
                    subprocess.Popen(['/usr/bin/canberra-gtk-play', '--id=system-ready'], preexec_fn=misc.drop_all_privileges)
            except:
                print >>sys.stderr, "Unable to set up accessibility profile support."

    def all_children(self, parent):
        if isinstance(parent, Gtk.Container):
            def recurse(x, y):
                return x + self.all_children(y)
            rv = reduce(recurse, parent.get_children(), [parent])
            return rv
        else:
            return [parent]

    def translate_pages(self, lang=None, just_current=True, not_current=False, reget=False):
        current_page = self.pages[self.pagesindex]
        if just_current:
            pages = [current_page]
        else:
            pages = self.pages

        if reget:
            self.translate_reget(lang)

        widgets = []
        for p in pages:
            # There's no sense retranslating the page we're leaving.
            if not_current and p == current_page:
                continue
            prefix = p.ui.get('plugin_prefix')
            for w in p.all_widgets:
                for c in self.all_children(w):
                    widgets.append((c, prefix))
        if not just_current:
            for toplevel in self.toplevels:
                if toplevel.get_name() != 'live_installer':
                    for c in self.all_children(toplevel):
                        widgets.append((c, None))
        self.translate_widgets(lang=lang, widgets=widgets, reget=False)
        self.set_page_title(current_page, lang)

        # Allow plugins to provide a hook for translation.
        for p in pages:
            # There's no sense retranslating the page we're leaving.
            if not_current and p == current_page:
                continue
            if hasattr(p.ui, 'plugin_translate'):
                try:
                    p.ui.plugin_translate(lang or self.locale)
                except Exception, e:
                    print >>sys.stderr, 'Could not translate page (%s): %s' \
                                        % (p.module.NAME, str(e))

    def excepthook(self, exctype, excvalue, exctb):
        """Crash handler."""

        if (issubclass(exctype, KeyboardInterrupt) or
            issubclass(exctype, SystemExit)):
            return

        # Restore the default cursor if we were using a spinning cursor on the
        # root window.
        try:
            set_root_cursor()
        except Exception:
            pass

        tbtext = ''.join(traceback.format_exception(exctype, excvalue, exctb))
        syslog.syslog(syslog.LOG_ERR,
                      "Exception in GTK frontend (invoking crash handler):")
        for line in tbtext.split('\n'):
            syslog.syslog(syslog.LOG_ERR, line)
        print >>sys.stderr, ("Exception in GTK frontend"
                             " (invoking crash handler):")
        print >>sys.stderr, tbtext

        self.post_mortem(exctype, excvalue, exctb)

        if os.path.exists('/usr/share/apport/apport-gtk'):
            self.previous_excepthook(exctype, excvalue, exctb)
        else:
            self.crash_detail_label.set_text(tbtext)
            self.crash_dialog.run()
            self.crash_dialog.hide()
            self.live_installer.hide()
            while Gtk.events_pending():
                Gtk.main_iteration()
            misc.execute_root("apport-bug", "ubiquity")
            sys.exit(1)

    def network_change(self, online=False):
        from gi.repository import GObject
        if not online:
            self.set_online_state(False)
            return
        if self.timeout_id:
            GObject.source_remove(self.timeout_id)
        self.timeout_id = GObject.timeout_add(300, self.check_returncode)

    def set_online_state(self, state):
        for p in self.pages:
            if hasattr(p.ui, 'plugin_set_online_state'):
                p.ui.plugin_set_online_state(state)

    def thunar_set_volmanrc (self, fields):
        previous = {}
        if 'SUDO_USER' in os.environ:
            thunar_dir = os.path.expanduser('~%s/.config/Thunar' %
                                            os.environ['SUDO_USER'])
        else:
            thunar_dir = os.path.expanduser('~/.config/Thunar')
        if os.path.isdir(thunar_dir):
            thunar_volmanrc = '%s/volmanrc' % thunar_dir
            parser = ConfigParser.RawConfigParser()
            parser.optionxform = str # case-sensitive
            parser.read(thunar_volmanrc)
            if not parser.has_section('Configuration'):
                parser.add_section('Configuration')
            for key, value in fields.iteritems():
                if parser.has_option('Configuration', key):
                    previous[key] = parser.get('Configuration', key)
                else:
                    previous[key] = 'TRUE'
                parser.set('Configuration', key, value)
            try:
                thunar_volmanrc_new = open('%s.new' % thunar_volmanrc, 'w')
                parser.write(thunar_volmanrc_new)
                thunar_volmanrc_new.close()
                os.rename('%s.new' % thunar_volmanrc, thunar_volmanrc)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                pass
        return previous

    def disable_terminal(self):
        terminal_key = '/apps/metacity/global_keybindings/run_command_terminal'
        self.gconf_previous[terminal_key] = gconftool.get(terminal_key)
        gconftool.set(terminal_key, 'string', 'disabled')
        atexit.register(self.enable_terminal)

    def enable_terminal(self):
        terminal_key = '/apps/metacity/global_keybindings/run_command_terminal'
        if self.gconf_previous[terminal_key] == '':
            gconftool.unset(terminal_key)
        else:
            gconftool.set(terminal_key, 'string',
                          self.gconf_previous[terminal_key])

    def disable_logout_indicator(self):
        gs_schema = 'com.canonical.indicator.session'
        gs_key = 'suppress-logout-menuitem'
        gs_previous = '%s/%s' % (gs_schema, gs_key)
        if gs_previous in self.gsettings_previous:
            return

        gs_value = gsettings.get(gs_schema, gs_key)
        self.gsettings_previous[gs_previous] = gs_value

        if gs_value != True:
            gsettings.set(gs_schema, gs_key, True)

        atexit.register(self.enable_logout_indicator)

    def enable_logout_indicator(self):
        gs_schema = 'com.canonical.indicator.session'
        gs_key = 'suppress-logout-menuitem'
        gs_previous = '%s/%s' % (gs_schema, gs_key)
        gs_value = self.gsettings_previous[gs_previous]

        gsettings.set(gs_schema, gs_key, gs_value)

    # Disable gnome-volume-manager automounting to avoid problems during
    # partitioning.
    def disable_volume_manager(self):
        volumes_visible = ('org.gnome.nautilus.desktop', 'volumes-visible', False)
        media_automount = ('org.gnome.desktop.media-handling', 'automount', False)
        media_automount_open = ('org.gnome.desktop.media-handling', 'automount-open', False)
        media_autorun_never = ('org.gnome.desktop.media-handling', 'autorun-never', True)
        for keys in (volumes_visible, media_automount, media_automount_open, media_autorun_never):
            gs_schema = keys[0]
            gs_key = keys[1]
            gs_wantedvalue = keys[2]
            gs_previous = '%s/%s' % (gs_schema, gs_key)
            if gs_previous in self.gsettings_previous:
                continue

            gs_value = gsettings.get(gs_schema, gs_key)
            self.gsettings_previous[gs_previous] = gs_value

            if gs_value != gs_wantedvalue:
                gsettings.set(gs_schema, gs_key, gs_wantedvalue)

        self.thunar_previous = self.thunar_set_volmanrc(
            {'AutomountDrives': 'FALSE', 'AutomountMedia': 'FALSE'})

        atexit.register(self.enable_volume_manager)

    def enable_volume_manager(self):
        volumes_visible = ('org.gnome.nautilus.desktop', 'volumes-visible')
        media_automount = ('org.gnome.desktop.media-handling', 'automount')
        media_automount_open = ('org.gnome.desktop.media-handling', 'automount-open')
        media_autorun_never = ('org.gnome.desktop.media-handling', 'autorun-never')
        for keys in (volumes_visible, media_automount, media_automount_open, media_autorun_never):
            gs_schema = keys[0]
            gs_key = keys[1]
            gs_previous = '%s/%s' % (gs_schema, gs_key)
            gs_value = self.gsettings_previous[gs_previous]

            gsettings.set(gs_schema, gs_key, gs_value)

        if self.thunar_previous:
            self.thunar_set_volmanrc(self.thunar_previous)

    def a11y_profile_keys(self, window, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.keyval_from_name('h'):
            self.a11y_profile_high_contrast_activate()
        elif event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.keyval_from_name('s'):
            self.a11y_profile_screen_reader_activate()

    def a11y_profile_high_contrast_activate(self, widget=None):
        subprocess.call(['log-output', '-t', 'ubiquity',
                         '--pass-stdout', '/usr/bin/casper-a11y-enable',
                         'high-contrast'], preexec_fn=misc.drop_all_privileges)
        os.environ['UBIQUITY_A11Y_PROFILE'] = 'high-contrast'

    def a11y_profile_screen_reader_activate(self, widget=None):
        subprocess.call(['log-output', '-t', 'ubiquity',
                         '--pass-stdout', '/usr/bin/casper-a11y-enable',
                         'blindness'], preexec_fn=misc.drop_all_privileges)
        os.environ['UBIQUITY_A11Y_PROFILE'] = 'screen-reader'
        if os.path.exists('/usr/bin/orca'):
            subprocess.Popen(['/usr/bin/orca', '-n'], preexec_fn=misc.drop_all_privileges)
             
    def a11y_profile_keyboard_modifiers_activate(self, widget=None):
        subprocess.call(['log-output', '-t', 'ubiquity',
                         '--pass-stdout', '/usr/bin/casper-a11y-enable',
                         'keyboard-modifiers'], preexec_fn=misc.drop_all_privileges)
        os.environ['UBIQUITY_A11Y_PROFILE'] = 'keyboard-modifiers'

    def a11y_profile_onscreen_keyboard_activate(self, widget=None):
        subprocess.call(['log-output', '-t', 'ubiquity',
                         '--pass-stdout', '/usr/bin/casper-a11y-enable',
                         'onscreen-keyboard'], preexec_fn=misc.drop_all_privileges)
        os.environ['UBIQUITY_A11Y_PROFILE'] = 'onscreen-keyboard'
        if os.path.exists('/usr/bin/onboard'):
            subprocess.Popen(['/usr/bin/onboard'], preexec_fn=misc.drop_all_privileges)

    def run(self):
        """run the interface."""

        if os.getuid() != 0:
            title = ('This installer must be run with administrative '
                     'privileges, and cannot continue without them.')
            dialog = Gtk.MessageDialog(self.live_installer, Gtk.DialogFlags.MODAL,
                                       Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
                                       title)
            dialog.run()
            sys.exit(1)

        self.disable_volume_manager()

        if 'UBIQUITY_ONLY' in os.environ:
            self.disable_logout_indicator()
            if not 'UBIQUITY_DEBUG' in os.environ:
                self.disable_terminal()

        # show interface
        self.allow_change_step(True)

        # Auto-connecting signals with additional parameters does not work.
        self.grub_new_device_entry.connect('changed', self.grub_verify_loop,
            self.grub_fail_okbutton)

        if 'UBIQUITY_AUTOMATIC' in os.environ:
            self.debconf_progress_start(0, self.pageslen,
                self.get_string('ubiquity/install/checking'))
            self.debconf_progress_cancellable(False)
            self.refresh()

        self.set_current_page(0)

        while(self.pagesindex < len(self.pages)):
            if self.current_page is None:
                return self.returncode

            if not self.pages[self.pagesindex].filter_class:
                # This page is just a UI page
                self.dbfilter = None
                self.dbfilter_status = None
                if self.set_page(self.pages[self.pagesindex].module.NAME):
                    self.run_main_loop()
            else:
                old_dbfilter = self.dbfilter
                if issubclass(self.pages[self.pagesindex].filter_class, Plugin):
                    ui = self.pages[self.pagesindex].ui
                else:
                    ui = None
                self.start_debconf()
                self.dbfilter = self.pages[self.pagesindex].filter_class(self, ui=ui)

                if self.dbfilter is not None and self.dbfilter != old_dbfilter:
                    self.allow_change_step(False)
                    GObject.idle_add(lambda: self.dbfilter.start(auto_process=True))

                self.pages[self.pagesindex].controller.dbfilter = self.dbfilter
                Gtk.main()
                self.pages[self.pagesindex].controller.dbfilter = None

            if self.backup or self.dbfilter_handle_status():
                if self.current_page is not None and not self.backup:
                    self.process_step()
                    if not self.stay_on_page:
                        self.pagesindex = self.pagesindex + 1
                    if 'UBIQUITY_AUTOMATIC' in os.environ:
                        # if no debconf_progress, create another one, set start to pageindex
                        self.debconf_progress_step(1)
                        self.refresh()
                if self.backup:
                    self.pagesindex = self.pop_history()

            while Gtk.events_pending():
                Gtk.main_iteration()

        # There's still work to do (postinstall).  Let's keep the user
        # entertained.
        self.start_slideshow()
        Gtk.main()
        # postinstall will exit here by calling Gtk.main_quit in
        # find_next_step.

        self.unlock_environment()
        if self.oem_user_config:
            self.quit_installer()
        elif not (self.get_reboot_seen() or self.get_shutdown_seen()):
            self.live_installer.hide()
            if ('UBIQUITY_ONLY' in os.environ or
                'UBIQUITY_GREETER' in os.environ):
                txt = self.get_string('ubiquity/finished_restart_only')
                self.quit_button.hide()
            else:
                txt = self.finished_label.get_label()
                txt = txt.replace('${RELEASE}', misc.get_release().name)
            self.finished_label.set_label(txt)
            with misc.raised_privileges():
                open('/var/run/reboot-required', "w").close()
            self.finished_dialog.set_keep_above(True)
            set_root_cursor()
            self.finished_dialog.run()
        elif self.get_reboot():
            self.reboot()
        elif self.get_shutdown():
            self.shutdown()

        return self.returncode

    def on_slideshow_link_clicked(self, unused_view, unused_frame, req,
                                  unused_action, decision):
        uri = req.get_uri()
        decision.ignore()
        subprocess.Popen(['sensible-browser', uri],
                         close_fds=True, preexec_fn=misc.drop_all_privileges)
        return True

    def start_slideshow(self):
        if not self.slideshow:
            self.page_mode.hide()
            return

        self.page_section.hide()
        slideshow_locale = self.slideshow_get_available_locale(self.slideshow, self.locale)
        slideshow_main = self.slideshow + '/slides/index.html'

        slides = 'file://' + slideshow_main
        if slideshow_locale != 'c': #slideshow will use default automatically
            slides += '#?locale=' + slideshow_locale
            ltr = i18n.get_string('default-ltr', slideshow_locale, 'ubiquity/imported')
            if ltr == 'default:RTL':
                slides += '?rtl'

        from gi.repository import WebKit
        webview = WebKit.WebView()
        # WebKit puts file URLs in their own domain by default.
        # This means that anything which checks for the same origin,
        # such as creating a XMLHttpRequest, will fail unless this
        # is disabled.
        # http://www.gitorious.org/webkit/webkit/commit/624b9463c33adbffa7f6705210384d0d7cf122d6
        s = webview.get_settings()
        s.set_property('enable-file-access-from-file-uris', True)
        s.set_property('enable-default-context-menu', False)
        if (os.environ.get('UBIQUITY_A11Y_PROFILE') == 'screen-reader'):
            s.set_property('enable-caret-browsing', True)
        
        webview.connect('new-window-policy-decision-requested',
                        self.on_slideshow_link_clicked)

        self.webkit_scrolled_window.add(webview)
        webview.open(slides)
        # TODO do these in a page loaded callback
        self.page_mode.show()
        self.page_mode.set_current_page(1)
        webview.show()
        webview.grab_focus()

    def customize_installer(self):
        """Initial UI setup."""

        self.live_installer.set_default_icon_from_file(os.path.join(PIXMAPS,
                                                        'ubiquity.png'))
        # ugly hack to get current gtk-theme
        cmd = "sudo -iu %s gsettings get org.gnome.desktop.interface gtk-theme"\
              % os.environ['SUDO_USER']
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout = p.stdout.read()
        gtk_theme = stdout.replace("'", "")
        gtk_theme = gtk_theme.replace("\n", "")

        # TODO: fix code below which currently raises this error:
        # CRITICAL **: unable to create '/root/.cache/dconf'; dconf will not work properly.

#        from gi.repository import Gio
#        iface_settings = Gio.Settings.new('org.gnome.desktop.interface')
#        gtk_theme = iface_settings.get_value('gtk-theme').get_string()


        provider = Gtk.CssProvider()
        # try to load theme's css
        try:
           css = open('/usr/share/themes/'+gtk_theme+'/gtk-3.0/gtk.css').read()
           # if colors are defined in current theme, then use them
           if 'dark_bg_color' in css and 'dark_fg_color' in css:
               dark_css_data = '''#live_installer,
#page_title,
#install_progress_text,
#install_details_expander {
color : @dark_fg_color;
background-color : @dark_bg_color;
}

GtkEntry, GtkButton, GtkLabel, GtkIconView, GtkTreeView row, GtkComboBox *, GtkDrawingArea {
color : @fg_color
}''' 
               provider.load_from_data(dark_css_data)
        except:
           syslog.syslog(syslog.LOG_ERR,
                      "Exception in GTK frontend: cannot load theme's css")
        
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # TODO lazy load
        from gi.repository import Vte
        self.vte = Vte.Terminal()
        self.install_details_sw.add(self.vte)
        self.vte.fork_command_full(0, None,
            ['/usr/bin/tail', '-f', '/var/log/installer/debug',
                              '-f', '/var/log/syslog', '-q'],
            None, 0, None, None)
        self.vte.show()
        # FIXME shrink the window horizontally instead of locking the window size.
        self.live_installer.set_resizable(False)
        def expand(widget):
            if widget.get_property('expanded'):
                self.progress_cancel_button.show()
            else:
                self.progress_cancel_button.hide()
        self.install_details_expander.connect_after('activate', expand)

        if self.custom_title:
            self.live_installer.set_title(self.custom_title)
        elif self.oem_config:
            self.live_installer.set_title(self.get_string('oem_config_title'))
        elif self.oem_user_config:
            self.live_installer.set_title(self.get_string('oem_user_config_title'))
            self.live_installer.set_icon_name("preferences-system")
            self.quit.hide()

        if 'UBIQUITY_AUTOMATIC' in os.environ:
            # Hide the notebook until the first page is ready.
            self.page_mode.hide()
            self.progress_section.show()
            self.live_installer.show()
        self.allow_change_step(False)

        # The default instantiation of GtkComboBoxEntry creates a
        # GtkCellRenderer, so reuse it.
        self.grub_new_device_entry.set_model(self.grub_options)
        self.grub_new_device_entry.set_entry_text_column(0)
        renderer = Gtk.CellRendererText()
        self.grub_new_device_entry.pack_start(renderer, True)
        self.grub_new_device_entry.add_attribute(renderer, 'text', 1)

        # Only show the Shutdown Now button if explicitly asked to.
        if not self.show_shutdown_button:
            self.shutdown_button.hide()

        # Parse the slideshow size early to prevent the window from growing
        if self.oem_user_config and os.path.exists('/usr/share/oem-config-slideshow'):
            self.slideshow = '/usr/share/oem-config-slideshow'
        else:
            self.slideshow = '/usr/share/ubiquity-slideshow'
        if os.path.exists(self.slideshow):
            try:
                cfg = ConfigParser.ConfigParser()
                cfg.read(os.path.join(self.slideshow, 'slideshow.conf'))
                config_width = int(cfg.get('Slideshow','width'))
                config_height = int(cfg.get('Slideshow','height'))
            except:
                config_width = 752
                config_height = 442
            self.webkit_scrolled_window.set_size_request(config_width, config_height)
        else:
            self.slideshow = None

        # set initial bottom bar status
        self.allow_go_backward(False)
        
    def poke_screensaver(self):
        """Attempt to make sure that the screensaver doesn't kick in."""
        if os.path.exists('/usr/bin/gnome-screensaver-command'):
            command = ["gnome-screensaver-command", "--poke"]
        elif os.path.exists('/usr/bin/xscreensaver-command'):
            command = ["xscreensaver-command", "--deactivate"]
        else:
            return

        env = ['LC_ALL=C']
        for key, value in os.environ.iteritems():
            if key != 'LC_ALL':
                env.append('%s=%s' % (key, value))
        GObject.spawn_async(command, envp=env,
                            flags=(GObject.SPAWN_SEARCH_PATH |
                                   GObject.SPAWN_STDOUT_TO_DEV_NULL |
                                   GObject.SPAWN_STDERR_TO_DEV_NULL))
        return True

    def set_window_hints(self, widget):
        if (self.oem_user_config or
            'UBIQUITY_ONLY' in os.environ or
            'UBIQUITY_GREETER' in os.environ):
            f = Gdk.WMFunction.RESIZE | Gdk.WMFunction.MAXIMIZE | Gdk.WMFunction.MOVE
            if not self.oem_user_config:
                f |= Gdk.WMFunction.CLOSE
            widget.get_window().set_functions(f)

    def lockdown_environment(self):
        atexit.register(self.unlock_environment)
        for key in (('com.canonical.indicator.session', 'suppress-logout-menuitem'),
                    ('com.canonical.indicator.session', 'suppress-logout-restart-shutdown'),
                    ('com.canonical.indicator.session', 'suppress-restart-menuitem'),
                    ('com.canonical.indicator.session', 'suppress-shutdown-menuitem'),
                    ('org.gnome.desktop.lockdown','disable-user-switching')):
            gs_schema = key[0]
            gs_key = key[1]
            gs_previous = '%s/%s' % (gs_schema, gs_key)
            if gs_previous in self.gsettings_previous:
                continue

            gs_value = gsettings.get(gs_schema, gs_key)
            self.gsettings_previous[gs_previous] = gs_value

            gsettings.set(gs_schema, gs_key, True)

        self.quit.hide()
        f = Gdk.WMFunction.RESIZE | Gdk.WMFunction.MAXIMIZE | Gdk.WMFunction.MOVE
        if not 'UBIQUITY_ONLY' in os.environ:
            f |= Gdk.WMFunction.MINIMIZE
        self.live_installer.get_window().set_functions(f)
        self.allow_change_step(False)
        self.refresh()

    def unlock_environment(self):
        syslog.syslog('Reverting lockdown of the desktop environment.')
        for key in (('com.canonical.indicator.session', 'suppress-logout-menuitem'),
                    ('com.canonical.indicator.session', 'suppress-logout-restart-shutdown'),
                    ('com.canonical.indicator.session', 'suppress-restart-menuitem'),
                    ('com.canonical.indicator.session', 'suppress-shutdown-menuitem'),
                    ('org.gnome.desktop.lockdown','disable-user-switching')):
            gs_schema = key[0]
            gs_key = key[1]
            gs_previous = '%s/%s' % (gs_schema, gs_key)

            if gs_previous in self.gsettings_previous:
                gs_value = self.gsettings_previous[gs_previous]
                gsettings.set(gs_schema, gs_key, gs_value)

        if not self.oem_user_config:
            self.quit.show()
        f = Gdk.WMFunction.RESIZE | Gdk.WMFunction.MAXIMIZE | \
            Gdk.WMFunction.MOVE | Gdk.WMFunction.CLOSE
        if not 'UBIQUITY_ONLY' in os.environ:
            f |= Gdk.WMFunction.MINIMIZE
        self.refresh()

    def set_locales(self):
        """internationalization config. Use only once."""

        domain = self.distro + '-installer'
        gettext.bindtextdomain(domain, LOCALEDIR)
        self.builder.set_translation_domain(domain)
        gettext.textdomain(domain)
        gettext.install(domain, LOCALEDIR, unicode=1)

    def translate_reget(self, lang):
        if lang is None:
            lang = self.locale
        if lang is None:
            languages = []
        else:
            languages = [lang]

        core_names = ['ubiquity/text/%s' % q for q in self.language_questions]
        core_names.append('ubiquity/text/oem_config_title')
        core_names.append('ubiquity/text/oem_user_config_title')
        core_names.append('ubiquity/imported/default-ltr')
        core_names.append('ubiquity/text/release_notes_only')
        core_names.append('ubiquity/text/update_installer_only')
        for stock_item in ('cancel', 'close', 'go-back', 'go-forward',
                            'ok', 'quit'):
            core_names.append('ubiquity/imported/%s' % stock_item)
        prefixes = []
        for p in self.pages:
            prefix = p.ui.get('plugin_prefix')
            if not prefix:
                prefix = 'ubiquity/text'
            if p.ui.get('plugin_is_language'):
                children = reduce(lambda x,y: x + self.all_children(y), p.all_widgets, [])
                core_names.extend([prefix+'/'+c.get_name() for c in children])
                title = p.ui.get('plugin_title')
                if title:
                    core_names.extend([title])
            prefixes.append(prefix)
        i18n.get_translations(languages=languages, core_names=core_names, extra_prefixes=prefixes)

    # widgets is a set of (widget, prefix) pairs
    def translate_widgets(self, lang=None, widgets=None, reget=True):
        if lang is None:
            lang = self.locale
        if widgets is None:
            widgets = [(x, None) for x in self.all_widgets]

        if reget:
            self.translate_reget(lang)

        # We always translate always-visible widgets
        for q in self.language_questions:
            if hasattr(self, q):
                widgets.append((getattr(self, q), None))

        for widget in widgets:
            self.translate_widget(widget[0], lang=lang, prefix=widget[1])

    def translate_widget(self, widget, lang=None, prefix=None):
        if isinstance(widget, Gtk.Button) and widget.get_use_stock():
            widget.set_label(widget.get_label())

        text = self.get_string(widget.get_name(), lang, prefix)
        if text is None:
            return
        name = widget.get_name()

        if isinstance(widget, Gtk.Label):
            widget.set_markup(text)

        elif isinstance(widget, Gtk.Button):
            question = i18n.map_widget_name(prefix, widget.get_name())
            widget.set_label(text)

            # Workaround for radio button labels disappearing on second
            # translate when not visible. LP: #353090
            widget.realize()

            if question.startswith('ubiquity/imported/'):
                stock_id = question[18:]
                widget.set_use_stock(False)
                widget.set_image(Gtk.Image.new_from_stock(
                    'gtk-%s' % stock_id, Gtk.IconSize.BUTTON))

        elif isinstance(widget, Gtk.Window):
            if name == 'live_installer':
                if self.custom_title:
                    text = self.custom_title
                elif self.oem_config:
                    text = self.get_string('oem_config_title', lang)
                elif self.oem_user_config:
                    text = self.get_string('oem_user_config_title', lang)
            widget.set_title(text)

    def allow_change_step(self, allowed):
        if allowed:
            cursor = None
        else:
            cursor = self.watch
        if self.live_installer.get_parent_window():
            self.live_installer.get_parent_window().set_cursor(cursor)
        set_root_cursor(cursor)
        self.back.set_sensitive(allowed and self.allowed_go_backward)
        self.next.set_sensitive(allowed and self.allowed_go_forward)
        self.allowed_change_step = allowed

    def allow_go_backward(self, allowed):
        self.back.set_sensitive(allowed and self.allowed_change_step)
        self.allowed_go_backward = allowed

    def allow_go_forward(self, allowed):
        self.next.set_sensitive(allowed and self.allowed_change_step)
        self.allowed_go_forward = allowed

    def dbfilter_handle_status(self):
        """If a dbfilter crashed, ask the user if they want to continue anyway.

        Returns True to continue, or False to try again."""

        if not self.dbfilter_status or self.current_page is None:
            return True

        syslog.syslog('dbfilter_handle_status: %s' % str(self.dbfilter_status))

        # TODO cjwatson 2007-04-04: i18n
        text = ('%s failed with exit code %s. Further information may be '
                'found in /var/log/syslog. Do you want to try running this '
                'step again before continuing? If you do not, your '
                'installation may fail entirely or may be broken.' %
                (self.dbfilter_status[0], self.dbfilter_status[1]))
        dialog = Gtk.Dialog('%s crashed' % self.dbfilter_status[0],
                            self.live_installer, Gtk.DialogFlags.MODAL,
                            (Gtk.STOCK_QUIT, Gtk.ResponseType.CLOSE,
                             'Continue anyway', 1,
                             'Try again', 2))
        self.dbfilter_status = None
        label = Gtk.Label(label=text)
        label.set_line_wrap(True)
        label.set_selectable(False)
        dialog.get_content_area().add(label)
        dialog.show_all()
        response = dialog.run()
        dialog.hide()
        syslog.syslog('dbfilter_handle_status: response %d' % response)
        if response == 1:
            return True
        elif response == Gtk.ResponseType.CLOSE:
            self.quit_installer()
        else:
            step = self.step_name(self.steps.get_current_page())
            if step == "partman":
                print('dbfilter_handle_status stepPart')
                self.set_current_page(self.steps.page_num(self.stepPartAuto))
            return False

    def step_name(self, step_index):
        w = self.steps.get_nth_page(step_index)
        for p in self.pages:
            if w in p.all_widgets:
                return p.module.NAME
        return None

    def page_name(self, step_index):
        return self.steps.get_nth_page(step_index).get_name()

    def toggle_next_button(self, label='gtk-go-forward'):
        if label != 'gtk-go-forward':
            self.next.set_label(self.get_string(label))
        else:
            self.next.set_label(label)
            self.translate_widget(self.next)

    def set_page(self, n):
        self.run_automation_error_cmd()
        # We only stop the backup process when we're on a page where questions
        # need to be asked, otherwise you wont be able to back up past
        # migration-assistant.
        self.backup = False
        visible = self.live_installer.get_property('visible')
        self.live_installer.show()
        # Work around a bug in the wrap_fix code whereby the layout does not
        # get properly rendered due to the window not being visible.
        if not visible:
            self.live_installer.resize_children()
        self.page_mode.show()
        cur = None
        is_install = False
        if 'UBIQUITY_GREETER' in os.environ:
            for page in self.pages:
                if page.module.NAME == 'language':
                    # The greeter page is quite large.  Hide it upon leaving.
                    page.ui.page.hide()
                    break
        for page in self.pages:
            if page.module.NAME == n:
                # Now ask ui class which page we want to be showing right now
                if hasattr(page.ui, 'plugin_get_current_page'):
                    cur = page.ui.call('plugin_get_current_page')
                    if isinstance(cur, str) and hasattr(self, cur):
                        cur = getattr(self, cur) # for not-yet-plugins
                elif page.widgets:
                    cur = page.widgets[0]
                elif page.optional_widgets:
                    cur = page.optional_widgets[0]
                if cur:
                    self.set_page_title(page)
                    cur.show()
                    is_install = page.ui.get('plugin_is_install')
                    break
        if not cur:
            return False

        if is_install and not self.oem_user_config:
            self.toggle_next_button('install_button')
        else:
            self.toggle_next_button()

        num = self.steps.page_num(cur)
        if num < 0:
            print >>sys.stderr, 'Invalid page found for %s: %s' % (n, str(cur))
            return False

        self.add_history(page, cur)
        self.set_current_page(num)

        if self.pagesindex == 0:
            self.allow_go_backward(False)
        elif self.pages[self.pagesindex - 1].module.NAME == 'partman':
            # We're past partitioning.  Unless the install fails, there is no
            # going back.
            self.allow_go_backward(False)
        elif 'UBIQUITY_AUTOMATIC' not in os.environ:
            self.allow_go_backward(True)
        return True

    def set_page_title(self, page, lang=None):
        """Fetches and/or retranslates a page title"""
        title = None
        if page.title:
            title = self.get_string(page.title, lang)
            if title:
                title = title.replace('${RELEASE}', misc.get_release().name)
                # TODO: Use attributes instead?  Would save having to
                # hardcode the size in here.
                self.page_title.set_markup(
                    '<span size="xx-large">%s</span>' % title)
                self.title_section.show()
        if not page.title or not title:
            self.title_section.hide()

    def set_focus(self):
        # Make sure that something reasonable has the focus.  If the first
        # focusable item is a label or a button (often, the welcome text label
        # and the quit button), set the focus to the next button.
        if not self.live_installer.get_focus():
            self.live_installer.child_focus(Gtk.DirectionType.TAB_FORWARD)
        focus = self.live_installer.get_focus()
        if focus:
            if focus.__class__ == Gtk.Label:
                focus.select_region(-1, -1) # when it got focus, whole text was selected
                self.next.grab_focus()
            elif focus.__class__ == Gtk.Button:
                self.next.grab_focus()
        return True

    def set_current_page(self, current):
        if self.steps.get_current_page() == current:
            # self.steps.set_current_page() will do nothing. Update state
            # ourselves.
            self.on_steps_switch_page(
                self.steps, self.steps.get_nth_page(current), current)
        else:
            self.steps.set_current_page(current)

    # Methods

    def reboot(self, *args):
        """reboot the system after installing process."""

        self.returncode = 10
        self.quit_installer()
    def shutdown(self, *args):
        """Shutdown the system after installing process."""

        self.returncode = 11
        self.quit_installer()
    def do_reboot(self):
        """Callback for main program to actually reboot the machine."""

        try:
            session = dbus.Bus.get_session()
            gnome_session = session.name_has_owner('org.gnome.SessionManager')
        except dbus.exceptions.DBusException:
            gnome_session = False

        if gnome_session:
            manager = session.get_object('org.gnome.SessionManager',
                                         '/org/gnome/SessionManager')
            manager.RequestReboot()
        else:
            misc.execute_root("reboot")

    def do_shutdown(self):
        """Callback for main program to actually shutdown the machine."""

        try:
            session = dbus.Bus.get_session()
            gnome_session = session.name_has_owner('org.gnome.SessionManager')
        except dbus.exceptions.DBusException:
            gnome_session = False

        if gnome_session:
            manager = session.get_object('org.gnome.SessionManager',
                                         '/org/gnome/SessionManager')
            manager.RequestShutdown()
        else:
            misc.execute_root("poweroff")


    def quit_installer(self, *args):
        """quit installer cleanly."""

        # Let the user know we're shutting down.
        self.finished_dialog.get_window().set_cursor(self.watch)
        set_root_cursor(self.watch)
        self.quit_button.set_sensitive(False)
        self.reboot_button.set_sensitive(False)
        self.refresh()

        # exiting from application
        self.current_page = None
        self.warning_dialog.hide()
        if self.dbfilter is not None:
            self.dbfilter.cancel_handler()
        self.quit_main_loop()

    # Callbacks

    def on_quit_clicked(self, unused_widget):
        self.warning_dialog.show()
        # Stop processing.
        return True

    def on_quit_cancelled(self, unused_widget):
        self.warning_dialog.hide()

    def on_live_installer_delete_event(self, widget, unused_event):
        return self.on_quit_clicked(widget)

    def on_next_clicked(self, unused_widget):
        """Callback to control the installation process between steps."""

        if not self.allowed_change_step or not self.allowed_go_forward:
            return

        self.allow_change_step(False)
        ui = self.pages[self.pagesindex].ui
        if hasattr(ui, 'plugin_on_next_clicked'):
            if ui.plugin_on_next_clicked():
                # Stop processing and return to the page.
                self.allow_change_step(True)
                return

        if self.dbfilter is not None:
            self.dbfilter.ok_handler()
            # expect recursive main loops to be exited and
            # debconffilter_done() to be called when the filter exits
        else:
            self.find_next_step(self.pages[self.pagesindex].module.__name__)
            self.quit_main_loop()

    def process_step(self):
        """Process and validate the results of this step."""

        # setting actual step
        step_num = self.steps.get_current_page()
        step = self.page_name(step_num)
        syslog.syslog('Step_before = %s' % step)

    def on_back_clicked(self, unused_widget):
        """Callback to set previous screen."""

        if not self.allowed_change_step:
            return

        self.allow_change_step(False)
        ui = self.pages[self.pagesindex].ui
        if hasattr(ui, 'plugin_on_back_clicked'):
            if ui.plugin_on_back_clicked():
                # Stop processing and return to the page.
                self.allow_change_step(True)
                return

        self.backup = True
        self.stay_on_page = False

        # Enabling next button
        self.allow_go_forward(True)

        if self.dbfilter is not None:
            self.dbfilter.cancel_handler()
            # expect recursive main loops to be exited and
            # debconffilter_done() to be called when the filter exits
        else:
            self.find_next_step(self.pages[self.pagesindex].module.__name__)
            self.quit_main_loop()

    def on_steps_switch_page (self, unused_notebook, unused_page, current):
        self.current_page = current
        name = self.step_name(current)
        if 'UBIQUITY_GREETER' in os.environ:
            if name == 'language':
                self.navigation_control.hide()
            else:
                self.navigation_control.show()

        syslog.syslog('switched to page %s' % name)

    # Callbacks provided to components.

    def watch_debconf_fd (self, from_debconf, process_input):
        GObject.io_add_watch(from_debconf,
                             GObject.IO_IN | GObject.IO_ERR | GObject.IO_HUP,
                             self.watch_debconf_fd_helper, process_input)

    def watch_debconf_fd_helper (self, source, cb_condition, callback):
        debconf_condition = 0
        if (cb_condition & GObject.IO_IN) != 0:
            debconf_condition |= filteredcommand.DEBCONF_IO_IN
        if (cb_condition & GObject.IO_ERR) != 0:
            debconf_condition |= filteredcommand.DEBCONF_IO_ERR
        if (cb_condition & GObject.IO_HUP) != 0:
            debconf_condition |= filteredcommand.DEBCONF_IO_HUP

        return callback(source, debconf_condition)

    def debconf_progress_start (self, progress_min, progress_max, progress_title):
        self.progress_position.start(progress_min, progress_max,
                                     progress_title)
        self.debconf_progress_set(0)
        self.debconf_progress_info(progress_title)

    def debconf_progress_set (self, progress_val):
        if self.progress_cancelled:
            return False
        self.progress_position.set(progress_val)
        fraction = self.progress_position.fraction()
        self.install_progress.set_fraction(fraction)
        return True

    def debconf_progress_step (self, progress_inc):
        if self.progress_cancelled:
            return False
        self.progress_position.step(progress_inc)
        fraction = self.progress_position.fraction()
        self.install_progress.set_fraction(fraction)
        return True

    def debconf_progress_info (self, progress_info):
        if self.progress_cancelled:
            return False
        self.install_progress_text.set_label(progress_info)
        return True

    def debconf_progress_stop (self):
        self.progress_cancelled = False
        self.progress_position.stop()

    def debconf_progress_region (self, region_start, region_end):
        self.progress_position.set_region(region_start, region_end)

    def debconf_progress_cancellable (self, cancellable):
        if cancellable:
            self.progress_cancel_button.set_sensitive(True)
        else:
            self.progress_cancel_button.set_sensitive(False)
            self.progress_cancelled = False

    def on_progress_cancel_button_clicked (self, unused_button):
        self.progress_cancelled = True

    def debconffilter_done (self, dbfilter):
        if not dbfilter.status:
            self.find_next_step(dbfilter.__module__)
        # TODO: This doesn't handle partman-commit failures.
        elif dbfilter.__module__ in ('ubiquity.components.install',
                                     'ubiquity.components.plugininstall'):
            # We don't want to try to retry a failing step here, because it
            # will have the same set of inputs, and thus likely the same
            # result.
            # TODO: We may want to call return_to_partitioning after the crash
            # dialog instead.
            self.crash_dialog.run()
            self.crash_dialog.hide()
            self.live_installer.hide()
            while Gtk.events_pending():
                Gtk.main_iteration()
            misc.execute_root("apport-bug", "ubiquity")
            sys.exit(1)
        if BaseFrontend.debconffilter_done(self, dbfilter):
            self.quit_main_loop()
            return True
        else:
            return False


    def switch_to_install_interface(self):
        self.installing = True
        self.lockdown_environment()
        self.progress_section.show()

    def find_next_step(self, finished_step):
        # TODO need to handle the case where debconffilters launched from
        # here crash.  Factor code out of dbfilter_handle_status.
        last_page = self.pages[-1].module.__name__
        if finished_step == last_page and not self.backup:
            self.finished_pages = True
            if self.finished_installing or self.oem_user_config:
                self.progress_section.show()
                dbfilter = plugininstall.Install(self)
                dbfilter.start(auto_process=True)

        elif finished_step == 'ubi-partman':
            # Flush changes to the database so that when the parallel db
            # starts, it does so with the most recent changes.
            self.stop_debconf()
            self.start_debconf()
            options = misc.grub_options()
            self.grub_options.clear()
            for opt in options:
                self.grub_options.append(opt)
            self.switch_to_install_interface()
            from ubiquity.debconfcommunicator import DebconfCommunicator
            if self.parallel_db is not None:
                # Partitioning failed and we're coming back through again.
                self.parallel_db.shutdown()
            env = os.environ.copy()
            # debconf-apt-progress, start_debconf()
            env['DEBCONF_DB_REPLACE'] = 'configdb'
            env['DEBCONF_DB_OVERRIDE'] = 'Pipe{infd:none outfd:none}'
            self.parallel_db = DebconfCommunicator('ubiquity', cloexec=True,
                                                   env=env)
            dbfilter = partman_commit.PartmanCommit(self, db=self.parallel_db)
            dbfilter.start(auto_process=True)

        # FIXME OH DEAR LORD.  Use isinstance.
        elif finished_step == 'ubiquity.components.partman_commit':
            dbfilter = install.Install(self, db=self.parallel_db)
            dbfilter.start(auto_process=True)

        elif finished_step == 'ubiquity.components.install':
            self.finished_installing = True
            if self.finished_pages:
                dbfilter = plugininstall.Install(self)
                dbfilter.start(auto_process=True)

        elif finished_step == 'ubiquity.components.plugininstall':
            self.installing = False
            self.run_success_cmd()
            self.quit_main_loop()

    def grub_verify_loop(self, widget, okbutton):
        if widget is not None:
            if validation.check_grub_device(widget.get_child().get_text()):
                okbutton.set_sensitive(True)
            else:
                okbutton.set_sensitive(False)

    def return_to_partitioning (self):
        """If the install progress bar is up but still at the partitioning
        stage, then errors can safely return us to partitioning.
        """

        self.page_section.show()
        if self.installing and not self.installing_no_return:
            # Stop the currently displayed page.
            if self.dbfilter is not None:
                self.dbfilter.cancel_handler()
            # Go back to the partitioner and try again.
            self.pagesindex = -1
            for page in self.pages:
                if page.module.NAME == 'partman':
                    self.pagesindex = self.pages.index(page)
                    break
            if self.pagesindex == -1:
                return

            self.start_debconf()
            ui = self.pages[self.pagesindex].ui
            self.dbfilter = self.pages[self.pagesindex].filter_class(self, ui=ui)
            self.allow_change_step(False)
            self.dbfilter.start(auto_process=True)
            self.toggle_next_button()
            self.translate_widget(self.next)
            self.installing = False
            self.progress_section.hide()
            self.unlock_environment()

    def error_dialog (self, title, msg, fatal=True):
        # TODO: cancel button as well if capb backup
        self.run_automation_error_cmd()
        # TODO cjwatson 2009-04-16: We need to call allow_change_step here
        # to get a normal cursor, but that also enables the Back/Forward
        # buttons. Cursor handling should be controllable independently.
        saved_allowed_change_step = self.allowed_change_step
        self.allow_change_step(True)
        if not msg:
            msg = title
        dialog = Gtk.MessageDialog(self.live_installer, Gtk.DialogFlags.MODAL,
                                   Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, msg)
        dialog.set_title(title)
        dialog.run()
        self.allow_change_step(saved_allowed_change_step)
        dialog.hide()
        if fatal:
            self.return_to_partitioning()

    def toggle_grub_fail (self, unused_widget):
        if self.grub_no_new_device.get_active():
            self.no_grub_warn.show()
            self.grub_new_device_entry.set_sensitive(False)
            self.abort_warn.hide()
        elif self.grub_fail_option.get_active():
            self.abort_warn.show()
            self.no_grub_warn.hide()
            self.grub_new_device_entry.set_sensitive(False)
        else:
            self.abort_warn.hide()
            self.no_grub_warn.hide()
            self.grub_new_device_entry.set_sensitive(True)

    def bootloader_dialog (self, current_device):
        l = self.skip_label.get_label()
        l = l.replace('${RELEASE}', misc.get_release().name)
        self.skip_label.set_label(l)
        self.grub_new_device_entry.get_child().set_text(current_device)
        self.grub_new_device_entry.get_child().grab_focus()
        response = self.bootloader_fail_dialog.run()
        self.bootloader_fail_dialog.hide()
        if response == Gtk.ResponseType.OK:
            if self.grub_new_device.get_active():
                return self.grub_new_device_entry.get_child().get_text()
            elif self.grub_no_new_device.get_active():
                return 'skip'
            else:
                return ''
        else:
            return ''

    def question_dialog (self, title, msg, options, use_templates=True):
        self.run_automation_error_cmd()
        # TODO cjwatson 2009-04-16: We need to call allow_change_step here
        # to get a normal cursor, but that also enables the Back/Forward
        # buttons. Cursor handling should be controllable independently.
        saved_allowed_change_step = self.allowed_change_step
        self.allow_change_step(True)
        if not msg:
            msg = title
        buttons = []
        for option in options:
            if use_templates:
                text = self.get_string(option)
            else:
                text = option
            if text is None:
                text = option
            buttons.extend((text, len(buttons) / 2 + 1))
        dialog = Gtk.Dialog(title, self.live_installer, Gtk.DialogFlags.MODAL, tuple(buttons))
        vbox = Gtk.VBox()
        vbox.set_border_width(5)
        label = Gtk.Label(label=msg)
        label.set_line_wrap(True)
        label.set_selectable(False)
        vbox.pack_start(label, True, True, 0)
        vbox.show_all()
        dialog.get_content_area().pack_start(vbox, True, True, 0)
        response = dialog.run()
        self.allow_change_step(saved_allowed_change_step)
        dialog.hide()
        if response < 0:
            # something other than a button press, probably destroyed
            return None
        else:
            return options[response - 1]

    def refresh (self):
        while Gtk.events_pending():
            Gtk.main_iteration()

    # Run the UI's main loop until it returns control to us.
    def run_main_loop (self):
        self.allow_change_step(True)
        self.set_focus()
        Gtk.main()

    # Return control to the next level up.
    pending_quits = 0
    def quit_main_loop (self):
        # We quit in an idle function, because successive calls to
        # main_quit will do nothing if the main loop hasn't had time to
        # quit.  So we stagger calls to make sure that if this function
        # is called multiple times (nested loops), it works as expected.
        def quit_decrement():
            # Defensively guard against negative pending
            self.pending_quits = max(0, self.pending_quits - 1)
            return False
        def idle_quit():
            if self.pending_quits > 1:
                quit_quit()
            if Gtk.main_level() > 0:
                Gtk.main_quit()
            return quit_decrement()
        def quit_quit():
            # Wait until we're actually out of this main loop
            GObject.idle_add(idle_quit)
            return False

        if self.pending_quits == 0:
            quit_quit()
        self.pending_quits += 1

# vim:ai:et:sts=4:tw=80:sw=4: