#!/usr/bin/python
#  
#  Copyright (c) 2007-2009 Canonical Ltd.
#  
#  Author: Oliver Grawert <ogra@ubuntu.com>
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU General Public License as 
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.

import gtk
import gtk.glade
import gobject
from subprocess import Popen,PIPE,call,STDOUT
import os
import signal

import gettext
from gettext import gettext as _


class ImageWriter:
    def __init__(self):
        APP="usb-imagewriter"
        DIR="/usr/share/locale"

        gettext.bindtextdomain(APP, DIR)
        gettext.textdomain(APP)
        gtk.glade.bindtextdomain(APP, DIR)
        gtk.glade.textdomain(APP)

        # get glade tree
        self.gladefile = "/usr/share/imagewriter/imagewriter.glade"
        self.wTree = gtk.glade.XML(self.gladefile)

        # make sure we have a target device
        self.get_devices()

        # get globally needed widgets
        self.window = self.wTree.get_widget("main_dialog")
        self.devicelist = self.wTree.get_widget("device_combobox")
        self.logview = self.wTree.get_widget("detail_text")
        eventbox = self.wTree.get_widget("eventbox")
        bgcol = gtk.gdk.color_parse("white")
        eventbox.modify_bg(gtk.STATE_NORMAL, bgcol)
        self.log = self.logview.get_buffer()
        self.ddpid = 0

        # set default file filter to *.img and hybrid-iso
        self.chooser = self.wTree.get_widget("filechooserbutton")
        filt = gtk.FileFilter()
        filt.add_pattern("*.img")
        filt.add_pattern("*.iso")
        self.chooser.set_filter(filt)

        # set callbacks
        dict = { "on_main_dialog_destroy" : self.close,
                 "on_cancel_button_clicked" : self.close,
                 "on_emergency_button_clicked" : self.close,
                 "on_success_button_clicked" : self.close,
                 "on_filechooserbutton_file_set" : self.activate_devicelist,
                 "on_detail_expander_activate" : self.expander_control,
                 "on_device_combobox_changed" : self.device_selected,
                 "on_write_button_clicked" : self.do_write}
        self.wTree.signal_autoconnect(dict)

        self.window.show_all()

    def get_devices(self):
        list = Popen(["/usr/lib/imagewriter/find_devices.sh"], stdout=PIPE).communicate()[0]
        if not len(list):
            dialog = self.wTree.get_widget("nodev_dialog")
            dialog.run()
            exit(0)
        self.combo = self.wTree.get_widget("device_combobox")
        list = list.strip().split('\n')
        for item in list:
            name,path = item.split(',')
            self.combo.append_text(name+' ('+path.lstrip()+')')

    def device_selected(self, widget):
        write_button = self.wTree.get_widget("write_button")
        write_button.set_sensitive(True)
        self.dev = self.combo.get_active_text()

    def do_write(self, widget):
        write_button = self.wTree.get_widget("write_button")
        write_button.set_sensitive(False)
        combo = self.wTree.get_widget("device_combobox")
        combo.set_sensitive(False)
        self.chooser.set_sensitive(False)
        source = self.chooser.get_filename()
        target = self.dev.split('(')[1].rstrip(')')
        dialog = self.wTree.get_widget("confirm_dialog")
        self.logger(_('Image: ')+source)
        self.logger(_('Target Device: ')+self.dev)
        resp = dialog.run()
        if resp:
            self.do_umount(target)
            dialog.hide()
            while gtk.events_pending():
                gtk.main_iteration(True)
            self.raw_write(source, target)
        else:
            self.close('dummy')

    def do_umount(self, target):
        mounts = self.get_mounted(target)
        print len(mounts)
        if mounts:
            self.logger(_('Unmounting all partitions of ')+target+':')
        for mount in mounts:
            self.logger(_('Trying to unmount ')+mount[0]+'...')
            while gtk.events_pending():
                gtk.main_iteration(True)
            try:
                retcode = call('umount '+mount[0], shell=True)
                if retcode < 0:
                    self.logger(_('Error, umount ')+mount[0]+_(' was terminated by signal ')+str(retcode))
                    self.emergency()
                else:
                    if retcode == 0:
                        self.logger(mount[0]+_(' successfully unmounted'))
                    else:
                        self.logger(_('Error, umount ')+mount[0]+_(' returned ')+str(retcode))
                        self.emergency()
            except OSError, e:
                self.logger(_('Execution failed: ')+str(e))
                self.emergency()

    def get_mounted(self, target):
        try:
            lines = [line.strip("\n").split(" ") for line in open ("/etc/mtab", "r").readlines()]
            return [mount for mount in lines if mount[0].startswith(target)]
        except:
             self.logger(_('Could not read mtab !'))
             self.emergency()

    def raw_write(self, source, target):
        data = Popen(['ls -l '+source], shell=True, stdout=PIPE, stderr=PIPE)
        src_size = float(data.stdout.readline().split()[4])*1.0
        progress = self.wTree.get_widget("progressbar")
        progress.set_sensitive(True)
        progress.set_text(_('Writing ')+source.split('/')[-1]+_(' to ')+self.dev)
        self.logger(_('Executing: dd if=')+source+' of='+target)
        while gtk.events_pending():
           gtk.main_iteration(True)
        output = Popen(['dd if='+source+' of='+target+' bs=1M'], stdout=PIPE, stderr=STDOUT, shell=True)
        self.ddpid = output.pid
        while output.stdout.readline():
            line = output.stdout.readline().strip()
            while gtk.events_pending():
                gtk.main_iteration(True)
            if line.endswith('MB/s'):
                target_size = line.split()[0]
                self.logger(_('Wrote: ')+target_size+' bytes')
                size = float(target_size)*100/float(src_size)
                while gtk.events_pending():
                    gtk.main_iteration(True)
                progress.set_fraction(float(size/100))
        pid, sts = os.waitpid(output.pid, 0)
        if sts != 0:
            self.logger(_('The dd process ended with an error !'))
            self.emergency()
            return False
        progress.set_fraction(1.0)
        self.logger(_('Image ')+source.split('/')[-1]+_(' successfully written to')+target)
        self.success()

    def success(self):
        dialog = self.wTree.get_widget("success_dialog")
        self.final_unsensitive()
        resp = dialog.run()
        if resp:
            exit(0)
            dialog.destroy()

    def emergency(self):
        self.final_unsensitive()
        dialog = self.wTree.get_widget("emergency_dialog")
        expander = self.wTree.get_widget("detail_expander")
        expander.set_expanded(True)
        mark = self.log.create_mark("end", self.log.get_end_iter(), False)
        self.logview.scroll_to_mark(mark, 0.05, True, 0.0, 1.0)
        resp = dialog.run()
        if resp:
            dialog.destroy()

    def final_unsensitive(self):
        self.chooser.set_sensitive(False)
        self.devicelist.set_sensitive(False)
        write_button = self.wTree.get_widget("write_button")
        write_button.set_sensitive(False)
        progress = self.wTree.get_widget("progressbar")
        progress.set_sensitive(False)

    def close(self, widget):
        self.write_logfile()
        if self.ddpid > 0:
            try:
                os.killpg(os.getpgid(self.ddpid), signal.SIGKILL)
            except:
                gtk.main_quit()
        else:
            gtk.main_quit()

    def write_logfile(self):
        start = self.log.get_start_iter()
        end = self.log.get_end_iter()
        print self.log.get_text(start, end, False)

    def logger(self, text):
        self.log.insert_at_cursor(text+"\n")

    def activate_devicelist(self, widget):
        label = self.wTree.get_widget("to_label")
        expander = self.wTree.get_widget("detail_expander")
        self.devicelist.set_sensitive(True)
        expander.set_sensitive(True)
        label.set_sensitive(True)
        self.img_name = self.chooser.get_filename()

    def expander_control(self, widget):
        # this is darn ugly but still better than the UI behavior of
        # the unexpanded expander which doesnt reset the window size
        if widget.get_expanded():
            gobject.timeout_add(130, lambda: self.window.reshow_with_initial_size())

if __name__ == "__main__":
    app = ImageWriter()
    gtk.main()
