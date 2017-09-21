#! /usr/bin/env python3

import subprocess
import urllib.request
import urllib.error
import re
import threading
import operator
import apt
import filecmp
from os import walk, listdir
from os.path import exists, isdir, expanduser,  splitext,  dirname

    
def shell_exec_popen(command, kwargs={}):
    print(("Executing: %s" % command))
    #return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, **kwargs)
    return subprocess.Popen(command, shell=True, bufsize=0, stdout=subprocess.PIPE, universal_newlines=True, **kwargs)


def shell_exec(command):
    print(("Executing: %s" % command))
    # Returns the returncode attribute
    return subprocess.call(command, shell=True)


def getoutput(command):
    #return shell_exec(command).stdout.read().strip()
    #print(("Executing: %s" % command))
    try:
        output = subprocess.check_output(command, shell=True).decode('utf-8').strip().split('\n')
    except:
        output = ['']
    return output


def chroot_exec(command, target):
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec('chroot %s/ /bin/sh -c "%s"' % (target, command))


def memoize(func):
    """ Caches expensive function calls.

    Use as:

        c = Cache(lambda arg: function_to_call_if_yet_uncached(arg))
        c('some_arg')  # returns evaluated result
        c('some_arg')  # returns *same* (non-evaluated) result

    or as a decorator:

        @memoize
        def some_expensive_function(args [, ...]):
            [...]

    See also: http://en.wikipedia.org/wiki/Memoization
    """
    class memodict(dict):
        def __call__(self, *args):
            return self[args]

        def __missing__(self, key):
            ret = self[key] = func(*key)
            return ret
    return memodict()


def get_config_dict(file, key_value=re.compile(r'^\s*(\w+)\s*=\s*["\']?(.*?)["\']?\s*(#.*)?$')):
    """Returns POSIX config file (key=value, no sections) as dict.
    Assumptions: no multiline values, no value contains '#'. """
    d = {}
    with open(file) as f:
        for line in f:
            try:
                key, value, _ = key_value.match(line).groups()
            except AttributeError:
                continue
            d[key] = value
    return d


# Check for internet connection
def has_internet_connection(testUrl='http://google.com'):
    try:
        urllib.request.urlopen(testUrl, timeout=1)
        return True
    except urllib.error.URLError:
        pass
    return False


# Check if running in VB
def in_virtualbox():
    dmiBIOSVersion = getoutput("dmidecode -t0 | grep 'Version:' | awk -F ': ' '{print $2}'")[0]
    dmiSystemProduct = getoutput("dmidecode -t1 | grep 'Product Name:' | awk -F ': ' '{print $2}'")[0]
    dmiBoardProduct = getoutput("dmidecode -t2 | grep 'Product Name:' | awk -F ': ' '{print $2}'")[0]
    if dmiBIOSVersion != "VirtualBox" and dmiSystemProduct != "VirtualBox" and dmiBoardProduct != "VirtualBox":
        return False
    return True


# Check if is 64-bit system
def is_amd64():
    machine = getoutput("uname -m")[0]
    if machine == "x86_64":
        return True
    return False


def get_package_version(package, candidate=False):
    version = ''
    cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Installed:\"'" % package
    if candidate:
        cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Candidate:\"'" % package
    lst = getoutput(cmd)[0].strip().split(' ')
    if lst:
        version = lst[-1]
    return version


# Get system version information
def get_system_version_info():
    info = ''
    try:
        infoList = getoutput('cat /proc/version')
        if infoList:
            info = infoList[0]
    except Exception as detail:
        print((detail))
    return info


