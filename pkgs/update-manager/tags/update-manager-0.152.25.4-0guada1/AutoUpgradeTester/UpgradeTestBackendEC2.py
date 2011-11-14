# ec2 backend

from UpgradeTestBackendSSH import UpgradeTestBackendSSH
from UpgradeTestBackend import UpgradeTestBackend

from DistUpgrade.sourceslist import SourcesList

from boto.ec2.connection import EC2Connection

import ConfigParser
import os
import sys
import os.path
import glob
import time
import atexit
import apt_pkg


# images created with EC2
class NoCredentialsFoundException(Exception):
    pass

class OptionError(Exception):
    pass


# Step to perform for a ec2 upgrade test
#
# 1. conn = EC2Connect()
# 2. reservation = conn.run_instances(image_id = image, security_groups = groups, key_name = key)
# 3. wait for instance.state == 'running':
#    instance.update()
# 4. ssh -i <key> root@instance.dns_name <command>


# TODO
#
# Using ebs (elastic block storage) and snapshots for the test
# 1. ec2-create-volume -s 80 -z us-east-1a
#    (check with ec2-describe-instance that its actually in 
#     the right zone)
# 2. ec2-attach-volume vol-7bd23de2 -i i-3325ad4 -d /dev/sdh
#    (do not name it anything but sd*)
# 3. mount/use the thing inside the instance
#
#
# Other useful things:
# - sda1: root fs
# - sda2: free space (~140G)
# - sda3: swapspace  (~1G)

