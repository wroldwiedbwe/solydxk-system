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
from dialogs import MessageDialog
from mirror import MirrorGetSpeed, Mirror, getMirrorData, getLocalRepos
from queue import Queue
from os import system

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
        self.btnRemoveBlackList = go("btnRemoveBlacklist")
        self.btnAddBlackList = go("btnAddBlacklist")
        self.tvBlacklist = go("tvBlacklist")
        self.tvAvailable = go("tvAvailable")
        self.progressbar = go("progressbar")

        # GUI translations
        self.window.set_title(_("SolydXK System Settings"))
        self.btnSaveMirrors.set_label(_("Save mirrors"))
        self.btnCheckMirrorsSpeed.set_label(_("Check mirrors speed"))
        self.btnRemoveBlackList.set_label(_("Remove"))
        self.btnAddBlackList.set_label(_("Blacklist"))
        self.lblMirrors.set_label(_("Repository mirrors"))
        go("lblBlacklist").set_label(_("Blacklisted packages"))
        go("lblMirrorsText").set_label(_("Select the fastest repository"))
        go("lblBlacklistText").set_label(_("Blacklisted packages"))
        go("lblAvailableText").set_label(_("Available packages"))


        # Initiate the treeview handler and connect the custom toggle event with on_tvMirrors_toggle
        self.tvMirrorsHandler = TreeViewHandler(self.tvMirrors)
        self.tvMirrorsHandler.connect('checkbox-toggled', self.on_tvMirrors_toggle)

        self.tvBlacklistHandler = TreeViewHandler(self.tvBlacklist)
        self.tvAvailableHandler = TreeViewHandler(self.tvAvailable)

        # Initialize
        self.queue = Queue(-1)
        self.threads = {}
        self.excludeMirrors = ['security', 'community']
        self.activeMirrors = getMirrorData(excludeMirrors=self.excludeMirrors)
        self.deadMirrors = getMirrorData(getDeadMirrors=True)
        self.mirrors = self.getMirrors()
        self.blacklist = []
        self.available = []

        self.fillTreeViewMirrors()
        self.fillTreeViewBlackList()
        self.fillTreeViewAvailable()

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

    def on_btnRemoveBlacklist_clicked(self, widget):
        self.removeBlacklist()

    def on_btnAddBlacklist_clicked(self, widget):
        self.addBlacklist()

    # ===============================================
    # Blacklist functions
    # ===============================================

    def fillTreeViewBlackList(self):
        self.blacklist = []
        cmd = "env LANG=C dpkg --get-selections | grep hold$ | awk '{print $1}'"
        lst = getoutput(cmd)
        for pck in lst:
            self.blacklist.append([False, pck.strip()])
        # Fill treeview
        columnTypesList = ['bool', 'str']
        self.tvBlacklistHandler.fillTreeview(self.blacklist, columnTypesList, 0, 400, False)

    def fillTreeViewAvailable(self):
        self.available = []
        cmd = "env LANG=C dpkg --get-selections | grep install$ | awk '{print $1}'"
        lst = getoutput(cmd)
        for pck in lst:
            self.available.append([False, pck.strip()])
        # Fill treeview
        columnTypesList = ['bool', 'str']
        self.tvAvailableHandler.fillTreeview(self.available, columnTypesList, 0, 400, False)

    def addBlacklist(self):
        packages = self.tvAvailableHandler.getToggledValues()
        for pck in packages:
            print(("Blacklist package: %s" % pck))
            cmd = "echo '%s hold' | dpkg --set-selections" % pck
            system(cmd)
        self.fillTreeViewBlackList()
        self.fillTreeViewAvailable()

    def removeBlacklist(self):
        packages = self.tvBlacklistHandler.getToggledValues()
        for pck in packages:
            print(("Remove package from blacklist: %s" % pck))
            cmd = "echo '%s install' | dpkg --set-selections" % pck
            system(cmd)
        self.fillTreeViewBlackList()
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
