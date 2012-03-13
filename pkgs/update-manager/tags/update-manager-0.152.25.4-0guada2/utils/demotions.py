#! /usr/bin/env python
#
# FIXME: strip "TryExec" from the extracted menu files (and noDisplay)
#        
# TODO:
# - emacs21 ships it's icon in emacs-data, deal with this
# - some stuff needs to be blacklisted (e.g. gnome-about)
# - lots of packages have there desktop file in "-data", "-comon" (e.g. anjuta)
# - lots of packages have multiple desktop files for the same application
#   abiword, abiword-gnome, abiword-gtk

import os
import sys
import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)
import apt
import apt_pkg
#import xdg.Menu
import os.path

ARCHES = ["i386","amd64"]
#ARCHES = ["i386"]

# pkgs in main for the given dist
class Dist(object):
  def __init__(self,name):
    self.name = name
    self.pkgs_in_comp = {}


def get_replace(cache, pkgname):
  replaces = set()
  if not cache.has_key(pkgname):
    #print "can not find '%s'" % pkgname
    return replaces
  pkg = cache[pkgname]
  ver = cache._depcache.get_candidate_ver(pkg._pkg)
  if not ver:
    return replaces
  depends = ver.depends_list
  for t in ["Replaces"]:
    if not depends.has_key(t):
      continue
    for depVerList in depends[t]:
      for depOr in depVerList:
        replaces.add(depOr.target_pkg.name)
  return replaces


if __name__ == "__main__":

  # init
  apt_pkg.config.set("Dir::state","./apt/")
  apt_pkg.config.set("Dir::Etc","./apt")
  apt_pkg.config.set("Dir::State::status","./apt/status")
  try:
    os.makedirs("apt/lists/partial")
  except OSError:
    pass

  old = Dist(sys.argv[1]) # Dist("gutsy")
  new = Dist(sys.argv[2]) # Dist("hardy")
  
  # go over the dists to find main pkgs
  for dist in [old, new]:
    
    for comp in ["main", "restricted", "universe", "multiverse"]:
      line = "deb http://archive.ubuntu.com/ubuntu %s %s\n" % (dist.name,comp)
      file("apt/sources.list","w").write(line)
      dist.pkgs_in_comp[comp] = set()

      # and the archs
      for arch in ARCHES:
        apt_pkg.Config.set("APT::Architecture",arch)
        cache = apt.Cache(apt.progress.base.OpProgress())
        prog = apt.progress.base.AcquireProgress() 
        cache.update(prog)
        cache.open(apt.progress.base.OpProgress())
        map(lambda pkg: dist.pkgs_in_comp[comp].add(pkg.name), cache)

  # check what is no longer in main
  no_longer_main = old.pkgs_in_comp["main"] - new.pkgs_in_comp["main"]
  no_longer_main |= old.pkgs_in_comp["restricted"] - new.pkgs_in_comp["restricted"]

  # check what moved to universe and what was removed (or renamed)
  in_universe = lambda pkg: pkg in new.pkgs_in_comp["universe"] or pkg in new.pkgs_in_comp["multiverse"]

  # debug
  #not_in_universe = lambda pkg: not in_universe(pkg)
  #print filter(not_in_universe, no_longer_main)

  # this stuff was demoted and is no in universe
  demoted = filter(in_universe, no_longer_main)
  demoted.sort()

  # remove items that are now in universe, but are replaced by something
  # in main (pidgin, gaim) etc
  #print "Looking for replaces"
  line = "deb http://archive.ubuntu.com/ubuntu %s %s\n" % (new.name, "main")
  file("apt/sources.list","w").write(line)
  dist.pkgs_in_comp[comp] = set()
  for arch in ARCHES:
    apt_pkg.Config.set("APT::Architecture",arch)
    cache = apt.Cache(apt.progress.base.OpProgress())
    prog = apt.progress.base.AcquireProgress() 
    cache.update(prog)
    cache.open(apt.progress.base.OpProgress())
    # go over the packages in "main" and check if they replaces something
    # that we think is a demotion
    for pkgname in new.pkgs_in_comp["main"]:
      replaces = get_replace(cache, pkgname)
      for r in replaces:
        if r in demoted:
          #print "found '%s' that is demoted but replaced by '%s'" % (r, pkgname)
          demoted.remove(r)

  #outfile = "demoted.cfg"
  #print "writing the demotion info to '%s'" % outfile
  # write it out
  #out = open(outfile,"w")
  #out.write("# demoted packages\n")
  #out.write("\n".join(demoted))
  print "# demoted packages from %s to %s" % (sys.argv[1], sys.argv[2])
  print "\n".join(demoted)
