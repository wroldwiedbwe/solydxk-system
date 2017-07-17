#! /usr/bin/env python3

import os
import threading
from dialogs import WarningDialog
from os.path import join, abspath, dirname, exists, basename
from utils import getoutput, get_config_dict, shell_exec, has_string_in_file, \
                  does_package_exist, is_package_installed, has_internet_connection, \
                  get_debian_version

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')

DEFAULTLOCALE = 'en_US'


class LocaleInfo():
    def __init__(self):
        self.scriptDir = abspath(dirname(__file__))
        self.timezones = getoutput("awk '/^[^#]/{print $3}' /usr/share/zoneinfo/zone.tab | sort -k3")
        self.refresh()

        # Genereate locale files with the default locale if they do not exist
        if not exists('/etc/locale.gen'):
            shell_exec("echo \"%s.UTF-8 UTF-8\" >> /etc/locale.gen" % DEFAULTLOCALE)
            shell_exec("locale-gen")
        if self.default_locale == '':
            self.default_locale = DEFAULTLOCALE
            shell_exec("echo \"\" > /etc/default/locale")
            shell_exec("update-locale LANG=\"%s.UTF-8\"" % self.default_locale)
            shell_exec("update-locale LANG=%s.UTF-8" % self.default_locale)

    def list_timezones(self, continent=None):
        timezones = []
        for tz in self.timezones:
            tz_lst = tz.split('/')
            if continent is None:
                # return continent only
                if tz_lst[0] not in timezones:
                    timezones.append(tz_lst[0])
            else:
                # return timezones of given continent
                if tz_lst[0] == continent:
                    timezones.append('/'.join(tz_lst[1:]))
        return timezones

    def get_readable_language(self, locale):
        lan = ''
        lan_list = join(self.scriptDir, 'languages.list')
        if exists(lan_list):
            lan = getoutput("grep '^%s' \"%s\" | awk -F'=' '{print $2}'" % (locale, lan_list))[0]
            if lan == '':
                lan = getoutput("grep '^%s' \"%s\" | awk -F'[= ]' '{print $2}' | uniq" % (locale.split('_')[0], lan_list))[0]
        return lan

    def refresh(self):
        self.locales = getoutput("awk -F'[@. ]' '/UTF-8/{ print $1 }' /usr/share/i18n/SUPPORTED | uniq")
        self.default_locale = getoutput("awk -F'[=.]' '/UTF-8/{ print $2 }' /etc/default/locale")[0]
        self.available_locales = getoutput("locale -a | grep '_' | awk -F'[@ .]' '{print $1}'")
        self.timezone_continents = self.list_timezones()
        tz = getoutput("cat /etc/timezone 2>/dev/null")[0]
        self.current_timezone_continent = dirname(tz)
        self.current_timezone = basename(tz)


