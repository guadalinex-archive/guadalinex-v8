# qemu backend

from UpgradeTestBackendSSH import UpgradeTestBackendSSH
from DistUpgrade.sourceslist import SourcesList

import ConfigParser
import subprocess
import os
import sys
import os.path
import shutil
import glob
import time
import tempfile
import atexit
import apt_pkg

# images created with http://bazaar.launchpad.net/~mvo/ubuntu-jeos/mvo
#  ./ubuntu-jeos-builder --vm kvm --kernel-flavor generic --suite feisty --ssh-key `pwd`/ssh-key.pub  --components main,restricted --rootsize 20G
# 


# TODO: 
# - add support to boot certain images with certain parameters
#   (dapper-386 needs qemu/kvm with "-no-acpi" to boot reliable)
# - add option to use pre-done base images
#   the bootstrap() step is then a matter of installing the right
#   packages into the image (via _runInImage())
# 
# - refactor and move common code to UpgradeTestBackend
# - convert ChrootNonInteractive 
# - benchmark qemu/qemu+kqemu/kvm/chroot
# - write tests (unittest, doctest?)
# - offer "test-upgrade" feature on real system, run it
#   as "qemu -hda /dev/hda -snapshot foo -append init=/upgrade-test"
#   (this *should* write the stuff to the snapshot file
# - add "runInTarget()" that will write a marker file so that we can
#   re-run a command if it fails the first time (or fails because
#   a fsck was done and reboot needed in the VM etc)
# - start a X session with the gui-upgrader in a special
#   "non-interactive" mode to see if the gui upgrade would work too

class NoImageFoundException(Exception):
    pass

class PortInUseException(Exception):
    pass

