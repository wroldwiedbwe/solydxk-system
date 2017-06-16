#! /usr/bin/env python3

import threading
import time
from shutil import rmtree
import os
from os.path import exists, join, basename, isdir
from udisks2 import Udisks2
from utils import shell_exec, get_logged_user, is_mounted, \
                    get_nr_files_in_dir, shell_exec_popen
from encryption import encrypt_partition, mount_partition, \
                        get_filesystem, get_uuid

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')


class EnDecryptPartitions(threading.Thread):
    def __init__(self, my_partitions, backup_dir, encrypt, passphrase, queue, log):
        super(EnDecryptPartitions, self).__init__()
        
        self.udisks2 = Udisks2()
        self.my_partitions = my_partitions
        self.backup_dir = backup_dir
        self.encrypt = encrypt
        self.passphrase = passphrase
        self.log = log
        # Queue returns list: [fraction, error_code, partition_index, partition, message]
        self.queue = queue

    def run(self):
        # Loop on index: need that when queueing a changed partition object
        steps = 10
        nr_partitions = len(self.my_partitions)
        total_steps = nr_partitions * steps
        for i in range(nr_partitions):
            partition = self.my_partitions[i]
            is_swap = partition['fs_type'] == 'swap'
            
            # Create the backup directory
            backup_dir = join(self.backup_dir, "luks_bak/%s" % basename(partition['device']))
            self.log.write("Backup directory: %s" % backup_dir, 'endecrypt', 'info')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Rsync partition content to backup medium
            if (is_mounted(partition['mount_point']) and isdir(backup_dir)) or is_swap:
                rsync_code = 0
                if not is_swap:
                    rsync_code = self.backup_partition(partition['mount_point'], backup_dir)
                if rsync_code > 0:
                    msg = _("Could not create a backup on {backup_dir} (rsync code: {rsync_code}).\n"
                            "Please, select another backup medium before you try again.".format(backup_dir=backup_dir, rsync_code=rsync_code))
                    self.queue.put([1, rsync_code, None, None, msg])
                    return False
                else:
                    step = (i + 1) * 1
                    self.queue.put([1 / (total_steps / step), rsync_code, None, None, None])
                    if self.encrypt:
                        # Encrypt
                        self.log.write("Start encryption of %s" % partition['device'], 'endecrypt', 'info')
                        partition['device'] = encrypt_partition(partition['device'], self.passphrase)
                        partition['encrypted'] = True
                        step = (i + 1) * 2
                        self.queue.put([1 / (total_steps / step), 0, None, None, None])
                    else:
                        # Decrypt
                        fs_type = self.udisks2.get_filesystem(partition['device'])
                        partition_path = partition['device'].replace('/mapper', '')
                        self.log.write("Unmount %s" % partition['device'], 'endecrypt', 'info')
                        self.udisks2.unmount_device(partition['device'])
                        partition['fs_type'] = fs_type
                        partition['device'] = partition_path
                        partition['encrypted'] = False
                        self.log.write("Save fs_type %s and partition_path %s of encrypted partition" % (partition['fs_type'], partition['device']), 'endecrypt', 'info')
                        step = (i + 1) * 3
                        self.queue.put([1 / (total_steps / step), 0, None, None, None])

                    #Format
                    self.log.write("Start formatting %s" % partition['device'], 'endecrypt', 'info')
                    if self.format_partition(partition):
                        partition['uuid'] = get_uuid(partition['device'])
                        step = (i + 1) * 4
                        self.queue.put([1 / (total_steps / step), 0, None, None, None])
                    else:
                        msg = _("Could not format the device {device}.\n"
                                "You need to manually format the device and restore your data from: {backup_dir}".format(device=partition['device'], backup_dir=backup_dir))
                        self.queue.put([1, 105, None, None, msg])
                        return False

                    # Mount the encrypted/decrypted partition to the old mount point
                    mount = ''
                    if not is_swap:
                        self.log.write("Mount (for restoring backup) %s to %s" % (partition['device'], partition['mount_point']), 'endecrypt', 'info')
                        device, mount, filesystem = mount_partition(partition['device'], partition['mount_point'], self.passphrase, partition['fs_type'])
                        step = (i + 1) * 5
                        self.queue.put([1 / (total_steps / step), 0, None, None, None])

                    restore_failed = False
                    if mount:
                        # Make sure the user owns the pen drive
                        if partition['removable']:
                            user = get_logged_user()
                            if user:
                                shell_exec("chown -R {0}:{0} {1}".format(user, mount))
                                step = (i + 1) * 6
                                self.queue.put([1 / (total_steps / step), 0, None, None, None])

                        # Rsync backup to the encrytped/decrypted partition
                        self.log.write("Restore backup %s to %s" % (backup_dir, partition['mount_point']), 'endecrypt', 'info')
                        rsync_code = self.backup_partition(backup_dir, partition['mount_point'])
                        if rsync_code == 0:
                            step = (i + 1) * 7
                            self.queue.put([1 / (total_steps / step), rsync_code, None, None, None])
                        else:
                            # Return rsync error code for no such file or directory: 2
                            rsync_code = 2
                            restore_failed = True
                    else:
                        if not is_swap:
                            restore_failed = True
                            
                    if restore_failed:
                        msg = _("Could not restore the backup (rsync code: {rsync_code}).\n"
                                "You need to manually restore your data from: {backup_dir}".format(rsync_code=rsync_code, backup_dir=backup_dir))
                        self.queue.put([1, rsync_code, None, None, msg])
                        return False

                    if exists(backup_dir):
                        # Remove backup data
                        self.log.write("Remove backup data: %s" % backup_dir, 'endecrypt', 'info')
                        rmtree(backup_dir)
                        luks_bak = join(self.backup_dir, "luks_bak")
                        if not os.listdir(luks_bak):
                            os.rmdir(luks_bak)
                        step = (i + 1) * 8
                        self.queue.put([1 / (total_steps / step), 0, None, None, None])
                        
            # Partition finished: pass the partition object back to the caller
            step = (i + 1) * 9
            self.queue.put([1 / (total_steps / step), 0, i, partition, None])
        # Done
        self.queue.put([1, 0, None, None, None])
            
    def format_partition(self, partition):
        device = partition['device']
        fs_type = partition['fs_type']

        if not fs_type:
            msg = _("Error formatting partition {0}:\n"
                    "It has no file system type.".format(device))
            self.queue.put([1, 110, None, None, msg])
            return False

        # Build format command
        if fs_type == "swap":
            cmd = "mkswap %s" % device
        elif fs_type[:3] == 'ext':
            cmd = "mkfs.%s -F -q %s" % (fs_type, device)
        elif fs_type == "jfs":
            cmd = "mkfs.%s -q %s" % (fs_type, device)
        elif fs_type == "xfs":
            cmd = "mkfs.%s -f %s" % (fs_type, device)
        elif fs_type == "vfat":
            cmd = "mkfs.%s %s -F 32" % (fs_type, device)
        else:
            cmd = "mkfs.%s %s" % (fs_type, device)  # works with bfs, btrfs, minix, msdos, ntfs

        self.log.write(cmd, 'format_partition')
        shell_exec(cmd)
        fs = get_filesystem(device)
        if fs == fs_type:
            return True
        return False
        
    def backup_partition(self, source, destination):
        self.log.write("Backup %s to %s" % (source, destination), 'backup_partition', 'info')
        prev_sec = -1
        current = 0
        exclude_dirs = "dev/* proc/* sys/* tmp/* run/* mnt/* media/* lost+found source".split()
        if source[-1] != '/':
            source += '/'
        if destination[-1] != '/':
            destination += '/'

        # assume: #(files to copy) ~= #(used inodes on /)
        #cmd = "df --inodes {src} | awk '/^.+?\{src_esc}$/{{ print $3 }}'".format(src=source, src_esc=source.strip('/').replace('/', '\/'))
        total_files = get_nr_files_in_dir(source)
        if total_files > 0:
            self.log.write("Copying {} files".format(total_files), "backup_partition", 'info')
            rsync_filter = ' '.join('--exclude=' + source + d for d in exclude_dirs)
            rsync = shell_exec_popen("rsync --owner --group --ignore-errors --verbose --archive --no-D --acls "
                                     "--times --perms --hard-links --xattrs {rsync_filter} "
                                     "{src} {dst}".format(src=source, dst=destination, rsync_filter=rsync_filter))

            # Check the output of rsync
            while rsync.poll() is None:
                # Cleanup the line: only path of file to be copied
                try:
                    line = rsync.stdout.readline().strip()
                    line = line[0:line.index(' ')]
                except:
                    pass
                if not line:
                    time.sleep(0.1)
                else:
                    current = min(current + 1, total_files)
                    # Check if localtime is on the second to prevent flooding the queue
                    sec = time.localtime()[5]
                    if sec != prev_sec:
                        val = round(1 / (total_files / current), 1)
                        self.queue.put([val, 0, None, None, None])
                        prev_sec = sec

            return rsync.poll()
        return 0