class Localize(threading.Thread):
    # locales = [[install_bool, locale_string, language_string, default_bool]]
    def __init__(self, locales, timezone, queue=None):
        threading.Thread.__init__(self)
        
        self.locales = locales
        self.default_locale = ''
        for loc in locales:
            if loc[3]:
                self.default_locale = loc[1]
                break
        if self.default_locale == '':
            self.default_locale = DEFAULTLOCALE
        self.timezone = timezone.strip()
        self.queue = queue
        self.user = getoutput("logname")[0]
        self.user_dir = "/home/%s" % self.user
        self.current_default = getoutput("awk -F'[=.]' '/UTF-8/{ print $2 }' /etc/default/locale")[0]
        self.scriptDir = abspath(dirname(__file__))
        self.edition = 'all'

        # Get configuration settings
        self.debian_version = get_debian_version()
        config = get_config_dict(join(self.scriptDir, "solydxk-system.conf"))
        self.debian_frontend = "DEBIAN_FRONTEND=%s" % config.get('DEBIAN_FRONTEND', 'noninteractive')
        self.apt_options = config.get('APT_OPTIONS_8', '')
        if self.debian_version == 0 or self.debian_version >= 9:
            self.apt_options = config.get('APT_OPTIONS_9', '')
        self.info = config.get('INFO', '/usr/share/solydxk/info')
        if exists(self.info):
            config = get_config_dict(self.info)
            self.edition = config.get('EDITION', 'all').replace(' ', '').lower()

        # Steps
        self.max_steps = 10
        self.current_step = 0

    def run(self):
        self.set_locale()
        self.set_timezone()
        if has_internet_connection():
            self.queue_progress()
            shell_exec("apt-get update")
            self.applications()
            self.language_specific()
        else:
            msg = _("SolydXK System Settings cannot download and install the software localization packages\n"
                    "Please repeat this process when you established an internet connection.")
            WarningDialog(_("No internet connection", msg))

    def set_locale(self):
        print((" --> Set locale %s" % self.default_locale))
        self.queue_progress()
        minus_list = []
        # First, comment all languages
        shell_exec("sed -i -e '/^[a-z]/ s/^#*/# /' /etc/locale.gen")
        # Loop through all locales
        for loc in self.locales:
            if loc[0]:
                if not loc[3]:
                    minus_list.append(loc[1].replace('_', '-'))
                if has_string_in_file(loc[1], '/etc/locale.gen'):
                    # Uncomment the first occurence of the locale
                    shell_exec("sed -i '0,/^# *%(lan)s.UTF-8/{s/^# *%(lan)s.UTF-8/%(lan)s.UTF-8/}' /etc/locale.gen" % {'lan': loc[1].replace('.', '\.')})
                else:
                    # Add the locale
                    shell_exec("echo \"%s.UTF-8 UTF-8\" >> /etc/locale.gen" % loc[1])

            # Save new default locale
            if loc[3]:
                self.default_locale = loc[1]

        # Check if at least one locale is set
        locales = getoutput("awk -F'[@. ]' '{print $1}' < /etc/locale.gen | grep -v -E '^#|^$'")
        if locales[0] == '':
            shell_exec("echo \"%s.UTF-8 UTF-8\" >> /etc/locale.gen" % self.default_locale)
        # Run locale-gen
        shell_exec("locale-gen")
        # Save default locale
        shell_exec("echo \"\" > /etc/default/locale")
        shell_exec("update-locale LANG=\"%s.UTF-8\"" % self.default_locale)
        #shell_exec("update-locale LANG=%s.UTF-8" % self.default_locale)
        
        # Localize Grub2
        default_grub = '/etc/default/grub'
        if self.default_locale != 'en_US' and exists(default_grub):
            # Copy mo files if needed
            cmd = 'mkdir -p /boot/grub/locale; for F in $(find /usr/share/locale -name "grub.mo"); do MO="/boot/grub/locale/$(echo $F | cut -d\'/\' -f 5).mo"; if [ ! -e $MO ]; then cp -v $F $MO; fi; done'
            shell_exec(cmd)
            # Configure Grub2
            sed_cmd = ''
            grub_lang_str = ''
            if not has_string_in_file("^GRUB_LANG=", default_grub):
                grub_lang_str = "\n# Set locale\nGRUB_LANG=%s\n" % self.default_locale
            else:
                sed_cmd += "sed -i -e '/GRUB_LANG=/ c GRUB_LANG=%s' %s;" % (self.default_locale, default_grub)
            if grub_lang_str:
                with open(default_grub, 'a') as f:
                    f.write(grub_lang_str)
            elif sed_cmd:
                shell_exec(sed_cmd)
            if grub_lang_str or sed_cmd:
                shell_exec('update-grub 2>/dev/null')

        # Change user settings
        if exists(self.user_dir):
            cur_short = self.current_default.split('_')[0]
            def_short = self.default_locale.split('_')[0]
            shell_exec("sudo -H -u %s bash -c \"sed -i 's/Language=.*/Language=%s\.utf8/' %s/.dmrc\"" % (self.user, self.default_locale, self.user_dir))
            shell_exec("sudo -H -u %s bash -c \"printf %s > %s/.config/user-dirs.locale\"" % (self.user, self.default_locale, self.user_dir))
            prefs = getoutput("find %s -type f -name \"prefs.js\" -not -path \"*/extensions/*\"" % self.user_dir)
            for pref in prefs:
                shell_exec("sudo -H -u %s bash -c \"sed -i 's/%s/%s/g\' %s\"" % (self.user, self.current_default, self.default_locale, pref))
                cmd = "sudo -H -u %s bash -c \"sed -i -E 's/(\\\")%s([\\\"#])/\\1%s\\2/' %s\"" % (self.user, cur_short, def_short, pref)
                print((cmd))
                os.system(cmd)
                cmd = "sudo -H -u %s bash -c \"sed -i -E 's/(\\\"[a-z]*#).*([\\\"])/\\1%s\\2/' %s\"" % (self.user, '#'.join(minus_list), pref)
                print(cmd)
                os.system(cmd)

        self.current_default = self.default_locale

    def set_timezone(self):
        # set the timezone
        if '/' in self.timezone and len(self.timezone) > 3:
            print((" --> Set time zone %s" % self.timezone))
            self.queue_progress()
            shell_exec("echo \"%s\" > /etc/timezone" % self.timezone)
            shell_exec("rm /etc/localtime; ln -sf /usr/share/zoneinfo/%s /etc/localtime" % self.timezone)

    def language_specific(self):
        localizeConf = join(self.scriptDir, "localize/%s" % self.default_locale)
        if exists(localizeConf):
            try:
                print((" --> Localizing %s" % self.edition))
                config = get_config_dict(localizeConf)
                packages = config.get(self.edition, '').strip()
                if packages != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, packages))
            except Exception as detail:
                msg = "ERROR: %s" % detail
                print(msg)

    def applications(self):
        if self.default_locale != "en_US":
            spellchecker = False
            # Localize KDE
            if is_package_installed("kde-runtime"):
                print((" --> Localizing KDE"))
                package = self.get_localized_package("kde-l10n")
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize LibreOffice
            if is_package_installed("libreoffice"):
                print((" --> Localizing LibreOffice"))
                package = self.get_localized_package("libreoffice-l10n")
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s libreoffice %s" % (self.debian_frontend, self.apt_options, package))
                package = self.get_localized_package("libreoffice-help")
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell")
                    if package == '':
                        package = self.get_localized_package("myspell")
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize AbiWord
            if is_package_installed("abiword"):
                print((" --> Localizing AbiWord"))
                package = self.get_localized_package("aspell")
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize Firefox
            ff = "firefox"
            isESR = is_package_installed("firefox-esr")
            if isESR:
                ff = "firefox-esr"
            if isESR or is_package_installed("firefox"):
                esr = ""
                if isESR:
                    esr = "esr-"
                print((" --> Localizing Firefox"))
                package = self.get_localized_package("firefox-%sl10n" % esr)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s %s" % (self.debian_frontend, self.apt_options, ff, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell")
                    if package == '':
                        package = self.get_localized_package("myspell")
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize Thunderbird
            if is_package_installed("thunderbird"):
                print((" --> Localizing Thunderbird"))
                package = self.get_localized_package("thunderbird-l10n")
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s thunderbird %s" % (self.debian_frontend, self.apt_options, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell")
                    if package == '':
                        package = self.get_localized_package("myspell")
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

    def queue_progress(self):
        self.current_step += 1
        if self.current_step > self.max_steps:
            self.current_step = self.max_steps
        if self.queue is not None:
            print((">> step %d of %d" % (self.current_step, self.max_steps)))
            self.queue.put([self.max_steps, self.current_step])

    def get_localized_package(self, package):
        language_list = self.default_locale.lower().split("_")
        lan = "".join(language_list)
        pck = "{}-{}".format(package, lan)
        if not does_package_exist(pck):
            lan = "-".join(language_list)
            pck = "{}-{}".format(package, lan)
            if not does_package_exist(pck):
                lan = language_list[0]
                pck = "{}-{}".format(package, lan)
                if not does_package_exist(pck):
                    pck = ''
        return pck
