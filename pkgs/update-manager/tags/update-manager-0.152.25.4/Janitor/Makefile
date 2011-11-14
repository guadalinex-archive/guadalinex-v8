# Makefile for Computer Janitor
# Copyright (C) 2008, 2009  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

all:

check: check-unittests check-has-unit-tests

check-unittests:
	env COMPUTER_JANITOR_UNITTEST=yes LC_ALL=C python -m CoverageTestRunner
	rm -f .coverage

check-has-unit-tests:
	find computerjanitor plugins -name '*.py' ! -name '*_tests.py' | \
	grep -Exv '^computerjanitor/(__init__|ui_gtk).py' | \
	grep -Exv '^plugins/(remove_lilo|check_admin_group)_plugin.py' | \
	grep -Exv '^plugins/(add_nfs_common)_plugin.py' | \
	grep -Exv '^plugins/(kdelibs4to5|langpack_manual)_plugin.py' | \
	grep -Exv '^plugins/(add_nfs_common)_plugin.py' | \
	sed 's/\.py$$//' | \
	while read file; do \
	    [ -e $${file}_tests.py ] || \
	    (echo "Missing unit test: $$file.py"; exit 1); done

clean:
	rm -f computerjanitor/*.py[co] testplugins/*.py[co] .coverage
	rm -rf build $(DESKTOP)

update-po:
	(echo '[encoding: UTF-8]'; \
	 ls computerjanitor/*.py plugins/*.py) > po/POTFILES.in
	python setup.py build_i18n --merge-po --po-dir po
