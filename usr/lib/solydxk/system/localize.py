#! /usr/bin/env python3

import re
import threading
from os.path import join, abspath, dirname, exists, basename
from utils import getoutput, get_config_dict, shell_exec, has_string_in_file, \
                  does_package_exist, is_package_installed, \
                  get_debian_version, get_firefox_version

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
            if tz_lst:
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
        self.queue_progress()
        shell_exec("apt-get update")
        self.applications()
        self.language_specific()

    def set_locale(self):
        print((" --> Set locale %s" % self.default_locale))
        self.queue_progress()
#        minus_list = []
        # First, comment all languages
        shell_exec("sed -i -e '/^[a-z]/ s/^#*/# /' /etc/locale.gen")
        # Loop through all locales
        for loc in self.locales:
            if loc[0]:
#                if not loc[3]:
#                    minus_list.append(loc[1].replace('_', '-'))
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
            
        cmd = "echo '{0}' > /etc/timezone && " \
              "rm /etc/localtime; ln -sf /usr/share/zoneinfo/{0} /etc/localtime && " \
              "echo 'LANG={1}.UTF-8' > /etc/default/locale && " \
              "dpkg-reconfigure --frontend=noninteractive locales && " \
              "update-locale LANG={1}.UTF-8".format(self.timezone, self.default_locale)
        shell_exec(cmd)
        
        # Copy mo files for Grub if needed
        cmd = "mkdir -p /boot/grub/locale && " \
              "for F in $(find /usr/share/locale -name 'grub.mo'); do " \
              "MO=/boot/grub/locale/$(echo $F | cut -d'/' -f 5).mo; " \
              "cp -afuv $F $MO; done"
        shell_exec(cmd)
        
        # Cleanup old default grub settings
        default_grub = '/etc/default/grub'
        shell_exec("sed -i '/^# Set locale$/d' {0} && " \
                   "sed -i '/^LANG=/d' {0} && " \
                   "sed -i '/^LANGUAGE=/d' {0} && " \
                   "sed -i '/^GRUB_LANG=/d' {0}".format(default_grub))
        
        # Update Grub and make sure it uses the new locale
        shell_exec('LANG={0}.UTF-8 update-grub'.format(self.default_locale))
            
        # Change user settings
        if exists(self.user_dir):
            shell_exec("sudo -H -u %s bash -c \"sed -i 's/Language=.*/Language=%s\.utf8/' %s/.dmrc\"" % (self.user, self.default_locale, self.user_dir))
            shell_exec("sudo -H -u %s bash -c \"printf %s > %s/.config/user-dirs.locale\"" % (self.user, self.default_locale, self.user_dir))
            prefs = getoutput("find %s -type f -name \"prefs.js\" -not -path \"*/extensions/*\"" % self.user_dir)
            for pref in prefs:
                self.localizePref(pref)

        self.current_default = self.default_locale
        
    def localizePref(self, prefsPath):
        if exists(prefsPath):
            with open(prefsPath, 'r') as f:
                text = f.read()

            prev_lan = self.current_default.split('_')[0]
            moz_prev_lan = self.current_default.replace('_', '-')
            lan = self.default_locale.split('_')[0]
            moz_lan = self.default_locale.replace('_', '-')
            if 'thunderbird' in prefsPath:
                ff_ver = 0
            else:
                ff_ver = get_firefox_version()

            # Set Mozilla parameters in prefs file
            mozLine = "user_pref(\"spellchecker.dictionary\", \"%s\");" % lan
            text = self.searchAndReplace(text, "^user_pref.*spellchecker\.dictionary.*", mozLine, mozLine)
            
            mozLine = "user_pref(\"intl.locale.matchOS\", true);"
            text = self.searchAndReplace(text, "^user_pref.*intl\.locale\.matchOS.*", mozLine, mozLine)
            
            # Setting these is not needed because of matchOS=true but
            # it helps users if they want to manually change Mozilla's interface language into
            # something different than the OS's locale.
            if ff_ver < 59:
                mozLine = "user_pref(\"general.useragent.locale\", \"%s\");" % moz_lan
                text = self.searchAndReplace(text, "^user_pref.*general\.useragent\.locale.*", mozLine, mozLine)
            else:
                # From FF version 59 a new variable is used
                mozLine = "user_pref(\"intl.locale.requested\", \"%s\");" % moz_lan
                text = self.searchAndReplace(text, "^user_pref.*intl\.locale\.requested.*", mozLine, mozLine)

            # Change language of anything that is left
            text = self.searchAndReplace(text, moz_prev_lan, moz_lan)
            text = self.searchAndReplace(text, '"{}"'.format(prev_lan), '"{}"'.format(lan))
            text = self.searchAndReplace(text, '"{}"'.format(prev_lan.upper()), '"{}"'.format(lan.upper()))

            with open(prefsPath, 'w') as f:
                f.write(text)

    def searchAndReplace(self, text, regexpSearch, replaceWithString, appendString=None):
        matchObj = re.search(regexpSearch, text, re.MULTILINE)
        if matchObj:
            # We need the flags= or else the index of re.MULTILINE is passed
            text = re.sub(regexpSearch, replaceWithString, text, flags=re.MULTILINE)
        else:
            if appendString is not None:
                text += "\n%s" % appendString
        return text

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
        for loc in self.locales:
            locale = ''
            if loc[0]:
                locale = loc[1]
            if locale == "en_US" or locale == '':
                continue
            spellchecker = False
            # Localize KDE
            if is_package_installed("kde-runtime"):
                print((" --> Localizing KDE"))
                package = self.get_localized_package("kde-l10n", locale)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize LibreOffice
            if is_package_installed("libreoffice"):
                print((" --> Localizing LibreOffice"))
                package = self.get_localized_package("libreoffice-l10n", locale)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s libreoffice %s" % (self.debian_frontend, self.apt_options, package))
                package = self.get_localized_package("libreoffice-help", locale)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell", locale)
                    if package == '':
                        package = self.get_localized_package("myspell", locale)
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize AbiWord
            if is_package_installed("abiword"):
                print((" --> Localizing AbiWord"))
                package = self.get_localized_package("aspell", locale)
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
                package = self.get_localized_package("firefox-%sl10n" % esr, locale)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s %s %s" % (self.debian_frontend, self.apt_options, ff, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell", locale)
                    if package == '':
                        package = self.get_localized_package("myspell", locale)
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

            # Localize Thunderbird
            if is_package_installed("thunderbird"):
                print((" --> Localizing Thunderbird"))
                package = self.get_localized_package("thunderbird-l10n", locale)
                if package != "":
                    self.queue_progress()
                    shell_exec("%s apt-get install %s thunderbird %s" % (self.debian_frontend, self.apt_options, package))
                # lightning-l10n has been integrated into thunderbird-l10n
                #if is_package_installed("lightning"):
                #    print(" --> Localizing Lightning")
                #    package = self.get_localized_package("lightning-l10n", locale)
                #    if package != "":
                #        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))
                if not spellchecker:
                    package = self.get_localized_package("hunspell", locale)
                    if package == '':
                        package = self.get_localized_package("myspell", locale)
                    if package != "":
                        spellchecker = True
                        self.queue_progress()
                        shell_exec("%s apt-get install %s %s" % (self.debian_frontend, self.apt_options, package))

    def queue_progress(self):
        self.current_step += 1
        if self.current_step > self.max_steps:
            self.current_step = self.max_steps
        if self.queue is not None:
            #print((">> step %d of %d" % (self.current_step, self.max_steps)))
            self.queue.put([self.max_steps, self.current_step])

    def get_localized_package(self, package, locale):
        language_list = locale.lower().split("_")
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