class UpgradeTestBackendQemu(UpgradeTestBackendSSH):
    " qemu/kvm backend - need qemu >= 0.9.0"

    QEMU_DEFAULT_OPTIONS = [
        "-monitor","stdio",
        "-localtime",
        "-no-reboot",    # exit on reboot
        #        "-no-kvm",      # crashes sometimes with kvm HW
        ]

    def __init__(self, profile):
        UpgradeTestBackendSSH.__init__(self, profile)
        self.qemu_options = self.QEMU_DEFAULT_OPTIONS[:]
        self.qemu_pid = None
        self.profiledir = os.path.dirname(profile)
        # get the kvm binary
        self.qemu_binary = self.config.getWithDefault("KVM","KVM","kvm")
        # setup mount dir/imagefile location
        self.baseimage = self.config.get("KVM","BaseImage")
        if not os.path.exists(self.baseimage):
            print "Missing '%s' base image, need to build it now" % self.baseimage
            ret = subprocess.call(["sudo",
                                   "ubuntu-vm-builder","kvm", self.fromDist,
                                   "--kernel-flavour", "generic",
                                   "--ssh-key", "%s.pub" % self.ssh_key ,
                                   "--components", "main,restricted",
                                   "--rootsize", "80000",
                                   "--addpkg", "openssh-server",
                                   "--arch", "i386"])
            # move the disk in place
            shutil.move(glob.glob("ubuntu-kvm/*.qcow2")[0],self.baseimage)
            if ret != 0:
                raise NoImageFoundException
        # check if we want virtio here and default to yes
        try:
            self.virtio = self.config.getboolean("KVM","Virtio")
        except ConfigParser.NoOptionError:
            self.virtio = True
        if self.virtio:
            self.qemu_options.extend(["-net","nic,model=virtio"])
            self.qemu_options.extend(["-net","user"])
        # swapimage
        if self.config.getWithDefault("KVM","SwapImage",""):
            self.qemu_options.append("-hdb")
            self.qemu_options.append(self.config.get("KVM","SwapImage"))
        # regular image
        profilename = self.config.get("NonInteractive","ProfileName")
        imagedir = self.config.get("KVM","ImageDir")
        self.image = os.path.join(imagedir, "test-image.%s" % profilename)
        # make ssh login possible (localhost 54321) available
        self.ssh_port = self.config.getWithDefault("KVM","SshPort","54321")
        self.ssh_hostname = "localhost"
        self.qemu_options.append("-redir")
        self.qemu_options.append("tcp:%s::22" % self.ssh_port)
        # vnc port/display
        vncport = self.config.getWithDefault("KVM","VncNum","0")
        self.qemu_options.append("-vnc")
        self.qemu_options.append("localhost:%s" % vncport)

        # make the memory configurable
        mem = self.config.getWithDefault("KVM","VirtualRam","768")
        self.qemu_options.append("-m")
        self.qemu_options.append(str(mem))

        # check if the ssh port is in use
        if subprocess.call("netstat -t -l -n |grep 0.0.0.0:%s" % self.ssh_port,
                           shell=True) == 0:
            raise PortInUseException, "the port is already in use (another upgrade tester is running?)"
        # register exit handler to ensure that we quit kvm on exit
        atexit.register(self.stop)

    def genDiff(self):
        """ 
        generate a diff that compares a fresh install to a upgrade.
        ideally that should be empty
        Ensure that we always run this *after* the regular upgrade was
        run (otherwise it is useless)
        """
        # generate ls -R output of test-image (
        self.start()
        self._runInImage(["find", "/bin", "/boot", "/etc/", "/home",
                          "/initrd", "/lib", "/root", "/sbin/",
                          "/srv", "/usr", "/var"],
                         stdout=open(self.resultdir+"/upgrade_install.files","w"))
        self._runInImage(["dpkg","--get-selections"],
                         stdout=open(self.resultdir+"/upgrade_install.pkgs","w"))
        self._runInImage(["tar","cvf","/tmp/etc-upgrade.tar","/etc"])
        self._copyFromImage("/tmp/etc-upgrade.tar", self.resultdir)
        self.stop()

        # HACK: now build fresh toDist image - it would be best if
        self.fromDist = self.config.get("Sources","To")
        self.config.set("Sources","From",
                        self.config.get("Sources","To"))
        diff_image = os.path.join(self.profiledir, "test-image.diff")
        # FIXME: we need to regenerate the base image too, but there is no
        #        way to do this currently without running as root
        # as a workaround we regenerate manually every now and then
        # and use UpgradeFromDistOnBootstrap=true here
        self.config.set("KVM","CacheBaseImage", "false")
        self.config.set("NonInteractive","UpgradeFromDistOnBootstrap","true")
        self.baseimage = "jeos/%s-i386.qcow2" % self.config.get("Sources","To")
        self.image = diff_image
        print "bootstraping into %s" % diff_image
        self.bootstrap()
        print "bootstrap finshsed"
        self.start()
        print "generating file diff list"
        self._runInImage(["find", "/bin", "/boot", "/etc/", "/home",
                          "/initrd", "/lib", "/root", "/sbin/",
                          "/srv", "/usr", "/var"],
                         stdout=open(self.resultdir+"/fresh_install","w"))
        self._runInImage(["dpkg","--get-selections"],
                         stdout=open(self.resultdir+"/fresh_install.pkgs","w"))
        self._runInImage(["tar","cvf","/tmp/etc-fresh.tar","/etc"])
        self._copyFromImage("/tmp/etc-fresh.tar", self.resultdir)
        self.stop()
        # now compare the diffs
        pass

    def bootstrap(self, force=False):
        print "bootstrap()"

        # move old crash files away so that test() is not
        # confused by them
        for f in glob.glob(self.resultdir+"/*.crash"):
            shutil.move(f, f+".old")

        # copy image into place, use baseimage as template
        # we expect to be able to ssh into the baseimage to
        # set it up
        if (not force and
            os.path.exists("%s.%s" % (self.image,self.fromDist)) and 
            self.config.has_option("KVM","CacheBaseImage") and
            self.config.getboolean("KVM","CacheBaseImage")):
            print "Not bootstraping again, we have a cached BaseImage"
            shutil.copy("%s.%s" % (self.image,self.fromDist), self.image)
            return True

        print "Building new image '%s' based on '%s'" % (self.image, self.baseimage)
        shutil.copy(self.baseimage, self.image)

        # get common vars
        basepkg = self.config.get("NonInteractive","BasePkg")
        additional_base_pkgs = self.config.getlist("Distro","BaseMetaPkgs")

        # start the VM
        self.start()

        # FIXME: make this part of the apt env
        #        otherwise we get funny debconf promtps for 
        #        e.g. the xserver
        #export DEBIAN_FRONTEND=noninteractive
        #export APT_LISTCHANGES_FRONTEND=none
        # 

        # generate static network config (NetworkManager likes
        # to reset the dhcp interface and that sucks when
        # going into the VM with ssh)
        nm = self.config.getWithDefault("NonInteractive","WorkaroundNetworkManager","")
        if nm:
            interfaces = tempfile.NamedTemporaryFile()
            interfaces.write("""
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
       address 10.0.2.15
       netmask 255.0.0.0
       gateway 10.0.2.2
""")
            interfaces.flush()
            self._copyToImage(interfaces.name, "/etc/network/interfaces")
        
        # generate hosts file, the default hosts file contains
        # "127.0.0.1 ubuntu. ubuntu" for some reason and the missing
        # domain part after the "." makes e.g. postfix rather unhappy
        etc_hosts = tempfile.NamedTemporaryFile()
        etc_hosts.write('127.0.0.1 localhost\n')
        etc_hosts.write('127.0.0.1 upgrade-test-vm\n')
        etc_hosts.flush()
        self._copyToImage(etc_hosts.name, "/etc/hosts")

        # generate apt.conf
        proxy = self.config.getWithDefault("NonInteractive","Proxy","")
        if proxy:
            aptconf = tempfile.NamedTemporaryFile()
            aptconf.write('Acquire::http::proxy "%s";' % proxy)
            aptconf.flush()
            self._copyToImage(aptconf.name, "/etc/apt/apt.conf")

        # tzdata is unhappy without that file
        tzone = tempfile.NamedTemporaryFile()
        tzone.write("Europe/Berlin")
        tzone.flush()
        self._copyToImage(tzone.name, "/etc/timezone")

        # create /etc/apt/sources.list
        sources = self.getSourcesListFile()
        self._copyToImage(sources.name, "/etc/apt/sources.list")

        # install some useful stuff
        ret = self._runInImage(["apt-get","update"])
        assert ret == 0
        # FIXME: instead of this retrying (for network errors with 
        #        proxies) we should have a self._runAptInImage() 
        for i in range(3):
            ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",basepkg]+additional_base_pkgs)
        assert ret == 0

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install","--reinstall","-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
                self.stop()
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            print "have PostBootstrapScript: %s" % script
            if os.path.exists(script):
                self._runInImage(["mkdir","/upgrade-tester"])
                self._copyToImage(script, "/upgrade-tester")
                self._copyToImage(glob.glob(os.path.dirname(
                            self.profile)+"/*.cfg"), "/upgrade-tester")
                script_name = os.path.basename(script)
                self._runInImage(["chmod","755",
                                  os.path.join("/upgrade-tester",script_name)])
                print "running script: %s" % script_name
                cmd = os.path.join("/upgrade-tester",script_name)
                ret = self._runInImage(["cd /upgrade-tester; %s" % cmd])
                print "PostBootstrapScript returned: %s" % ret
                assert ret == 0, "PostBootstrapScript returned non-zero"
            else:
                print "WARNING: %s not found" % script

        if self.config.getWithDefault("NonInteractive",
                                      "UpgradeFromDistOnBootstrap", False):
            print "running apt-get upgrade in from dist (after bootstrap)"
            for i in range(3):
                ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","-y","dist-upgrade"])
            assert ret == 0, "dist-upgrade returned %s" % ret

        print "Cleaning image"
        ret = self._runInImage(["apt-get","clean"])
        assert ret == 0, "apt-get clean returned %s" % ret

        # done with the bootstrap
        self.stop()

        # copy cache into place (if needed)
        if (self.config.has_option("KVM","CacheBaseImage") and
            self.config.getboolean("KVM","CacheBaseImage")):
            shutil.copy(self.image, "%s.%s" % (self.image,self.fromDist))
        
        return True

    def saveVMSnapshot(self,name):
        # savevm
        print "savevm"
        self.stop()
        shutil.copy(self.image, self.image+"."+name)
        return
        # *sigh* buggy :/
        #self.qemu_pid.stdin.write("stop\n")
        #self.qemu_pid.stdin.write("savevm %s\n" % name)
        #self.qemu_pid.stdin.write("cont\n")
    def delVMSnapshot(self,name):
        print "delvm"
        self.qemu_pid.stdin.write("delvm %s\n" % name)
    def restoreVMSnapshot(self,name):
        print "restorevm"
        self.stop()
        shutil.copy(self.image+"."+name, self.image)
	return
        # loadvm
        # *sigh* buggy :/
        #self.qemu_pid.stdin.write("stop\n")
        #self.qemu_pid.stdin.write("loadvm %s\n" % name)
        #self.qemu_pid.stdin.write("cont\n")

    def start(self):
        if self.qemu_pid != None:
            print "already runing"
            return True
        # mvo: disabled for now, hardy->lucid does not work well with it
        #      (random hangs)
        #if self.virtio:
        #    drive = ["-drive", "file=%s,if=virtio,boot=on" % self.image]
        #else:
        drive = ["-hda", self.image]
        # build cmd
        cmd = [self.qemu_binary]+drive+self.qemu_options
        print "Starting %s" % cmd
        self.qemu_pid = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        # spin here until ssh has come up and we can login
        now = time.time()
        while True:
            time.sleep(1)
            if self._runInImage(["/bin/true"]) == 0:
                break
            if (time.time() - now) > 900:
                print "Could not start image after 900s, exiting"
                return False
        return True

    def stop(self):
        " we stop because we run with -no-reboot"
        print "stop"
        if self.qemu_pid:
            print "stop pid: ", self.qemu_pid
            self._runInImage(["/sbin/reboot"])
            print "waiting for qemu to shutdown"
            for i in range(600):
                if self.qemu_pid.poll() is not None:
                    print "poll() returned"
                    break
                time.sleep(1)
            else:
                print "Not stopped after 600s, killing "
                try:
                    os.kill(int(self.qemu_pid.pid), 15)
                    time.sleep(10)
                    os.kill(int(self.qemu_pid.pid), 9)
                except Exception, e:
                    print "FAILED to kill %s '%s'" % (self.qemu_pid, e)
            self.qemu_pid = None
            print "qemu stopped"


    def upgrade(self):
        print "upgrade()"

        # clean from any leftover pyc files
        for f in glob.glob("%s/*.pyc" %  self.upgradefilesdir):
            os.unlink(f)

        print "Starting for upgrade"
        if not self.start():
            return False

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
            self._runInImage(["mkdir","-p","/upgrade-tester"])
            self._runInImage(["echo -e '[Sources]\nValidMirrors=/upgrade-tester/new_mirrors.cfg' > /etc/update-manager/release-upgrades.d/new_mirrors.cfg"])
            for entry in sources.list:
                if (not (entry.invalid or entry.disabled) and
                    entry.type == "deb"):
                    print "adding %s to mirrors" % entry.uri
                    self._runInImage(["echo '%s' >> /upgrade-tester/new_mirrors.cfg" % entry.uri])
                    
            # upgrade *before* the regular upgrade runs 
            if self.config.getWithDefault("NonInteractive", "AddRepoUpgradeImmediately", False):
                self._runInImage(["apt-get", "update"])
                self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","-y","dist-upgrade", "--allow-unauthenticated"])

        apt_conf = self.config.getWithDefault("NonInteractive","AddAptConf","")
        if apt_conf:
            apt_conf = os.path.join(os.path.dirname(self.profile), apt_conf)
            self._copyToImage(apt_conf, "/etc/apt/apt.conf.d")

        # check if we have a bzr checkout dir to run against or
        # if we should just run the normal upgrader
        cmd_prefix=[]
        if not self.config.getWithDefault("NonInteractive","ForceOverwrite", False):
            print "Disabling ForceOverwrite"
            cmd_prefix = ["export RELEASE_UPGRADE_NO_FORCE_OVERWRITE=1;"]
        if (os.path.exists(self.upgradefilesdir) and
            self.config.getWithDefault("NonInteractive", 
                                       "UseUpgraderFromBzr", 
                                       True)):
            print "Using ./DistUpgrade/* for the upgrade"
            self._copyUpgraderFilesFromBzrCheckout()
            ret = self._runBzrCheckoutUpgrade(cmd_prefix)
        else:
            print "Using do-release-upgrade for the upgrade"
            ret = self._runInImage(cmd_prefix+["do-release-upgrade","-d",
                                    "-f","DistUpgradeViewNonInteractive"])
        print "dist-upgrade.py returned: %i" % ret

        # copy the result
        print "coyping the result"
        self._copyFromImage("/var/log/dist-upgrade/*",self.resultdir)

        # give the ssh output extra time
        time.sleep(10)

        # stop the machine
        print "Shuting down the VM"
        self.stop()
        return (ret == 0)
        

if __name__ == "__main__":
    
    # FIXME: very rough proof of conecpt, unify with the chroot
    #        and automatic-upgrade code
    # see also /usr/sbin/qemu-make-debian-root
    
    qemu = UpgradeTestBackendQemu(sys.argv[1],".")
    #qemu.bootstrap()
    #qemu.start()
    #qemu._runInImage(["ls","/"])
    #qemu.stop()
    qemu.upgrade()

    # FIXME: now write something into rc.local again and run reboot
    #        and see if we come up with the new kernel
