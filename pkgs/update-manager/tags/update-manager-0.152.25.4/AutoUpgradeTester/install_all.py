#!/usr/bin/python


import apt
import apt_pkg
import re
import os
import string
import sys

# global install blacklist
pkg_blacklist = None

# whitelist regexp to include only certain packages (useful for e.g.
# installing only all python packages)
pkg_whitelist = ""

class InstallProgress(apt.progress.base.InstallProgress):
   " Out install progress that can automatically remove broken pkgs "
   def error(self, pkg, errormsg):
      # on failure: 
      # - add failing package to "install_failures.txt"  [done]
      # - remove package from best.txt [done]
      # FIXME: - remove all rdepends from best.txt
      # - remove the failed install attempts [done]
      #   * explode if a package can not be removed and let the user cleanup
      open("install_failures.txt","a").write("%s _:_ %s" % (pkg, errormsg))
      bad = set()
      bad.add(os.path.basename(pkg).split("_")[0])
      # FIXME: just run apt-cache rdepends $pkg here?
      #        or use apt.Package.candidateDependencies ?
      #        or calculate the set again? <- BEST!
      for name in bad:
         new_best = open("best.txt").read().replace(name+"\n","")
         open("best.txt","w").write(new_best)
         open("install_blacklist.cfg","a").write("# auto added by install_all.py\n%s\n" % name)

def do_install(cache):
   # go and install
   res = False
   current = 0
   maxRetries = 5
   while current < maxRetries:
      print "Retry: ", current
      try:
         res = cache.commit(apt.progress.text.AcquireProgress(),
                            InstallProgress())
         break
      except IOError, e:
         # fetch failed, will be retried
         current += 1
         print "Retrying to fetch: ", current, e
         continue
      except SystemError, e:
         print "Error installing packages! "
         print e
         print "Install result: ",res
         break
   # check for failed packages and remove them
   if os.path.exists("install_failures.txt"):
      failures =  set(map(lambda s: os.path.basename(s.split("_:_")[0]).split("_")[0], 
                          open("install_failures.txt").readlines()))
      print "failed: ", failures
      assert(os.system("dpkg -r %s" % " ".join(failures)) == 0)
      assert(os.system("dpkg --configure -a") == 0)
      # remove pos.txt and best.txt to force recalculation
      os.unlink("pos.txt")
      os.unlink("best.txt")
   return res

def blacklisted(name):
   global pkg_blacklist
   if pkg_blacklist is None and os.path.exists("install_blacklist.cfg"):
      pkg_blacklist = set()
      for name in map(string.strip, open("install_blacklist.cfg").readlines()):
         if name and not name.startswith("#"):
            pkg_blacklist.add(name)
      print "blacklist: ", pkg_blacklist
   if pkg_blacklist:
      for b in pkg_blacklist:
	   if re.match(b, name):
              return True
   return False

def reapply(cache, pkgnames):
   for name in pkgnames:
      cache[name].mark_install(False)

def contains_blacklisted_pkg(cache):
   for pkg in cache:
      if pkg.marked_install and blacklisted(pkg.name):
         return True
   return False


# ----------------------------------------------------------------

#apt_pkg.Config.Set("Dir::State::status","./empty")

# debug stuff
#apt_pkg.Config.Set("Debug::pkgProblemResolver","true")
#apt_pkg.Config.Set("Debug::pkgDepCache::AutoInstall","true")
#apt_pkg.Config.Set("Debug::pkgDpkgPM","true")

# Increase the maxsize limits here
#
# this code in apt that splits the argument list if its too long
#  is problematic, because it may happen that
# the argument list is split in a way that A depends on B
# and they are in the same "--configure A B" run
# - with the split they may now be configured in different
#   runs 

apt_pkg.config.set("Dpkg::MaxArgs",str(16*1024))
apt_pkg.config.set("Dpkg::MaxArgBytes",str(64*1024))

