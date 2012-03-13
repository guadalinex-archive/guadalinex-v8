#!/usr/bin/python

from optparse import OptionParser
import os
import os.path
import time

import sys
sys.path.insert(0, "../DistUpgrade")

from UpgradeTestBackendQemu import UpgradeTestBackendQemu

import apt
import apt_pkg

def do_install_remove(backend, pkgname):
    """ install a package in the backend """
    #print "watchdog_runing: ", backend.watchdog_running
    if not backend.watchdog_running:
        print "starting watchdog"
        backend._runInImage(["/bin/apt-watchdog"])
        backend.watchdog_running = True
#    ret = backend._runInImage(["DEBIAN_FRONTEND=text","DEBIAN_PRIORITY=low",
#                               "apt-get","install","-q","-y",pkg.name])
    ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive",
                               "apt-get","install","-q","-y",pkg.name])
    print "apt returned: ", ret
    if ret != 0:
        return False
    # now remove it again
    ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive",
                               "apt-get","autoremove", "-y",pkg.name])
    print "apt returned: ", ret
    if ret != 0:
        return False
    return True

def test_downloadable(backend, pkgname):
    """ test if the pkg is downloadable or gives a 404 """ 
    ret = backend._runInImage(["apt-get","install","-q","--download-only","-y",pkg.name])
    print "apt --download-only returned: ", ret
    if ret != 0:
        return False
    return True

if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-p", "--profile", dest="profile", 
                      default="profile/auto-install-tester/",
                      help="base profile dir")

    (options, args) = parser.parse_args()

    # create backend
    apt_pkg.Config.Set("APT::Architecture","i386")
    basedir = os.path.abspath(os.path.dirname(options.profile))
    aptbasedir = os.path.join(basedir,"auto-install-test")


    # create apt dirs if needed
    for d in ["etc/apt/",
              "var/lib/dpkg",
              "var/lib/apt/lists/partial",
              "var/cache/apt/archives/partial"]:
        if not os.path.exists(os.path.join(aptbasedir,d)):
            os.makedirs(os.path.join(aptbasedir,d))


    backend = UpgradeTestBackendQemu(options.profile)
    backend.watchdog_running = False
    backend.bootstrap()

    # copy status file from image to aptbasedir
    backend.start()
    print "copy apt-watchdog"
    backend._copyToImage("apt-watchdog", "/bin/")
    print "copy status file"
    backend._copyFromImage("/var/lib/dpkg/status",
                           os.path.join(aptbasedir,"var/lib/dpkg/","status"))
    print "run update"
    backend._runInImage(["apt-get","-q", "update"])
    backend.stop()

    # build apt stuff (outside of the kvm)
    mirror = backend.config.get("NonInteractive","Mirror")
    dist = backend.config.get("Sources","From")
    components = backend.config.getlist("NonInteractive","Components")
    pockets =  backend.config.getlist("NonInteractive","Pockets")
    f=open(os.path.join(aptbasedir,"etc","apt","sources.list"),"w")
    f.write("deb %s %s %s\n" % (mirror, dist, " ".join(components)))
    for pocket in pockets:
        f.write("deb %s %s-%s %s\n" % (mirror, dist, pocket, " ".join(components)))
    f.close()
    
    # get a cache
    cache = apt.Cache(rootdir=os.path.abspath(aptbasedir))
    cache.update(apt.progress.text.AcquireProgress())
    cache.open(apt.progress.OpProgress())

    # now test if we can install stuff
    backend.saveVMSnapshot("clean-base")
    backend.start()

    # setup dirs
    resultdir = backend.resultdir
    print "Using resultdir: '%s'" % resultdir
    failures = open(os.path.join(resultdir,"failures.txt"),"w")

    # pkg blacklist - only useful for pkg that causes exsessive delays
    # when installing, e.g. by requiring input or by tryint to connect
    # to a (firewalled) network
    pkgs_blacklisted = set()
    sname = os.path.join(resultdir,"pkgs_blacklisted.txt")
    print "looking at ", sname
    if os.path.exists(sname):
        pkgs_blacklisted = set(open(sname).read().split("\n"))
        print "have '%s' with '%i' entries" % (sname, len(pkgs_blacklisted))

    # set with package that have been tested successfully
    pkgs_tested = set()
    sname = os.path.join(resultdir,"pkgs_done.txt")
    print "looking at ", sname
    if os.path.exists(sname):
        pkgs_tested = set(open(sname).read().split("\n"))
        print "have '%s' with '%i' entries" % (sname, len(pkgs_tested))
        statusfile = open(sname, "a")
    else:
        statusfile = open(sname, "w")

    # now see if we can install and remove it again
    for (i, pkg) in enumerate(cache):
#    for (i, pkg) in enumerate([ cache["abook"],
#                                cache["emacspeak"],
#                                cache["postfix"] ]):
        # clean the cache
        cache._depcache.Init()
        print "\n\nPackage %s: %i of %i (%f.2)" % (pkg.name, i, len(cache), 
                                             float(i)/float(len(cache))*100)
        print "pkgs_tested has %i entries\n\n" % len(pkgs_tested)

        pkg_failed = False

        # skip stuff in the ubuntu-minimal that we can't install or upgrade
        if pkg.is_installed and not pkg.is_upgradable:
            continue

        # skip blacklisted pkg names
        if pkg.name in pkgs_blacklisted:
            print "blacklisted: ", pkg.name
            continue

        # skip packages we tested already
        if "%s-%s" % (pkg.name, pkg.candidateVersion) in pkgs_tested:
            print "already tested: ", pkg.name
            continue

        # see if we can install/upgrade the pkg
        try:
            pkg.markInstall()
        except SystemError, e:
            pkg.markKeep()
        if not (pkg.markedInstall or pkg.markedUpgrade):
            print "pkg: %s not installable" % pkg.name
            failures.write("%s markInstall()\n " % pkg.name)
            continue
        
        if not test_downloadable(backend, pkg.name):
            # because the test runs for so long its likely that we hit
            # 404 because the archive has changed since we ran, deal with
            # that here by not outputing it as a error for a start
            # FIXME: restart whole test
            continue

        # mark as tested
        statusfile.write("%s-%s\n" % (pkg.name, pkg.candidateVersion))
            
        if not do_install_remove(backend, pkg.name):
            # on failure, re-run in a clean env so that the log
            # is more meaningful
            print "pkg: %s failed, re-testing in a clean(er) environment" % pkg.name
            backend.restoreVMSnapshot("clean-base")
            backend.watchdog_running = False
            backend.start()
            if not do_install_remove(backend, pkg.name):
                outname = os.path.join(resultdir,"%s-fail.txt" % pkg.name)
                failures.write("failed to install/remove %s (log at %s)\n" % (pkg.name, outname))
                time.sleep(5)
                backend._copyFromImage("/var/log/apt/term.log",outname)
                                       
                # now restore back to a clean state and continue testing
                # (but do not record the package as succesful tested)
                backend.restoreVMSnapshot("clean-base")
                backend.watchdog_running = False
                backend.start()
                continue

        # installation worked, record that we have tested this package
        for pkg in cache:
            if pkg.markedInstall or pkg.markedUpgrade:
                pkgs_tested.add("%s-%s" % (pkg.name, pkg.candidateVersion))
        statusfile.flush()
        failures.flush()
            
    # all done, stop the backend
    backend.stop()

