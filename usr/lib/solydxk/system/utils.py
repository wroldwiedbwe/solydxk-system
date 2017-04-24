#! /usr/bin/env python3

import subprocess
import urllib.request
import urllib.error
import re
import threading
import operator
import apt
from os.path import exists


def shell_exec_popen(command, kwargs={}):
    print(('Executing:', command))
    return subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, **kwargs)


def shell_exec(command):
    print(('Executing:', command))
    return subprocess.call(command, shell=True)


def getoutput(command):
    #return shell_exec(command).stdout.read().strip()
    print(('Executing:', command))
    try:
        output = subprocess.check_output(command, shell=True).decode('utf-8').strip().split('\n')
    except:
        output = []
    return output


def chroot_exec(command):
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec('chroot /target/ /bin/sh -c "%s"' % command)


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
def hasInternetConnection(testUrl='http://google.com'):
    try:
        urllib.request.urlopen(testUrl, timeout=1)
        return True
    except urllib.error.URLError:
        pass
    return False


# Check if running in VB
def runningInVirtualBox():
    dmiBIOSVersion = getoutput("dmidecode -t0 | grep 'Version:' | awk -F ': ' '{print $2}'")
    dmiSystemProduct = getoutput("dmidecode -t1 | grep 'Product Name:' | awk -F ': ' '{print $2}'")
    dmiBoardProduct = getoutput("dmidecode -t2 | grep 'Product Name:' | awk -F ': ' '{print $2}'")
    if dmiBIOSVersion != "VirtualBox" and dmiSystemProduct != "VirtualBox" and dmiBoardProduct != "VirtualBox":
        return False
    return True


# Check if is 64-bit system
def isAmd64():
    machine = getoutput("uname -m")
    if machine == "x86_64":
        return True
    return False


def getPackageVersion(package, candidate=False):
    version = ''
    cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Installed:\"'" % package
    if candidate:
        cmd = "env LANG=C bash -c 'apt-cache policy %s | grep \"Candidate:\"'" % package
    lst = getoutput(cmd)[0].strip().split(' ')
    if lst:
        version = lst[-1]
    return version


# Get system version information
def getSystemVersionInfo():
    info = ''
    try:
        infoList = getoutput('cat /proc/version')
        if infoList:
            info = infoList[0]
    except Exception as detail:
        print((detail))
    return info


# Get valid screen resolutions
def getResolutions(minRes='', maxRes='', reverseOrder=False, getVesaResolutions=False):
    cmd = None
    cmdList = ['640x480', '800x600', '1024x768', '1280x1024', '1600x1200']

    if getVesaResolutions:
        vbeModes = '/sys/bus/platform/drivers/uvesafb/uvesafb.0/vbe_modes'
        if exists(vbeModes):
            cmd = "cat %s | cut -d'-' -f1" % vbeModes
        elif isPackageInstalled('v86d') and isPackageInstalled('hwinfo'):
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
        minW = strToNumber(minResList[0], True)
        minH = strToNumber(minResList[1], True)
    if 'x' in maxRes:
        maxResList = maxRes.split('x')
        maxW = strToNumber(maxResList[0], True)
        maxH = strToNumber(maxResList[1], True)

    # Fill the list with screen resolutions
    for line in resList:
        for item in line.split():
            itemChk = re.search('\d+x\d+', line)
            if itemChk:
                itemList = item.split('x')
                itemW = strToNumber(itemList[0], True)
                itemH = strToNumber(itemList[1], True)
                # Check if it can be added
                if itemW >= minW and itemH >= minH and (maxW == 0 or itemW <= maxW) and (maxH == 0 or itemH <= maxH):
                    print(("Resolution added: %(res)s" % { "res": item }))
                    avlResTmp.append([itemW, itemH])

    # Sort the list and return as readable resolution strings
    avlResTmp.sort(key=operator.itemgetter(0), reverse=reverseOrder)
    for res in avlResTmp:
        avlRes.append(str(res[0]) + 'x' + str(res[1]))
    return avlRes


# Convert string to number
def strToNumber(stringnr, toInt=False):
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
def hasStringInFile(searchString, filePath):
    if exists(filePath):
        with open(filePath) as f:
            for line in f:
                if re.search("{0}".format(searchString), line):
                    return True
    return False


# Check if a package is installed
def isPackageInstalled(packageName, alsoCheckVersion=True):
    isInstalled = False
    try:
        cmd = 'dpkg-query -l %s | grep ^i' % packageName
        if '*' in packageName:
            cmd = 'aptitude search -w 150 %s | grep ^i' % packageName
        pckList = getoutput(cmd)
        for line in pckList:
            matchObj = re.search('([a-z]+)\s+([a-z0-9\-_\.]*)', line)
            if matchObj:
                if matchObj.group(1)[:1] == 'i':
                    if alsoCheckVersion:
                        cache = apt.Cache()
                        pkg = cache[matchObj.group(2)]
                        if pkg.installed.version == pkg.candidate.version:
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


def isRunningLive():
    liveDirs = ['/live', '/lib/live/mount', '/rofs']
    for ld in liveDirs:
        if exists(ld):
            return True
    return False


def getProcessPids(processName, fuzzy=True):
    if fuzzy:
        pids = getoutput("ps -ef | grep -v sudo | grep -v grep | grep '%s' | awk '{print $2}'" % processName)
    else:
        pids = getoutput("pidof %s" % processName)
    return pids


def isProcessRunning(processName, fuzzy=True, excludeSelf=True):
    pids = getProcessPids(processName, fuzzy)
    if pids[0] != '':
        return True
    return False


def get_apt_force():
    # --force-yes is deprecated in stretch
    force = '--force-yes'
    ver = strToNumber(getoutput("head -n 1 /etc/debian_version | sed 's/[a-zA-Z]/0/' 2>/dev/null || echo 0")[0])
    if ver == 0 or ver >= 9:
        force = '--allow-downgrades --allow-remove-essential --allow-change-held-packages'
    return force


# Class to run commands in a thread and return the output in a queue
class ExecuteThreadedCommands(threading.Thread):

    def __init__(self, commandList, theQueue=None, returnOutput=False):
        super(ExecuteThreadedCommands, self).__init__()
        self.commands = commandList
        self.queue = theQueue
        self.returnOutput = returnOutput

    def run(self):
        if isinstance(self.commands, (list, tuple)):
            for cmd in self.commands:
                self.exec_cmd(cmd)
        else:
            self.exec_cmd(self.commands)

    def exec_cmd(self, cmd):
        if self.returnOutput:
            ret = getoutput(cmd)
        else:
            ret = shell_exec(cmd)
        if self.queue is not None:
            self.queue.put(ret)
