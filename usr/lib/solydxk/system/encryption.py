#! /usr/bin/python3

import re
from os.path import basename, exists, join
from utils import shell_exec, getoutput, mount_device, is_mounted


def clear_partition(device):
    if is_mounted(device):
        unmount_partition(device)
    shell_exec("openssl enc -aes-256-ctr -pass pass:\"$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | base64)\" -nosalt < /dev/zero > %s 2>/dev/null" % device)


def encrypt_partition(device, passphrase):
    if is_mounted(device):
        unmount_partition(device)
    # Cannot use echo to pass the passphrase to cryptsetup because that adds a carriadge return
    shell_exec("printf \"%s\" | cryptsetup luksFormat --cipher aes-xts-plain64 --key-size 512 --hash sha512 --iter-time 5000 --use-random %s" % (passphrase, device))
    return connect_block_device(device, passphrase)


def connect_block_device(device, passphrase):
    mapped_name = basename(device)
    shell_exec("printf \"{}\" | cryptsetup open --type luks {} {}".format(passphrase, device, mapped_name))
    cur_status = get_status(device)
    return (cur_status['active'], cur_status['filesystem'])


def unmount_partition(device):
    shell_exec("umount -lf {}".format(device))
    if is_encrypted(device):
        shell_exec("cryptsetup close {} 2>/dev/null".format(device))


# Mount a (encrypted) partition - returns tuple (device, mount)
def mount_partition(device, mount_point, passphrase, filesystem=None, options=None):
    # Open the device if it is encrypted
    if is_encrypted(device) and not is_connected(device):
        device, filesystem = connect_block_device(device, passphrase)
    if filesystem != 'swap':
        if mount_device(device, mount_point, filesystem, options):
            return (device, mount_point, filesystem)
    return (device, '', filesystem)


def is_connected(device):
    mapped_name = basename(device)
    if exists(join("/dev/mapper", mapped_name)):
        return True
    return False


def is_encrypted(device):
    if "crypt" in get_filesystem(device).lower() or '/dev/mapper' in device:
        return True
    return False


def get_status(device):
    status_dict = {'offset': '', 'mode': '', 'device': '', 'cipher': '', 'keysize': '', 'filesystem': '', 'active': '', 'type': '', 'size': ''}
    mapped_name = basename(device)
    status_info = getoutput("env LANG=C cryptsetup status {}".format(mapped_name))
    for line in status_info:
        parts = line.split(':')
        if len(parts) == 2:
            status_dict[parts[0].strip()] = parts[1].strip()
        elif " active" in line:
            parts = line.split(' ')
            status_dict['active'] = parts[0]
            status_dict['filesystem'] = get_filesystem(parts[0])

    # No info has been retrieved: save minimum
    if status_dict['device'] == '':
        status_dict['device'] = device
    if status_dict['active'] == '' and is_encrypted(device):
        mapped_name = basename(device)
        status_dict['active'] = "/dev/mapper/{}".format(mapped_name)

    return status_dict


def get_filesystem(device):
    return getoutput("blkid -o value -s TYPE {}".format(device))[0]


def get_uuid(device):
    return getoutput("blkid -o value -s UUID {}".format(device))[0]
    

def get_device_from_uuid(uuid):
    uuid = uuid.replace('UUID=', '')
    return getoutput("blkid -U {}".format(uuid))[0]
    

def create_keyfile(keyfile_path, device, passphrase):
    # Note: do this outside the chroot.
    # https://www.martineve.com/2012/11/02/luks-encrypting-multiple-partitions-on-debianubuntu-with-a-single-passphrase/
    if not exists(keyfile_path):
        shell_exec("dd if=/dev/urandom of=%s bs=1024 count=4" % keyfile_path)
        shell_exec("chmod 0400 %s" % keyfile_path)
    shell_exec("printf \"%s\" | cryptsetup luksAddKey %s %s" % (passphrase, device, keyfile_path))


def write_crypttab(device, fs_type, crypttab_path=None, keyfile_path=None, remove_device=False):
    if crypttab_path is None or not '/' in crypttab_path:
        crypttab_path = '/etc/crypttab'
    device = device.replace('/mapper', '')

    if not exists(crypttab_path):
        with open(crypttab_path, 'w') as f:
            f.write('# <target name>\t<source device>\t<key file>\t<options>\n')

    if keyfile_path is None or keyfile_path == '':
        keyfile_path = 'none'
    crypttab_uuid = "UUID=%s" % get_uuid(device)
    new_line = ''
    if not remove_device:
        swap = ''
        if fs_type == 'swap':
            swap = 'swap,'
        new_line = "%s %s %s %sluks,timeout=60\n" % (basename(device), crypttab_uuid, keyfile_path, swap)

    # Create new crypttab contents
    cont = ''
    with open(crypttab_path, 'r') as f:
        cont = f.read()
    regexp = ".*\s{}\s.*".format(crypttab_uuid)
    matchObj = re.search(regexp, cont)
    if matchObj:
        cont = (re.sub(regexp, new_line, cont))
    else:
        if not remove_device:
            cont += new_line

    # Save the new fstab
    with open(crypttab_path, 'w') as f:
        f.write(cont)


# Returns dictionary {device: {target_name, uuid, key_file}}
def get_crypttab_info(crypttab_path):
    crypttab_info = {}
    if exists(crypttab_path):
        with open(crypttab_path, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                lineData = line.split()
                uuid = lineData[1].split('=')[0]
                device = get_device_from_uuid(uuid)
                if device != '':
                    key_file = lineData[2]
                    if key_file == 'none':
                        key_file = ''
                    crypttab_info[device] = {'target_name': lineData[0],
                                             'uuid': uuid,
                                             'key_file': key_file}
    return crypttab_info
