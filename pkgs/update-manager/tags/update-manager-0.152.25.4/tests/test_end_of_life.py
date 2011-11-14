#!/usr/bin/python

from gi.repository import GLib, Gtk

import mock
import unittest
import subprocess
import sys

sys.path.insert(0,"../")

class TestDistroEndOfLife(unittest.TestCase):

    # we need to test two cases:
    # - the current distro is end of life
    # - the next release (the upgrade target) is end of life

    def test_distro_current_distro_end_of_life(self):
        """ this code tests that check-new-release-gtk shows a 
            dist-no-longer-supported dialog when it detects that the 
            running distribution is no longer supported
        """
        def _nag_dialog_close_helper(checker):
            # this helper is called to verify that the nag dialog appears
            # and that it 
            dialog = checker.window_main.get_data("no-longer-supported-nag")
            self.assertNotEqual(dialog, None)
            dialog.response(Gtk.ResponseType.DELETE_EVENT)
            self.dialog_called = True
        # ----
        from check_new_release_gtk import CheckNewReleaseGtk
        options = mock.Mock()
        options.datadir = "../data"
        options.test_uri = None
        checker = CheckNewReleaseGtk(options)
        meta_release = mock.Mock()
        # pretend the current distro is no longer supported
        meta_release.no_longer_supported = subprocess.Popen(
            ["lsb_release","-c","-s"], 
            stdout=subprocess.PIPE).communicate()[0].strip()
        # build new release mock
        new_dist = mock.Mock()
        new_dist.name = "zaphod"
        new_dist.version = "127.0"
        new_dist.supported = True
        new_dist.releaseNotesHtmlUri = "http://www.ubuntu.com/html"
        new_dist.releaseNotesURI = "http://www.ubuntu.com/text"
        # schedule a close event in 1 s
        GObject.timeout_add_seconds(1, _nag_dialog_close_helper, checker)
        # run the dialog, this will also run a gtk mainloop so that the 
        # timeout works
        self.dialog_called = False
        checker.new_dist_available(meta_release, new_dist)
        self.assertTrue(self.dialog_called, True)


    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
