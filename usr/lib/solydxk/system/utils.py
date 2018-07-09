#! /usr/bin/env python3

import subprocess
from socket import timeout
from urllib.request import ProxyHandler, HTTPBasicAuthHandler, Request, \
                           build_opener, HTTPHandler, install_opener, urlopen
from urllib.error import URLError, HTTPError
from random import choice
import re
import threading
import operator
import apt
import filecmp
from os import walk, listdir
from os.path import exists, isdir, expanduser,  splitext,  dirname
from distutils.version import LooseVersion, StrictVersion

    
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
def has_internet_connection(test_url=None):
    urls = []
    if test_url is not None:
        urls.append(test_url)
    if not urls:
        src_lst = '/etc/apt/sources.list'
        if exists(src_lst):
            with open(src_lst, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith('#'):
                        matchObj = re.search(r'http[s]{,1}://[a-z0-9\.]+', line)
                        if matchObj:
                            urls.append(matchObj.group(0))
    for url in urls:
        if get_value_from_url(url) is not None:
            return True
    return False


def get_value_from_url(url, timeout_secs=5, return_errors=False):
    try:
        # http://www.webuseragents.com/my-user-agent
        user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
        ]

        # Create proxy handler
        proxy = ProxyHandler({})
        auth = HTTPBasicAuthHandler()
        opener = build_opener(proxy, auth, HTTPHandler)
        install_opener(opener)

        # Create a request object with given url
        req = Request(url)

        # Get a random user agent and add that to the request object
        ua = choice(user_agents)
        req.add_header('User-Agent', ua)

        # Get the output of the URL
        output = urlopen(req, timeout=timeout_secs)

        # Decode to text
        txt = output.read().decode('utf-8')
        
        # Return the text
        return txt
        
    except (HTTPError, URLError) as error:
        err = 'ERROR: could not connect to {}: {}'.format(url, error)
        if return_errors:
            return err
        else:
            print((err))
            return None
    except timeout:
        err = 'ERROR: socket timeout on: {}'.format(url)
        if return_errors:
            return err
        else:
            print((err))
            return None


# Check if running in VB
def in_virtualbox():
    vb = 'VirtualBox'
    dmiBIOSVersion = getoutput("grep '{}' /sys/devices/virtual/dmi/id/bios_version".format(vb))
    dmiSystemProduct = getoutput("grep '{}' /sys/devices/virtual/dmi/id/product_name".format(vb))
    dmiBoardProduct = getoutput("grep '{}' /sys/devices/virtual/dmi/id/board_name".format(vb))
    if vb not in dmiBIOSVersion and \
       vb not in dmiSystemProduct and \
       vb not in dmiBoardProduct:
        return False
    return True


# Check if is 64-bit system
def is_amd64():
    machine = getoutput("uname -m")[0]
    if machine == "x86_64":
        return True
    return False

# Check if xfce is running
def is_xfce_running():
    xfce = getoutput('pidof xfce4-session')[0]
    if xfce:
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
    
