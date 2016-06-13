#! /usr/bin/env python3

from os.path import exists, realpath
import re
from shutil import move
import time


class Sources():

    def __init__(self):
        self.domain = "solydxk.com"
        self.sourcesPath = "/etc/apt/sources.list"
        self.business = False
        self.sources = self.readSources()
        self.sourcesData = self.readData()

    def readData(self):
        # Data file structure:
        # 0) active (0, 1)
        # 1) action (replace, remove, removeline, append)
        # 2) search string
        # 3) replace string

        data = []
        datPath = "%s.dat" % realpath(__file__)
        if exists(datPath):
            with open(datPath, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    lineData = line.split(',')
                    if lineData[0] == '1':
                        data.append(lineData)
        return data

    def readSources(self):
        sources = []
        if exists(self.sourcesPath):
            with open(self.sourcesPath, 'r') as f:
                for line in f.readlines():
                    sources.append(line.strip())
                    if not self.business:
                        if "business" in line or "wheezy" in line:
                            self.business = True
        return sources

    def isEnthusiastsEdition(self):
        infoPath = '/etc/solydxk/info'
        with open(infoPath, 'r') as f:
            text = f.read()
            match = re.search('EDITION\s*\=\s*([a-z0-9]*)', text)
            # Check the last two characters
            if match.group(1).lower()[-4:-2] == 'ee':
                return True
        return False

    def check(self):
        # Do not adjust sources.list for the EE
        if not self.isEnthusiastsEdition():
            newSources = []
            changed = False

            # Replace and remove
            for line in self.sources:
                if "solydxk" in line:
                    for data in self.sourcesData:
                        if data[2] in line:
                            if data[1] == "replace":
                                # Check if the line has been commented out
                                match = re.search('(.*)deb\s+http', line)
                                comment = match.group(1)
                                if comment != '':
                                    comment += ' '
                                # Save the new line
                                line = "%s%s" % (comment, data[3])
                                changed = True
                            elif data[1] == "remove":
                                # Remove search string from line
                                line = line.replace(data[2], '')
                                changed = True
                            elif data[1] == "removeline":
                                # Remove the line
                                line = ''
                                changed = True
                # Add line to the new sources list
                if line != '':
                    newSources.append(line.strip())

            # Append
            for data in self.sourcesData:
                if data[1] == "append":
                    append = True
                    appLine = data[2].strip()

                    # Ugly hack to make sure the right backports are added
                    if self.business:
                        if "jessie" in data[3]:
                            append = False
                    else:
                        if "wheezy" in data[3]:
                            append = False

                    # Now check if the line already exists
                    if append:
                        for line in newSources:
                            if appLine in line:
                                append = False
                                break
                    if append:
                        newSources.append(data[3].strip())
                        changed = True

            # Write the new sources.list file
            if changed and len(newSources) > 2:
                # Backup current sources.list
                bak = time.strftime("%Y%m%d%H%M")
                move(self.sourcesPath, "%s.bak-%s" % (self.sourcesPath, bak))
                with open(self.sourcesPath, 'w') as f:
                    f.write('\n'.join(newSources) + '\n')
