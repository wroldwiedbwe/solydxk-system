#! /usr/bin/env python3

import os
from os.path import exists, splitext, dirname, isdir, basename, join
from adjust_sources import Sources
from logger import Logger
from utils import getoutput,  get_apt_force,  get_package_version,  \
                             get_apt_cache_locked_program,  has_string_in_file,  \
                             get_debian_version,  can_copy

# Init logging
log_file = "/var/log/solydxk-system.log"
log = Logger(log_file, addLogTime=True, maxSizeKB=5120)
log.write('=====================================', 'adjust')
log.write(">>> Start SolydXK Adjustment <<<", 'adjust')
log.write('=====================================', 'adjust')


# --force-yes is deprecated in stretch
force = get_apt_force()
#force += " --assume-yes -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"


# Fix some programs [package, what to fix, options, exec from version (0 = all)]
fix_progs = [['apache2', '/var/log/apache2', 'root:adm', 0],
             ['mysql-client', '/var/log/mysql', 'mysql:adm', 0],
             ['clamav', '/var/log/clamav', 'clamav:clamav', 0],
             ['lightdm', '/var/lib/lightdm/data', 'lightdm:lightdm', 0],
             ['v86d', 'v86d', 'purge', 0],
             ['usb-creator', 'solydxk-usb-creator', 'purge', 0],
             ['solydk-system-adjustments-8', 'solydk-system-adjustments', 'purge', 0],
             ['solydx-system-adjustments-8', 'solydx-system-adjustments', 'purge', 0],
             ['solydk-system-adjustments-9', 'solydk-system-adjustments', 'purge', 0],
             ['solydx-system-adjustments-9', 'solydx-system-adjustments', 'purge', 0],
             ['firefox-solydxk-adjustments', 'firefox-esr-solydxk-adjustments', 'purge', 0]]
             
gtk_deprecated_properties = ['child-displacement', 
                             'scrollbars-within-bevel', 
                             'indicator-size', 
                             'GtkExpander-expander-size', 
                             'shadow-type']

ver = get_debian_version()
for prog in fix_progs:
    if ver >= prog[3] or prog[3] == 0:
        if get_package_version(prog[0]) != '':
            if prog[2] == 'purge' or prog[2] == 'install':
                if get_apt_cache_locked_program() == '':
                    os.system("apt-get %s %s %s" % (prog[2], force, prog[1]))
            elif ':' in prog[2] and not isdir(prog[1]):
                os.system("mkdir -p %s" % prog[1])
                os.system("chown %s %s" % (prog[2], prog[1]))


