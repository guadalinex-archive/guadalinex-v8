#!/usr/bin/python
# -*- encoding: utf-8 -*-
#       diagnosis_report.py
#       
#       Copyright 2010 Álvaro Pinel Bueno <alvaropinel@gmail.com>
#           date: 27/Apr/2010
#
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#
#               ####################

import pygtk
pygtk.require("2.0")
import gtk, os, gettext
#import tarfile

gettext.install("diagnostic_report")

class diagnosis:
#Output var to store diagnosis report
    path_out = "/tmp/diagnosis_report.txt"
    curdir=os.getenv('HOME')
    route_split=curdir.split('/')
    curusr=route_split[2]
    print(curusr)


    def show_file(self, file_r):
        try:
            inp = open (file_r, "r")

        except IOError as (errno, strerror):
            print "Error FICHERO "+file_r+ "I/O error({0}): {1}".format(errno, strerror)
            outp = open(self.path_out, "a")
            outp.write("Error FICHERO: "+file_r+"\n")
            outp.write("I/O error({0}): {1}".format(errno, strerror))
            outp.write("*----------\n")
            outp.write("\n")
            outp.close()

        else:
            outp = open(self.path_out, "a")
            outp.write("FICHERO: "+file_r+"\n")

            for line in inp.readlines():

                outp.write (line)

            outp.write("*----------\n")
            outp.write("\n")
            outp.close()


    def show_binary_exit(self, command):
        outp = open(self.path_out, "a")
        outp.write("COMANDO:"+command+"\n")
        
        for line in os.popen(command).readlines():
            outp.write (line)
            
        outp.write("*----------\n")
        outp.write("\n")
        outp.close()


    def launch_initial_glade(self, widget, data=None):

        self.builder_init=gtk.Builder()

        ##INITIAL WINDOW

        self.builder_init.add_from_file("/usr/share/diagnostic_report/diagnostic_report_init.glade")
        self.builder_init.connect_signals(self)

        self.bt_cancel_init=self.builder_init.get_object("bt_cancel_init")
        self.wddiagn_init=self.builder_init.get_object("wddiagn")
        self.textinfo_init=self.builder_init.get_object("textinfo")
        self.create_bt_init=self.builder_init.get_object("bt_init")

        self.wddiagn_init.set_title(_("Diagnostic report generator init window"))
        self.wddiagn_init.set_icon_from_file("/usr/share/icons/diagnostic-report.png")

        buffer=self.textinfo_init.get_buffer()
        buffer.set_text(_("Initial msg"))
        self.wddiagn_init.set_position(gtk.WIN_POS_CENTER)
        self.wddiagn_init.show_all()
		
    def on_bt_init_clicked(self, widget, data=None):
        self.wddiagn_init.hide()
        self.launch_os_calls(self)

        ##Attach file to text
        if os.path.isfile(self.path_out):
            f=open(self.path_out, "r")


            try:
                self.content=unicode(f.read(), "utf-8")
                #print (self.content)

            except UnicodeDecodeError:

                self.launch_exception_glade(self)

            else:

                self.launch_diagnostic_glade(self)

            f.close
			
			
    def on_bt_cancel_init_clicked(self, widget, data=None):
        gtk.main_quit()


    def launch_exception_glade(self, widget, data=None):

        outp = open(self.path_out, "a")
        err_msg=(_("Error using standard interface"))
        outp.write("\n"+err_msg+"\n")
        outp.close()

        self.builder_exception=gtk.Builder()
        
        #Create exeption window when diagnostic report can't be shown

        self.builder_exception.add_from_file("/usr/share/diagnostic_report/diagnostic_report_exception.glade")
        self.builder_exception.connect_signals(self)

        self.wddiagn_exception=self.builder_exception.get_object("wddiagn")
        self.textinfo_exception=self.builder_exception.get_object("textinfo")
        self.create_bt_exception=self.builder_exception.get_object("create_bt")


        self.wddiagn_exception.set_title(_("Diagnostic report generator exception window"))
        self.wddiagn_exception.set_icon_from_file("/usr/share/icons/diagnostic-report.png")

        buffer=self.textinfo_exception.get_buffer()
        buffer.set_text(_("Error message"))
        self.wddiagn_exception.set_position(gtk.WIN_POS_CENTER)
        self.wddiagn_exception.show_all()


    def create_bt_clicked_cb(self, widget, data=None):
        self.save_log(self)
	gtk.main_quit()


    def launch_diagnostic_glade(self, widget, data=None):
        self.builder=gtk.Builder()
        self.builder.add_from_file("/usr/share/diagnostic_report/diagnostic_report.glade")
        self.builder.connect_signals(self)

        #Initial autoconnetions
        self.wddiagn=self.builder.get_object("wddiagn")
        self.textinfo=self.builder.get_object("textinfo")
        self.create_bt=self.builder.get_object("create_bt")

        self.wddiagn.set_title(_("Diagnostic report generator"))
        self.wddiagn.set_icon_from_file("/usr/share/icons/diagnostic-report.png")

        buffer=self.textinfo.get_buffer()
        buffer.set_text(self.content)
        self.wddiagn.set_position(gtk.WIN_POS_CENTER)

        self.wddiagn.show_all()


    def on_create_bt_clicked(self, widget, data=None):
        self.save_log(self)
        self.launch_final_glade(self)


    def on_bt_cancel_clicked(self, widget, data=None):

        if (os.path.exists(self.path_out)):
            os.remove(self.path_out)

        gtk.main_quit()
		
		
    def launch_final_glade(self, widget, data=None):
        self.builder_final=gtk.Builder()
        self.builder_final.add_from_file("/usr/share/diagnostic_report/diagnostic_report_end.glade")
        self.wddiagn.hide()
        self.builder_final.connect_signals(self)

        #Initial autoconnetions
        self.wddiagn_final=self.builder_final.get_object("wddiagn")
        self.textinfo_final=self.builder_final.get_object("textinfo")
        self.create_bt_final=self.builder_final.get_object("bt_ok")

        self.wddiagn_final.set_title(_("Diagnostic report generator"))
        self.wddiagn_final.set_icon_from_file("/usr/share/icons/diagnostic-report.png")

        buffer=self.textinfo_final.get_buffer()
        buffer.set_text(_("Final msg"))

        self.wddiagn_final.set_position(gtk.WIN_POS_CENTER)

        self.wddiagn_final.show_all()


    def launch_os_calls(self, widget, data=None):
        #Remove tmp file if exists
        if (os.path.exists(self.path_out)):
            os.remove(self.path_out)


        ## Different system files and commands
        # system wide related info
        self.show_file ("/etc/lsb-release")
        self.show_binary_exit ("dmesg")

        # users related info
        self.show_binary_exit ("whoami")
        self.show_binary_exit ("date")
        self.show_binary_exit ("cut -d: -f 1,3,4 /etc/passwd")
        self.show_file ("/etc/group")

        # X related info
