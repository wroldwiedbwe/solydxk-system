#! /usr/bin/env python3

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk, GObject
import os
import re
from queue import Queue
from localize import LocaleInfo, Localize
from udisks2 import Udisks2
from logger import Logger
from treeview import TreeViewHandler
from combobox import ComboBoxHandler
# abspath, dirname, join, expanduser, exists, basename
from os.path import join, abspath, dirname, isdir, exists, basename
from utils import getoutput, ExecuteThreadedCommands, \
                  shell_exec, human_size, has_internet_connection, \
                  get_backports, get_debian_name, comment_line, \
                  in_virtualbox, get_apt_force, is_running_live, \
                  get_device_from_uuid, get_label, is_package_installed, \
                  get_logged_user, get_uuid
from dialogs import MessageDialog, QuestionDialog, InputDialog, \
                    WarningDialog
from mirror import MirrorGetSpeed, Mirror, get_mirror_data, get_local_repos
from encryption import is_encrypted, create_keyfile, write_crypttab
from endecrypt_partitions import EnDecryptPartitions, ChangePassphrase

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')

TMPMOUNT = '/mnt/solydxk-system'


#class for the main window
class SolydXKSystemSettings(object):
    def __init__(self):
        # Load and install test data for the device manager
        self.test_devices = False
        
        # Check if script is running
        self.scriptDir = abspath(dirname(__file__))
        self.shareDir = self.scriptDir.replace('lib', 'share')

        # Init logging
        self.log_file = "/var/log/solydxk-system.log"
        self.log = Logger(self.log_file, addLogTime=True, maxSizeKB=5120)
        self.log.write('=====================================', 'init')
        self.log.write(">>> Start SolydXK System Settings <<<", 'init')
        self.log.write('=====================================', 'init')

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.shareDir, 'solydxk_system.glade'))

        # Preferences window objects
        go = self.builder.get_object
        self.window = go("windowPref")
        self.nbPref = go('nbPref')
        self.btnSaveBackports = go('btnSaveBackports')
        self.btnSaveMirrors = go('btnSaveMirrors')
        self.btnCheckMirrorSpeed = go("btnCheckMirrorSpeed")
        self.lblRepositories = go('lblRepositories')
        self.tvMirrors = go("tvMirrors")
        self.chkEnableBackports = go("chkEnableBackports")
        self.btnRemoveHoldback = go("btnRemoveHoldback")
        self.btnHoldback = go("btnHoldback")
        self.tvHoldback = go("tvHoldback")
        self.tvAvailable = go("tvAvailable")
        self.tvLocale = go("tvLocale")
        self.tvPartitions = go("tvPartitions")
        self.lblLocaleUserInfo = go("lblLocaleUserInfo")
        self.cmbTimezoneContinent = go("cmbTimezoneContinent")
        self.cmbTimezone = go("cmbTimezone")
        self.btnSaveLocale = go("btnSaveLocale")
        self.lblEncryption = go("lblEncryption")
        self.btnEncrypt = go("btnEncrypt")
        self.btnDecrypt = go("btnDecrypt")
        self.btnRefresh = go("btnRefresh")
        self.btnChangePassphrase = go("btnChangePassphrase")
        self.btnCreateKeyfile = go("btnCreateKeyfile")
        self.progressbar = go("progressbar")
        self.txtPassphrase1 = go("txtPassphrase1")
        self.txtPassphrase2 = go("txtPassphrase2")
        self.imgPassphraseCheck = go("imgPassphraseCheck")
        self.tvCleanup = go("tvCleanup")
        self.btnCleanup = go("btnCleanup")
        self.btnSaveFstabMounts = go("btnSaveFstabMounts")
        self.tvFstabMounts = go("tvFstabMounts")
        self.tvDeviceDriver = go("tvDeviceDriver")
        self.btnSaveDeviceDriver = go("btnSaveDeviceDriver")
        self.btnHelpDeviceDriver = go("btnHelpDeviceDriver")
        self.btnLogDeviceDriver = go("btnLogDeviceDriver")
        self.chkBackportsDeviceDriver = go("chkBackportsDeviceDriver")

        # GUI translations
        self.window.set_title(_("SolydXK System Settings"))
        self.btnSaveBackports.set_label(_("Save backports"))
        self.btnSaveMirrors.set_label(_("Save mirrors"))
        self.btnCheckMirrorSpeed.set_label(_("Check mirrors speed"))
        self.btnRemoveHoldback.set_label(_("Remove"))
        self.btnHoldback.set_label(_("Hold back"))
        self.lblRepositories.set_label(_("Repositories"))
        self.lblEncryption.set_label(_("Encryption"))
        go("lblPassphrase").set_label(_("Passphrase (6-20 chr)"))
        self.btnEncrypt.set_label(_("Encrypt"))
        self.btnDecrypt.set_label(_("Decrypt"))
        self.btnChangePassphrase.set_label(_("Change passphrase"))
        self.btnCreateKeyfile.set_label(_("Manually create key file"))
        go("lblLocalization").set_label(_("Localization"))
        go("lblTimezone").set_label(_("Timezone"))
        go("lblLocale").set_label(_("Locale"))
        go("lblEncryptionInfo").set_label(_("Encrypt partitions and keep your data safe.\n"
                                            "Warning: backup your data before you continue!\n"
                                            "Note: you can Ctrl-left click to select multiple partitions."))
        go("lblLocaleInfo").set_label(_("Configure your locales (one as default) and time zone.\n"
                                        "Note: make sure you have an internet connection to localize your software."))
        go("lblBackportsInfo").set_label(_("Enable the Backports repository if you need a newer software version.\n"
                                           "Warning: installing software from the backports repository may de-stabalize your system.\n"
                                           "Use at your own risk!"))
        go("lblMirrorsInfo").set_label(_("Select the fastest repository for your updates.\n"
                                         "Note: make sure you have an internet connection."))
        go("lblHoldback").set_label(_("Hold back packages"))
        go("lblHoldbackText").set_label(_("Held back packages"))
        go("lblAvailableText").set_label(_("Available packages"))
        go("lblHoldbackInfo").set_label(_("Hold back individual packages.\n"
                                          "Holding back a package will prevent this package from being updated."))
        self.btnSaveLocale.set_label(_("Save locale"))
        self.installed_title = _('Installed')
        self.locale_title = _('Locale')
        self.language_title = _('Language')
        self.default_title = _('Default')
        self.no_passphrase_msg = _("Please provide a passphrase (6-20 characters).")
        self.mount_error = _("Could not mount {0}\nPlease mount {0} and refresh when done.")
        go("lblCleanupInfo").set_label(_("Remove unneeded packages\n"
                                          "Pre-selected packages are safe to remove (autoremove).\n"
                                          "Other packages are orphaned packages. Remove with caution!"))
        go("lblCleanupText").set_label(_("Unneeded packages"))
        go("lblFstabMounts").set_label(_("Fstab mounts"))
        go("lblCurrentFstabMounts").set_label(_("Fstab mounts"))
        go("lblFstabMountsInfo").set_label(_("Mount additional partitions on boot with Fstab.\n"
                                            "When added to Fstab, the partition will be mounted in /media."))
        self.btnSaveFstabMounts.set_label(_("Save Fstab mounts"))
        self.btnSaveDeviceDriver.set_label(_("Install"))
        self.chkBackportsDeviceDriver.set_label(_("Use Backports"))
        go("lblDeviceDriverInfo").set_label(_("Install drivers for supported hardware.\n"
                                          "Note: do not install these drivers if your hardware functions correctly with the current open drivers."))

        # Initiate the treeview handlers and connect the custom toggle events
        self.tvMirrorsHandler = TreeViewHandler(self.tvMirrors)
        self.tvMirrorsHandler.connect('checkbox-toggled', self.on_tvMirrors_toggle)
        self.tvHoldbackHandler = TreeViewHandler(self.tvHoldback)
        self.tvAvailableHandler = TreeViewHandler(self.tvAvailable)
        self.tvLocaleHandler = TreeViewHandler(self.tvLocale)
        self.tvLocaleHandler.connect('checkbox-toggled', self.on_tvLocale_toggled)
        self.tvPartitionsHandler = TreeViewHandler(self.tvPartitions)
        self.tvCleanupHandler = TreeViewHandler(self.tvCleanup)
        self.tvFstabMountsHandler = TreeViewHandler(self.tvFstabMounts)
        self.cmbTimezoneContinentHandler = ComboBoxHandler(self.cmbTimezoneContinent)
        self.cmbTimezoneHandler = ComboBoxHandler(self.cmbTimezone)
        self.tvDeviceDriverHandler = TreeViewHandler(self.tvDeviceDriver)

        # Initialize
        self.queue = Queue(-1)
        self.threads = {}
        self.excludeMirrors = ['security', 'community']
        self.current_debian_repo = ''
        self.holdback = []
        self.available = []
        self.locales = []
        self.new_default_locale = ''
        self.partitions = []
        self.my_partitions = []
        self.my_passphrase = ''
        self.htmlDir = join(self.shareDir, 'html')
        self.helpFile = join(self.get_language_dir(), 'help.html')
        self.helpddFile = join(self.get_language_dir(), 'helpdd.html')
        self.udisks2 = Udisks2()
        self.keyfile_path = None
        self.debian_name = get_debian_name()
        self.endecrypt_success = True
        self.encrypt = False
        self.failed_mount_devices = []
        self.boot_partition = None
        self.changed_devices = []
        self.hardware = []

        # Collect data and disable tabs when running live: Device Driver, Fstab mounts, Localization, Hold back packages, Cleanup
        self.activeMirrors = get_mirror_data(excludeMirrors=self.excludeMirrors)
        self.deadMirrors = get_mirror_data(getDeadMirrors=True)
        self.mirrors = self.get_mirrors()
        self.fill_treeview_partition()
        self.save_my_partitions()
        self.fill_treeview_mirrors()
        if is_running_live():
            self.nbPref.get_nth_page(0).set_visible(False)
            self.nbPref.get_nth_page(2).set_visible(False)
            self.nbPref.get_nth_page(3).set_visible(False)
            self.nbPref.get_nth_page(5).set_visible(False)
            self.nbPref.get_nth_page(6).set_visible(False)
        else:
            self.backports = get_backports()
            self.locale_info = LocaleInfo()
            self.fill_treeview_cleanup()
            self.fill_treeview_device_driver()
            self.fill_treeview_holdback()
            self.fill_treeview_available()
            self.fill_cmb_timezone_continent()
            self.fill_treeview_locale()
            if self.backports[0]:
                self.chkEnableBackports.set_active(True)
            else:
                self.chkBackportsDeviceDriver.set_sensitive(False)

        # Disable this for later implementation
        self.btnCreateKeyfile.set_visible(False)

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show()

    # ===============================================
    # Main window functions
    # ===============================================

    def on_btnCheckMirrorSpeed_clicked(self, widget):
        self.check_mirror_speed()

    def on_btnSaveBackports_clicked(self, widget):
        self.save_backports()

    def on_btnSaveMirrors_clicked(self, widget):
        self.save_mirrors()

    def on_btnCancel_clicked(self, widget):
        self.window.destroy()

    def on_btnRemoveHoldback_clicked(self, widget):
        self.remove_holdback()

    def on_btnHoldback_clicked(self, widget):
        self.add_holdback()

    def on_cmbTimezoneContinent_changed(self, widget):
        self.fill_cmb_timezone(self.cmbTimezoneContinentHandler.getValue())

    def on_btnSaveLocale_clicked(self, widget):
        self.save_locale()

    def on_btnEncrypt_clicked(self, widget):
        self.encrypt = True
        self.endecrypt()

    def on_btnDecrypt_clicked(self, widget):
        self.encrypt = False
        self.endecrypt()

    def on_btnChangePassphrase_clicked(self, widget):
        self.change_passphrase()
        
    def on_btnCreateKeyfile_clicked(self, widget):
        self.set_buttons_state(False)
        self.write_partition_configuration(True)
        self.set_buttons_state(True)

    def on_txtPassphrase1_changed(self, widget=None):
        self.check_passphrase()

    def on_txtPassphrase2_changed(self, widget=None):
        self.check_passphrase()

    def on_btnRefresh_clicked(self, widget):
        self.set_buttons_state(False)
        self.fill_treeview_partition()
        self.set_buttons_state(True)

    def on_btnHelp_clicked(self, widget):
        # Open the help file as the real user (not root)
        shell_exec("open-as-user \"%s\"" % self.helpFile)

    def on_tvPartitions_selection_changed(self, widget):
        self.save_my_partitions()
        
    def on_btnCleanup_clicked(self, widget):
        self.remove_unneeded_packages()
               
    def on_btnSaveFstabMounts_clicked(self, widget):
        self.save_fstab_mounts()
        
    def on_btnSaveDeviceDriver_clicked(self, widget):
        self.install_device_drivers()
    
    def on_btnLogDeviceDriver_clicked(self, widget):
        shell_exec("open-as-user \"%s\"" % self.log_file)
        
    def on_btnHelpDeviceDriver_clicked(self, widget):
        shell_exec("open-as-user \"%s\"" % self.helpddFile)
        
    # ===============================================
    # Fstab mount functions
    # ===============================================
    
    def fill_treeview_fstab_partitions(self):
        fs_partitions = []
        
        # Add headers
        fs_partitions.append([_('Add'), _('Partition'), _('Mount point'), _('Label')])
        
        for partition in self.partitions:
            if partition['fstab_mount']:
                fs_partitions.append([True, partition['device'], partition['fstab_mount'], partition['label']])
            else:
                # Do not show temporary mount point: it only confuses the user
                mount = partition['mount_point']
                if TMPMOUNT in mount:
                    mount = ''
                fs_partitions.append([False, partition['device'], mount, partition['label']])

        columnTypes = ['bool', 'str', 'str', 'str']
                
        # Fill treeview
        self.tvFstabMountsHandler.fillTreeview(contentList=fs_partitions, columnTypesList=columnTypes, firstItemIsColName=True, fontSize=12000)
        
    def save_fstab_mounts(self):
        changed = False
        fix_virtualbox = False
        fstab_path = '/etc/fstab'
        crypttab_path = '/etc/crypttab'
        crypttab_keyfile_path = '/.lukskey'

        fstab_cont = []
        with open(fstab_path, 'r') as f:
            fstab_cont = f.readlines()
        
        # Loop through the partitions
        model = self.tvFstabMounts.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            selected = model.get_value(itr, 0)
            device = model.get_value(itr, 1)
            mount = model.get_value(itr, 2)
            label = model.get_value(itr, 3).strip()
            uuid = ''
            fs_type = ''
            fstab_mount = ''

            # Get additional information
            for p in self.partitions:
                if p['device'] == device:
                    uuid = p['uuid']
                    fs_type = p['fs_type']
                    fstab_mount = p['fstab_mount']
                    encrypted = p['encrypted']
                    passphrase = p['passphrase']
                    break
                                   
            if selected and not fstab_mount:
                # Add information to fstab
                if (uuid or device) and fs_type:
                    # Decide new mount point
                    mount = join('/media', basename(device))
                    if label:
                        mount = join('/media', label.replace(' ', '_'))
                        
                    # Create mount directory and mount
                    if not exists(mount):
                        os.makedirs(mount)
                    
                    if exists(mount):
                        # Mount the device
                        shell_exec('mount {} {}'.format(device, mount))
                        usr = get_logged_user()
                        if usr:
                            # Make current user owner of the mount
                            shell_exec('chown {0}:{0} {1}'.format(usr, mount))
                    
                    # Create new line for fstab
                    uuid = 'UUID={}'.format(uuid) if uuid and not encrypted else device
                    fsck = 0 if fs_type in ('ntfs', 'swap', 'vfat') else 1 if mount == '/' else 2
                    opts = 'rw,errors=remount-ro' if 'ext' in fs_type else 'sw' if fs_type == 'swap' else 'defaults'
                    new_line = '%s\t%s\t%s\t%s\t0\t%s\n' % (uuid, mount, fs_type, opts, fsck)
                    fstab_cont.append(new_line)
                    changed = True
                    self.log.write('Add new line to {}: {}'.format(fstab_path, new_line), 'save_fstab_mounts')
                    
                    if encrypted:
                        fix_virtualbox = True
                        
                        # Only add key file if you can safe to another encrypted partition.
                        add_key = False
                        for p in self.partitions:
                            if p['mount_point'] == '/' and p['encrypted']:
                                add_key = True
                                break

                        enc_device = device.replace('/mapper', '')
                        if passphrase and add_key:
                            # Write keyfile
                            self.log.write('Add device to key file {}: {}'.format(crypttab_keyfile_path, enc_device), 'save_fstab_mounts', 'info')
                            create_keyfile(crypttab_keyfile_path, enc_device, passphrase)
                        else:
                            crypttab_keyfile_path = 'none'
                            
                        # Write crypttab
                        self.log.write('Add device to crypttab {}: {}'.format(crypttab_path, enc_device), 'save_fstab_mounts', 'info')
                        write_crypttab(enc_device, fs_type, crypttab_path, crypttab_keyfile_path, not encrypted)
                else:
                    # We should not get here
                    msg = _("Could not add {} to {}: missing fs type.".format(device, fstab_path))
                    self.log.write(msg, 'save_fstab_mounts')
                    WarningDialog(self.btnSaveFstabMounts.get_label(), msg)
                    continue
            elif not selected and fstab_mount:
                # Remove partition line from fstab
                for i, line in enumerate(fstab_cont):
                    if (uuid in line or device in line) and \
                        mount in line:
                        self.log.write('Remove device from {}: {}'.format(fstab_path, device), 'save_fstab_mounts', 'info')
                        del fstab_cont[i]
                        changed = True
                        break
                # Remove partition from crypttab
                if encrypted and exists(crypttab_path):
                    enc_device = device.replace('/mapper', '')
                    enc_device_uuid = get_uuid(enc_device)
                    #print(("+++ {} exists for device {}".format(crypttab_path, enc_device)))
                    crypttab_cont = []
                    with open(crypttab_path, 'r') as f:
                        crypttab_cont = f.readlines()
                    #print(("   {}".format(''.join(crypttab_cont))))
                    for i, line in enumerate(crypttab_cont):
                        #print(("+++ '{}' or '{}' exists '{}'".format(enc_device, enc_device_uuid, line)))
                        if enc_device in line or enc_device_uuid in line:
                            self.log.write('Remove device from crypttab {}: {}'.format(crypttab_path, enc_device), 'save_fstab_mounts', 'info')
                            del crypttab_cont[i]
                            with open(crypttab_path, 'w') as f:
                                f.write(''.join(crypttab_cont))
                            break
            
            # Get the next in line
            itr = model.iter_next(itr)
        
        if fix_virtualbox:
            # Fix VirtualBox by disabling Plymouth
            if in_virtualbox():
                grub_path = '/etc/default/grub'
                grubcfg_path = '/boot/grub/grub.cfg'
                if exists(grub_path) and exists(grubcfg_path):
                    self.log.write("Fix Grub in VirtualBox: %s and %s" % (grub_path, grubcfg_path), 'save_fstab_mounts', 'info')
                    shell_exec("sed -i 's/ *splash *//g' %s" % grub_path)
                    shell_exec("sed -i 's/ *splash *//g' %s" % grubcfg_path)

        if changed:
            # Save fstab
            with open(fstab_path, 'w') as f:
                f.write(''.join(fstab_cont))
                
            # Log fstab and crypttab  
            self.log.write(''.join(fstab_cont), 'save_fstab_mounts', 'info')
            if exists(crypttab_path):
                with open(crypttab_path, 'r') as f:
                    self.log.write(f.read(), 'save_fstab_mounts', 'info')
                    
            # Show a message
            msg = _("Changes were made to fstab.\n"
                    "Please reboot your computer for these changes to take effect.")
            MessageDialog(self.btnSaveFstabMounts.get_label(), msg)
        else:
            msg = _("No changes were made to fstab.")
            MessageDialog(self.btnSaveFstabMounts.get_label(), msg)
    
    # ===============================================
    # Device Driver functions
    # ===============================================
    
    def install_device_drivers(self):
        # Save selected hardware
        arguments = []

        model = self.tvDeviceDriver.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            action = 'no change'
            selected = model.get_value(itr, 0)
            device = model.get_value(itr, 2)
            manufacturerId = ''

            # Check currently selected state with initial state
            # This decides whether we should install or purge the drivers
            for hw in self.hardware[1:]:
                self.log.write('Device = {} in {}'.format(device, hw[2]), 'install_device_drivers')
                if device in hw[2]:
                    hw_driver = hw[3]
                    manufacturerId = hw[4]
                    if hw[0] and not selected:
                        action = 'purge'
                    elif not hw[0] and selected:
                        action = 'install'
                    break

            self.log.write('{}: {} ({})'.format(action, device, manufacturerId), 'install_device_drivers')

            # Install/purge selected driver
            option = ''
            if action == 'install':
                option = '-i'
            elif action == 'purge':
                option = '-p'

            if option:
                driver = ''
                # Run the manufacturer specific bash script
                if manufacturerId == '1002':
                    driver = 'amd'
                elif manufacturerId == '10de':
                    driver = 'nvidia '
                    # If nvidia-detect needs a drivers from the backports repository
                    # and the user didn't select the backports check box,
                    # force the use of backports to install the appropriate drivers
                    if 'backports' in hw_driver and not self.chkBackports.get_active():
                        option = "-b %s" % option
                elif manufacturerId == '14e4':
                    driver = 'broadcom '
                elif 'pae' in manufacturerId:
                    driver = 'pae '
                if driver:
                    arguments.append("{} {}".format(option, driver))

            # Get the next in line
            itr = model.iter_next(itr)

        # Execute the command
        if arguments:
            if '-i' in arguments and not has_internet_connection:
                title = _("No internet connection")
                msg = _("You need an internet connection to install the additional software.\n"
                        "Please, connect to the internet and try again.")
                WarningDialog(title, msg)
            else:
                # Warn for use of Backports
                if self.chkBackportsDeviceDriver.get_active():
                    answer = QuestionDialog(self.chkBackportsDeviceDriver.get_label(),
                            _("You have selected to install drivers from the backports repository whenever they are available.\n\n"
                              "Although you can run more up to date software using the backports repository,\n"
                              "you introduce a greater risk of breakage doing so.\n\n"
                              "Are you sure you want to continue?"))
                    if not answer:
                        self.chkBackportsDeviceDriver.set_active(False)
                        return True
                    arguments.append('-b')

                # Testing
                if self.test_devices:
                    arguments.append('-t')

                command = 'ddm {}'.format(' '.join(arguments))
                self.log.write('Command to execute: {}'.format(command), 'install_device_drivers')
                
                # Run driver installation in a thread and show progress
                name = 'driver'
                self.set_buttons_state(False)
                # Pass -g to let the ddm script know it is run from a GUI
                t = ExecuteThreadedCommands('{} -g'.format(command), self.queue)
                self.threads[name] = t
                t.daemon = True
                t.start()
                self.queue.join()
                GObject.timeout_add(250, self.check_thread, name)

    def fill_hw(self, driver_name, hw_lst):
        # Expected lspci output plus drivers:
        # driver name [manufacturer id:device id] [driver-1 driver-2 etc]
        regexp = '(.*)\[([0-9a-z]{4}):([0-9a-z]{4})\]\s+\[([0-9a-z\-]*)'
        for hw in hw_lst:
            matchObj = re.search(regexp, hw)
            if matchObj:
                #Check if driver is installed (check for multiple drivers)
                installed = False
                drivers = matchObj.group(4).split(' ')
                for drv in drivers:
                    if is_package_installed(drv):
                        installed = True
                    else:
                        break
                # Save the information
                self.hardware.append([installed, join(self.shareDir, 'images/{}.png'.format(driver_name)), matchObj.group(1), matchObj.group(4), matchObj.group(2), matchObj.group(3)])
                
    def fill_treeview_device_driver(self):
        # Fill a list with supported hardware
        self.hardware = []
        self.hardware.append([_("Install"), '', _("Device"), 'driver', 'manid', 'deviceid'])
        
        # Use test data (check /usr/lib/solydxk/scripts/ddm-*.sh)
        tst = ''
        if self.test_devices:
            tst = '-t -f'
        
        # Fill with supported hardware
        self.fill_hw('amd', getoutput('ddm -i amd -s {}'.format(tst)))
        self.fill_hw('nvidia', getoutput('ddm -i nvidia -s {}'.format(tst)))
        self.fill_hw('broadcom', getoutput('ddm -i broadcom -s {}'.format(tst)))
        self.fill_hw('pae', getoutput('ddm -i pae -s {}'.format(tst)))
        
        print((self.hardware))

        # columns: checkbox, image (logo), device, driver
        columnTypes = ['bool', 'GdkPixbuf.Pixbuf', 'str']

        # Keep some info from the user
        showHw = []
        for hw in self.hardware:
            showHw.append([hw[0], hw[1], hw[2]])

        # Fill treeview
        self.tvDeviceDriverHandler.fillTreeview(contentList=showHw, columnTypesList=columnTypes, firstItemIsColName=True, fontSize=12000)

    # ===============================================
    # Encryption functions
    # ===============================================

    def save_my_partitions(self):
        # Get selected partition paths from tvPartitions
        self.my_partitions = []
        my_swap = []
        selected_rows = self.tvPartitionsHandler.getSelectedRows()
        for selected_row in selected_rows:
            device = selected_row[1][1]
            for p in self.partitions:
                if p['device'] == device:
                    if p['fs_type'] == 'swap':
                        my_swap.append(p)
                    else:
                        self.my_partitions.append(p)
                        break

        # Make sure a swap partitions are done last
        # Need that in write_partition_configuration
        if my_swap:
            self.my_partitions.extend(my_swap)

    def endecrypt(self):
        name = 'endecrypt'
        action = self.btnDecrypt.get_label()
        
        # Check passphrase first
        if self.encrypt:
            action = self.btnEncrypt.get_label()
            if self.my_passphrase == '':
                # Message user for passphrase
                MessageDialog(action, self.no_passphrase_msg)
                return
        else:
            self.my_passphrase = ''
        
        if self.my_partitions:
            # Search for a backup directory
            backup_partition = self.get_backup_partition()
            if not backup_partition:
                print(("ERROR: no backup directory"))
                return
            
            for p in self.my_partitions:
                is_swap = p['fs_type'] == 'swap'
                if self.encrypt:
                    if p['encrypted']:
                        if p['mount_point']:
                            answer = QuestionDialog(_("Encrypted partition"),
                                                    _("The partition {0} is already encrypted.\n"
                                                      "Continuing will change the encryption key of this partition.\n\n"
                                                      "Do you want to continue?".format(p['device'])))
                            if not answer:
                                return
                        elif not is_swap:
                            current_passphrase = self.get_passphrase_dialog(p['device'])
                            if current_passphrase:
                                device, mount, filesystem = self.temp_mount(p, current_passphrase)
                                if mount:
                                    p['passphrase'] = current_passphrase
                                    p['device'] = device
                                    p['mount_point'] = mount
                                    p['fs_type'] = filesystem
                                else:
                                    self.log.write(self.mount_error.format(p['device']), name, 'error')
                                    return
                else:
                    if not p['encrypted']:
                        # Message the user that the partition is not encrypted
                        msg = _("The partition is not encrypted.\n"
                                "Please choose another partition to decrypt.")
                        self.log.write(msg, name, 'error')
                        return

                    # For safety reasons the encrypted partition needs to be mounted
                    if not p['mount_point'] and not is_swap:
                        current_passphrase = self.get_passphrase_dialog(p['device'])
                        if current_passphrase:
                            device, mount, filesystem = self.temp_mount(p, current_passphrase)
                            if mount:
                                p['passphrase'] = current_passphrase
                                p['device'] = device
                                p['mount_point'] = mount
                                p['fs_type'] = filesystem
                            else:
                                self.log.write(self.mount_error.format(p['device']), name, 'error')
                                return

                # Mount partition if not already mounted
                if not p['mount_point'] and not is_swap:
                    device, mount, filesystem = self.temp_mount(p, self.my_passphrase)
                    self.log.write("Mount (for creating backup) %s to %s" % (device, mount), name, 'info')
                    if mount:
                        p['device'] = device
                        p['mount_point'] = mount
                        p['fs_type'] = filesystem
                    else:
                        self.log.write(self.mount_error.format(p['device']), name, 'error')
                        return
                        
            # Run encrypt/decrypt in separate thread
            self.set_buttons_state(False)
            t = EnDecryptPartitions(self.my_partitions, backup_partition, self.encrypt, self.my_passphrase, self.queue, self.log)
            self.threads[name] = t
            t.daemon = True
            t.start()
            self.queue.join()
            GObject.timeout_add(5, self.check_thread, name)

    def change_passphrase(self):
        if len(self.my_partitions) == 0:
            return
        
        # Check passphrase first
        if not self.my_passphrase:
            # Message user for passphrase
            MessageDialog(self.btnChangePassphrase.get_label(), self.no_passphrase_msg)
            return
            
        for p in self.my_partitions:
            if not p['encrypted']:
                # Message the user that the partition is not encrypted
                msg = _("%s is not encrypted.\n"
                        "Please choose an encrypted partition." % p['device'])
                MessageDialog(self.btnChangePassphrase.get_label(), msg)
                return

        # Run encrypt/decrypt in separate thread
        self.changed_devices = []
        name = 'changepassphrase'
        self.set_buttons_state(False)
        t = ChangePassphrase(self.my_partitions, self.my_passphrase, self.queue, self.log)
        self.threads[name] = t
        t.daemon = True
        t.start()
        self.queue.join()
        GObject.timeout_add(250, self.check_thread, name)

    def is_active_swap_partition(self, device):
        out = getoutput('grep "{}" /proc/swaps'.format(device))[0]
        if out:
            return True
        return False
    
    def fill_treeview_partition(self):
        # Exclude these device paths
        exclude_devices = ['/dev/sr0', '/dev/sr1', '/dev/cdrom', '/dev/dvd', '/dev/fd0', '/dev/mmcblk0boot0', '/dev/mmcblk0boot1', '/dev/mmcblk0rpmb']

        # columns: encrypted image, partition path, fs type, size, free space
        column_types = ['GdkPixbuf.Pixbuf', 'str', 'str', 'str', 'str', 'str', 'str']

        # List partition info
        self.my_partitions = []
        self.partitions = []
        tmp_partitions = []
        self.udisks2.fill_devices(flash_only=False)
        for device_path in self.udisks2.devices:
            if device_path not in exclude_devices:
                device = self.udisks2.devices[device_path]
                # Exclude the root partition, home partition, boot partitions and swap
                if not '/boot' in device['mount_point'] and \
                   device['mount_point'] != '/' and \
                   device['mount_point'] != '/home' and \
                   not self.is_active_swap_partition(device_path):
                    tmp_partitions.append({'device': device_path,
                                                'old_device': device_path,
                                                'fs_type': device['fs_type'],
                                                'label': device['label'],
                                                'total_size': device['total_size'],
                                                'free_size': device['free_size'],
                                                'used_size': device['used_size'],
                                                'encrypted': is_encrypted(device_path),
                                                'passphrase': '',
                                                'mount_point': device['mount_point'],
                                                'old_mount_point': device['mount_point'],
                                                'uuid': device['uuid'],
                                                'old_uuid': device['uuid'],
                                                'removable': device['removable'],
                                                'has_grub': device['has_grub']
                                               })
        self.failed_mount_devices = []
        for partition in tmp_partitions:
            # Get fstab information
            fstab_path, fstab_device, fstab_mount, fstab_cont, crypttab_path, keyfile_path = self.get_partition_configuration_info(partition, tmp_partitions)
            partition['fstab_path'] = fstab_path
            partition['fstab_device'] = fstab_device
            partition['fstab_mount'] = fstab_mount
            partition['fstab_cont'] = fstab_cont
            partition['crypttab_path'] = crypttab_path
            partition['keyfile_path'] = keyfile_path

            # Only add swap and root if /boot is configured in fstab
            can_encrypt = False
            if fstab_mount == '/' or fstab_mount == 'swap':
                # Check for /boot partition in fstab_cont
                p = re.compile('.*\s/boot\s')
                lines = p.findall(fstab_cont)
                for line in lines:
                    if line[:1] != '#':
                        can_encrypt = True
                        break
            elif fstab_mount == '/boot':
                    self.boot_partition = partition
            elif not '/boot' in fstab_mount:
                can_encrypt = True

            if can_encrypt:
                print(">>> partition = %s" % str(partition))
                self.partitions.append(partition)

        # Sort the list with dictionaries
        self.partitions = sorted(self.partitions, key=lambda k: k['device'])

        # Create human readable list of partitions
        hr_list = [['', _('Partition'), _('Label'), _('File system'), _('Total size'), _('Free size'), _('Mount point')]]
        for p in self.partitions:
            if p['encrypted']:
                if p['removable']:
                    enc_img = join(self.shareDir, 'icons/encrypted-usb.png')
                else:
                    enc_img = join(self.shareDir, 'icons/encrypted.png')
            else:
                if p['removable']:
                    enc_img = join(self.shareDir, 'icons/unencrypted-usb.png')
                else:
                    enc_img = join(self.shareDir, 'icons/unencrypted.png')
            ts = human_size(p['total_size'])
            fs = ''
            if p['free_size'] > 0:
                fs = human_size(p['free_size'])
            hr_list.append([enc_img, p['device'], p['label'], p['fs_type'], ts, fs, p['mount_point']])

        # Fill treeview
        self.tvPartitionsHandler.fillTreeview(contentList=hr_list,
                                              columnTypesList=column_types,
                                              firstItemIsColName=True,
                                              multipleSelection=True)
                                              
        # Refresh fstab mount treeviews as well
        self.fill_treeview_fstab_partitions()

    def check_passphrase(self):
        self.my_passphrase = ''
        pf1 = self.txtPassphrase1.get_text().strip()
        pf2 = self.txtPassphrase2.get_text().strip()
        if pf1 == '' and pf2 == '':
            self.imgPassphraseCheck.hide()
        else:
            self.imgPassphraseCheck.show()
        if pf1 != pf2 or len(pf1) < 6:
            self.imgPassphraseCheck.set_from_stock(Gtk.STOCK_NO, Gtk.IconSize.BUTTON)
        else:
            self.imgPassphraseCheck.set_from_stock(Gtk.STOCK_OK, Gtk.IconSize.BUTTON)
            self.my_passphrase = pf1

    def get_backup_partition(self):
        # Set a safe margin to have extra available on the backup partition
        safe_margin_kb = 10240
        
        # Search for mounted partition with enough space to backup the selected partition
        bak_str = _("Backup")
        system_partitions = ['/home', '/']
        bak_partition = ''
        used_size = 0

        # Get the combined used size of the selected partitions, except the swap partition
        for my_p in self.my_partitions:
            if my_p['fs_type'] != 'swap':
                used_size += my_p['used_size']
                
        # Add the safe margin
        used_size += safe_margin_kb

        # First check booted system partitions
        for my_p in self.my_partitions:
            if not bak_partition:
                for sp in system_partitions:
                    if sp != my_p['mount_point']:
                        st = os.statvfs(sp)
                        free_size = (st.f_bavail * st.f_frsize) / 1024
                        if free_size > used_size:
                            bak_partition = sp
                            break

            # Check other mounted devices
            if not bak_partition:
                for p in self.partitions:
                    if p['device'] != my_p['device'] and \
                       p['mount_point'] != '' and \
                       p['free_size'] > used_size:
                        bak_partition = p['mount_point']
                        break

        # If not enough space: exit with message
        if not bak_partition:
            msg = _("You need a backup partition with at least %s free.\n"
                    "Mount a backup drive and hit the refresh button." % human_size(used_size))
            MessageDialog(bak_str, msg)

        return bak_partition

    def sort_fstab(self, fstab_path):
        # Sort the contents of fstab
        cont = ''
        sort_lst = []
        sorted_lst = []
        fstab_lines = []

        with open(fstab_path, 'r') as f:
            fstab_lines = f.readlines()

        for line in fstab_lines:
            line = line.strip()
            if line[0:1] == '#':
                line_added = False
                if not sorted_lst:
                    # First line in fstab is commented
                    sorted_lst.append(line)
                    line_added = True
                if sort_lst:
                    # Sort list on mount point
                    sort_lst = sorted(sort_lst, key=lambda x: x[1])
                for sort_line in sort_lst:
                    # Add sorted line to list
                    sorted_lst.append('\t'.join(sort_line))
                # Cleanup before next iteration
                sort_lst = []
                if not line_added:
                    # Add empty line for readability
                    sorted_lst.append('')
                    # Add comment
                    sorted_lst.append(line)
            else:
                # Add mount device line
                lst = line.split()
                if len(lst) == 6:
                    sort_lst.append(lst)

        # Add left overs
        if sort_lst:
            sort_lst = sorted(sort_lst, key=lambda x: x[1])
        for sort_line in sort_lst:
            sorted_lst.append('\t'.join(sort_line))

        # Create the sorted fstab contents
        if sorted_lst:
            cont = '\n'.join(sorted_lst) + '\n'

        return cont
        
    def get_partition_configuration_info(self, partition, partitions):
        fstab_paths = ['/etc/fstab']

        # Search for fstab file if you're in a live session
        for p in partitions:
            if not p['mount_point'] \
               and p['fs_type'] != 'swap' \
               and p['device'] not in self.failed_mount_devices:
                current_passphrase = ''
                if p['encrypted']:
                    # This is an encrypted, not mounted partition.
                    # Ask the user for the passphrase
                    current_passphrase = self.get_passphrase_dialog(p['device'])
                device, mount, filesystem = self.temp_mount(p, current_passphrase)
                
                # Save necessary information
                p['fs_type'] = filesystem
                p['passphrase'] = current_passphrase
                p['device'] = device
                
                if mount:
                    #print((">> Save %s: mount=%s, fs_type=%s" % (device, mount, filesystem)))
                    p['mount_point'] = mount

                    # Get free_size from mapped path
                    total, free, used = self.udisks2.get_mount_size(mount)
                    p['free_size'] = free
                    p['used_size'] = used
                    
                    # Get label
                    p['label'] = get_label(device)
                    
                #print(("++++ p = %s" % str(p)))
                if not mount:
                    show_error = True
                    #print((">>>> Could not mount %s (%s)" % (p['device'], p['fs_type'])))
                    if 'crypt' in p['fs_type'] or p['fs_type'] == 'swap' or p['fs_type'] == '':
                        # Don't show error
                        show_error = False
                    self.log.write(self.mount_error.format(p['device']), 'get_partition_configuration_info', 'error', show_error)
                    if p['device'] not in self.failed_mount_devices:
                        self.failed_mount_devices.append(p['device'])
            if p['mount_point']:
                # Add fstab path
                fstab_path = join(p['mount_point'], 'etc/fstab')
                if exists(fstab_path) and not fstab_path in fstab_paths:
                    fstab_paths.append(fstab_path)
            
        # Check if given partition is listed in /etc/fstab
        for fstab_path in fstab_paths:
            fstab_cont = self.sort_fstab(fstab_path)
            fstab_mount = ''
            
            fstab_device = partition['old_device'].replace('/dev/mapper', '/dev')
            if not 'mapper' in fstab_device:
                fstab_device = fstab_device.replace('/dev', '/dev/mapper')

            regexp = "(%s|%s|%s)\s+(\S+)" % ("UUID=%s" % partition['old_uuid'], partition['old_device'], fstab_device)
            #print(("++++ regexp = %s" % regexp))
            matchObj = re.search(regexp, fstab_cont)
            if matchObj:
                fstab_device = matchObj.group(1)
                fstab_mount = matchObj.group(2)
            if fstab_mount:
                # Set fs_type for swap partitions
                if fstab_mount == 'swap':
                    partition['fs_type'] = 'swap'
                    
                # Get encryption information
                crypttab_path = ''
                keyfile_path = ''
                #print(("**** crypttab partition: %s" % str(partition)))
                if partition['encrypted']:
                    crypttab_path = fstab_path.replace('fstab', 'crypttab')
                    #print(("++++ crypttab_path=%s" % crypttab_path))
                    if exists(crypttab_path):
                        lines = []
                        with open(crypttab_path, 'r') as f:
                            lines = f.readlines()
                        for line in lines:
                            line = line.strip()
                            lineData = line.split()
                            #print(("++++ lineData=%s" % str(lineData)))
                            matchObj = re.search('[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12}', lineData[1])
                            if matchObj:
                                crypttab_uuid = matchObj.group(0)
                                #print(("++++ crypttab_uuid=%s" % crypttab_uuid))
                                device = get_device_from_uuid(crypttab_uuid)
                                #print(("++++ device=%s, partition['device']=%s" % (device, partition['device'])))
                                if basename(device) == basename(partition['device']):
                                    # Get crypttab data
                                    crypttab_keyfile_path = lineData[2]
                                    if crypttab_keyfile_path == 'none':
                                        crypttab_keyfile_path = ''
                                    if crypttab_keyfile_path:
                                        # Search the keyfile path
                                        crypttab_keyfile_dir = dirname(crypttab_keyfile_path)
                                        regexp = "([0-9a-z-/]+)\s+{0}\s+".format(crypttab_keyfile_dir.replace('/', '\/'))
                                        #print(("++++ regexp = %s" % regexp))
                                        matchObj = re.search(regexp, fstab_cont)
                                        if matchObj:
                                            keyfile_device = matchObj.group(1)
                                            if keyfile_device[:1] != '/':
                                                keyfile_device = get_device_from_uuid(keyfile_device)
                                            #print(("++++ keyfile_device = %s" % keyfile_device))
                                            #print(self.partitions)
                                            for p in self.partitions:
                                                #print(("    ++++ bn_device = %s, bn_keyfile_device = %s" % (basename(p['device']), basename(keyfile_device))))
                                                if basename(p['device']) == basename(keyfile_device):
                                                    keyfile_path = join(p['mount_point'], crypttab_keyfile_path.lstrip('/'))
                                                    #print(("        ++++ keyfile_path = %s" % keyfile_path))
                                                    break
                                    break
                return (fstab_path, fstab_device, fstab_mount, fstab_cont, crypttab_path, keyfile_path)
                
        # Nothing found
        return ('', '', '', '', '', '')

    def write_partition_configuration(self, keyfile_only=False):
        keyfile_path = ''
        crypttab_keyfile_path = None
        encrypt_info = []
        saved_fstabs = {}
        grub_partitions = []
        root_devices = []
        
        # Make sure to only write those partitions that are already in fstab
        for p in self.my_partitions:
            # Get fstab path for this partition
            if not p['fstab_path']:
                continue

            # Check if Grub has been installed on this partition
            if p['has_grub']:
                grub_partitions.append(p['device'].replace('/mapper', ''))

            # Save the boot devices for Grub update
            if p['fstab_mount'] == '/':
                root_devices.append(p['device'].replace('/mapper', ''))

            # Set uuid string if not mapped device
            device = p['device']
            if not '/dev/mapper' in p['device']:
                device = "UUID=%s" % p['uuid']
            
            # Check if fstab contents has changed before
            try:
                fstab_cont = saved_fstabs[p['fstab_path']]
            except:
                fstab_cont = p['fstab_cont']
            
            # Rewrite this device in fstab
            fstab_cont = re.sub(p['fstab_device'], device, fstab_cont)
            saved_fstabs[p['fstab_path']] = fstab_cont
            
            # Save configuration information
            skip_keyfile_config = False
            if p['encrypted'] and p['fstab_mount']:
                # Get the keyfile path and the path it will have in the crypttab file
                if not keyfile_path and p['fs_type'] != 'swap':
                    skip_keyfile_config = True
                    keyfile_path = join(p['mount_point'], '.lukskey')
                    crypttab_keyfile_path = join(p['fstab_mount'], '.lukskey')
                    
            # Create a dictionary with the info
            info_dict = {}
            info_dict['device'] = p['device']
            info_dict['fs_type'] = p['fs_type']
            info_dict['fstab_path'] = p['fstab_path']
            info_dict['keyfile_path'] = ''
            info_dict['crypttab_keyfile_path'] = ''
            info_dict['passphrase'] = p['passphrase']
            if not skip_keyfile_config:
                self.log.write("Path to luks key file: %s" % keyfile_path, 'write_partition_configuration', 'info')
                self.log.write("Crypttab luks key file path: %s" % crypttab_keyfile_path, 'write_partition_configuration', 'info')
                info_dict['keyfile_path'] = keyfile_path
                info_dict['crypttab_keyfile_path'] = crypttab_keyfile_path
            
            # Append the dictionary to the list
            encrypt_info.append(info_dict)

            # Crypttab
            if not p['encrypted'] and not keyfile_only:
                # Remove device from crypttab
                bn = basename(p['device'])
                self.log.write("Remove %s from %s" % (bn, p['crypttab_path']), 'write_partition_configuration', 'info')
                cmd = "sed -i '/^%s /d' %s" % (bn, p['crypttab_path'])
                shell_exec(cmd)
                
                # Remove any references of a key file when the key file is on this decrypted and unsafe partition
                lukskey = join(p['mount_point'], '.lukskey')
                if exists(lukskey):
                    self.log.write("Remove %s from unencrypted and unsafe %s" % (lukskey, p['device']), 'write_partition_configuration', 'info')
                    os.remove(lukskey)
                self.log.write("Remove %s references from %s" % (lukskey, p['crypttab_path']), 'write_partition_configuration', 'info')
                cmd = "sed -i 's#%s#none#g' %s" % (lukskey, p['crypttab_path'])
                shell_exec(cmd)
            
        # Write the new content to the fstab files, the key files and crypttab files
        saved_fstab = ''
        for enc_dict in encrypt_info:
            if not keyfile_only and saved_fstab != enc_dict['fstab_path']:
                saved_fstab = enc_dict['fstab_path']
                # Logging
                self.log.write("%s blkid %s" % ('=' * 10, '=' * 10), 'write_partition_configuration', 'info')
                self.log.write('\n'.join(getoutput("blkid")), 'write_partition_configuration', 'info')
                self.log.write("%s %s %s" % ('=' * 10, enc_dict['fstab_path'], '=' * 10), 'write_partition_configuration', 'info')
                self.log.write(saved_fstabs[enc_dict['fstab_path']], 'write_partition_configuration', 'info')
                self.log.write('=' * 25, 'write_partition_configuration', 'info')
                
                # Fstab
                with open(enc_dict['fstab_path'], 'w') as f:
                    f.write(saved_fstabs[enc_dict['fstab_path']])

            # Key file
            if enc_dict['keyfile_path']:
                pf = self.my_passphrase
                if keyfile_only and enc_dict['passphrase']:
                    pf = enc_dict['passphrase']
                if pf:
                    create_keyfile(enc_dict['keyfile_path'], enc_dict['device'].replace('/mapper', ''), pf)

            #print(("++++ keyfile_only=%s" % str(keyfile_only)))
            if not keyfile_only:
                # Crypttab
                #print(("++++ Start write_crypttab"))
                write_crypttab(enc_dict['device'].replace('/mapper', ''), enc_dict['fs_type'], p['crypttab_path'], enc_dict['crypttab_keyfile_path'], not self.encrypt)

                # Log crypttab
                if exists(p['crypttab_path']):
                    self.log.write("%s %s %s" % ('=' * 10, p['crypttab_path'], '=' * 10), 'write_partition_configuration', 'info')
                    with open(p['crypttab_path'], 'r') as f:
                        self.log.write(f.read(), 'write_partition_configuration', 'info')
                    self.log.write('=' * 25, 'write_partition_configuration', 'info')
                    
        # Get the grub path to fix VirtualBox by disabling Plymouth
        if in_virtualbox() and self.encrypt:
            grub_path = ''
            grubcfg_path = ''
            for p in self.partitions:
                #print(("---- %s" % str(p)))
                if p['fstab_mount'] == '/':
                    grub_path = join(p['mount_point'], 'etc/default/grub')
                    grubcfg_path = join(p['mount_point'], 'boot/grub/grub.cfg')
                    break
            if not self.boot_partition is None:
                mount = self.boot_partition['mount_point']
                if not mount:
                    self.log.write("Mount /boot partition %s" % self.boot_partition['device'], 'write_partition_configuration', 'info')
                    device, mount, filesystem = self.temp_mount(p, self.my_passphrase)
                if mount:
                    grubcfg_path = join(self.boot_partition['mount_point'], 'grub/grub.cfg')

            #print((">>> grub_path=%s, grubcfg_path=%s" % (grub_path, grubcfg_path)))
            if grub_path and grubcfg_path:
                self.log.write("Fix Grub in VirtualBox: %s and %s" % (grub_path, grubcfg_path), 'write_partition_configuration', 'info')
                shell_exec("sed -i 's/ *splash *//g' %s" % grub_path)
                shell_exec("sed -i 's/ *splash *//g' %s" % grubcfg_path)

        if not keyfile_only:
            pf = ''
            if self.encrypt:
                pf = self.my_passphrase
            # Restore Grub when encrypting a root device
            for grub_partition in grub_partitions:
                cmd = "grub-install --force %s;exit" % grub_partition
                shell_exec("chroot-partition %s \"%s\" \"%s\"" % (grub_partition, pf, cmd))
            for root_device in root_devices:
                if not grub_partitions:
                    cmd = "grub-install --force %s;" % root_device.rstrip('0123456789')
                cmd += "update-initramfs -u;update-grub;exit"
                shell_exec("chroot-partition %s \"%s\" \"%s\"" % (root_device, pf, cmd))

    # ===============================================
    # Localization functions
    # ===============================================

    def save_locale(self):
        # Collect information
        locales = self.tvLocaleHandler.model_to_list()
        timezone = join(self.cmbTimezoneContinentHandler.getValue(),
                        self.cmbTimezoneHandler.getValue())

        # Run localization in a thread and show progress
        name = 'localize'
        self.set_buttons_state(False)
        t = Localize(locales, timezone, self.queue)
        self.threads[name] = t
        t.daemon = True
        t.start()
        # TODO: why is queue.join sometimes blocking the thread but not always?
        #self.queue.join()
        GObject.timeout_add(250, self.check_thread, name)

    def fill_treeview_locale(self):
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
        col_type_lst = ['bool', 'str', 'str', 'bool']
        self.tvLocaleHandler.fillTreeview(self.locales, col_type_lst, select_row, 400, True)

    def fill_cmb_timezone_continent(self):
        self.cmbTimezoneContinentHandler.fillComboBox(self.locale_info.timezone_continents,
                                                      self.locale_info.current_timezone_continent)
        self.fill_cmb_timezone(self.cmbTimezoneContinentHandler.getValue())

    def fill_cmb_timezone(self, timezone_continent):
        timezones = self.locale_info.list_timezones(timezone_continent)
        self.cmbTimezoneHandler.fillComboBox(timezones,
                                             self.locale_info.current_timezone)

    def on_tvLocale_toggled(self, obj, path, colNr, toggleValue):
        path = int(path)
        model = self.tvLocale.get_model()
        selectedIter = model.get_iter(path)
        if not toggleValue:
            model[selectedIter][3] = True
            return

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

    def fill_treeview_holdback(self):
        self.holdback = []
        lst = getoutput("env LANG=C dpkg --get-selections | grep hold$ | awk '{print $1}'")
        for pck in lst:
            if pck != '':
                self.holdback.append([False, pck.strip()])
        # Fill treeview
        col_type_lst = ['bool', 'str']
        self.tvHoldbackHandler.fillTreeview(self.holdback, col_type_lst, 0, 400, False)

    def fill_treeview_available(self):
        self.available = []
        lst = getoutput("env LANG=C dpkg --get-selections | grep install$ | awk '{print $1}'")
        for pck in lst:
            self.available.append([False, pck.strip()])
        # Fill treeview
        col_type_lst = ['bool', 'str']
        self.tvAvailableHandler.fillTreeview(self.available, col_type_lst, 0, 400, False)

    def add_holdback(self):
        packages = self.tvAvailableHandler.getToggledValues()
        for pck in packages:
            self.log.write("Hold back package: %s" % pck, 'add_holdback')
            shell_exec("echo '%s hold' | dpkg --set-selections" % pck)
        self.fill_treeview_holdback()
        self.fill_treeview_available()

    def remove_holdback(self):
        packages = self.tvHoldbackHandler.getToggledValues()
        for pck in packages:
            self.log.write("Remove hold back from: %s" % pck, 'remove_holdback')
            shell_exec("echo '%s install' | dpkg --set-selections" % pck)
        self.fill_treeview_holdback()
        self.fill_treeview_available()

    # ===============================================
    # Mirror functions
    # ===============================================

    def save_backports(self):
        sources_path  = '/etc/apt/sources.list'
        sources_changed = False

        if self.chkEnableBackports.get_active():
            self.backports = get_backports(False)
            # Check which regular repository is enabled
            debian_domain = ''
            matchObj = re.search("([a-z0-9\.]+)debian\.org", self.current_debian_repo)
            if matchObj:
                debian_domain = "{}debian.org".format(matchObj.group(1))
            # Create backports line for sources.list
            if self.debian_name and debian_domain:
                backports_name = "{}-backports".format(self.debian_name)
                uncomment = False
                for bp in self.backports:
                    if debian_domain in bp:
                        self.log.write("Uncomment line in sources.list: %s" % bp, 'save_backport')
                        uncomment = True
                        break
                if uncomment:
                    comment_line(sources_path, backports_name, False)
                    sources_changed = True
                else:
                    # Add new line
                    repo_line = "deb http://{debian_domain}/debian/ {backports_name} main contrib non-free".format(debian_domain=debian_domain, backports_name=backports_name)
                    self.log.write("Add line to sources.list: %s" % repo_line, 'save_backport')
                    with open(sources_path, 'a') as f:
                        f.write(repo_line)
                    sources_changed = True
        else:
            # Comment the backports repository entry in sources.list
            comment = False
            self.backports = get_backports()
            backports_name = "{}-backports".format(self.debian_name)
            for bp in self.backports:
                if backports_name in bp:
                    comment = True
            if comment:
                self.log.write("Comment line in sources.list with pattern: %s" % backports_name, 'save_backport')
                comment_line(sources_path, backports_name)
                sources_changed = True

        # Update the apt cache
        if sources_changed:
            if has_internet_connection():
                # Run update in a thread and show progress
                name = 'updatebp'
                self.set_buttons_state(False)
                t = ExecuteThreadedCommands("apt-get update", self.queue)
                self.threads[name] = t
                t.daemon = True
                t.start()
                self.queue.join()
                GObject.timeout_add(250, self.check_thread, name)
            else:
                msg = _("Could not update the apt cache.\n"
                        "Please update the apt cache manually with: apt-get update")
                WarningDialog(self.btnSaveBackports.get_label(), msg)
        else:
            msg = _("Nothing to do.")
            MessageDialog(self.btnSaveBackports.get_label(), msg)
            
        # Make sure the current state is saved
        # and that the backports checkbox for devices is enabled/disabled
        self.backports = get_backports()
        if self.backports[0]:
            self.chkBackportsDeviceDriver.set_sensitive(True)
        else:
            self.chkBackportsDeviceDriver.set_sensitive(False)

    def fill_treeview_mirrors(self):
        # Fill mirror list
        if len(self.mirrors) > 1:
            # Fill treeview
            col_type_lst = ['bool', 'str', 'str', 'str', 'str']
            self.tvMirrorsHandler.fillTreeview(self.mirrors, col_type_lst, 0, 400, True)

            # TODO - We have no mirrors: hide the tab until we do
            #self.nbPref.get_nth_page(1).set_visible(False)
        else:
            self.nbPref.get_nth_page(1).set_visible(False)

    def save_mirrors(self):
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
                if has_internet_connection():
                    # Run update in a thread and show progress
                    name = 'updatebp'
                    self.set_buttons_state(False)
                    t = ExecuteThreadedCommands("apt-get update", self.queue)
                    self.threads[name] = t
                    t.daemon = True
                    t.start()
                    self.queue.join()
                    GObject.timeout_add(250, self.check_thread, name)
                else:
                    msg = _("Could not update the apt cache.\n"
                            "Please update the apt cache manually with: apt-get update")
                    WarningDialog(self.btnSaveMirrors.get_label(), msg)
            else:
                self.log.write(ret, 'save_mirrors')

        else:
            msg = _("There are no repositories to save.")
            MessageDialog(self.lblRepositories.get_label(), msg)

    def get_mirrors(self):
        mirrors = [[_("Current"), _("Country"), _("Repository"), _("URL"), _("Speed")]]
        for mirror in self.activeMirrors:
            if mirror:
                self.log.write("Mirror data: %s" % ' '.join(mirror), 'get_mirrors')
                blnCurrent = self.is_url_in_sources(mirror[2])
                # Save current debian repo in a variable
                if blnCurrent and 'debian.org' in mirror[2]:
                    self.current_debian_repo = mirror[2]
                mirrors.append([blnCurrent, mirror[0], mirror[1], mirror[2], ''])
        return mirrors

    def is_url_in_sources(self, url):
        url = "://%s" % url
        blnRet = False

        for repo in get_local_repos():
            if url in repo:
                blnRet = True
                for excl in self.excludeMirrors:
                    if excl in repo:
                        blnRet = False
                        break
                break
        return blnRet

    def check_mirror_speed(self):
        name = 'mirrorspeed'
        self.set_buttons_state(False)
        t = MirrorGetSpeed(self.mirrors, self.queue)
        self.threads[name] = t
        t.daemon = True
        t.start()
        self.queue.join()
        GObject.timeout_add(5, self.check_thread, name)

    def write_speed(self, url, speed):
        model = self.tvMirrors.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            repo = model.get_value(itr, 3)
            if repo == url:
                self.log.write("Mirror speed for %s = %s" % (url, speed), 'write_speed')
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
    # Cleanup functions
    # ===============================================
    
    def fill_treeview_cleanup(self):
        pck_data = []
        # Get list of packages from autoremove and deborphan
        for pck in self.get_autoremove_packages():
            pck_data.append([True, pck])
        for pck in self.get_deborphan_packages():
            pck_data.append([False, pck])
        # Fill treeview
        col_type_lst = ['bool', 'str']
        self.tvCleanupHandler.fillTreeview(pck_data, col_type_lst, 0, 400, False)
        
    def get_autoremove_packages(self):
        ret = []
        # Create approriate command
        # Use env LANG=C to ensure the output of dist-upgrade is always en_US
        cmd = "env LANG=C sudo apt-get autoremove --assume-no | grep -E '^ '"
        lst = getoutput(cmd)

        # Loop through each line and fill the package lists
        for line in lst:
            packages = line.split()
            for package in packages:
                package = package.strip().replace('*', '')
                if package and package not in ret:
                    ret.append(package)
        return ret
        
    def get_deborphan_packages(self):
        orphans = getoutput('deborphan')
        if len(orphans) == 1 and orphans[0] == '':
            orphans = []
        return orphans
        
    def remove_unneeded_packages(self):
        force = get_apt_force()
        packages = []
        # Build list with selected packages
        model = self.tvCleanup.get_model()
        itr = model.get_iter_first()
        while itr is not None:
            if model.get_value(itr, 0):
                packages.append(model.get_value(itr, 1))
            itr = model.iter_next(itr)
        if packages:
            # Run cleanup in a thread and show progress
            name = 'cleanup'
            self.set_buttons_state(False)
            t = ExecuteThreadedCommands("apt-get {0} clean; apt-get purge {0} {1}".format(force, ' '.join(packages)), self.queue)
            self.threads[name] = t
            t.daemon = True
            t.start()
            self.queue.join()
            GObject.timeout_add(250, self.check_thread, name)

    # ===============================================
    # General functions
    # ===============================================

    def check_thread(self, name):
        if self.threads[name].is_alive():
            if 'update' in name or name == 'cleanup' or name == 'driver':
                self.update_progress(0.1, True)
            if not self.queue.empty():
                ret = self.queue.get()
                self.queue.task_done()
                if ret:
                    self.log.write("Queue returns: {}".format(ret), 'check_thread')
                    if name == 'mirrorspeed':
                        self.update_progress(1 / (ret[3] / ret[2]))
                        self.write_speed(ret[0], ret[1])
                    elif name == 'localize':
                        self.update_progress(1 / (ret[0] / ret[1]))
                    elif name == 'endecrypt':
                        # Queue returns list: [fraction, error_code, partition_index, partition, message]
                        self.endecrypt_success = True
                        self.update_progress(ret[0])
                        if ret[1] > 0:
                            self.log.write(str(ret[4]), name, 'error')
                            self.endecrypt_success = False
                        if ret[2] is not None and ret[3] is not None:
                            # Replace old partition with new partition in my_partitions
                            self.my_partitions[ret[2]] = ret[3]
                    elif name == 'changepassphrase':
                        # Queue returns list: [fraction, error_code, partition_index, partition, message]
                        self.update_progress(ret[0])
                        if ret[1] > 0:
                            self.log.write(str(ret[4]), name, 'error')
                        if ret[2] is not None and ret[3] is not None:
                            # Replace old partition with new partition in my_partitions
                            self.my_partitions[ret[2]] = ret[3]
                            self.changed_devices.append(ret[3]['device'].replace('/mapper', ''))
            return True

        # Thread is done
        print(("Thread %s ended" % name))
        if not self.queue.empty():
            ret = self.queue.get()
            self.queue.task_done()
            if ret:
                self.log.write("Queue returns: {}".format(ret), 'check_thread')
                if name == 'mirrorspeed':
                    self.write_speed(ret[0], ret[1])
                elif name == 'endecrypt':
                    # Queue returns list: [fraction, error_code, partition, message]
                    self.endecrypt_success = True
                    self.update_progress(ret[0])
                    if ret[1] > 0:
                        self.log.write(str(ret[4]), name, 'error')
                        self.endecrypt_success = False
                    if ret[2] is not None and ret[3] is not None:
                        # Replace old partition with new partition in my_partitions
                        self.my_partitions[ret[2]] = ret[3]
                elif name == 'changepassphrase':
                    # Queue returns list: [fraction, error_code, partition_index, partition, message]
                    self.update_progress(ret[0])
                    if ret[1] > 0:
                        self.log.write(str(ret[4]), name, 'error')
                    if ret[2] is not None and ret[3] is not None:
                        # Replace old partition with new partition in my_partitions
                        self.my_partitions[ret[2]] = ret[3]
                        self.changed_devices.append(ret[3]['device'].replace('/mapper', ''))
        del self.threads[name]

        if name == 'update':
            self.mirrors = self.get_mirrors()
            self.fill_treeview_mirrors()
            self.update_progress(0)
            self.set_buttons_state(True)
        elif name == 'cleanup':
            self.fill_treeview_cleanup()
            self.update_progress(0)
            self.set_buttons_state(True)
        elif name == 'localize':
            msg = _("You need to reboot your system for the new settings to take affect.")
            MessageDialog(self.btnSaveLocale.get_label(), msg)
            self.update_progress(0)
            self.set_buttons_state(True)
        elif name == 'endecrypt':
            if self.endecrypt_success:
                # Write all needed configuration
                self.write_partition_configuration()
                
                # Ask to reboot
                answer = False
                if self.encrypt:
                    answer = QuestionDialog(_("Encryption done"),
                                            _("Encryption has finished.\n\n"
                                              "Do you want to restart your computer?"))
                else:
                    answer = QuestionDialog(_("Decryption done"),
                                            _("Decryption has finished.\n\n"
                                              "Do you want to restart your computer?"))
                if answer:
                    # Reboot
                    shell_exec('reboot')

            # Refresh
            self.update_progress(0)
            self.on_btnRefresh_clicked(None)
            self.set_buttons_state(True)
        elif name == 'changepassphrase':
            if self.changed_devices:
                msg = _("Passphrase changed for {0}.".format(', '.join(self.changed_devices)))
                MessageDialog(self.btnChangePassphrase.get_label(), msg)
            self.update_progress(0)
            self.set_buttons_state(True)
        else:
            self.update_progress(0)
            self.set_buttons_state(True)

        return False

    def set_buttons_state(self, enable):
        self.btnCheckMirrorSpeed.set_sensitive(enable)
        self.btnSaveBackports.set_sensitive(enable)
        self.btnSaveMirrors.set_sensitive(enable)
        self.btnEncrypt.set_sensitive(enable)
        self.btnDecrypt.set_sensitive(enable)
        self.btnRefresh.set_sensitive(enable)
        self.btnChangePassphrase.set_sensitive(enable)
        self.btnCreateKeyfile.set_sensitive(enable)
        self.btnSaveLocale.set_sensitive(enable)
        self.btnSaveMirrors.set_sensitive(enable)
        self.btnCheckMirrorSpeed.set_sensitive(enable)
        self.btnHoldback.set_sensitive(enable)
        self.btnRemoveHoldback.set_sensitive(enable)
        self.btnCleanup.set_sensitive(enable)
        self.btnSaveFstabMounts.set_sensitive(enable)
        self.btnSaveDeviceDriver.set_sensitive(enable)

    def get_language_dir(self):
        # First test if full locale directory exists, e.g. html/pt_BR,
        # otherwise perhaps at least the language is there, e.g. html/pt
        # and if that doesn't work, try html/pt_PT
        lang = self.get_current_language()
        path = join(self.htmlDir, lang)
        if not isdir(path):
            base_lang = lang.split('_')[0].lower()
            path = join(self.htmlDir, base_lang)
            if not isdir(path):
                path = join(self.htmlDir, "{}_{}".format(base_lang, base_lang.upper()))
                if not isdir(path):
                    path = join(self.htmlDir, 'en')
        return path

    def get_current_language(self):
        lang = os.environ.get('LANG', 'US').split('.')[0]
        if lang == '':
            lang = 'en'
        return lang

    def get_passphrase_dialog(self, device_path):
        passphrase_title = _("Partition passphrase")
        passphrase_text = _("Please, provide the current passphrase\n"
                            "for the encrypted partition")
        pf_dialog = InputDialog(title=passphrase_title,
                    text="%s:\n\n<b>%s</b>" % (passphrase_text, device_path),
                    is_password=True)
        return pf_dialog.show().strip()
        
    def update_progress(self, step=-1, pulse=False, text=None):
        if step >= 0 and step <= 1:
            if pulse:
                self.progressbar.set_pulse_step(step)
                self.progressbar.pulse()
            else:
                self.progressbar.set_fraction(step)
        else:
            self.progressbar.pulse()
        if text is not None:
            self.progressbar.set_text(str(text))
            
    def temp_mount(self, partition, passphrase=''):
        mount_point =  join(TMPMOUNT, basename(partition['device']))
        return self.udisks2.mount_device(partition['old_device'], mount_point, None, None, passphrase)
        
    def temp_unmount_all(self):
        # Unmount temp mounts and remove
        tmp_mounts = getoutput("grep '%s' /proc/mounts | awk '{print $1,$2}'" % TMPMOUNT)
        for tmp_mount in tmp_mounts:
            try:
                device, mount = tmp_mount.split()
                try:
                    if self.udisks2.unmount_device(device):
                        self.log.write("Remove temporary mount point: %s" % mount, 'temp_unmount_all', 'info')
                        os.rmdir(mount)
                    else:
                        self.log.write("Unable to remove temporary mount point: %s" % mount, 'temp_unmount_all', 'warning')
                except Exception as e:
                    self.log.write("ERROR: %s" %e, 'temp_unmount_all')
            except:
                pass

    # Close the gui
    def on_windowPref_destroy(self, widget):
        self.temp_unmount_all()
        Gtk.main_quit()