try:
    adjustment_directory = "/usr/share/solydxk/system-adjustments/"
    array_preserves = []
    overwrites = {}

    # Perform file execution adjustments
    for filename in sorted(os.listdir(adjustment_directory)):
        full_path = adjustment_directory + filename
        bn, extension = splitext(filename)
        if extension == ".execute":
            log.write("> Execute: %s" % full_path,  'execute')
            os.system("chmod a+rx %s" % full_path)
            os.system(full_path)
        elif extension == ".preserve":
            log.write("> Preserve: %s" % full_path,  'preserve')
            filehandle = open(full_path)
            for line in filehandle:
                line = line.strip()
                array_preserves.append(line)
            filehandle.close()
        elif extension == ".overwrite":
            log.write("> Overwrite: %s" % full_path,  'overwrite')
            filehandle = open(full_path)
            for line in filehandle:
                line = line.strip()
                line_items = line.split()
                if len(line_items) == 2:
                    source, destination = line.split()
                    if destination not in array_preserves:
                        overwrites[destination] = source
            filehandle.close()
            # Perform file overwriting adjustments
            for key in list(overwrites.keys()):
                source = overwrites[key]
                destination = key
                if exists(source):
                    if not "*" in destination:
                        # Simple destination, do a cp
                        if can_copy(source, destination):
                            os.system("cp " + source + " " + destination)
                            log.write("%s overwritten with %s" % (destination,  source),  'overwrite')
                    else:
                        # Wildcard destination, find all possible matching destinations
                        matching_destinations = getoutput("find " + destination)
                        matching_destinations = matching_destinations.split("\n")
                        for matching_destination in matching_destinations:
                            matching_destination = matching_destination.strip()
                            if can_copy(source, matching_destination):
                                os.system("cp " + source + " " + matching_destination)
                                log.write("%s overwritten with %s" % (matching_destination,  source),  'overwrite')
        elif extension == ".link":
            log.write("> Link: %s" % full_path)
            filehandle = open(full_path)
            for line in filehandle:
                line = line.strip()
                line_items = line.split()
                if len(line_items) == 2:
                    link, destination = line.split()
                    if destination not in array_preserves and \
                       exists(dirname(link)) and \
                       exists(destination):
                        os.system("ln -sf %s %s" % (destination ,  link))
                        log.write("link %s created to %s" % (link,  destination),  'link')

    # Restore LSB information
    codename = getoutput("grep CODENAME /usr/share/solydxk/info")[0].strip()
    if not has_string_in_file(codename, "/etc/lsb-release"):
        with open("/etc/lsb-release", "w") as f:
            f.writelines(getoutput("grep DISTRIB_ID /usr/share/solydxk/info")[0].strip() + "\n")
            f.writelines("DISTRIB_" + getoutput("grep \"RELEASE=\" /usr/share/solydxk/info")[0].strip() + "\n")
            f.writelines("DISTRIB_" + codename + "\n")
            f.writelines("DISTRIB_" + getoutput("grep DESCRIPTION /usr/share/solydxk/info")[0].strip() + "\n")
        log.write("/etc/lsb-release overwritten",  'lsb-release')

    # Restore /etc/issue and /etc/issue.net
    issue = getoutput("grep DESCRIPTION /usr/share/solydxk/info")[0].replace("DESCRIPTION=", "").replace("\"", "")
    if not has_string_in_file(issue, "/etc/issue"):
        with open("/etc/issue", "w") as f:
            f.writelines(issue + " \\n \\l\n")
        log.write("/etc/issue overwritten",  'issue')
    if not has_string_in_file(issue, "/etc/issue.net"):
        with open("/etc/issue.net", "w") as f:
            f.writelines(issue)
        log.write("/etc/issue.net overwritten",  'issue')

    # Force prompt colors in bashrc
    bashrc = '/etc/skel/.bashrc'
    if exists(bashrc):
        os.system("sed -i 's/#\s*force_color_prompt=.*/force_color_prompt=yes/' %s" % bashrc)
        os.system("sed -i 's/;31m/;34m/' %s" % bashrc)
        os.system("sed -i 's/;32m/;34m/' %s" % bashrc)
        os.system("sed -i 's/#\s*alias\s/alias /g' %s" % bashrc)
        if not has_string_in_file("/usr/share/solydxk/info",  bashrc):
            with open(bashrc, 'a') as f:
                f.write("\n# Source the SolydXK info file\n"
                        "if [ -f /usr/share/solydxk/info ]; then\n"
                        "  . /usr/share/solydxk/info\n"
                        "fi\n")
        log.write("%s adapted" % bashrc,  'bashrc')

    # Check start menu favorite for either Firefox ESR or Firefox
    ff = getoutput("which firefox-esr")[0]
    if ff == "":
        ff = getoutput("which firefox")[0]
    if exists(ff):
        dt = "%s.desktop" % basename(ff)
        configs = ["/usr/share/solydxk/default-settings/kde4-profile/default/share/config/kickoffrc",
                   "/etc/xdg/kickoffrc",
                   "/etc/skel/.config/xfce4/panel/whiskermenu-9.rc",
                   "/usr/share/plasma/look-and-feel/org.kde.solydk.desktop/contents/layouts/org.kde.plasma.desktop.defaultPanel/contents/layout.js",
                   "/usr/share/plasma/look-and-feel/org.kde.solydk-dark.desktop/contents/layouts/org.kde.plasma.desktop.defaultPanel/contents/layout.js",
                   "/usr/share/solydxk/default-settings/plasma5-profile/kickoffrc"]
        for config in configs:
            if exists(config):
                if not has_string_in_file(dt,  config):
                    os.system("sed -i -e 's/firefox[a-z-]*.desktop/%s/' %s" % (dt, config))
        log.write("Firefox configuration adapted",  'firefox')

    # Add live menus in grub when needed
    grubsh = "/etc/grub.d/10_linux"
    livesh = "/usr/lib/solydxk/grub/boot-isos.sh"
    if exists(grubsh) and exists(livesh):
        if not has_string_in_file(livesh,  grubsh):
            escPath = livesh.replace('/', '\/')
            os.system("sed -i \"s/echo '}'/if [ -e %s ]; then \/bin\/bash %s; fi; echo '}'/\" %s" % (escPath, escPath, grubsh))
            log.write("%s adapted for live boot menu" % grubsh,  'boot-isos')
        
    # Fix gpg
    if exists('/etc/apt/trusted.gpg'):
        os.system('/bin/bash /usr/lib/solydxk/scripts/fix-gpg.sh')

    # Fix device notifiers for Plasma 5
    actions_k4 = '/usr/share/kde4/apps/solid/actions/'
    actions_p5 = '/usr/share/solid/actions/'
    if exists(actions_k4) and exists(actions_p5):
        for fle in os.listdir(actions_k4):
            if fle.endswith(".desktop"):
                link = join(actions_k4, fle)
                destination = join(actions_p5, fle)
                if not exists(destination):
                    os.system("ln -s %s %s" % (link, destination))
                    log.write("link %s created to %s" % (link,  destination),  'plasma5-notifier-fix')

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
                
    # Fix Breeze themes by deleting lines with deprecated style properties from the gtk.css files
    gtk_files = ['/usr/share/themes/Breeze/gtk-3.0/gtk.css',
                 '/usr/share/themes/Breeze-Dark/gtk-3.0/gtk.css']
    for gtk in gtk_files:
        if exists(gtk):
            for property in gtk_deprecated_properties:
                os.system("sed -i '/%s/d' %s" % (property, gtk))

except Exception as detail:
    print(detail)
    log.write(detail,  'adjust')
