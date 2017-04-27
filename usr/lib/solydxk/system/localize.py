#! /usr/bin/env python3

import os
from os.path import join, abspath, dirname, exists, basename
from utils import getoutput, get_config_dict, shell_exec, \
                  doesPackageExist, isPackageInstalled, hasInternetConnection

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
        self.locales = getoutput("awk -F'[@ \.]' '/UTF-8/{ print $1 }' /usr/share/i18n/SUPPORTED | uniq")
        self.default_locale = getoutput("awk -F'[= \.]' '/UTF-8/{ print $2 }' /etc/default/locale")[0]
        self.available_locales = getoutput("locale -a | grep '_' | awk -F'[@ \.]' '{print $1}'")
        self.timezone_continents = self.list_timezones()
        tz = getoutput("cat /etc/timezone 2>/dev/null")[0]
        self.current_timezone_continent = dirname(tz)
        self.current_timezone = basename(tz)


class Localize():
    # locales = [[install_bool, locale_string, default_bool]]
    def __init__(self, locales, timezone):
        self.locales = locales
        self.default_locale = ''
        for loc in locales:
            if loc[2]:
                self.default_locale = loc[1]
                break
        if self.default_locale == '':
            self.default_locale = DEFAULTLOCALE
        self.timezone = timezone.trim()
        self.user = getoutput("logname")[0]
        self.user_dir = getoutput("echo ~/%s" % self.user)[0]
        self.total_steps = 10
        self.current_step = 0
        self.scriptDir = abspath(dirname(__file__))
        self.edition = 'all'
        config = get_config_dict(join(self.scriptDir, "solydxk-system.conf"))
        self.info = config.get('INFO', '/usr/share/solydxk/info')
        if exists(self.info):
            config = get_config_dict(self.info)
            self.edition = config.get('EDITION', 'all').replace(' ', '').lower()

    def set_progress_hook(self, progresshook):
        ''' Set a callback to be called on progress updates '''
        ''' i.e. def my_callback(progress_type, message, current_progress, total) '''
        ''' Where progress_type is any off PROGRESS_START, PROGRESS_UPDATE, PROGRESS_COMPLETE, PROGRESS_ERROR '''
        self.update_progress = progresshook

    def update_progressbar(self):
        self.current_step += 1
        self.update_progress.set_fraction(1 / (self.total_steps / self.current_step))

    def start(self):
        self.set_locale()
        self.set_timezone()
        self.applications()
        self.languageSpecific()
        self.update_progress.set_fraction(0)

    def set_locale(self):
        # set the locale
        self.update_progressbar()
        for loc in self.locales:
            if loc[0]:
                # Add the locale
                shell_exec("echo \"%s.UTF-8 UTF-8\" >> /etc/locale.gen" % loc[1])
            else:
                # Comment loc[1] in /etc/locale.gen
                shell_exec("sed -i 's/^{0}.UTF-8/# {0}.UTF-8/' /etc/locale.gen".format(loc[1].replace('.', '\.')))

            # Save new default locale
            if loc[2]:
                self.default_locale = loc[1]

        # Check if at least one locale is set
        locales = getoutput("grep '_' < /etc/locale.gen | grep -v '^#' | awk -F'[@ \.]' '{print $1}'")
        if locales[0] == '':
            shell_exec("echo \"%s.UTF-8 UTF-8\" >> /etc/locale.gen" % self.default_locale)
        # Run locale-gen
        shell_exec("locale-gen")
        # Save default locale
        shell_exec("echo \"\" > /etc/default/locale")
        shell_exec("update-locale LANG=\"%s.UTF-8\"" % self.default_locale)
        shell_exec("update-locale LANG=%s.UTF-8" % self.default_locale)

        # Change user settings
        if exists(self.user_dir):
            bash_path = join(self.user_dir, ".set_locale.sh")
            bash = '''#!/bin/bash
CURLANG={0}
. /etc/default/locale 2>/dev/null
if [ "$CURLANG" != "$LANG" ]; then
  CURLANGSHORT=${CURLANG:0:5}
  LANGSHORT=${LANG:0:5}
  LANGEXT=$(echo $LANG | cut -d'.' -f 2)
  LANGEXT=${LANGEXT//-}
  LANGEXT=${LANGEXT,,}
  sed -i "s/Language=.*/Language=$LANGSHORT\.$LANGEXT/" ~/.dmrc 2>/dev/null
  printf $LANGSHORT > ~}/.config/user-dirs.locale 2>/dev/null
  find ~/ -type f -name "prefs.js" -not -path "*/extensions/*" -exec sed -i "s/\"$CURLANG\"/\"$LANG\"/g" {} \;
  find ~/ -type f -name "prefs.js" -not -path "*/extensions/*" -exec sed -i "s/\"$CURLANGSHORT\"/\"$LANGSHORT\"/g" {} \;
fi'''.format(self.current_locale)
            with open(bash_path, "w") as f:
                f.write(bash)
            shell_exec("sudo -H -u {0} bash -c -c {1}".format(self.user, bash_path))
            os.remove(bash_path)

    def set_timezone(self):
        # set the timezone
        self.update_progressbar()
        if '/' in self.timezone and len(self.timezone) > 3:
            shell_exec("echo \"%s\" > /etc/timezone" % self.timezone)
            shell_exec("cp /usr/share/zoneinfo/%s /etc/localtime" % self.timezone)

    def languageSpecific(self):
        if hasInternetConnection():
            localizeConf = join(self.scriptDir, "localize/%s" % self.default_locale)
            if exists(localizeConf):
                try:
                    print((" --> Localizing %s" % self.edition))
                    self.update_progressbar()
                    config = get_config_dict(localizeConf)
                    packages = config.get(self.edition, '').strip()
                    if packages != "":
                        shell_exec("apt-get install %s" % packages)
                except Exception as detail:
                    msg = "ERROR: %s" % detail
                    print(msg)

    def applications(self):
        if hasInternetConnection():
            if self.default_locale != "en_US":
                # Localize KDE
                if isPackageInstalled("kde-runtime"):
                    print(" --> Localizing KDE")
                    self.update_progressbar()
                    package = self.get_localized_package("kde-l10n")
                    if package != "":
                        shell_exec("apt-get install %s" % package)

                # Localize LibreOffice
                if isPackageInstalled("libreoffice"):
                    print(" --> Localizing LibreOffice")
                    self.update_progressbar()
                    package = self.get_localized_package("libreoffice-l10n")
                    if package != "":
                        shell_exec("apt-get install %s" % package)
                    package = self.get_localized_package("libreoffice-help")
                    if package != "":
                        self.update_progressbar()
                        shell_exec("apt-get install %s" % package)
                    package = self.get_localized_package("myspell")
                    if package != "":
                        self.update_progressbar()
                        shell_exec("apt-get install %s" % package)

                # Localize AbiWord
                if isPackageInstalled("abiword"):
                    print(" --> Localizing AbiWord")
                    self.update_progressbar()
                    package = self.get_localized_package("aspell")
                    if package != "":
                        shell_exec("apt-get install %s" % package)

                # Localize Firefox
                ff = "firefox"
                isESR = isPackageInstalled("firefox-esr")
                if isESR:
                    ff = "firefox-esr"
                if isESR or isPackageInstalled("firefox"):
                    esr = ""
                    if isESR:
                        esr = "esr-"
                    print(" --> Localizing Firefox")
                    self.update_progressbar()
                    package = self.get_localized_package("firefox-%sl10n" % esr)
                    if package != "":
                        shell_exec("apt-get install %s %s" % (ff, package))

                # Localize Thunderbird
                if isPackageInstalled("thunderbird"):
                    print(" --> Localizing Thunderbird")
                    self.update_progressbar()
                    package = self.get_localized_package("thunderbird-l10n")
                    if package != "":
                        shell_exec("apt-get install %s" % package)

    def get_localized_package(self, package):
        language_list = self.default_locale.lower().split("_")
        lan = "".join(language_list)
        pck = "{}-{}".format(package, lan)
        if not doesPackageExist(pck):
            lan = "-".join(language_list)
            pck = "{}-{}".format(package, lan)
            if not doesPackageExist(pck):
                lan = language_list[0]
                pck = "{}-{}".format(package, lan)
                if not doesPackageExist(pck):
                    pck = ''
        return pck
