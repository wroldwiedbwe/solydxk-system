#! /usr/bin/env python3

# http://wiki.debian.org/plymouth
# https://wiki.ubuntu.com/Plymouth

import re
import threading
import os
from os.path import exists, isfile
from utils import getoutput, shell_exec, str_to_nr, get_package_version
from grub import Grub
from shutil import which

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')

# Handles general plymouth functions
class Plymouth():
    def __init__(self, loggerObject=None):
        self.log = loggerObject
        self.grub = Grub(self.log)
        self.boot = self.grub.getConfig()
        self.avlThemesSearchstr = '^plymouth-theme'
        self.setThemePath = which('plymouth-set-default-theme')
        self.modulesPath = '/etc/initramfs-tools/modules'
        self.grubcfg = '/boot/grub/grub.cfg'

    # Get a list of installed Plymouth themes
    def getInstalledThemes(self):
        instThemes = []
        try:
            if isfile(self.setThemePath):
                cmd = '%s --list' % self.setThemePath
                instThemes = getoutput(cmd)
        except:
            pass
        return instThemes
        
    def is_plymouth_booted(self):
        cmdline = getoutput("cat /proc/cmdline")[0]
        if ' splash' in cmdline:
            return True
        else:
            # It could be that the user manually removed splash in Grub when booting
            # Check grub.cfg
            matchObj = re.search('\/.*=[0-9a-z\-]+', cmdline)
            if matchObj:
                if exists(self.grubcfg):
                    grubcfg_splash = getoutput('grep "{}" "{}" | grep " splash"'.format(matchObj.group(0), self.grubcfg))[0]
                    if grubcfg_splash:
                        return True
        return False

    # Get the currently used Plymouth theme
    def getCurrentTheme(self):
        try:
            if isfile(self.setThemePath) and \
               self.is_plymouth_booted():
                    return getoutput(self.setThemePath)[0]
        except:
            pass
        return ''

    # Get a list of Plymouth themes in the repositories that can be installed
    def getAvailableThemes(self):
        cmd = 'apt-cache pkgnames {}'.format(self.avlThemesSearchstr)
        availableThemes = getoutput(cmd)
        avlThemes = []

        for line in availableThemes:
            matchObj = re.search('%s-([a-zA-Z0-9-]*)' % self.avlThemesSearchstr, line)
            if matchObj:
                theme = matchObj.group(1)
                if not 'all' in theme:
                    avlThemes.append(theme)

        return avlThemes

    def previewPlymouth(self):
        try:
            cmd = "su -c 'plymouthd; plymouth --show-splash ; for ((I=0; I<10; I++)); do plymouth --update=test$I ; sleep 1; done; plymouth quit'"
            shell_exec(cmd)
        except Exception as detail:
            self.write_log(detail, 'exception')

    # Get the package name that can be uninstalled of a given Plymouth theme
    def getRemovablePackageName(self, theme):
        cmd = 'dpkg -S %s.plymouth' % theme
        package = None
        packageNames = getoutput(cmd)

        for line in packageNames:
            if self.avlThemesSearchstr in line:
                matchObj = re.search('(^.*):', line)
                if matchObj:
                    package = matchObj.group(1)
                    break
        self.write_log("Package found %(pck)s" % { "pck": package })
        return package

    # Get valid package name of a Plymouth theme (does not have to exist in the repositories)
    def getPackageName(self, theme):
        return self.avlThemesSearchstr + "-" + theme

    # Get current Plymouth resolution
    def getCurrentResolution(self):
        lines = []
        res = self.grub.getCurrentResolution()

        # The Wheezy way of configuring
        if res is None:
            with open(self.modulesPath, 'r') as f:
                lines = f.readlines()
            for line in lines:
                matchObj = re.search('^uvesafb\s+mode_option\s*=\s*([0-9x]+)', line)
                if matchObj:
                    res = matchObj.group(1)
                    self.write_log("Current Plymouth resolution: %(res)s" % { "res": res })
                    break

        # Old way of configuring Plymouth
        if res is None:
            if self.boot is not None:
                with open(self.boot, 'r') as f:
                    lines = f.readlines()
                for line in lines:
                    # Search text for resolution
                    matchObj = re.search('^GRUB_GFXPAYLOAD_LINUX\s*=[\s"]*([0-9]+x[0-9]+)', line)
                    if matchObj:
                        res = matchObj.group(1)
                        self.write_log("Current Plymouth resolution: %(res)s" % { "res": res })
                        break
            else:
                self.write_log(_("Neither grub nor burg found in /etc/default"), 'warning')
        return res
        
    def write_log(self, message, level='debug'):
        if self.log is not None:
            self.log.write(message, 'Plymouth', level)