# Get valid screen resolutions
def get_resolutions(minRes='', maxRes='', reverseOrder=False, getVesaResolutions=False):
    cmd = None
    cmdList = ['640x480', '800x600', '1024x768', '1280x1024', '1600x1200']

    if getVesaResolutions:
        vbeModes = '/sys/bus/platform/drivers/uvesafb/uvesafb.0/vbe_modes'
        if exists(vbeModes):
            cmd = "cat %s | cut -d'-' -f1" % vbeModes
        elif is_package_installed('v86d') and is_package_installed('hwinfo'):
            cmd = "sudo hwinfo --framebuffer | grep '0x0' | cut -d' ' -f5 | uniq"
    else:
        cmd = "xrandr | grep '^\s' | cut -d' ' -f4"

    if cmd is not None:
        cmdList = getoutput(cmd)
    # Remove any duplicates from the list
    resList = list(set(cmdList))

    avlRes = []
    avlResTmp = []
    minW = 0
    minH = 0
    maxW = 0
    maxH = 0

    # Split the minimum and maximum resolutions
    if 'x' in minRes:
        minResList = minRes.split('x')
        minW = str_to_nr(minResList[0], True)
        minH = str_to_nr(minResList[1], True)
    if 'x' in maxRes:
        maxResList = maxRes.split('x')
        maxW = str_to_nr(maxResList[0], True)
        maxH = str_to_nr(maxResList[1], True)

    # Fill the list with screen resolutions
    for line in resList:
        for item in line.split():
            itemChk = re.search('\d+x\d+', line)
            if itemChk:
                itemList = item.split('x')
                itemW = str_to_nr(itemList[0], True)
                itemH = str_to_nr(itemList[1], True)
                # Check if it can be added
                if itemW >= minW and itemH >= minH and (maxW == 0 or itemW <= maxW) and (maxH == 0 or itemH <= maxH):
                    print(("Resolution added: %(res)s" % { "res": item }))
                    avlResTmp.append([itemW, itemH])

    # Sort the list and return as readable resolution strings
    avlResTmp.sort(key=operator.itemgetter(0), reverse=reverseOrder)
    for res in avlResTmp:
        avlRes.append(str(res[0]) + 'x' + str(res[1]))
    return avlRes


# Return human readable string from number of kilobytes
def human_size(nkbytes):
    suffixes = ['KB', 'MB', 'GB', 'TB', 'PB']
    nkbytes = float(nkbytes)
    if nkbytes == 0:
        return '0 B'
    i = 0
    while nkbytes >= 1024 and i < len(suffixes) - 1:
        nkbytes /= 1024.
        i += 1
    f = ('%.2f' % nkbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])


def can_copy(file1, file2):
    ret = False
    if exists(file1):
        if exists(file2):
            if not filecmp.cmp(file1, file2):
                ret = True
        else:
            if "desktop" not in splitext(file2)[1]:
                if exists(dirname(file2)):
                    ret = True
    return ret


# Convert string to number
def str_to_nr(stringnr, toInt=False):
    nr = 0
    stringnr = stringnr.strip()
    try:
        if toInt:
            nr = int(stringnr)
        else:
            nr = float(stringnr)
    except ValueError:
        nr = 0
    return nr


# Check for string in file
def has_string_in_file(searchString, filePath):
    if exists(filePath):
        with open(filePath) as f:
            for line in f:
                if re.search("{0}".format(searchString), line):
                    return True
    return False


# Check if a package is installed
def is_package_installed(packageName, alsoCheckVersion=False):
    isInstalled = False
    expr = '^i\s([a-z0-9\-_\.]+)\s+(.*)\s+(.*)'
    if not '*' in packageName:
        packageName = '^{}$'.format(packageName)
    try:
        # https://aptitude.alioth.debian.org/doc/en/ch02s05s01.html
        cmd = "aptitude search -F '%c %p %v %V' --disable-columns {} | grep ^i".format(packageName)
        pckList = getoutput(cmd)
        for line in pckList:
            matchObj = re.search(expr, line)
            if matchObj:
                if alsoCheckVersion:
                    if matchObj.group(2) == matchObj.group(3):
                        isInstalled = True
                        break
                else:
                    isInstalled = True
                    break
            if isInstalled:
                break
    except:
        pass
    return isInstalled


# Check if a package exists
def does_package_exist(packageName):
    exists = False
    try:
        cache = apt.Cache()
        cache[packageName]
        exists = True
    except:
        pass
    return exists


def is_running_live():
    liveDirs = ['/live', '/lib/live/mount', '/rofs']
    for ld in liveDirs:
        if exists(ld):
            return True
    return False


def get_process_pids(processName, fuzzy=True):
    if fuzzy:
        pids = getoutput("ps -ef | grep -v sudo | grep -v grep | grep '%s' | awk '{print $2}'" % processName)
    else:
        pids = getoutput("pidof %s" % processName)
    return pids


def is_process_running(processName, fuzzy=True, excludeSelf=True):
    pids = get_process_pids(processName, fuzzy)
    if pids[0] != '':
        return True
    return False


def get_apt_force():
    # --force-yes is deprecated in stretch
    force = '--force-yes'
    ver = get_debian_version()
    if ver == 0 or ver >= 9:
        force = '--allow-downgrades --allow-remove-essential --allow-change-held-packages'
    force += ' --yes -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold'
    return force
    
    
