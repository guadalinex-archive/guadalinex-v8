#!/usr/bin/env python
# -*- coding: utf-8 -*-

### BEGIN LICENSE
# Copyright 2010 <Alvaro Pinel> <alvaropinel@gmail.com>
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

setup(name='diagnostic_report',
    version='1.0',
    license='GPL v3',
    author='Alvaro Pinel',
    author_email='alvaro@gmail.com',
    url='https://launchpad.net/diagnostic-report',
    scripts=['scripts/diagnostic_report.py'],
    packages=[''],
    data_files=[('share/diagnostic_report/',['data/diagnostic_report.glade']),
                ('share/diagnostic_report/',['data/diagnostic_report_exception.glade']),
                ('share/diagnostic_report/',['data/diagnostic_report_init.glade']),
                ('share/diagnostic_report/',['data/diagnostic_report_end.glade']),
                ('share/icons/',['data/diagnostic-report.png']),
		('share/applications',['data/diagnostic_report.desktop'])],
    cmdclass = { "build" : build_extra.build_extra,
        "build_i18n" :  build_i18n.build_i18n,
        "clean": clean_i18n.clean_i18n,
        }
    )


