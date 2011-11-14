#!/usr/bin/python

import apt
import apt_pkg

def blacklisted(name):
	# we need to blacklist linux-image-* as it does not install
	# cleanly in the chroot (postinst failes)
	blacklist = ["linux-image-","ltsp-client",
		     "glibc-doc-reference", "libpthread-dev",
		     "cman", "mysql-server", "fuse-utils",
		     "ltspfs", "gfs2-tools", "edubuntu-server",
		     "gnbd-client", "gnbd-server", "mysql-server-5.0",
		     "rgmanager", "clvm","redhat-cluster-suit",
		     # has a funny "can not be upgraded automatically" policy
		     # see debian #368226
		     "quagga",
		     "system-config-cluster", "gfs-tools"]
	for b in blacklist:
		if name.startswith(b):
			return True
	return False

#apt_pkg.Config.Set("Dir::State::status","./empty")

cache = apt.Cache()
group = apt_pkg.GetPkgActionGroup(cache._depcache)
#print [pkg.name for pkg in cache if pkg.is_installed]

troublemaker = set()
for pkg in cache:
    for c in pkg.candidateOrigin:
        if c.component == "main":
            current = set([p.name for p in cache if p.marked_install])
	    if not (pkg.is_installed or blacklisted(pkg.name)):
	            pkg.mark_install()
            new = set([p.name for p in cache if p.marked_install])
            #if not pkg.markedInstall or len(new) < len(current):
	    if not (pkg.is_installed or pkg.marked_install):
                print "Can't install: %s" % pkg.name
            if len(current-new) > 0:
                troublemaker.add(pkg.name)
                print "Installing '%s' caused removals_ %s" % (pkg.name, current - new)

#print len(troublemaker)
for pkg in ["ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard"]:
    cache[pkg].mark_install()

# make sure we don't install blacklisted stuff
for pkg in cache:
	if blacklisted(pkg.name):
		pkg.mark_keep()

print "We can install:"
print len([pkg.name for pkg in cache if pkg.marked_install])
print "Download: "
pm = apt_pkg.GetPackageManager(cache._depcache)
fetcher = apt_pkg.GetAcquire()
pm.GetArchives(fetcher, cache._list, cache._records)
print apt_pkg.SizeToStr(fetcher.FetchNeeded)
print "Total space: ", apt_pkg.SizeToStr(cache._depcache.UsrSize)

res = False
current = 0
maxRetries = 3
while current < maxRetries:
    try:
        res = cache.commit(apt.progress.text.AcquireProgress(),
                           apt.progress.base.InstallProgress())    
    except IOError, e:
        # fetch failed, will be retried
        current += 1
        print "Retrying to fetch: ", current
        continue
    except SystemError, e:
        print "Error installing packages! "
        print e
    print "Install result: ",res
    break
