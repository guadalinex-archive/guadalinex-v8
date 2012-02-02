#!/usr/bin/python
# This software is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this package; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

__author__ = "Roberto C. Morano <rcmorano@emergya.es>"
__copyright__ = "Copyright 2010, Junta de Andalucia"
__license__ = "GPL-2"

from distutils.core import setup
import glob
import os
import re

# look/set what version we have
changelog = "debian/changelog"
if os.path.exists(changelog):
    head=open(changelog).readline()
    match = re.compile(".*\((.*)\).*").match(head)
    if match:
        version = match.group(1)

etcpath    = "/etc/" 

setup(name='dangerous',
      version=version,
      packages=[''],
      scripts=['dangerous'],
      data_files=[
                (etcpath,['dangerous.conf']),
                ('share/applications',['dangerous.desktop']),
                ('share/dangerous',['dangerous.descriptions']),
                ('share/dangerous',['dangerous.glade']),
                ('share/pixmaps',['dangerous.png'])
                ]
)