# Handles plymouth saving (threaded)
class PlymouthSave(threading.Thread):
    def __init__(self, theme=None, resolution=None, queue=None, loggerObject=None):
        threading.Thread.__init__(self)
        self.log = loggerObject
        self.grub = Grub(self.log)
        self.boot = self.grub.getConfig()
        self.theme = None
        self.resolution = None
        self.queue = queue
        self.modulesPath = '/etc/initramfs-tools/modules'
        self.setThemePath = which('plymouth-set-default-theme')
        self.plymouth = Plymouth(self.log)
        self.installedThemes = self.plymouth.getInstalledThemes()
        if theme in self.installedThemes and resolution is not None:
            self.write_log("Set theme: {0} ({1})".format(theme, resolution))
            self.theme = theme
            self.resolution = resolution
            
        # Steps
        self.max_steps = 6
        self.current_step = 0

    # Save given theme and resolution
    def run(self):
        if self.setThemePath is None:
            self.write_log('Plymouth not installed - exiting', 'warning')
            return
            
        try:
            if not exists(self.modulesPath):
                shell_exec("touch {}".format(self.modulesPath))

            # Cleanup first
            self.queue_progress()
            shell_exec("sed -i -e 's/^ *//; s/ *$//' %s" % self.modulesPath)    # Trim all lines
            shell_exec("sed -i -e '/^.*KMS$/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^intel_agp$/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^drm$/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^nouveau modeset.*/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^radeon modeset.*/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^i915 modeset.*/d' %s" % self.modulesPath)
            shell_exec("sed -i -e '/^uvesafb\s*mode_option.*/d' %s" % self.modulesPath)
            if self.boot is not None:
                shell_exec("sed -i -e '/^GRUB_GFXPAYLOAD_LINUX.*/d' %s" % self.boot)
            splashFile = '/etc/initramfs-tools/conf.d/splash'
            if exists(splashFile):
                os.remove(splashFile)

            # Set/Unset splash
            self.queue_progress()
            if self.boot is not None:
                cmd = "sed -i -e 's/\s*[a-z]*splash//' {}".format(self.boot)
                shell_exec(cmd)
                if self.theme is None:
                    self.write_log("Set nosplash")
                    cmd = "sed -i -e '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/\"$/ nosplash\"/' {}".format(self.boot)
                    shell_exec(cmd)
                    # Comment the GRUB_GFXMODE line if needed
                    cmd = "sed -i '/GRUB_GFXMODE=/s/^/#/' %s" % self.boot
                    shell_exec(cmd)
                else:
                    self.write_log("Set splash")
                    cmd = "sed -i -e '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/\"$/ splash\"/' {}".format(self.boot)
                    shell_exec(cmd)
                    # Set resolution
                    if self.resolution is not None:
                        self.write_log("GRUB_GFXMODE={}".format(self.resolution))
                        cmd = "sed -i -e '/GRUB_GFXMODE=/ c GRUB_GFXMODE={0}' {1}".format(self.resolution, self.boot)
                        shell_exec(cmd)

            # Only for plymouth version older than 9
            self.queue_progress()
            if self.theme is not None and self.resolution is not None:
                plymouthVersion = str_to_nr(get_package_version("plymouth").replace('.', '')[0:2], True)
                self.write_log("plymouthVersion={}".format(plymouthVersion))
                if plymouthVersion < 9:
                    # Write uvesafb command to modules file
                    self.write_log("> Use uvesafb to configure Plymouth")
                    line = "\nuvesafb mode_option=%s-24 mtrr=3 scroll=ywrap\ndrm\n" % self.resolution
                    with open(self.modulesPath, 'a') as f:
                        f.write(line)

                    # Use framebuffer
                    line = "FRAMEBUFFER=y"
                    with open('/etc/initramfs-tools/conf.d/splash', 'w') as f:
                        f.write(line)

            if self.boot is not None:
                # Read grub for debugging purposes
                with open(self.boot, 'r') as f:
                    content = f.read()
                    self.write_log("\nNew grub:\n{}\n".format(content))

                # Update grub
                self.queue_progress()
                if 'grub' in self.boot:
                    shell_exec('update-grub')
                else:
                    shell_exec('update-burg')

            # Set the theme and update initramfs
            self.queue_progress()
            if self.theme is not None:
                shell_exec("{0} -R {1}".format(self.setThemePath, self.theme))

        except Exception as detail:
            self.write_log(detail, 'exception')
            
    def queue_progress(self):
        self.current_step += 1
        if self.current_step > self.max_steps:
            self.current_step = self.max_steps
        if self.queue is not None:
            #print((">> step %d of %d" % (self.current_step, self.max_steps)))
            self.queue.put([self.max_steps, self.current_step])
            
    def write_log(self, message, level='debug'):
        if self.log is not None:
            self.log.write(message, 'PlymouthSave', level)
