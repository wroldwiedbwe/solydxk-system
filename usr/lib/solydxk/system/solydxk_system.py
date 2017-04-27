#! /usr/bin/env python3

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk, GObject
# abspath, dirname, join, expanduser, exists, basename
from os.path import join, abspath, dirname
from utils import getoutput, ExecuteThreadedCommands
from treeview import TreeViewHandler
from combobox import ComboBoxHandler
from dialogs import MessageDialog
from mirror import MirrorGetSpeed, Mirror, getMirrorData, getLocalRepos
from queue import Queue
from os import system
from localize import LocaleInfo, Localize

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')


#class for the main window
class SolydXKSystemSettings(object):

    def __init__(self):
        # Check if script is running
        self.scriptDir = abspath(dirname(__file__))
        self.shareDir = self.scriptDir.replace('lib', 'share')

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.shareDir, 'solydxk_system.glade'))

        # Preferences window objects
        go = self.builder.get_object
        self.window = go("windowPref")
        self.nbPref = go('nbPref')
        self.btnSaveMirrors = go('btnSaveMirrors')
        self.btnCheckMirrorsSpeed = go("btnCheckMirrorsSpeed")
        self.lblMirrors = go('lblMirrors')
        self.tvMirrors = go("tvMirrors")
        self.btnRemoveHoldback = go("btnRemoveHoldback")
        self.btnHoldback = go("btnHoldback")
        self.tvHoldback = go("tvHoldback")
        self.tvAvailable = go("tvAvailable")
        self.tvLocale = go("tvLocale")
        self.lblLocaleUserInfo = go("lblLocaleUserInfo")
        self.cmbTimezoneContinent = go("cmbTimezoneContinent")
        self.cmbTimezone = go("cmbTimezone")
        self.btnSaveLocale = go("btnSaveLocale")
        self.progressbar = go("progressbar")

        # GUI translations
        self.window.set_title(_("SolydXK System Settings"))
        self.btnSaveMirrors.set_label(_("Save mirrors"))
        self.btnCheckMirrorsSpeed.set_label(_("Check mirrors speed"))
        self.btnRemoveHoldback.set_label(_("Remove"))
        self.btnHoldback.set_label(_("Hold back"))
        self.lblMirrors.set_label(_("Repository mirrors"))
        go("lblLocaleInfo").set_label(_("Configure your locales (one as default) and time zone.\n"
                                        "Make sure you have an internet connection to localize your software."))
        go("lblMirrorsInfo").set_label(_("Select the fastest repository for your updates.\n"
                                         "Make sure you have an internet connection."))
        go("lblHoldback").set_label(_("Hold back packages"))
        go("lblHoldbackText").set_label(_("Held back packages"))
        go("lblAvailableText").set_label(_("Available packages"))
        go("lblHoldbackInfo").set_label(_("Here you can hold back individual packages.\n"
                                          "This will prevent these packages from being upgraded."))
        self.btnSaveLocale.set_label(_("Save locale"))
        self.installed_title = _('Installed')
        self.locale_title = _('Locale')
        self.language_title = _('Language')
        self.default_title = _('Default')

        # Initiate the treeview handler and connect the custom toggle event with on_tvMirrors_toggle
        self.tvMirrorsHandler = TreeViewHandler(self.tvMirrors)
        self.tvMirrorsHandler.connect('checkbox-toggled', self.on_tvMirrors_toggle)

        self.tvHoldbackHandler = TreeViewHandler(self.tvHoldback)
        self.tvAvailableHandler = TreeViewHandler(self.tvAvailable)
        self.tvLocaleHandler = TreeViewHandler(self.tvLocale)
        self.tvLocaleHandler.connect('checkbox-toggled', self.on_tvLocale_toggle)

        self.cmbTimezoneContinentHandler = ComboBoxHandler(self.cmbTimezoneContinent)
        self.cmbTimezoneHandler = ComboBoxHandler(self.cmbTimezone)

        # Initialize
        self.queue = Queue(-1)
        self.threads = {}
        self.excludeMirrors = ['security', 'community']
        self.activeMirrors = getMirrorData(excludeMirrors=self.excludeMirrors)
        self.deadMirrors = getMirrorData(getDeadMirrors=True)
        self.mirrors = self.getMirrors()
        self.holdback = []
        self.available = []
        self.locales = []
        self.new_default_locale = ''

        self.locale_info = LocaleInfo()
        self.fillTreeViewMirrors()
        self.fillTreeViewHoldback()
        self.fillTreeViewAvailable()
        self.fillTreeViewLocale()
        self.fillComboboxTimezoneContinent()

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show()

    # ===============================================
    # Main window functions
    # ===============================================

    def on_btnCheckMirrorsSpeed_clicked(self, widget):
        self.checkMirrorsSpeed()

    def on_btnSaveMirrors_clicked(self, widget):
        self.saveMirrors()

    def on_btnCancel_clicked(self, widget):
        self.window.destroy()

    def on_btnRemoveHoldback_clicked(self, widget):
        self.removeHoldback()

    def on_btnHoldback_clicked(self, widget):
        self.addHoldback()

    def on_cmbTimezoneContinent_changed(self, widget):
        self.fillComboboxTimezone(self.cmbTimezoneContinentHandler.getValue())

    def on_btnSaveLocale_clicked(self, widget):
        # Collect information
        locales = self.tvLocaleHandler.model_to_list()
        timezone = join(self.cmbTimezoneContinentHandler.getValue(),
                        self.cmbTimezoneHandler.getValue())

        # Start localizing
        loc = Localize(locales, timezone)
        loc.set_progress_hook(self.progressbar)
        loc.start()

        # Done: show message to reboot
        msg = _("You need to reboot your system for the new settings to take affect.")
        MessageDialog(self.btnSaveLocale.get_label(), msg)

    # ===============================================
    # Localization functions
    # ===============================================

    def fillTreeViewLocale(self):
        self.locales = [[self.installed_title, self.locale_title, self.language_title, self.default_title]]
        select_row = 0
        i = 0
        for loc in self.locale_info.locales:
            lan = self.locale_info.get_readable_language(loc)
            select = False
            default = False
            if loc in self.locale_info.available_locales:
                select = True
            if loc == self.locale_info.default_locale:
                default = True
                select_row = i
            self.locales.append([select, loc, lan, default])
            i += 1

        # Fill treeview
        columnTypesList = ['bool', 'str', 'str', 'bool']
        self.tvLocaleHandler.fillTreeview(self.locales, columnTypesList, select_row, 400, True)

    def fillComboboxTimezoneContinent(self):
        self.cmbTimezoneContinentHandler.fillComboBox(self.locale_info.timezone_continents,
                                                      self.locale_info.current_timezone_continent)
        self.fillComboboxTimezone(self.cmbTimezoneContinentHandler.getValue())

    def fillComboboxTimezone(self, timezone_continent):
        timezones = self.locale_info.list_timezones(timezone_continent)
        self.cmbTimezoneHandler.fillComboBox(timezones,
                                             self.locale_info.current_timezone)

    def on_tvLocale_toggle(self, obj, path, colNr, toggleValue):
        path = int(path)
        model = self.tvLocale.get_model()
        selectedIter = model.get_iter(path)

        # Check that only one default locale can be selected
        # and that the locale should be selected for installation
        if colNr == 3:
            installed = model.get_value(selectedIter, 0)
            if not installed:
                model[selectedIter][3] = False
                return False
            self.new_default_locale = model.get_value(selectedIter, 1)
            # Deselect any other default locale
            rowCnt = 0
            itr = model.get_iter_first()
            while itr is not None:
                if rowCnt != path:
                    model[itr][3] = False
                itr = model.iter_next(itr)
                rowCnt += 1

    # ===============================================
    # Hold back functions
    # ===============================================

    def fillTreeViewHoldback(self):
        self.holdback = []
        lst = getoutput("env LANG=C dpkg --get-selections | grep hold$ | awk '{print $1}'")
        for pck in lst:
            if pck != '':
                self.holdback.append([False, pck.strip()])
        # Fill treeview
        columnTypesList = ['bool', 'str']
        self.tvHoldbackHandler.fillTreeview(self.holdback, columnTypesList, 0, 400, False)

    def fillTreeViewAvailable(self):
        self.available = []
        lst = getoutput("env LANG=C dpkg --get-selections | grep install$ | awk '{print $1}'")
        for pck in lst:
            self.available.append([False, pck.strip()])
        # Fill treeview
        columnTypesList = ['bool', 'str']
        self.tvAvailableHandler.fillTreeview(self.available, columnTypesList, 0, 400, False)

    def addHoldback(self):
        packages = self.tvAvailableHandler.getToggledValues()
        for pck in packages:
            print(("Hold back package: %s" % pck))
            system("echo '%s hold' | dpkg --set-selections" % pck)
        self.fillTreeViewHoldback()
        self.fillTreeViewAvailable()

    def removeHoldback(self):
        packages = self.tvHoldbackHandler.getToggledValues()
        for pck in packages:
            print(("Remove hold back from: %s" % pck))
            system("echo '%s install' | dpkg --set-selections" % pck)
        self.fillTreeViewHoldback()
        self.fillTreeViewAvailable()

    # ===============================================
    # Mirror functions
    # ===============================================

    def fillTreeViewMirrors(self):
        # Fill mirror list
        if len(self.mirrors) > 1:
            # Fill treeview
            columnTypesList = ['bool', 'str', 'str', 'str', 'str']
            self.tvMirrorsHandler.fillTreeview(self.mirrors, columnTypesList, 0, 400, True)

            # TODO - We have no mirrors: hide the tab until we do
            #self.nbPref.get_nth_page(1).set_visible(False)
        else:
            self.nbPref.get_nth_page(1).set_visible(False)

    def saveMirrors(self):
        # Safe mirror settings
        replaceRepos = []
        # Get user selected mirrors
        model = self.tvMirrors.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            sel = model.get_value(itr, 0)
            if sel:
                repo = model.get_value(itr, 2)
                url = model.get_value(itr, 3)
                not_changed = ''
                # Get currently selected data
                for mirror in self.mirrors:
                    if mirror[0] and mirror[2] == repo:
                        if mirror[3] != url:
                            # Currently selected mirror
                            replaceRepos.append([mirror[3], url])
                        else:
                            not_changed = url
                        break
                if url not in replaceRepos and url not in not_changed:
                    # Append the repositoriy to the sources file
                    replaceRepos.append(['', url])
            itr = model.iter_next(itr)

        if not replaceRepos:
            # Check for dead mirrors
            model = self.tvMirrors.get_model()
            itr = model.get_iter_first()
            while itr is not None:
                sel = model.get_value(itr, 0)
                if sel:
                    repo = model.get_value(itr, 2)
                    url = model.get_value(itr, 3)
                    # Get currently selected data
                    for mirror in self.deadMirrors:
                        if mirror[1] == repo and mirror[2] != url:
                            # Currently selected mirror
                            replaceRepos.append([mirror[2], url])
                            break
                itr = model.iter_next(itr)

        if replaceRepos:
            m = Mirror()
            ret = m.save(replaceRepos, self.excludeMirrors)
            if ret == '':
                # Run update in a thread and show progress
                name = 'update'
                self.set_buttons_state(False)
                t = ExecuteThreadedCommands("apt-get update", self.queue)
                self.threads[name] = t
                t.daemon = True
                t.start()
                self.queue.join()
                GObject.timeout_add(250, self.check_thread, name)
            else:
                print((ret))

        else:
            msg = _("There are no repositories to save.")
            MessageDialog(self.lblMirrors.get_label(), msg)

    def getMirrors(self):
        mirrors = [[_("Current"), _("Country"), _("Repository"), _("URL"), _("Speed")]]
        for mirror in  self.activeMirrors:
            if mirror:
                print(("Mirror data: %s" % ' '.join(mirror)))
                blnCurrent = self.isUrlInSources(mirror[2])
                mirrors.append([blnCurrent, mirror[0], mirror[1], mirror[2], ''])
        return mirrors

    def isUrlInSources(self, url):
        url = "://%s" % url
        blnRet = False

        for repo in getLocalRepos():
            if url in repo:
                blnRet = True
                for excl in self.excludeMirrors:
                    if excl in repo:
                        blnRet = False
                        break
                break
        return blnRet

    def checkMirrorsSpeed(self):
        name = 'mirrorspeed'
        self.set_buttons_state(False)
        t = MirrorGetSpeed(self.mirrors, self.queue)
        self.threads[name] = t
        t.daemon = True
        t.start()
        self.queue.join()
        GObject.timeout_add(5, self.check_thread, name)

    def writeSpeed(self, url, speed):
        model = self.tvMirrors.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            repo = model.get_value(itr, 3)
            if repo == url:
                print(("Mirror speed for %s = %s" % (url, speed)))
                model.set_value(itr, 4, speed)
                path = model.get_path(itr)
                self.tvMirrors.scroll_to_cell(path)
            itr = model.iter_next(itr)
        self.tvMirrors.set_model(model)
        # Repaint GUI, or the update won't show
        while Gtk.events_pending():
            Gtk.main_iteration()

    def on_tvMirrors_toggle(self, obj, path, colNr, toggleValue):
        path = int(path)
        model = self.tvMirrors.get_model()
        selectedIter = model.get_iter(path)
        selectedRepo = model.get_value(selectedIter, 2)

        rowCnt = 0
        itr = model.get_iter_first()
        while itr is not None:
            if rowCnt != path:
                repo = model.get_value(itr, 2)
                if repo == selectedRepo:
                    model[itr][0] = False
            itr = model.iter_next(itr)
            rowCnt += 1

    # ===============================================
    # General functions
    # ===============================================

    def check_thread(self, name):
        if self.threads[name].is_alive():
            if name == 'update':
                self.progressbar.set_pulse_step(0.1)
                self.progressbar.pulse()
            if not self.queue.empty():
                ret = self.queue.get()
                #print(("Queue returns: {}".format(ret)))
                if ret and name == 'mirrorspeed':
                    self.progressbar.set_fraction(1 / (ret[3] / ret[2]))
                    self.writeSpeed(ret[0], ret[1])
                self.queue.task_done()
            return True

        # Thread is done
        print((">> Thread is done"))
        if not self.queue.empty():
            ret = self.queue.get()
            print((ret))
            if ret and name == 'mirrorspeed':
                self.writeSpeed(ret[0], ret[1])
            self.queue.task_done()
        del self.threads[name]

        if name == 'update':
            self.mirrors = self.getMirrors()
            self.fillTreeViewMirrors()

        self.progressbar.set_fraction(0)

        self.set_buttons_state(True)

        return False

    def set_buttons_state(self, enable):
        if not enable:
            # Disable buttons
            self.btnCheckMirrorsSpeed.set_sensitive(False)
            self.btnSaveMirrors.set_sensitive(False)
        else:
            # Enable buttons
            self.btnCheckMirrorsSpeed.set_sensitive(True)
            self.btnSaveMirrors.set_sensitive(True)

    # Close the gui
    def on_windowPref_destroy(self, widget):
        Gtk.main_quit()
