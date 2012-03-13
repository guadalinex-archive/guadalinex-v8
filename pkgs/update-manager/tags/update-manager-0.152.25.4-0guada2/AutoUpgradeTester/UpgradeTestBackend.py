# TargetNonInteractive.py
#
# abstraction for non-interactive backends (like chroot, qemu)
#

from DistUpgrade.DistUpgradeConfigParser import DistUpgradeConfig

import ConfigParser
import os
import os.path
import tempfile

# refactor the code so that we have
# UpgradeTest - the controler object
# UpgradeTestImage - abstraction for chroot/qemu/xen

class UpgradeTestImage(object):
    def runInTarget(self, command):
        pass
    def copyToImage(self, fromFile, toFile):
        pass
    def copyFromImage(self, fromFile, toFile):
        pass
    def bootstrap(self, force=False):
        pass
    def start(self):
        pass
    def stop(self):
        pass

class UpgradeTestBackend(object):
    """ This is a abstrace interface that all backends (chroot, qemu)
        should implement - very basic currently :)
    """

    apt_options = ["-y","--allow-unauthenticated"]

    def __init__(self, profiledir, resultdir=""):
        " init the backend with the given profile "
        # init the dirs
        assert(profiledir != None)
        profiledir = os.path.normpath(profiledir)
        profile = os.path.join(os.path.abspath(profiledir), "DistUpgrade.cfg")
        self.upgradefilesdir = "./DistUpgrade"

        if os.path.exists("./post_upgrade_tests/"):
            self.post_upgrade_tests_dir = "./post_upgrade_tests/"
        else:
            self.post_upgrade_tests_dir = "/usr/share/auto-upgrade-tester/post_upgrade_tests/"
        # init the rest
        if os.path.exists(profile):
            global_cfg_d = os.path.join(profiledir, "..", "global.cfg.d")
            self.profile = os.path.abspath(profile)
            self.config = DistUpgradeConfig(datadir=os.path.dirname(profile),
                                            name=os.path.basename(profile),
                                            override_dir=global_cfg_d)
        else:
            raise IOError, "Can't find profile '%s' (%s) " % (profile, os.getcwd())
        if resultdir:
            base_resultdir = resultdir
        else:
            base_resultdir = self.config.getWithDefault(
                "NonInteractive", "ResultDir", "results-upgrade-tester")
        self.resultdir = os.path.abspath(
            os.path.join(base_resultdir, profiledir.split("/")[-1]))
        if not os.path.exists(self.resultdir):
            os.makedirs(self.resultdir)
        
        self.fromDist = self.config.get("Sources","From")
        if "http_proxy" in os.environ and not self.config.has_option("NonInteractive","Proxy"):
	    self.config.set("NonInteractive","Proxy", os.environ["http_proxy"])
        elif self.config.has_option("NonInteractive","Proxy"):
            proxy=self.config.get("NonInteractive","Proxy")
            os.putenv("http_proxy",proxy)
        os.putenv("DEBIAN_FRONTEND","noninteractive")
        self.cachedir = None
        try:
            self.cachedir = self.config.get("NonInteractive","CacheDebs")
        except ConfigParser.NoOptionError:
            pass
        # init a sensible environment (to ensure proper operation if
        # run from cron)
        os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"

    def installPackages(self, pkgs):
        """
        install packages in the image
        """
        pass

    def getSourcesListFile(self):
        """
        creates a temporary sources.list file and returns it to 
        the caller
        """
        # write new sources.list
        sourceslist = tempfile.NamedTemporaryFile()
        comps = self.config.getlist("NonInteractive","Components")
        pockets = self.config.getlist("NonInteractive","Pockets")
        mirror = self.config.get("NonInteractive","Mirror")
        sourceslist.write("deb %s %s %s\n" % (mirror, self.fromDist, " ".join(comps)))
        for pocket in pockets:
            sourceslist.write("deb %s %s-%s %s\n" % (mirror, self.fromDist,pocket, " ".join(comps)))
        sourceslist.flush()
        return sourceslist
    
    def bootstrap(self):
        " bootstaps a pristine install"
        pass

    def upgrade(self):
        " upgrade a given install "
        pass

    def test(self):
        " test if the upgrade was successful "
        pass
