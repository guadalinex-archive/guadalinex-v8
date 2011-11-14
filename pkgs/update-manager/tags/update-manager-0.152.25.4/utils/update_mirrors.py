#!/usr/bin/python

import feedparser
import sys

# read what we have
current_mirrors = set()
for line in open(sys.argv[1], "r"):
    current_mirrors.add(line.strip())

    
outfile = open(sys.argv[1],"a")
d = feedparser.parse("https://launchpad.net/ubuntu/+archivemirrors-rss")

#import pprint
#pp  = pprint.PrettyPrinter(indent=4)
#pp.pprint(d)

for entry in d.entries:
    for link in entry.links:
        if not link.href in current_mirrors:
            outfile.write(link.href+"\n")
