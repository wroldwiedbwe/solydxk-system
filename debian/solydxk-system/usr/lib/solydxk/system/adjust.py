#! /usr/bin/env python3

import os
from os.path import exists, splitext, dirname, isdir, basename
import subprocess
import filecmp
from time import strftime
from adjust_sources import Sources

# Prepare the log file
global logfile
logfile = open("/var/log/solydxk-system.log", "w")


# Convert string to number
def strToNumber(stringnr, toInt=False):
    nr = 0
    stringnr = stringnr.strip()
    try:
        if toInt:
            nr = int(stringnr)
        else:
            nr = float(stringnr)
    except ValueError:
        nr = 0
    return nr


# --force-yes is deprecated in stretch
force = '--force-yes'
ver = strToNumber(subprocess.getoutput("head -n 1 /etc/debian_version | sed 's/[a-zA-Z]/0/' 2>/dev/null || echo 0"))
if ver == 0 or ver >= 9:
    force = '--allow-downgrades --allow-remove-essential --allow-change-held-packages'
force = "%s --assume-yes -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold" % force


def getAptCacheLockedProgram():
    aptPackages = ["dpkg", "apt-get", "synaptic", "adept", "adept-notifier"]
    procLst = subprocess.getoutput("ps -U root -u root -o comm=")
    for aptProc in aptPackages:
        if aptProc in procLst:
            return aptProc
    return ''


def getPackageVersion(package, candidate=False):
    cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Installed:\"'" % package
    if candidate:
        cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Candidate:\"'" % package
    lst = subprocess.getoutput(cmd).strip().split(' ')
    version = lst[-1]
    if 'none' in version:
        version = ''
    return version


# Fix some programs [package, what to fix, options, exec from version (0 = all)]
fix_progs = [['apache2', '/var/log/apache2', 'root:adm', 0],
             ['mysql-client', '/var/log/mysql', 'mysql:adm', 0],
             ['clamav', '/var/log/clamav', 'clamav:clamav', 0],
             ['solydk-info-8', 'solydk-info', 'purge', 0],
             ['solydx-info-8', 'solydx-info', 'purge', 0],
             ['solydk-info-9', 'solydkee-info', 'purge', 0],
             ['solydx-info-9', 'solydxee-info', 'purge', 0],
             ['solydx-info-8', 'solydx-info-9', 'install', 9],
             ['solydk-info-8', 'solydk-info-9', 'install', 9],
             ['solydk-system-adjustments-8', 'solydk-system-adjustments', 'purge', 0],
             ['solydx-system-adjustments-8', 'solydx-system-adjustments', 'purge', 0],
             ['solydk-system-adjustments-9', 'solydk-system-adjustments', 'purge', 0],
             ['solydx-system-adjustments-9', 'solydx-system-adjustments', 'purge', 0],
             ['firefox-solydxk-adjustments', 'firefox-esr-solydxk-adjustments', 'purge', 0]]


for prog in fix_progs:
    if ver >= prog[3] or prog[3] == 0:
        if getPackageVersion(prog[0]) != '':
            if prog[2] == 'purge' or prog[2] == 'install':
                if getAptCacheLockedProgram() == '':
                    os.system("apt-get %s %s %s" % (prog[2], force, prog[1]))
            elif ':' in prog[2] and not isdir(prog[1]):
                os.system("mkdir -p %s" % prog[1])
                os.system("chown %s %s" % (prog[2], prog[1]))


def log(string):
    logfile.writelines("%s - %s\n" % (strftime("%Y-%m-%d %H:%M:%S"), string))
    logfile.flush()


def stringExistsInFile(filePath, searchString):
    if exists(filePath):
        with open(filePath, 'r') as f:
            txt = f.read()
        if searchString in txt:
            return True
    return False


def canCopy(file1, file2):
    ret = False
    if exists(file1):
        if exists(file2):
            if not filecmp.cmp(file1, file2):
                ret = True
        else:
            if "desktop" not in splitext(file2)[1]:
                if exists(dirname(file2)):
                    ret = True
    return ret


log("solydxk-system started")