# Compare two package version strings
def compare_package_versions(package_version_1, package_version_2, compare_loose=True):
    if compare_loose:
        try:
            if LooseVersion(package_version_1) < LooseVersion(package_version_2):
                return 'smaller'
            if LooseVersion(package_version_1) > LooseVersion(package_version_2):
                return 'larger'
            else:
                return 'equal'
        except:
            return ''
    else:
        try:
            if StrictVersion(package_version_1) < StrictVersion(package_version_2):
                return 'smaller'
            if StrictVersion(package_version_1) > StrictVersion(package_version_2):
                return 'larger'
            else:
                return 'equal'
        except:
            return ''

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
def get_resolutions(minRes='', maxRes='', reverse_order=False, use_vesa=False):
    cmd = None
    resolutions = []
    default_res = ['640x480', '800x600', '1024x768', '1280x1024', '1600x1200']

    cmd = "xrandr | awk '{print $1}' | egrep '[0-9]+x[0-9]+$'"
    if use_vesa:
        vbeModes = '/sys/bus/platform/drivers/uvesafb/uvesafb.0/vbe_modes'
        if exists(vbeModes):
            cmd = "cat %s | cut -d'-' -f1" % vbeModes
        elif is_package_installed('hwinfo'):
            cmd = "hwinfo --framebuffer | awk '{print $3}' | egrep '[0-9]+x[0-9]+$' | uniq"        

    resolutions = getoutput(cmd)
    if not resolutions[0]:
        resolutions = default_res

    # Remove any duplicates from the list
    resList = list(set(resolutions))

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
                    #print(("Resolution added: %(res)s" % { "res": item }))
                    avlResTmp.append([itemW, itemH])

    # Sort the list and return as readable resolution strings
    avlResTmp.sort(key=operator.itemgetter(0), reverse=reverse_order)
    for res in avlResTmp:
        avlRes.append(str(res[0]) + 'x' + str(res[1]))
    return avlRes
    

def get_current_resolution():
    res = getoutput("xrandr | grep '*' | awk '{print $1}'")[0]
    if not res:
        res = getoutput("xdpyinfo | grep dimensions | sed -r 's/^[^0-9]*([0-9]+x[0-9]+).*$/\1/'")[0]
    return res
    
    
def get_current_aspect_ratio():
    return get_resolution_aspect_ratio(get_current_resolution())


def get_resolution_aspect_ratio(resolution_string):
    res = resolution_string.split('x')
    if len(res) != 2:
        return ''

    width = str_to_nr(res[0], True)
    height = str_to_nr(res[1], True)
    
    if width <= 0 or height <= 0:
        return ''

    m = width
    n = height
    temp = 0
    remainder = 0
    hcf = 1
    
    if m < n:
        temp = m
        m = n
        n = temp

    while True:
        remainder = m % n
        if remainder == 0:
            hcf = n
            break
        else:
            m = n
        n = remainder
    
    # Return aspect ratio string
    return "{}:{}".format(int(width / hcf), int(height / hcf))
    
    
def get_resolutions_with_aspect_ratio(aspect_ratio_string, use_vesa=False):
    ret_arr = []
    resolutions = get_resolutions(use_vesa=use_vesa)
    for res in resolutions:
        ar = get_resolution_aspect_ratio(res)
        if ar == aspect_ratio_string:
            ret_arr.append(res)
    return ret_arr


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
    try:
        cache = apt.Cache()
        cache[packageName]
        return True
    except:
        return False


def is_running_live():
    liveDirs = ['/live', '/lib/live/mount', '/rofs']
    for ld in liveDirs:
        if exists(ld):
            return True
    return False


def get_process_pids(process_name, process_argument=None, fuzzy=False):
    if fuzzy:
        args = ''
        if process_argument is not None:
            args = "| grep '%s'" % process_argument
        cmd = "ps -ef | grep -v grep | grep '%s' %s | awk '{print $2}'" % (process_name, args)
        #print(cmd)
        pids = getoutput(cmd)
    else:
        pids = getoutput("pidof %s" % process_name)
    return pids


def is_process_running(process_name, process_argument=None, fuzzy=False):
    pids = get_process_pids(process_name, process_argument, fuzzy)
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
    out = getoutput("egrep -o '[0-9]{1,}' /etc/debian_version | head -n 1 2>/dev/null || echo 0")
    return str_to_nr(out[0], True)


def get_firefox_version():
    return str_to_nr(getoutput("firefox --version 2>/dev/null | egrep -o '[0-9]{2,}' || echo 0")[0], True)


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


def get_swap_device():
    return getoutput("grep '/' /proc/swaps | awk '{print $1}'")[0]


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
 
    def run(self):
        out = self._target(*self._args)
        if self._queue is not None:
            self._queue.put(out)