#        self.show_file ("/etc/X11/xorg.conf")
#        self.show_file ("/var/log/Xorg.0.log")
#        self.show_binary_exit ("ddcprobe")
####
        # disks related info
        self.show_binary_exit ("mount")
        self.show_binary_exit ("df -h")
        self.show_binary_exit ("fdisk -l")
        self.show_file ("/etc/fstab")
        self.show_file ("/etc/mtab")

        # devices related info
        self.show_binary_exit ("ls -lR /dev")
        self.show_binary_exit ("lsusb")
        self.show_binary_exit ("lsusb -v")

        # network related info
        self.show_binary_exit ("/sbin/ifconfig")
        self.show_binary_exit ("/sbin/route -n")
        self.show_file ("/etc/network/interfaces")

        # modules related info
        self.show_file ("/etc/modules")
        self.show_binary_exit ("/sbin/lsmod")

        # grub related info
#        self.show_file ("/boot/grub/menu.lst")

        # 'proc' related info
#        self.show_file ("/proc/apm")
        self.show_file ("/proc/cmdline")
        self.show_file ("/proc/cpuinfo")
        self.show_file ("/proc/crypto")
        self.show_file ("/proc/devices")
        self.show_file ("/proc/dma")
        self.show_file ("/proc/execdomains")
        self.show_file ("/proc/fb")
        self.show_file ("/proc/filesystems")
        self.show_file ("/proc/interrupts")
        self.show_file ("/proc/iomem")
        self.show_file ("/proc/ioports")
        self.show_file ("/proc/loadavg")
        self.show_file ("/proc/locks")
        self.show_file ("/proc/meminfo")
        self.show_file ("/proc/misc")
        self.show_file ("/proc/modules")
        self.show_file ("/proc/mounts")
        self.show_file ("/proc/mtrr")
        self.show_file ("/proc/partitions")
        self.show_file ("/proc/bus/pci/devices")
        self.show_file ("/proc/slabinfo")
        self.show_file ("/proc/stat")
        self.show_file ("/proc/swaps")
        self.show_file ("/proc/uptime")
        self.show_file ("/proc/version")

        #/proc/{    apm,cmdline,cpuinfo,crypto,devices,dma,execdomains,fb,filesystems,interrupts,iomem,
        #           ioports,loadavg,locks,meminfo,misc,modules,mounts,mtrr,partitions,bus/pci/devices,slabinfo,stat,swaps,uptime,version}

        # suitable lspci info for 'discover'
        self.show_binary_exit ("lspci -n")
        self.show_binary_exit ("lspci | sort")
        ## -- ##

    
#    def save_log(self, widget, data=None):
#        print (self.content)
#        curdir=os.getenv('HOME')
#        file_tar=curdir+"/Escritorio/informe_de_diagnostico.bz2"
        
#        tar = tarfile.open(file_tar,  "w:bz2")
        #Using True allow to only package the file without dirs
#        tar.add(self.path_out, os.path.basename(self.path_out))
#        tar.close()


    def save_log(self, widget, data=None):
        curdir=os.getenv('HOME')
        file_tar=curdir+"/Escritorio/informe_diagnostico.bz2"

#        os.system("bzip2 -k %s" % self.path_out)
        os.system("mv %s %s" %(self.path_out, file_tar))
        os.system("chown %s.%s %s" %(self.curusr, self.curusr, file_tar))

#        os.system("rm /tmp/diagnosis_report.txt.bz2")

	
    def on_bt_ok_clicked (self, widget, data=None):
        gtk.main_quit()

    
    def on_wddiagn_destroy(self, widget, data=None):
        gtk.main_quit()
		
	
    def destroy (self, widget, data=None):
        gtk.main_quit()
        
    def __init__(self):
        self.launch_initial_glade(self)        


    def main(self):
        gtk.main()

if __name__ == "__main__":
    diagn_instance=diagnosis()
    diagn_instance.main()


