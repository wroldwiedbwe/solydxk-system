#! /usr/bin/env python3

# Depends: curl

import os
import threading
import datetime
import re
from utils import getoutput, get_config_dict, get_debian_version
from os.path import join, abspath, dirname, exists, basename
from urllib.request import urlopen


def get_local_repos():
    # Get configured repos
    repos = []
    skip_repos = ['backports', 'security', 'updates']
    with open("/etc/apt/sources.list", 'r') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        matchObj = re.search("^deb\s+(https?:[\/a-zA-Z0-9\.\-]*).*", line)
        if matchObj:
            line = matchObj.group(0)
            repo = matchObj.group(1)
            # Do not add these repositories
            if not any(x in line for x in skip_repos):
                repos.append(repo)
    return repos


def get_mirror_data(excludeMirrors=[], getDeadMirrors=False):
    mirrorData = []
    scriptDir = abspath(dirname(__file__))
    config = get_config_dict(join(scriptDir, "solydxk-system.conf"))
    mirrors_url = config.get('MIRRORSLIST', 'https://repository.solydxk.nl/umfiles/mirrors.list')
    print(mirrors_url)
    mirrorsList = join(scriptDir, basename(mirrors_url))
    if getDeadMirrors:
        mirrorsList = "%s.dead" % mirrorsList

    try:
        # Download the mirrors list from the server
        url = mirrors_url
        if getDeadMirrors:
            url = "%s.dead" % url
        txt = urlopen(url).read().decode('utf-8')
        if txt != '':
            # Save to a file
            with open(mirrorsList, 'w') as f:
                f.write(txt)
    except:
        pass

    if exists(mirrorsList):
        with open(mirrorsList, 'r') as f:
            lines = f.readlines()
        for line in lines:
            data = line.strip().split(',')
            if len(data) > 2:
                if getDeadMirrors:
                    blnAdd = False
                    for repo in get_local_repos():
                        if data[2] in repo:
                            blnAdd = True
                            break
                else:
                    blnAdd = True
                    for excl in excludeMirrors:
                        if excl in data[2]:
                            blnAdd = False
                            break
                if blnAdd:
                    mirrorData.append(data)
    return mirrorData


class MirrorGetSpeed(threading.Thread):
    def __init__(self, mirrors, queue):
        threading.Thread.__init__(self)
        
        self.mirrors = mirrors
        self.queue = queue
        self.scriptDir = abspath(dirname(__file__))

    def run(self):
        httpCode = -1
        dlSpeed = 0
        mirror_index = 0
        for mirrorData in self.mirrors:
            mirror_index += 1
            try:
                mirror = mirrorData[3].strip()
                if mirror == "URL":
                    continue
                if mirror.endswith('/'):
                    mirror = mirror[:-1]

                # Only check Debian repository: SolydXK is on the same server
                httpCode = -1
                dlSpeed = 0
                config = get_config_dict(join(self.scriptDir, "solydxk-system.conf"))
                dl_file = config.get('DLTEST', 'extrafiles')
                url = os.path.join(mirror, dl_file)
                http = 'http://'
                if '://' in url:
                    http = ''
                cmd = "curl --connect-timeout 5 -m 5 -w '%%{http_code}\n%%{speed_download}\n' -o /dev/null -s --location %s%s" % (http, url)

                lst = getoutput(cmd)
                if len(lst) == 2:
                    httpCode = int(lst[0])
                    dlSpeed = lst[1]
                    # Download speed returns as string with decimal separator
                    # On non-US systems converting to float throws an error
                    # Split on the separator, and use the left part only
                    if ',' in dlSpeed:
                        dlSpeed = dlSpeed.split(',')[0]
                    elif '.' in dlSpeed:
                        dlSpeed = dlSpeed.split('.')[0]
                    dlSpeed = int(dlSpeed) / 1024

                    self.queue.put([mirror, "%d kb/s" % dlSpeed, mirror_index, len(self.mirrors)])
                    print(("Server {0} - {1} kb/s ({2})".format(mirror, dlSpeed, self.get_human_readable_http_code(httpCode))))

            except Exception as detail:
                # This is a best-effort attempt, fail graciously
                print(("Error: http code = {} / error = {}".format(self.get_human_readable_http_code(httpCode), detail)))

    def get_human_readable_http_code(self, httpCode):
        if httpCode == 200:
            return "OK"
        elif httpCode == 302:
            return "302: found (redirect)"
        elif httpCode == 403:
            return "403: forbidden"
        elif httpCode == 404:
            return "404: not found"
        elif httpCode >= 500:
            return "%d: server error" % httpCode
        else:
            return "Error: %d" % httpCode


class Mirror():
    def __init__(self):
        self.debian_version = get_debian_version()

    def save(self, replaceRepos, excludeStrings=[]):
        try:
            src = '/etc/apt/sources.list'
            if os.path.exists(src):
                new_repos = []
                srcList = []
                with open(src, 'r') as f:
                    srcList = f.readlines()

                # Get the suite of the Debian repositories
                debian_suite = ''
                matchObj = re.search("debian\.org\/debian/?\s+(\S*)", ' '.join(srcList))
                if matchObj:
                    debian_suite = matchObj.group(1).replace('-backports', '').replace('-updates', '')
                if debian_suite == '':
                    distribution = self.umglobal.getDistribution()
                    if 'ee' in distribution:
                        debian_suite = 'testing'
                    else:
                        debian_suite = 'stable'

                for line in srcList:
                    line = line.strip()
                    if not line.startswith('#'):
                        for repo in replaceRepos:
                            if repo[0] != '' and repo[0] in line:
                                skip = False
                                for excl in excludeStrings:
                                    if excl in line:
                                        skip = True
                                        break
                                if not skip:
                                    # Change repository url
                                    line = line.replace(repo[0], repo[1])
                                    break
                    if line != '':
                        new_repos.append(line)

                for repo in replaceRepos:
                    if repo[0] == '':
                        # Check if repo is already present in new_repos (replacement)
                        if not any(repo[1] in x for x in new_repos):
                            line = ''
                            http = ''
                            if repo[1][:4] != 'http':
                                http = 'http://'
                            if 'solydxk' in repo[1]:
                                solydxk_ext = str(self.debian_version)
                                if debian_suite == 'testing':
                                    solydxk_ext = 'ee'
                                line = "deb %s%s solydxk-%s main upstream import" % (http, repo[1], solydxk_ext)
                            elif 'debian.org/debian' in repo[1] and debian_suite != '':
                                line = "deb %s%s %s main contrib non-free" % (http, repo[1], debian_suite)
                            if line != '':
                                new_repos.append(line)

                if new_repos:
                    # Backup the current sources.list
                    dt = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    print(("Backup %(src)s to %(src)s.%(date)s" % { "src": src, "src": src, "date": dt }))
                    os.system("cp -f %s %s.%s" % (src, src, dt))
                    # Save the new sources.list
                    with open(src, 'w') as f:
                        for repo in new_repos:
                            f.write("%s\n" % repo)

            return ''

        except Exception as detail:
            # This is a best-effort attempt, fail graciously
            print(("Error: %s" % detail))
            return detail
