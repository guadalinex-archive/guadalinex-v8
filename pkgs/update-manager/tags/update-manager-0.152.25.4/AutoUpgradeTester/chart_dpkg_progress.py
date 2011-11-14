#!/usr/bin/python


import sys
import string
from heapq import heappush, heappop

if __name__ == "__main__":
    
    start_time = 0.0
    last_time = 0.0
    total_time = 0.0
    pkgs = {}
    last_pkgname = None

    log = open(sys.argv[1])
    for line in map(string.strip, log):
        line_data = line.split(":")

        # special cases
        if line_data[1].strip() == "Start":
            start_time = float(line_data[0])
            continue
        elif line_data[1].strip() == "Finished":
            total_time = float(line_data[0]) - start_time
            continue

        # we have a real pkg here
        current_time = float(line_data[0])
        pkgname = line_data[2]
        
        # special cases
        if not last_time:
            last_time = current_time
        if not pkgname in pkgs:
            pkgs[pkgname] = 0

        # add up time
        if last_pkgname:
            pkgs[last_pkgname] += (current_time-last_time)
        last_time = current_time
        last_pkgname = pkgname
    
    
    # put into heap and output by time it takes
    heap = []
    for pkg in pkgs:
        heappush(heap, (pkgs[pkg], pkg))
    while heap:
        print "%.6ss: %s" % heappop(heap)
    print "total: %4.7ss %4.6sm" % (total_time, total_time/60)
