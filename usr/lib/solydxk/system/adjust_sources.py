#! /usr/bin/env python3

from os.path import exists, realpath
import re
from shutil import move
import time
import subprocess


class Sources():

    def __init__(self):
        self.domain = "solydxk.com"
        self.sourcesPath = "/etc/apt/sources.list"
        self.infoPath = '/usr/share/solydxk/info'
        self.sources = self.readSources()
        self.sourcesData = self.readData()
        self.deb_version = self.get_debian_version(True)
        self.is_ee = self.isEnthusiastsEdition()

    def readData(self):
        # Data file structure:
        # 0) active (0, 1)
        # 1) Debian version (0 = any)
        # 2) action (replace, remove, removeline, append)
        # 3) search string
        # 4) replace string

        data = []
        datPath = "%s.dat" % realpath(__file__)
        if exists(datPath):
            with open(datPath, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    lineData = line.split(',')
                    lineData[0] = self.str_to_nr(lineData[0], True)
                    lineData[1] = self.str_to_nr(lineData[1], True)
                    if lineData[0] == 1:
                        data.append(lineData)
        return data

    def readSources(self):
        sources = []
        if exists(self.sourcesPath):
            with open(self.sourcesPath, 'r') as f:
                for line in f.readlines():
                    sources.append(line.strip())
        return sources

    def isEnthusiastsEdition(self):
        with open(self.infoPath, 'r') as f:
            text = f.read()
            match = re.search('EDITION\s*\=\s*([a-z0-9]*)', text)
            # Check the last two characters
            if match.group(1).lower()[-4:-2] == 'ee':
                return True
        return False

    # Convert string to number
    def str_to_nr(self, stringnr, toInt=False):
        nr = 0
        stringnr = stringnr.strip()
        try:
            if toInt:
                nr = int(float(stringnr))
            else:
                nr = float(stringnr)
        except ValueError:
            nr = 0
        return nr

    # Get output of command
    def getoutput(self, command, always_as_list=False):
        try:
            output = subprocess.check_output(command, shell=True).decode('utf-8').strip().split('\n')
        except:
            # Even if an error occurs, don't crash here
            output = ['']
        if len(output) == 1 and not always_as_list:
            # Single line: return as string
            output = output[0]
        return output

    # Get Debian's version number (float)
    def get_debian_version(self, toInt=False):
        return self.str_to_nr(self.getoutput("head -n 1 /etc/debian_version | sed 's/[a-zA-Z]/0/' 2>/dev/null || echo 0"), toInt)

    def check(self):
        # Do not adjust sources.list for the EE
        if not self.is_ee:
            newSources = []
            changed = False

            #print(('= deb_version ===================================='))
            #print((self.deb_version))
            #print(('= sources ===================================='))
            #print((self.sources))
            #print(('= sourcesData ===================================='))
            #print((self.sourcesData))
            #print(('====================================='))

            # Replace and remove
            for line in self.sources:
                if "solydxk" in line:
                    for data in self.sourcesData:
                        if data[3] in line and \
                           (data[1] == self.deb_version or
                           data[1] == 0):
                            if data[2] == "replace":
                                # Check if the line has been commented out
                                match = re.search('(.*)deb\s+http', line)
                                comment = match.group(1)
                                if comment != '':
                                    comment += ' '
                                # Save the new line
                                line = "%s%s" % (comment, data[4])
                                changed = True
                            elif data[2] == "remove":
                                # Remove search string from line
                                line = line.replace(data[3], '')
                                changed = True
                            elif data[2] == "removeline":
                                # Remove the line
                                line = ''
                                changed = True
                # Add line to the new sources list
                if line != '':
                    newSources.append(line.strip())

            # Append
            for data in self.sourcesData:
                if data[2] == "append" and \
                   (data[1] == self.deb_version or
                   data[1] == 0):
                    append = True
                    appLine = data[3].strip()

                    # Now check if the line already exists
                    for line in newSources:
                        if appLine in line:
                            append = False
                            break

                    if append:
                        newSources.append(data[4].strip())
                        changed = True

            # Write the new sources.list file
            if changed and len(newSources) > 2:
                # Backup current sources.list
                bak = time.strftime("%Y%m%d%H%M")
                move(self.sourcesPath, "%s.bak-%s" % (self.sourcesPath, bak))
                with open(self.sourcesPath, 'w') as f:
                    f.write('\n'.join(newSources) + '\n')
