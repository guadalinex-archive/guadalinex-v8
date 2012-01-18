#!/usr/bin/env python
# -*- coding: utf-8 -*-

### BEGIN LICENSE
# Copyright 2009 <Alfonso de Cala> <alfonso@el-magnifico.org>
#This program is free software: you can redistribute it and/or modify it 
#under the terms of the GNU General Public License version 3, as published 
#by the Free Software Foundation.
#
#This program is distributed in the hope that it will be useful, but 
#WITHOUT ANY WARRANTY; without even the implied warranties of 
#MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
#PURPOSE.  See the GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License along 
#with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

from distutils.core import setup
from DistUtilsExtra.command import *

setup(name='grubaker2',
    version='1.0',
    license='GPL v3',
    author='Alfonso de Cala',
    author_email='alfonso@el-magnifico.org',
    url='https://launchpad.net/grubaker2',
    scripts=['scripts/grubaker2'],
    packages=[''],
    data_files=[('share/grubaker2/',['data/grubaker2.ui']),
                ('share/icons/',['data/grubaker2.png']),
		('share/applications',['data/grubaker2.desktop'])],
    cmdclass = { "build" : build_extra.build_extra,
        "build_i18n" :  build_i18n.build_i18n,
        "clean": clean_i18n.clean_i18n,
        }
    )


