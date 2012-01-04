# Copyright (C) 2009 Canonical
#
# Authors:
#  Andrew Higginson
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import os
import logging

from xdg import BaseDirectory as xdg

SOFTWARE_CENTER_CONFIG_DIR = os.path.join(xdg.xdg_config_home, "softwarecenter")
SOFTWARE_CENTER_CONFIG_FILE = os.path.join(SOFTWARE_CENTER_CONFIG_DIR, "softwarecenter.cfg") 
