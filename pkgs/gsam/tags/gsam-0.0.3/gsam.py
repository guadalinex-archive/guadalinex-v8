#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#       ssh-manager.py
#       
#       Copyright 2009 Álvaro Pinel Bueno <alvaropinel@gmail.com> and David Amián Valle <amialinux@gmail.com>
# 	    date: 24/Nov/2009
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
#		####################

import pygtk
pygtk.require("2.0")
import gtk
import subprocess
import os
import time


fileroute = "/etc/ssh/sshd_not_to_be_run"

class Ssh:
    clicked=0
    
    def __init__(self):
        self.builder=gtk.Builder()
			
        #Take glade
        ## Cambiar a ruta absoluta /usr/share/ssh_activation
        self.builder.add_from_file("/usr/share/gsam/gsam.glade")
        #self.builder.add_from_file("gsam.glade")
        #Initial autoconetions
        self.builder.connect_signals(self)
        self.wdssh=self.builder.get_object("wdssh")

        #Option combo list
        self.cell = gtk.CellRendererText()
        self.cb_status=self.builder.get_object("cb_status")
        self.bt_ok=self.builder.get_object("bt_ok")

        self.cb_status.pack_start(self.cell)
        self.cb_status.add_attribute(self.cell, 'text', 0)
        
        self.liststore=gtk.ListStore(str)
        self.liststore.append(['Activado'])
        self.liststore.append(['Desactivado'])
        
        self.cb_status.set_model(self.liststore)
        
        if os.path.exists(fileroute):
            self.cb_status.set_active(1)
            
        else:
            self.cb_status.set_active(0)
        
        self.bt_ok.set_label("Cerrar")
        
        self.wdssh.set_title("Administrador del servicio ssh")
        self.wdssh.set_icon_from_file("/usr/share/pixmaps/gsam.png")
        self.wdssh.show_all()
	
    def on_wdssh_destroy(self, widget, data=None):
        gtk.main_quit()
		
    #def on_bt_ok_clicked (self, widget, data=None):
        #Take desired effect
    
    ##MODIFICAR##
    def on_cb_status_changed(self, widget, data=None):
        self.bt_ok.set_label("Aplicar")
        print "entra"
    
    ### ----- ###
    
    def on_bt_ok_clicked (self, widget, data=None):

        #Take desired effect
        model=self.cb_status.get_model()
        index=self.cb_status.get_active()
        self.typeselect=model[index][0]
        
        #Check the file /etc/ssh/sshd_not_to_be_run
        ##self.fileroute = "/etc/ssh/sshd_not_to_be_run"
        
        if self.typeselect == "Activado":
            #Servicio ACTIVADO sigue existiendo /etc/ssh/sshd_not_to_be_run -> Borra y reinicia el servicio
            if os.path.exists(fileroute):
                subprocess.Popen(["rm", fileroute], stdout=subprocess.PIPE)
                subprocess.Popen(["sh", "/etc/init.d/ssh", "start"], stdout=subprocess.PIPE)
                time.sleep(0.5)
                
            else:
                subprocess.Popen(["sh", "/etc/init.d/ssh", "start"], stdout=subprocess.PIPE)

        #Desactivado
        else:
            #Servicio desactivado y no existe fichero flag -> Para el servicio y crea el fichero
            if not os.path.exists(fileroute):
                subprocess.Popen(["sh", "/etc/init.d/ssh", "stop"], stdout=subprocess.PIPE)
                subprocess.Popen(["touch", fileroute], stdout=subprocess.PIPE)
                
            else:
                subprocess.Popen(["sh", "/etc/init.d/ssh", "stop"], stdout=subprocess.PIPE)
        
            #Salir de la aplicación una vez activado/desactivado
        
        #Bloquear combo-box y aparecer Cerrar
        self.cb_status.set_sensitive(False)
       
        # Ya se ha terminado de actualizar o bien no se ha tocado
        self.clicked=self.clicked+1
        if self.clicked == 2 or self.bt_ok.get_label()=="Cerrar":
            self.wdssh.destroy()

        #Cambiar nombre botón OK. Aplicar por Cerrar
        if self.clicked == 1:
            self.bt_ok.set_label("Cerrar")
		
    def main(self):
        gtk.main()
			
if __name__ == "__main__":
    ssh_instance=Ssh()
    ssh_instance.main()
