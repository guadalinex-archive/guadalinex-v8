# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

import gobject
import logging

from softwarecenter.utils import unescape

# FIXME: sucks, move elsewhere
in_replay_history_mode = False

class NavigationHistory(object):
    """
    class to manage navigation history in the "Get Software" section (the
    available pane).
    """

    MAX_NAV_ITEMS = 25  # limit number of NavItems allowed in the NavStack


    def __init__(self, available_pane):
        self.available_pane = available_pane
        # this is a bit ugly, but the way the available pane works
        # is that it adds the item on the first search and saves the
        # terms then. for subsequent searches (that do not go to a 
        # different page) we need to update the search terms here
        available_pane.searchentry.connect("terms-changed",
                                           self.on_search_terms_changed)
        # use stacks to track navigation history
        self._nav_stack = NavigationStack(self.MAX_NAV_ITEMS)

    def on_search_terms_changed(self, entry, terms):
        # The search terms changed, update them in the current navigation item
        self._nav_stack[self._nav_stack.cursor].apps_search_term = terms

    def navigate(self, nav_item):
        """
        append a new NavigationItem to the history stack
        """
        if in_replay_history_mode:
            return

        # reset navigation forward stack items on a direct navigation
        self._nav_stack.clear_forward_items()

        nav_item.parent = self
        self._nav_stack.append(nav_item)

        if self._nav_stack.cursor > 0:
            self.available_pane.back_forward.left.set_sensitive(True)
        self.available_pane.back_forward.right.set_sensitive(False)

    def navigate_no_cursor_step(self, nav_item):
        if in_replay_history_mode:
            return

        nav_item.parent = self
        self._nav_stack.append_no_cursor_step(nav_item)
        return

    def nav_forward(self):
        """
        navigate forward one item in the history stack
        """
        nav_item = self._nav_stack.step_forward()
        nav_item.navigate_to()

        self.available_pane.back_forward.left.set_sensitive(True)
        if self._nav_stack.at_end():
            if self.available_pane.back_forward.right.has_focus():
                self.available_pane.back_forward.left.grab_focus()
            self.available_pane.back_forward.right.set_sensitive(False)

    def nav_back(self):
        """
        navigate back one item in the history stack
        """
        nav_item = self._nav_stack.step_back()
        nav_item.navigate_to()

        self.available_pane.back_forward.right.set_sensitive(True)
        if self._nav_stack.at_start():
            if self.available_pane.back_forward.left.has_focus():
                self.available_pane.back_forward.right.grab_focus()
            self.available_pane.back_forward.left.set_sensitive(False)

    def get_last_label(self):
        if self._nav_stack.stack:
            if self._nav_stack[-1].parts:
                return self._nav_stack[-1].parts[-1].label
        return None

    def reset(self):
        """
        reset the navigation history by clearing the history stack
        """
        self._nav_stack.reset()


class NavigationItem(object):
    """
    class to implement navigation points to be managed in the history queues
    """

    def __init__(self, available_pane, update_available_pane_cb):
        self.available_pane = available_pane
        self.update_available_pane = update_available_pane_cb
        self.apps_category = available_pane.apps_category
        self.apps_subcategory = available_pane.apps_subcategory
        self.apps_search_term = available_pane.apps_search_term
        self.current_app = available_pane.get_current_app()
        self.parts = self.available_pane.navigation_bar.get_parts()

    def navigate_to(self):
        """
        navigate to the view that corresponds to this NavigationItem
        """
        global in_replay_history_mode
        in_replay_history_mode = True
        available_pane = self.available_pane
        available_pane.apps_category = self.apps_category
        available_pane.apps_subcategory = self.apps_subcategory
        available_pane.apps_search_term = self.apps_search_term
        available_pane.searchentry.set_text(self.apps_search_term)
        available_pane.searchentry.set_position(-1)
        available_pane.app_details.show_app(self.current_app)

        nav_bar = self.available_pane.navigation_bar
        nav_bar.remove_all(do_callback=False)

        for part in self.parts[1:]:
            nav_bar.add_with_id(unescape(part.label),
                                part.callback,
                                part.get_name(),
                                do_callback=False,
                                animate=False)

        gobject.idle_add(self._update_available_pane_cb, nav_bar)
        in_replay_history_mode = False

    def _update_available_pane_cb(self, nav_bar):
        last_part = nav_bar.get_parts()[-1]
        nav_bar.set_active_no_callback(last_part)
        self.update_available_pane()
        return False

    def __str__(self):
        details = []
        details.append("\n%s" % type(self))
        category_name = ""
        if self.apps_category:
            category_name = self.apps_category.name
        details.append("  apps_category.name: %s" % category_name)
        subcategory_name = ""
        if self.apps_subcategory:
            subcategory_name = self.apps_subcategory.name
        details.append("  apps_subcategory.name: %s" % subcategory_name)
        details.append("  current_app: %s" % self.current_app)
        details.append("  apps_search_term: %s" % self.apps_search_term)
        return '\n'.join(details)


class NavigationStack(object):
    """
    a navigation history stack
    """

    def __init__(self, max_length):
        self.max_length = max_length
        self.stack = []
        self.cursor = 0

    def __len__(self):
        return len(self.stack)

    def __repr__(self):
        BOLD = "\033[1m"
        RESET = "\033[0;0m"
        s = '['
        for i, item in enumerate(self.stack):
            if i != self.cursor:
                s += str(item.parts[-1].label) + ', '
            else:
                s += BOLD + str(item.parts[-1].label) + RESET + ', '
        return s + ']'

    def __getitem__(self, item):
        return self.stack[item]

    def _isok(self, item):
        if len(self.stack) == 0: 
            return True
        pre_item = self.stack[-1]
        if pre_item.parts[-1].label == item.parts[-1].label:
            if pre_item.apps_search_term != item.apps_search_term:
                return True
            return False
        return True

    def append(self, item):
        if not self._isok(item):
            self.cursor = len(self.stack)-1
            logging.debug('A:%s' % repr(self))
            return
        if len(self.stack) + 1 > self.max_length:
            self.stack.pop(0)
        self.stack.append(item)
        self.cursor = len(self.stack)-1
        logging.debug('A:%s' % repr(self))
        return

    def append_no_cursor_step(self, item):
        if not self._isok(item):
            logging.debug('a:%s' % repr(self))
            return
        if len(self.stack) + 1 > self.max_length:
            self.stack.pop(0)
        self.stack.append(item)
        logging.debug('a:%s' % repr(self))
        return

    def step_back(self):
        if self.cursor > 0:
            self.cursor -= 1
        else:
            self.cursor = 0
        logging.debug('B:%s' % repr(self))
        return self.stack[self.cursor]

    def step_forward(self):
        if self.cursor < len(self.stack)-1:
            self.cursor += 1
        else:
            self.cursor = len(self.stack)-1
        logging.debug('B:%s' % repr(self))
        return self.stack[self.cursor]

    def clear_forward_items(self):
        self.stack = self.stack[:(self.cursor + 1)]

    def at_end(self):
        return self.cursor == len(self.stack)-1

    def at_start(self):
        return self.cursor == 0

    def reset(self):
        self.stack = []
        self.cursor = 0