print "install_all.py"
os.environ["DEBIAN_FRONTEND"] = "noninteractive"
os.environ["APT_LISTCHANGES_FRONTEND"] = "none"

cache = apt.Cache()

# dapper does not have this yet 
group = cache.actiongroup()
#print [pkg.name for pkg in cache if pkg.is_installed]

# see what gives us problems
troublemaker = set()
best = set()

# first install all of main, then the rest
comps= ["main","universe"]
i=0

# reapply checkpoints
if os.path.exists("best.txt"):
   best = map(string.strip, open("best.txt").readlines())
   reapply(cache, best)

if os.path.exists("pos.txt"):
   (comp, i) = open("pos.txt").read().split()
   i = int(i)
   if comp == "universe":
      comps = ["universe"]

sorted_pkgs = cache.keys()[:]
sorted_pkgs.sort()


for comp in comps:
   for pkgname in sorted_pkgs[i:]:
      pkg = cache[pkgname]
      i += 1
      percent = (float(i)/len(cache))*100.0
      print "\r%.3f     " % percent,
      sys.stdout.flush()
      # ignore stuff that does not match the whitelist pattern
      # (if we use this)
      if pkg_whitelist:
         if not re.match(pkg_whitelist, pkg.name):
            #print "skipping '%s' (not in whitelist)" % pkg.name
            continue
      print "looking at ", pkg.name
      # only work on stuff that has a origin
      if pkg.candidate:
         for c in pkg.candidate.origins:
            if comp == None or c.component == comp:
               current = set([p.name for p in cache if p.marked_install])
               if not (pkg.is_installed or blacklisted(pkg.name)):
                  try:
                     pkg.mark_install()
                  except SystemError, e:
                     print "Installing '%s' cause problems: %s" % (pkg.name, e)
                     pkg.mark_keep()
                  # check blacklist
                  if contains_blacklisted_pkg(cache):
                     cache.clear()
                     reapply(cache, best)
                     continue
                  new = set([p.name for p in cache if p.marked_install])
                  #if not pkg.marked_install or len(new) < len(current):
                  if not (pkg.is_installed or pkg.marked_install):
                     print "Can't install: %s" % pkg.name
                  if len(current-new) > 0:
                     troublemaker.add(pkg.name)
                     print "Installing '%s' caused removals %s" % (pkg.name, current - new)
                  # FIXME: instead of len() use score() and score packages
                  #        according to criteria like "in main", "priority" etc
                  if len(new) >= len(best):
                     best = new
                     open("best.txt","w").write("\n".join(best))
                     open("pos.txt","w").write("%s %s" % (comp, i))
                  else:
                     print "Installing '%s' reduced the set (%s < %s)" % (pkg.name, len(new), len(best))
                     cache.clear()
                     reapply(cache, best)
   i=0

# make sure that the ubuntu base packages are installed (and a bootloader)
print len(troublemaker)
for pkg in ["ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard", "grub-pc"]:
    cache[pkg].mark_install()

# make sure we don't install blacklisted stuff
for pkg in cache:
	if blacklisted(pkg.name):
		pkg.mark_keep()

# install it
print "We can install:", len([pkg.name for pkg in cache if pkg.marked_install])
# get size
pm = apt_pkg.PackageManager(cache._depcache)
fetcher = apt_pkg.Acquire()
pm.get_archives(fetcher, cache._list, cache._records)
print "Download: ", apt_pkg.size_to_str(fetcher.fetch_needed)
print "Total space: ", apt_pkg.size_to_str(cache._depcache.usr_size)

# write out file with all pkgs
outf = "all_pkgs.cfg"
print "writing out file with the selected package names to '%s'" % outf
f = open(outf, "w")
f.write("\n".join([pkg.name for pkg in cache if pkg.marked_install]))
f.close()

# now do the real install
res = do_install(cache)

if not res:
   # FIXME: re-exec itself
   sys.exit(1)

sys.exit(0)