def get_apt_cache_locked_program():
    aptPackages = ["dpkg", "apt-get", "synaptic", "adept", "adept-notifier"]
    procLst = getoutput("ps -U root -u root -o comm=")
    for aptProc in aptPackages:
        if aptProc in procLst:
            return aptProc
    return ''


def get_debian_name():
    deb_name = {}
    deb_name[10] = "buster"
    deb_name[9] = "stretch"
    deb_name[8] = "jessie"
    deb_name[7] = "wheezy"
    try:
        ver = get_debian_version()
        return deb_name[ver]
    except:
        return ''


# Get Debian's version number (float)
def get_debian_version():
    out = getoutput("head -n 1 /etc/debian_version | sed 's/[a-zA-Z]/0/' | cut -d'.' -f 1 2>/dev/null || echo 0")
    return str_to_nr(out[0], True)


# Check for backports
def get_backports(exclude_disabled=True):
    opt = ''
    if exclude_disabled:
        opt = '| grep -v ^#'
    try:
        bp = getoutput("grep backports /etc/apt/sources.list %s" % opt)
    except:
        bp = ['']
    if not bp[0]:
        try:
            bp = getoutput("grep backports /etc/apt/sources.list.d/*.list %s" % opt)
        except:
            bp = ['']
    return bp


def has_newer_in_backports(package_name, backports_repository):
    try:
        out = getoutput("apt-cache madison %s | grep %s" % (package_name, backports_repository))[0]
        if out != '':
            return True
    except:
        return False


# Comment or uncomment a line with given pattern in a file
def comment_line(file_path, pattern, comment=True):
    if exists(file_path):
        pattern = pattern.replace("/", "\/")
        cmd = "sed -i '/{p}/s/^/#/' {f}".format(p=pattern, f=file_path)
        if not comment:
            cmd = "sed -i '/^#.*{p}/s/^#//' {f}".format(p=pattern, f=file_path)
        shell_exec(cmd)


def get_nr_files_in_dir(path, recursive=True):
    total = 0
    if isdir(path):
        #return str_to_nr(getoutput("find %s -type f | wc -l" % path)[0], True)
        if recursive:
            for root, directories, filenames in walk(path):
                total += len(filenames)
        else:
            total = len(listdir(path))
    return total


def get_logged_user():
    return getoutput("logname")[0]


def get_user_home():
    return expanduser("~%s" % get_logged_user())
    
    
def has_grub(path):
    cmd = "dd bs=512 count=1 if=%s 2>/dev/null | strings" % path
    out = ' '.join(getoutput(cmd)).upper()
    if "GRUB" in out:
        print(("Grub installed on %s" % path))
        return True
    return False
    
    
def get_uuid(partition_path):
    return getoutput("blkid -o value -s UUID {}".format(partition_path))[0]


def get_mount_point(partition_path):
    return getoutput("lsblk -o MOUNTPOINT -n %s | grep -v '^$'" % partition_path)[0]


def get_filesystem(partition_path):
    return getoutput("blkid -o value -s TYPE %s" % partition_path)[0]


def get_device_from_uuid(uuid):
    uuid = uuid.replace('UUID=', '')
    return getoutput("blkid -U {}".format(uuid))[0]


def get_label(partition_path):
    return getoutput("sudo blkid -o value -s LABEL %s" % partition_path)[0]


# Class to run commands in a thread and return the output in a queue
class ExecuteThreadedCommands(threading.Thread):
    def __init__(self, commandList, queue=None, return_output=False):
        threading.Thread.__init__(self)
        
        self._commands = commandList
        self._queue = queue
        self._return_output = return_output

    def run(self):
        if isinstance(self._commands, (list, tuple)):
            for cmd in self._commands:
                self.exec_cmd(cmd)
        else:
            self.exec_cmd(self._commands)

    def exec_cmd(self, cmd):
        if self._return_output:
            ret = getoutput(cmd)
        else:
            ret = shell_exec(cmd)
        if self._queue is not None:
            self._queue.put(ret)


# Class to run a function in a thread and return the output in a queue
class ExecuteThreadedFunction(threading.Thread):
    def __init__(self, target, queue=None, *args):
        threading.Thread.__init__(self)
        
        self._target = target
        self._args = args
        self._queue = queue
        #threading.Thread.__init__(self)
 
    def run(self):
        out = self._target(*self._args)
        if self._queue is not None:
            self._queue.put(out)
