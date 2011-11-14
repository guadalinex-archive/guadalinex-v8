
import sys
import os
import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)

from UpgradeTestBackend import UpgradeTestBackend

import tempfile
import subprocess
import shutil
import glob
import ConfigParser

class UpgradeTestBackendChroot(UpgradeTestBackend):

    diverts = ["/usr/sbin/mkinitrd",
               "/sbin/modprobe",
               "/usr/sbin/invoke-rc.d",
               # install-info has a locking problem quite often
               "/usr/sbin/install-info",
	       "/sbin/start-stop-daemon"]

    def __init__(self, profile):
        UpgradeTestBackend.__init__(self, profile)
        self.tarball = None

    def _umount(self, chrootdir):
        umount_list = []
        for line in open("/proc/mounts"):
            (dev, mnt, fs, options, d, p) = line.split()
            if mnt.startswith(chrootdir):
                umount_list.append(mnt)
        # now sort and umount by reverse length (to ensure
        # we umount /sys/fs/binfmt_misc before /sys)
        umount_list.sort(key=len)
        umount_list.reverse()
        # do the list
        for mpoint in umount_list:
            print "Umount '%s'" % mpoint
            os.system("umount %s" % mpoint)

            
    def login(self):
        d = self._unpackToTmpdir(self.tarball)
        print "logging into: '%s'" % d
        self._runInChroot(d, ["/bin/sh"])
        print "Cleaning up"
        if d:
            shutil.rmtree(d)

    def _runInChroot(self, chrootdir, command, cmd_options=[]):
        print "runing: ",command
        print "in: ", chrootdir
        pid = os.fork()
        if pid == 0:
            os.chroot(chrootdir)
            os.chdir("/")
            os.system("mount -t devpts devpts /dev/pts")
            os.system("mount -t sysfs sysfs /sys")
            os.system("mount -t proc proc /proc")
            os.system("mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc")
            env = os.environ
            env["DEBIAN_FRONTEND"] = "noninteractive"
            os.execve(command[0], command, env)
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            self._umount(chrootdir)
            return exitstatus

    def _runApt(self, tmpdir, command, cmd_options=[]):
        ret = self._runInChroot(tmpdir,
                                ["/usr/bin/apt-get", command]+self.apt_options+cmd_options)
        return ret


    def installPackages(self, pkgs):
        print "installPackages: ", pkgs
        if not pkgs:
            return True
        res = self._runApt(self.tmpdir, "install", pkgs)
        return res == 0

    def _tryRandomPkgInstall(self, amount):
        " install 'amount' packages randomly "
        self._runApt(self.tmpdir,"install",["python2.4-apt", "python-apt"])
        shutil.copy("%s/randomInst.py",self.tmpdir+"/tmp")
        ret = subprocess.call(["chroot",self.tmpdir,"/tmp/randomInst.py","%s" % amount])
        print ret

    def _cacheDebs(self, tmpdir):
        # see if the debs should be cached
        if self.cachedir:
            print "Caching debs"
            for f in glob.glob(tmpdir+"/var/cache/apt/archives/*.deb"):
                if not os.path.exists(self.cachedir+"/"+os.path.basename(f)):
                    try:
                        shutil.copy(f,self.cachedir)
                    except IOError, e:
                        print "Can't copy '%s' (%s)" % (f,e)

    def _getTmpDir(self):
        tmpdir = self.config.getWithDefault("CHROOT","Tempdir",None)
        if tmpdir is None:
            tmpdir = tempfile.mkdtemp()
        else:
            if os.path.exists(tmpdir):
                self._umount(tmpdir)
                shutil.rmtree(tmpdir)
            os.makedirs(tmpdir)
        return tmpdir
    
    def bootstrap(self,outfile=None):
        " bootstaps a pristine fromDist tarball"
        if not outfile:
            outfile = os.path.dirname(self.profile) + "/dist-upgrade-%s.tar.gz" % self.fromDist
        outfile = os.path.abspath(outfile)
        self.tarball = outfile

        # don't bootstrap twice if this is something we can cache
        try:
            if (self.config.getboolean("CHROOT","CacheTarball") and
                os.path.exists(self.tarball) ):
                self.tmpdir = self._unpackToTmpdir(self.tarball)
                if not self.tmpdir:
                    print "Error extracting tarball"
                    return False
                return True
        except ConfigParser.NoOptionError:
            pass
        
        # bootstrap!
        self.tmpdir = tmpdir = self._getTmpDir()
        print "tmpdir is %s" % tmpdir

        print "bootstraping to %s" % outfile
        ret = subprocess.call(["debootstrap", self.fromDist, tmpdir, self.config.get("NonInteractive","Mirror")])
        print "debootstrap returned: %s" % ret
        if ret != 0:
            return False

        print "diverting"
        self._dpkgDivert(tmpdir)

        # create some minimal device node
        print "Creating some devices"
        os.system("(cd %s/dev ; echo $PWD; ./MAKEDEV null)" % tmpdir)
        #self._runInChroot(tmpdir, ["/bin/mknod","/dev/null","c","1","3"])

        # set a hostname
        shutil.copy("/etc/hostname","%s/etc/hostanme" % tmpdir)

        # copy the stuff from toChroot/
        if os.path.exists("./toChroot/"):
            os.chdir("toChroot/")
            for (dirpath, dirnames, filenames) in os.walk("."):
                for name in filenames:
                    if not os.path.exists(os.path.join(tmpdir,dirpath,name)):
                        shutil.copy(os.path.join(dirpath,name), os.path.join(tmpdir,dirpath,name))
            os.chdir("..")

        # write new sources.list
        if (self.config.has_option("NonInteractive","Components") and
            self.config.has_option("NonInteractive","Pockets")):
            sourcelist=self.getSourcesListFile()
            shutil.copy(sourcelist.name, tmpdir+"/etc/apt/sources.list")
            print open(tmpdir+"/etc/apt/sources.list","r").read()

        # move the cache debs
        self._populateWithCachedDebs(tmpdir)
                
        print "Updating the chroot"
        ret = self._runApt(tmpdir,"update")
        print "apt update returned %s" % ret
        if ret != 0:
            return False
        # run it three times to work around network issues
        for i in range(3):
            ret = self._runApt(tmpdir,"dist-upgrade")
        print "apt dist-upgrade returned %s" % ret
        if ret != 0:
            return False

        print "installing basepkg"
        ret = self._runApt(tmpdir,"install", [self.config.get("NonInteractive","BasePkg")])
        print "apt returned %s" % ret
        if ret != 0:
            return False

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runApt(tmpdir,"install",pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                self._cacheDebs(tmpdir)
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            if os.path.exists(script):
                shutil.copy(script, os.path.join(tmpdir,"tmp"))
                self._runInChroot(tmpdir,[os.path.join("/tmp",script)])
            else:
                print "WARNING: %s not found" % script

        try:
            amount = self.config.get("NonInteractive","RandomPkgInstall")
            self._tryRandomPkgInstall(amount)
        except ConfigParser.NoOptionError:
            pass

        print "Caching debs"
        self._cacheDebs(tmpdir)

        print "Cleaning chroot"
        ret = self._runApt(tmpdir,"clean")
        if ret != 0:
            return False

        print "building tarball: '%s'" % outfile
        os.chdir(tmpdir)
        ret = subprocess.call(["tar","czf",outfile,"."])
        print "tar returned %s" % ret

        return True

    def _populateWithCachedDebs(self, tmpdir):
        # now populate with hardlinks for the debs
        if self.cachedir:
            print "Linking cached debs into chroot"
            for f in glob.glob(self.cachedir+"/*.deb"):
                try:
                    os.link(f, tmpdir+"/var/cache/apt/archives/%s"  % os.path.basename(f))
                except OSError, e:
                    print "Can't link: %s (%s)" % (f,e)
        return True

    def upgrade(self, tarball=None):
        if not tarball:
            tarball = self.tarball
        assert(tarball != None)
        print "runing upgrade on: %s" % tarball
        tmpdir = self.tmpdir
        #self._runApt(tmpdir, "install",["apache2"])

        self._populateWithCachedDebs(tmpdir)
        
        # copy itself to the chroot (resolve symlinks)
        targettmpdir = os.path.join(tmpdir,"tmp","dist-upgrade")
        if not os.path.exists(targettmpdir):
            os.makedirs(targettmpdir)
        for f in glob.glob("%s/*" %  self.upgradefilesdir):
            if not os.path.isdir(f):
                shutil.copy(f, targettmpdir)
                
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to '%s' " % (self.profile,targettmpdir)
            shutil.copy(self.profile, targettmpdir)
        # copy the .cfg and .list stuff from there too
        for f in glob.glob("%s/*.cfg" % (os.path.dirname(self.profile))):
            shutil.copy(f, targettmpdir)
        for f in glob.glob("%s/*.list" % (os.path.dirname(self.profile))):
            shutil.copy(f, targettmpdir)
            
        # run it
        pid = os.fork()
        if pid == 0:
            os.chroot(tmpdir)
            os.chdir("/tmp/dist-upgrade")
            os.system("mount -t devpts devpts /dev/pts")
            os.system("mount -t sysfs sysfs /sys")
            os.system("mount -t proc proc /proc")
            os.system("mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc")
            if os.path.exists("/tmp/dist-upgrade/dist-upgrade.py"):
                os.execl("/tmp/dist-upgrade/dist-upgrade.py",
                         "/tmp/dist-upgrade/dist-upgrade.py")
            else:
                os.execl("/usr/bin/do-release-upgrade",
                         "/usr/bin/do-release-upgrade","-d",
                         "-f","DistUpgradeViewNonInteractive")
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            print "Child exited (%s, %s): %s" % (id, exitstatus, os.WEXITSTATUS(exitstatus))
            # copy the result
            for f in glob.glob(tmpdir+"/var/log/dist-upgrade/*"):
                print "copying result to: ", self.resultdir
                shutil.copy(f, self.resultdir)
            # cache debs and cleanup
            self._cacheDebs(tmpdir)
            self._umount(tmpdir)
            shutil.rmtree(tmpdir)
            return (exitstatus == 0)

    def _unpackToTmpdir(self, baseTarBall):
        # unpack the tarball
        self.tmpdir = tmpdir = self._getTmpDir()
        os.chdir(tmpdir)
        ret = subprocess.call(["tar","xzf",baseTarBall])
        if ret != 0:
            return None
        return tmpdir

    def _dpkgDivert(self, tmpdir):
        for d in self.diverts:
            cmd = ["chroot",tmpdir,
                   "dpkg-divert","--add","--local",
                   "--divert",d+".thereal",
                   "--rename",d]
            ret = subprocess.call(cmd)
            if ret != 0:
                print "dpkg-divert returned: %s" % ret
            shutil.copy(tmpdir+"/bin/true",tmpdir+d)

    def test(self):
        # FIXME: add some sanity testing here
        return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        profilename = sys.argv[1]
    else:
	profilename = "default"
    chroot = UpgradeTestBackendChroot(profilename)
    tarball = "%s/tarball/dist-upgrade-%s.tar.gz" % (os.getcwd(),profilename)
    if not os.path.exists(tarball):
        print "No existing tarball found, creating a new one"
        chroot.bootstrap(tarball)
    chroot.upgrade(tarball)

    #tmpdir = chroot._unpackToTmpdir(tarball)
    #chroot._dpkgDivert(tmpdir)
    #print tmpdir
