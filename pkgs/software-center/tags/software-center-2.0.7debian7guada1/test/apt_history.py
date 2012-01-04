#!/usr/bin/python

import sys
sys.path.insert(0, "..")

from softwarecenter.apt.apthistory import AptHistory

if __name__ == "__main__":

    # current
    history = AptHistory()
    for trans in history.transactions:
        print "Date: %s - Count: %s" % (trans.start_date, len(trans))
        print "".join(history.find_terminal_log(trans.start_date))
        print

    # read one from a gzip log
    print history.find_terminal_log("2009-11-04  10:41:22")

    # old
    for old in history.older_parts:
        history = AptHistory(old)
        for trans in history.transactions:
            print "older: %s (count: %s)" % (trans.start_date, len(trans))

