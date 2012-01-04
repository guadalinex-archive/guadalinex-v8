
import commands
VERSION='2.0.7debian7'
CODENAME=commands.getoutput("lsb_release -s -c")
DISTRO=commands.getoutput("lsb_release -s -i")
RELEASE=commands.getoutput("lsb_release -s -r")
