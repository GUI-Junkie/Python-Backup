#!/usr/bin/python3
"""
Program dedicated to tracking and creating backup files
Created: 2018-07-30
"""
from datetime import datetime
from os import listdir, mkdir
from posixpath import isdir, getmtime
from subprocess import Popen, PIPE
from sys import argv

READ = 'r'
WRITE = 'w'
BACKUP_INI = 'backup.ini'


class Backup:
    def __init__(self, verbose_member=False):
        self.verbose = verbose_member
        self.last_date = None
        self.last_backup_folder = None
        self.this_backup_folder = datetime.today().strftime("%Y%m%d")
        self.base_folders = []
        self.backup = None  # backup directory
        self.always = []
        self.excluded = []
        self.normal = []
        self.individual = []
        section = 0

        try:
            # Open the .ini file
            with open(BACKUP_INI, READ) as file:
                for line in file:
                    # Check section we're in
                    if '[Backup date]' in line:
                        section = 1
                        continue
                    elif '[Base folders]' in line:
                        section = 2
                        continue
                    elif '[Backup folder]' in line:
                        section = 3
                        continue
                    elif '[Always]' in line:
                        section = 4
                        continue
                    elif '[Excluded]' in line:
                        section = 5
                        continue
                    elif '[Normal]' in line:
                        section = 6
                        continue
                    elif '[Individual files]' in line:
                        section = 7
                        continue
                    elif '#' == line[0] or '\n' == line:
                        continue

                    if 1 == section:
                        self.last_date = datetime.strptime(line[:-1], "%Y%m%d")
                        self.last_backup_folder = line[:-1]
                    elif 2 == section:
                        self.base_folders.append(line[:-1])
                    elif 3 == section:
                        self.backup = line[:-1]

                        # Check if the backup folder exists
                        #   If it doesn't exist, create it
                        if not isdir(self.backup):
                            command = f'Creating backup folder: {self.backup}'
                            if self.verbose:
                                print(command)
                            else:
                                mkdir(self.backup)
                    elif 4 == section:
                        self.always.append(line[:-1])
                    elif 5 == section:
                        self.excluded.append(line[:-1])
                    elif 6 == section:
                        self.normal.append(line[:-1])
                    elif 7 == section:
                        self.individual.append(line[:-1])

        except FileNotFoundError:
            # always, excluded & normal are empty
            pass

        self.modified = False
        self.checked = False    # If there are new folders found, this will be True

    def __del__(self):
        # If there are new folders found, this will be True
        if self.checked:
            return

        # If verbose, no command has been executed, so backup.ini should not be updated
        if self.verbose:
            return

        # Set the current date for the next backup
        with open(BACKUP_INI, WRITE) as file:
            file.write('[Backup date]\n')
            file.write('# Date (YYYYMMDD) since the last backup empty if for first backup.\n')
            file.write(self.this_backup_folder)
            file.write('\n')
            file.write('\n')

            file.write('[Base folders]\n')
            file.write('# These are the top most folders. Subfolders will be analyzed.\n')
            file.write('# Base folders are not backed up themselves.\n')
            for line in self.base_folders:
                file.write(line)
                file.write('\n')
            file.write('\n')

            file.write('[Backup folder]\n')
            file.write('# This is where the backup will be saved.\n')
            file.write(f'{self.backup}\n')
            file.write('\n')

            file.write('[Always]\n')
            file.write('# Folders that are always backed up because the content changes anyway.\n')
            for line in self.always:
                file.write(line)
                file.write('\n')
            file.write('\n')

            file.write('[Excluded]\n')
            file.write('# Folders that are never backed up because you don\'t want to back them up.\n')
            for line in self.excluded:
                file.write(line)
                file.write('\n')
            file.write('\n')

            file.write('[Normal]\n')
            file.write('# Folders that are checked before back-up.\n')
            file.write('#   If the folder has been modified, it will be backed up.\n')
            file.write('#   Otherwise, the folder will be moved to the new backup.\n')
            for line in self.normal:
                file.write(line)
                file.write('\n')
            file.write('\n')

            file.write('[Individual files]\n')
            file.write('# Files that you would like to back-up, but are not in any folder you would like to back-up.\n')
            file.write('#     For instance /etc/hosts\n')
            file.write('#     The program has no means of discovering these files, so add them ... individually.\n')
            for line in self.individual:
                file.write(line)
                file.write('\n')

    def _check_folders(self, path):
        # The goal is to find out if there was a modification
        if self.modified:
            return

        # Recursive check the last modified date
        for local_path in listdir(path):
            local_file = f'{path}/{local_path}'
            if isdir(local_file):
                # If there is no last backup
                if not self.last_date:
                    self.modified = True
                    return

                modified_date = datetime.utcfromtimestamp(getmtime(local_file))
                if modified_date > self.last_date:
                    self.modified = True
                    return

                # print(local_file)
                self._check_folders(local_file)

        # If there is no last backup
        if not self.last_date:
            self.modified = True

    def go(self):
        print('Checking for new folders.')
        self._check_new()
        if self.checked:
            return

        local_path = f'{self.backup}/{self.this_backup_folder}'
        if not isdir(local_path):
            command = f'Create current backup folder: {local_path})'
            if self.verbose:
                print(command)
            else:
                mkdir(local_path)

        # Backup files in base folders
        print('Backup files in base folders.')
        for local_path in self.base_folders:
            self._make_tarball(local_path)

        # Always backup
        print('Backup folders that should always be backed up.')
        self.modified = True
        for local_path in self.always:
            self._backup(local_path)

        # Normal folders, check if they're modified
        #   If they're not modified, move to new backup folder
        #   If they are modified, create new backup tarball
        print('Backup modified folders.')
        for local_path in self.normal:
            self.modified = False
            self._check_folders(local_path)
            self._backup(local_path)

        # Individual files
        print('Backup individual files.')
        for local_file in self.individual:
            command = f'tar -rf "{self.backup}/{self.this_backup_folder}/individual.tar" "{local_file}"'
            if self.verbose:
                print(command)
            else:
                p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
                p.wait()

        command = f'gzip -c "{self.backup}/{self.this_backup_folder}/individual.tar" > ' \
                  f'"{self.backup}/{self.this_backup_folder}/individual.tar.gz"'
        if self.verbose:
            print(command)
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
            p.wait()

        command = f'rm "{self.backup}/{self.this_backup_folder}/individual.tar"'
        if self.verbose:
            print(command)
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
            p.wait()

    def _check_new(self):
        # Below these base folders are "always", "excluded" and "normal" folders
        # Keep the newly found folders to show later
        new = []

        # Go through all base folders
        for path in self.base_folders:
            # Get the files and folders from the base folder
            for local_path in listdir(path):
                # Make a local path to check, only one level down
                local_folder = f'{path}/{local_path}'

                # If it is a folder
                if not isdir(local_folder):
                    continue

                # Check that the folder is now known
                if local_folder in self.always:
                    continue

                # Not excluded
                if local_folder in self.excluded:
                    continue

                # Definitely not known
                if local_folder in self.normal:
                    continue

                new.append(local_folder)

        # New folders detected
        if new:
            self.checked = True
            print('New folders detected')
            for line in new:
                print(line)

    def _backup(self, path):
        # tar -czvf /path/destine.tar.gz /path/origin
        i = path.rfind('/') + 1
        visible_name = path[i:]
        visible_name = visible_name.replace('.', '')
        # If the folder was modified since the last backup, create a new tarball
        if self.modified:
            command = f'tar -czf "{self.backup}/{self.this_backup_folder}/{visible_name}.tar.gz" "{path}"'
            if self.verbose:
                print(command)
            else:
                p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
                p.wait()

        else:
            # If the folder was not modified, just move the tarball to the next backup_folder
            if self.last_backup_folder \
             and self.last_backup_folder != self.this_backup_folder:
                command = f'mv "{self.backup}/{self.last_backup_folder}/{visible_name}.tar.gz" ' \
                          f'"{self.backup}/{self.this_backup_folder}/"'
                if self.verbose:
                    print(command)
                else:
                    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
                    p.wait()

    def _make_tarball(self, path):
        i = path.rfind('/') + 1
        visible_name = path[i:]
        visible_name = visible_name.replace('.', '')

        if self.verbose:
            print('Make tarball')
        for local_path in listdir(path):
            local_file = f'{path}/{local_path}'
            if not isdir(local_file) and '.' != local_path[0]:
                # Make a local path to add to the tar file
                command = f'tar -rf "{self.backup}/{self.this_backup_folder}/{visible_name}.tar" "{local_file}"'
                if self.verbose:
                    print(command)
                else:
                    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
                    p.wait()

        # Make the tarball
        command = f'gzip -c "{self.backup}/{self.this_backup_folder}/{visible_name}.tar" > ' \
                  f'"{self.backup}/{self.this_backup_folder}/{visible_name}.tar.gz"'
        if self.verbose:
            print(command)
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
            p.wait()

        # Remove the tar file
        command = f'rm "{self.backup}/{self.this_backup_folder}/{visible_name}.tar"'
        if self.verbose:
            print(command)
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
            p.wait()

        if self.verbose:
            print('FIN Make tarball')


if __name__ == '__main__':
    tStart = datetime.now()

    # print command line arguments
    verbose = False
    for arg in argv[1:]:
        if '-v' == arg:
            verbose = True

    backup = Backup(verbose)
    backup.go()

    backup = None

    tFin = datetime.now()
    tDiff = tFin - tStart
    print("\nDuration:", ''.join([str(tDiff.seconds), ":", str(tDiff.microseconds)]))
