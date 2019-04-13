#! /usr/bin/env python3

# Udisks2 API reference: 
# http://storaged.org/doc/udisks2-api/latest/ref-library.html

import gi
# Make sure the right UDisks version is loaded
gi.require_version('UDisks', '2.0')
from gi.repository import UDisks, GLib
from os.path import exists, join, basename
import os
from os import makedirs
from utils import getoutput, shell_exec, has_grub, get_uuid, \
                  get_mount_points, get_filesystem, get_label
from encryption import get_status, is_encrypted, \
                       is_connected, connect_block_device


# Subclass dict class to overwrite the __missing__() method
# to implement autovivificious dictionaries:
# https://en.wikipedia.org/wiki/Autovivification#Python
class Tree(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


class Udisks2():
    def __init__(self):
        super(Udisks2, self).__init__()
        self.no_options = GLib.Variant('a{sv}', {})
        self.read_only = GLib.Variant('a{sv}', {'options': GLib.Variant('s', 'ro')})
        self.no_interaction = GLib.Variant('a{sv}', {'auth.no_user_interaction': GLib.Variant('b', True)})
        self.devices = Tree()

    # Create multi-dimensional dictionary with drive/device/deviceinfo
    def fill_devices(self, include_drives=True, include_flash=True):

        self.devices.clear()

        client = UDisks.Client.new_sync(None)
        manager = client.get_object_manager()
        objects = manager.get_objects()

        for obj in objects:
            block = None
            partition = None
            fs = None
            drive = None
            device_path = ''
            fs_type = ''
            drive_path = ''
            add_device = False
            removable = False
            connectionbus = ''
            mount_point = ''
            total_size = 0
            free_size = 0
            used_size = 0
            
            block = obj.get_block()
            if block is None:
                continue

            device_path = block.get_cached_property('Device').get_bytestring().decode('utf-8')
            fs_type = block.get_cached_property('IdType').get_string()
            if fs_type == '':
                continue

            mapper_path = ''
            luks_mount = ''
            if 'luks' in fs_type.lower():
                mapper_path, luks_mount = self.get_luks_info(device_path)
                if mapper_path:
                    device_path = mapper_path
                    fs_type = get_filesystem(device_path)
                else:
                    # Block object doesn't refresh correctly after decrypting
                    # block.call_rescan_sync doesn't do anything
                    # Fix with workaround:
                    fs_type = get_filesystem(device_path)

            drive_path = self.get_drive_from_device_path(device_path)

            if device_path != drive_path:
                total_size = (block.get_cached_property('Size').get_uint64() / 1024)
                if (mapper_path and total_size == 0) or \
                   (not mapper_path and not exists(drive_path)) or \
                   (not mapper_path and total_size == 0 and not 'luks' in fs_type.lower()):
                    continue

                if luks_mount:
                    mount_point = luks_mount
                    total_size, free_size, used_size = self.get_mount_size(mount_point)
                else:
                    fs = obj.get_filesystem()
                    if fs is not None:
                        unmount = False
                        # Get the file system's mount point
                        mount_points = fs.get_cached_property('MountPoints').get_bytestring_array()
                        if not mount_points:
                            # It can be manually mounted (with mount command)
                            mount_points = get_mount_points(device_path)
                        if not mount_points:
                            # If not mounted, temporary mount it to get needed info
                            mount_points = self._mount_filesystem(fs, read_only=True)
                            unmount = True
                        if mount_points:
                            mount_point = mount_points[0]
                            if exists(mount_point):
                                # Get the info of the mounted file system
                                total_size, free_size, used_size = self.get_mount_size(mount_point)
                            if unmount:
                                # Unmount the temporary mounted file system
                                if self._unmount_filesystem(fs):
                                    mount_point = ''

                # There are no partitions: set free size to total size
                partition = obj.get_partition()
                if partition is None:
                    free_size = total_size

                drive_name = block.get_cached_property('Drive').get_string()
                drive_obj = manager.get_object(drive_name)
                if drive_obj is None:
                    continue
                drive = drive_obj.get_drive()
                removable = drive.get_cached_property("Removable").get_boolean()
                connectionbus = drive.get_cached_property("ConnectionBus").get_string()
                ejectable = drive.get_cached_property("Ejectable").get_boolean()
                canpoweroff = drive.get_cached_property("CanPowerOff").get_boolean()
                

                # Check for usb mounted flash drives
                if include_flash:
                    if connectionbus == 'usb' and removable and ejectable: add_device = True
                elif include_drives:
                    if connectionbus != 'usb' and not removable and not ejectable: add_device = True

                if add_device:
                    uuid = get_uuid(device_path)
                    label = get_label(device_path)
                    grub = has_grub(device_path)
                    debug_title = "Device Info of: %s" % device_path
                    print(('========== %s ==========' % debug_title))
                    print(('UUID: %s' % uuid))
                    print(('FS Type: %s' % fs_type))
                    print(('Mount point: %s' % mount_point))
                    print(('Label: %s' % label))
                    print(('Total size: %s' % total_size))
                    print(('Free size: %s' % free_size))
                    print(('Used size: %s' % used_size))
                    print(('ConnectionBus: %s' % connectionbus))
                    print(('Removable: %s' % str(removable)))
                    print(('Ejectable: %s' % str(ejectable)))
                    print(('CanPowerOff: %s' % str(canpoweroff)))
                    print(('Has Grub: %s' % str(grub)))
                    print((('=' * 22) + ('=' * len(debug_title))))

                    # Partition information
                    self.devices[device_path]['uuid'] = uuid
                    self.devices[device_path]['fs_type'] = fs_type
                    self.devices[device_path]['mount_point'] = mount_point
                    self.devices[device_path]['label'] = label
                    self.devices[device_path]['total_size'] = total_size
                    self.devices[device_path]['free_size'] = free_size
                    self.devices[device_path]['used_size'] = used_size
                    self.devices[device_path]['connectionbus'] = connectionbus
                    self.devices[device_path]['removable'] = removable
                    self.devices[device_path]['ejectable'] = ejectable
                    self.devices[device_path]['canpoweroff'] = canpoweroff
                    self.devices[device_path]['has_grub'] = grub

    def _get_object_path(self, device_path):
        return "/org/freedesktop/UDisks2/block_devices/%s" % basename(device_path)

    def _get_block(self, device_path):
        obj_path = self._get_object_path(device_path)
        client = UDisks.Client.new_sync(None)
        dev = client.get_object(obj_path)
        return dev.get_block()

    def _get_filesystem(self, device_path):
        obj_path = self._get_object_path(device_path)
        client = UDisks.Client.new_sync(None)
        dev = client.get_object(obj_path)
        return dev.get_filesystem()

    def _get_partition(self, device_path):
        obj_path = self._get_object_path(device_path)
        client = UDisks.Client.new_sync(None)
        dev = client.get_object(obj_path)
        return dev.get_partition()

    def _get_drive(self, device_path):
        obj_path = self._get_object_path(device_path)
        client = UDisks.Client.new_sync(None)
        manager = client.get_object_manager()
        dev = client.get_object(obj_path)
        block = dev.get_block()
        if block is not None:
            drive_name = block.get_cached_property('Drive').get_string()
            drive_obj = manager.get_object(drive_name)
            if drive_obj is not None:
                return drive_obj.get_drive()
        return None

    def _unmount_filesystem(self, fs):
        try:
            fs.call_unmount_sync(self.no_options, None)
            return True
        except:
            return False

    # This is why the entire backend needs to be its own thread.
    def _mount_filesystem(self, fs, read_only=False):
        mount_points = []
        if fs is not None:
            try:
                options = self.read_only if read_only else self.no_options
                mount_points = [fs.call_mount_sync(options, None)]
            except:
                # Best effort
                pass
        return mount_points

    def get_drives(self):
        drives = []
        for d in self.devices:
            drive_path = self.get_drive_from_device_path(d)
            if exists(drive_path) and drive_path not in drives:
                drives.append(drive_path)
        return drives

    def get_drive_device_paths(self, drive=None):
        devices = []
        for d in self.devices:
            drive_path = None
            if drive is not None:
                drive_path = self.get_drive_from_device_path(d)
            if drive_path == drive:
                if exists(d) and d not in devices:
                    devices.append(d)
        return devices

    def is_mounted(self, device_path):
        ret = getoutput("grep '%s ' /proc/mounts" % device_path)[0]
        if device_path in ret:
            return True
        return False
    
    def mount_device(self, device_path, mount_point=None, filesystem=None, options=None, passphrase=None):
        if mount_point is None:
            mount_point = ''
        if filesystem is None:
            filesystem = ''
        if options is None:
            options = ''
        if passphrase is None:
            passphrase = ''
            
        # Connect encrypted partition
        connected = False
        if passphrase:
            if is_encrypted(device_path) and not is_connected(device_path):
                device_path, filesystem = connect_block_device(device_path, passphrase)
                
        # Do not mount swap partition
        if filesystem == 'swap':
            #print((">>>> swap partition: return device_path=%s, filesystem=%s" % (device_path, filesystem)))
            return (device_path, '', filesystem)
        
        # Try udisks way if no mount point has been given
        if not mount_point:
            fs = self._get_filesystem(device_path)
            if fs is not None:
                mount_points = self._mount_filesystem(fs)
                if mount_points:
                    # Set mount point and free space for this device
                    total, free, used = self.get_mount_size(mount_points[0])
                    self.devices[device_path]['mount_point'] = mount_points[0]
                    self.devices[device_path]['free_size'] = free
                    filesystem = get_filesystem(device_path)
                    return (device_path, mount_points[0], filesystem)
            # Try a temporary mount point on uuid
            uuid = get_uuid(device_path)
            if uuid:
                mount_point = join('/media', uuid)
            else:
                return (device_path, mount_point, filesystem)
        
        # Mount the device to the given mount point
        if not exists(mount_point):
            makedirs(mount_point, exist_ok=True)
        if exists(mount_point):
            if options:
                if options[0:1] != '-':
                    options = '-o ' + options
            else:
                options = ''
            fs = '-t ' + filesystem if filesystem else ''
            cmd = "mount {options} {fs} {device_path} {mount_point}".format(**locals())
            shell_exec(cmd)
        if self.is_mounted(device_path):
            filesystem = get_filesystem(device_path)
            return (device_path, mount_point, filesystem)
        return (device_path, '', filesystem)

    def unmount_device(self, device_path):
        fs = self._get_filesystem(device_path)
        if fs is not None:
            try:
                self._unmount_filesystem(fs)
            except:
                pass
        if self.is_mounted(device_path):
            shell_exec("umount -f {}".format(device_path))
        if not self.is_mounted(device_path):
            if is_encrypted(device_path):
                shell_exec("cryptsetup close {} 2>/dev/null".format(device_path))
            return True
        return False

    def unmount_drive(self, drive_path):
        for device_path in self.get_drive_device_paths(drive_path):
            self.unmount_device(device_path)

    def poweroff_drive(self, drive_path):
        try:
            for device_path in self.get_drive_device_paths(drive_path):
                drive = self._get_drive(device_path)
                if drive is not None:
                    return drive.call_power_off_sync(self.no_options, None)
        except:
            raise

    def set_filesystem_label(self, fs, label):
        try:
            return fs.set_label_sync(label, self.no_options, None)
        except:
            raise

    def set_filesystem_label_by_device(self, device_path, label):
        fs = self._get_filesystem(device_path)
        if fs is not None:
            return self.set_filesystem_label(fs, label)
        return False

    def set_partition_bootable(self, partition):
        try:
            return partition.SetFlags(7, self.no_options)
        except:
            raise

    def set_partition_bootable_by_device_path(self, device_path):
        partition = self._get_partition(device_path)
        return self.set_partition_bootable(partition)

    def set_partition_label(self, partition, label):
        try:
            return partition.SetName(label, self.no_options)
        except:
            raise

    def set_partition_label_by_device_path(self, device_path, label):
        partition = self._get_partition(device_path)
        return self.set_partition_label(partition, label)

    # =================================================================
    # Useful non-udisks2 functions
    # =================================================================

    def get_drive_from_device_path(self, device_path):
        if '/dev/mapper' in device_path:
            if exists(device_path):
                status = get_status(device_path)
                device_path = status['device']
            else:
                device_path = device_path.replace('/mapper', '')
        return device_path.rstrip('0123456789')

    # returns total/free/used tuple (Kb)
    def get_mount_size(self, mount_point):
        try:
            st = os.statvfs(mount_point)
        except:
            return (0, 0, 0)
        total = (st.f_blocks * st.f_frsize) / 1024
        free = (st.f_bavail * st.f_frsize) / 1024
        used = ((st.f_blocks - st.f_bfree) * st.f_frsize) / 1024
        return (total, free, used)

    def get_luks_info(self, partition_path):
        mapper_path = ''
        mount_points = []
        mapper = '/dev/mapper'
        mapper_name = getoutput("ls %s | grep %s$" % (mapper, basename(partition_path)))[0]
        if not mapper_name:
            uuid = get_uuid(partition_path)
            if uuid:
                mapper_name = getoutput("ls %s | grep %s$" % (mapper, uuid))[0]
        if mapper_name:
            mapper_path = join(mapper, mapper_name)
        if mapper_path:
            mount_points = get_mount_points(mapper_path)
        return (mapper_path, mount_points[0])