try:
    adjustment_directory = "/usr/share/solydxk/system-adjustments/"
    array_preserves = []
    overwrites = {}
    links = {}

    # Perform file execution adjustments
    for filename in sorted(os.listdir(adjustment_directory)):
        bn, extension = splitext(filename)
        if extension == ".execute":
            full_path = adjustment_directory + "/" + filename
            os.system("chmod a+rx %s" % full_path)
            os.system(full_path)
            log("%s executed" % full_path)
        elif extension == ".preserve":
            filehandle = open(adjustment_directory + "/" + filename)
            for line in filehandle:
                line = line.strip()
                array_preserves.append(line)
            filehandle.close()
        elif extension == ".overwrite":
            filehandle = open(adjustment_directory + "/" + filename)
            for line in filehandle:
                line = line.strip()
                line_items = line.split()
                if len(line_items) == 2:
                    source, destination = line.split()
                    if destination not in array_preserves:
                        overwrites[destination] = source
            filehandle.close()
        elif extension == ".link":
            filehandle = open(adjustment_directory + "/" + filename)
            for line in filehandle:
                line = line.strip()
                line_items = line.split()
                if len(line_items) == 2:
                    link, destination = line.split()
                    if destination not in array_preserves:
                        links[destination] = link
            filehandle.close()

    # Perform file overwriting adjustments
    for key in list(links.keys()):
        link = links[key]
        destination = key
        os.system("ln -sf " + destination + " " + link)
        log("link " + link + " created to " + destination)

    # Perform file overwriting adjustments
    for key in list(overwrites.keys()):
        source = overwrites[key]
        destination = key
        if exists(source):
            if not "*" in destination:
                # Simple destination, do a cp
                if canCopy(source, destination):
                    os.system("cp " + source + " " + destination)
                    log(destination + " overwritten with " + source)
            else:
                # Wildcard destination, find all possible matching destinations
                matching_destinations = subprocess.getoutput("find " + destination)
                matching_destinations = matching_destinations.split("\n")
                for matching_destination in matching_destinations:
                    matching_destination = matching_destination.strip()
                    if canCopy(source, matching_destination):
                        os.system("cp " + source + " " + matching_destination)
                        log(matching_destination + " overwritten with " + source)

    # Restore LSB information
    distribId = subprocess.getoutput("grep DISTRIB_ID /usr/share/solydxk/info").strip()
    if not stringExistsInFile("/etc/lsb-release", distribId):
        with open("/etc/lsb-release", "w") as f:
            f.writelines(distribId + "\n")
            f.writelines("DISTRIB_" + subprocess.getoutput("grep \"RELEASE=\" /usr/share/solydxk/info") + "\n")
            f.writelines("DISTRIB_" + subprocess.getoutput("grep CODENAME /usr/share/solydxk/info") + "\n")
            f.writelines("DISTRIB_" + subprocess.getoutput("grep DESCRIPTION /usr/share/solydxk/info") + "\n")
        log("/etc/lsb-release overwritten")

    # Restore /etc/issue and /etc/issue.net
    issue = subprocess.getoutput("grep DESCRIPTION /usr/share/solydxk/info").replace("DESCRIPTION=", "").replace("\"", "")
    if not stringExistsInFile("/etc/issue", issue):
        with open("/etc/issue", "w") as f:
            f.writelines(issue + " \\n \\l\n")
        log("/etc/issue overwritten")
    if not stringExistsInFile("/etc/issue.net", issue):
        with open("/etc/issue.net", "w") as f:
            f.writelines(issue)
        log("/etc/issue.net overwritten")

    # Force prompt colors in bashrc
    bashrc = '/etc/skel/.bashrc'
    if exists(bashrc):
        os.system("sed -i 's/#\s*force_color_prompt=yes/force_color_prompt=yes/' %s" % bashrc)
        os.system("sed -i 's/;32m/;34m/' %s" % bashrc)
        os.system("sed -i 's/#\s*alias\s/alias /g' %s" % bashrc)

    # Check start menu favorite for either Firefox ESR or Firefox
    ff = subprocess.getoutput("which firefox-esr")
    if ff == "":
        ff = subprocess.getoutput("which firefox")
    if exists(ff):
        dt = "%s.desktop" % basename(ff)
        configs = ["/usr/share/solydxk/default-settings/kde4-profile/default/share/config/kickoffrc",
                   "/etc/xdg/kickoffrc",
                   "/etc/skel/.config/xfce4/panel/whiskermenu-9.rc"]
        for config in configs:
            if exists(config):
                if not stringExistsInFile(config, dt):
                    os.system("sed -i -e 's/firefox[a-z-]*.desktop/%s/' %s" % (dt, config))

    # Add live menus in grub when needed
    grubsh = "/etc/grub.d/10_linux"
    livesh = "/usr/lib/solydxk/grub/boot-isos.sh"
    if exists(grubsh) and exists(livesh):
        if not stringExistsInFile(grubsh, livesh):
            escPath = livesh.replace('/', '\/')
            os.system("sed -i \"s/echo '}'/if [ -e %s ]; then \/bin\/bash %s; fi; echo '}'/\" %s" % (escPath, escPath, grubsh))

    # Make sure sources.list is correct
    sources = Sources()
    sources.check()

    # Update cache
    os.system("update-desktop-database -q")
    # Recreate pixbuf cache
    pix_cache = '/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
    if not exists(pix_cache):
        pix_cache = '/usr/lib/i386-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
    if exists(pix_cache):
        os.system("%s --update-cache" % pix_cache)

    # When on Raspbian
    raspi_config = '/usr/bin/raspi-config'
    if exists(raspi_config):
        os.system("sed -i 's/ pi / solydxk /g' %s" % raspi_config)
        os.system("sed -i 's/(pi)/(solydxk)/g' %s" % raspi_config)
        os.system("sed -i 's/=pi/=solydxk/g' %s" % raspi_config)
        with open(raspi_config, 'r') as f:
            if not '/boot/firmware' in f.read():
                os.system("sed -i 's/\/boot/\/boot\/firmware/g' %s" % raspi_config)

except Exception as detail:
    print(detail)
    log(detail)

log("solydxk-system stopped")
logfile.close()