class UpgradeTestBackendEC2(UpgradeTestBackendSSH):
    " EC2 backend "

    def __init__(self, profile):
        UpgradeTestBackend.__init__(self, profile)
        self.profiledir = os.path.abspath(os.path.dirname(profile))
        # ami base name (e.g .ami-44bb5c2d)
        self.ec2ami = self.config.get("EC2","AMI")
        self.ssh_key = self.config.get("EC2","SSHKey")
        try:
            self.access_key_id = (os.getenv("AWS_ACCESS_KEY_ID") or
                                  self.config.get("EC2","access_key_id"))
            self.secret_access_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or
                                      self.config.get("EC2","secret_access_key"))
        except ConfigParser.NoOptionError:
            print "Either export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or"
            print "set access_key_id and secret_access_key in the profile config"
            print "file."
            sys.exit(1)
        self._conn = EC2Connection(self.access_key_id, self.secret_access_key)
        self.ubuntu_official_ami = False
        if self.config.has_option("EC2","UbuntuOfficialAMI"):
            self.ubuntu_official_ami = self.config.getboolean("EC2","UbuntuOfficialAMI")
        
        try:
            self.security_groups = self.config.getlist("EC2","SecurityGroups")
        except ConfigParser.NoOptionError:
            self.security_groups = []

        if self.ssh_key.startswith("./"):
            self.ssh_key = self.profiledir + self.ssh_key[1:]
        self.ssh_port = "22"
        self.instance = None

        # the public name of the instance, e.g. 
        #  ec2-174-129-152-83.compute-1.amazonaws.com
        self.ssh_hostname = ""
        # the instance name (e.g. i-3325ad4)
        self.ec2instance = ""
        if (self.config.has_option("NonInteractive","RealReboot") and
            self.config.getboolean("NonInteractive","RealReboot")):
            raise OptionError, "NonInteractive/RealReboot option must be set to False for the ec2 upgrader"
        atexit.register(self._cleanup)

    def _cleanup(self):
        print "_cleanup(): stopping running instance"
        if self.instance:
            self.instance.stop()

    def _enableRootLogin(self):
        command = ["sudo", 
                   "sed", "-i", "-e", "'s,\(.*\)\(ssh-rsa.*\),\\2,'", 
                   "/root/.ssh/authorized_keys"]
        ret = self._runInImageAsUser("ubuntu", command)
        return (ret == 0)

    def bootstrap(self, force=False):
        print "bootstrap()"

        print "Building new image based on '%s'" % self.ec2ami

        # get common vars
        basepkg = self.config.get("NonInteractive","BasePkg")

        # start the VM
        self.start_instance()

        # prepare the sources.list (needed because a AMI may have any
        # sources.list)
        sources = self.getSourcesListFile()
        ret = self._copyToImage(sources.name, "/etc/apt/sources.list")
        assert(ret == 0)

        # install some useful stuff
        ret = self._runInImage(["apt-get","update"])
        assert(ret == 0)
        # FIXME: instead of this retrying (for network errors with 
        #        proxies) we should have a self._runAptInImage() 
        for i in range(3):
            ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "--allow-unauthenticated", "-y",basepkg])
        assert(ret == 0)

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install","--reinstall", "--allow-unauthenticated", "-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
                print "apt returned a error, stopping"
                self.stop_instance()
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            print "have PostBootstrapScript: %s" % script
            if os.path.exists(script):
                self._runInImage(["mkdir","/upgrade-tester"])
                self._copyToImage(script, "/upgrade-tester")
                print "running script: %s" % os.path.join("/tmp",script)
                self._runInImage([os.path.join("/upgrade-tester",script)])
            else:
                print "WARNING: %s not found" % script

        if self.config.getWithDefault("NonInteractive",
                                      "UpgradeFromDistOnBootstrap", False):
            print "running apt-get upgrade in from dist (after bootstrap)"
            for i in range(3):
                ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","--allow-unauthenticated", "-y","dist-upgrade"])
            assert(ret == 0)

        print "Cleaning image"
        ret = self._runInImage(["apt-get","clean"])
        assert(ret == 0)

        # done with the bootstrap

        # FIXME: idealy we would reboot here, but its less important
        #        because we can't get a new kernel anyway in ec2 (yet)
        # - the reboot thing is *not* yet reliable!
        #self.reboot_instance()

        # FIXME: support for caching/snapshoting the base image here
        
        return True

    def start_instance(self):
        print "Starting ec2 instance and wait until its availabe "

        # start the instance
        reservation = self._conn.run_instances(image_id=self.ec2ami,
                                               security_groups=self.security_groups,
                                               key_name=self.ssh_key[:-4].split("/")[-1])
        self.instance = reservation.instances[0]
        while self.instance.state == "pending":
                print "Waiting for instance %s to come up..." % self.instance.id
                time.sleep(10)
                self.instance.update()

        print "It's up: hostname =", self.instance.dns_name
        self.ssh_hostname = self.instance.dns_name
        self.ec2instance = self.instance.id

        # now sping until ssh comes up in the instance
        if self.ubuntu_official_ami:
            user = "ubuntu"
        else:
            user = "root"
        for i in range(900):
            time.sleep(1)
            if self.ping(user):
                print "instance available via ssh ping"
                break
        else:
            print "Could not connect to instance after 900s, exiting"
            return False
        # re-enable root login if needed
        if self.ubuntu_official_ami:
            print "Re-enabling root login... ",
            ret = self._enableRootLogin()
            if ret:
                print "Done!"
            else:
                print "Oops, failed to enable root login..."
            assert (ret == True)
            # the official image seems to run a update on startup?!?
            print "waiting for the official image to leave apt alone"
            time.sleep(10)
        return True
    
    def reboot_instance(self):
        " reboot a ec2 instance and wait until its available again "
        self.instance.reboot()
        # FIMXE: find a better way to know when the instance is 
        #        down - maybe with "-v" ?
        time.sleep(5)
        while True:
            if self._runInImage(["/bin/true"]) == 0:
                print "instance rebootet"
                break

    def stop_instance(self):
        " permanently stop a instance (it can never be started again "
        # terminates are final - all data is lost
        self.instance.stop()
        # wait until its down
        while True:
            if self._runInImage(["/bin/true"]) != 0:
                print "instance stopped"
                break

    def upgrade(self):
        print "upgrade()"

        # clean from any leftover pyc files
        for f in glob.glob("%s/*.pyc" %  self.upgradefilesdir):
            os.unlink(f)

        print "Starting for upgrade"

        assert(self.ec2instance)
        assert(self.ssh_hostname)

        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to image overrides" % self.profile
            self._runInImage(["mkdir","-p","/etc/update-manager/release-upgrades.d"])
            self._copyToImage(self.profile, "/etc/update-manager/release-upgrades.d/")

        # copy test repo sources.list (if needed)
        test_repo = self.config.getWithDefault("NonInteractive","AddRepo","")
        if test_repo:
            test_repo = os.path.join(os.path.dirname(self.profile), test_repo)
            self._copyToImage(test_repo, "/etc/apt/sources.list.d")
            sourcelist = self.getSourcesListFile()
            apt_pkg.Config.Set("Dir::Etc", os.path.dirname(sourcelist.name))
            apt_pkg.Config.Set("Dir::Etc::sourcelist", 
                               os.path.basename(sourcelist.name))
            sources = SourcesList(matcherPath=".")
            sources.load(test_repo)
            # add the uri to the list of valid mirros in the image
            for entry in sources.list:
                if (not (entry.invalid or entry.disabled) and
                    entry.type == "deb"):
                    print "adding %s to mirrors" % entry.uri
                    self._runInImage(["echo '%s' >> /upgrade-tester/mirrors.cfg" % entry.uri])

        # check if we have a bzr checkout dir to run against or
        # if we should just run the normal upgrader
        if (os.path.exists(self.upgradefilesdir) and
            self.config.getWithDefault("NonInteractive", 
                                       "UseUpgraderFromBzr", 
                                       True)):
            self._copyUpgraderFilesFromBzrCheckout()
            ret = self._runBzrCheckoutUpgrade()
        else:
            ret = self._runInImage(["do-release-upgrade","-d",
                                    "-f","DistUpgradeViewNonInteractive"])
        print "dist-upgrade.py returned: %i" % ret
        

        # copy the result
        print "coyping the result"
        self._copyFromImage("/var/log/dist-upgrade/*",self.resultdir)

        # stop the machine
        print "Shuting down the VM"
        self.stop_instance()

        return True

    def test(self):
        # FIXME: add some tests here to see if the upgrade worked
        # this should include:
        # - new kernel is runing (run uname -r in target)
        # - did it sucessfully rebooted
        # - is X runing
        # - generate diff of upgrade vs fresh install
        # ...
        return True
        

    # compatibility for the auto-install-tester
    def start(self):
        self.start_instance()
    def stop(self):
        self.stop_instance()
    def saveVMSnapshot(self):
        print "saveVMSnapshot not supported yet"
    def restoreVMSnapshot(self):
        print "restoreVMSnapshot not supported yet"

    
# vim:ts=4:sw=4:et

