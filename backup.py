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


class PipeError(Exception):
    pass


def pipe(command):
    with Popen(command, stdout=PIPE, stderr=PIPE, shell=True) as proc:
        err = proc.stderr.read().decode()
        # out = proc.stdout.read().decode()
        # print(f"Out: {out}")
        if err:
            if "Removing leading `/' from member names" not in err:
                print(f"Error executing command: {command}")
                raise PipeError(err)


class Backup:
    def __init__(self, verbose_member=False):
        self.always = []                # Folders that will always be backed up
        self.backup = None              # Backup folder (where the backups will be saved)
        self.base_folders = []          # Base folder to be checked to see if backup is needed
        self.checked = False            # If there are new folders found under the base folders, this will be True
        self.excluded = []              # Folders that will never be backed up
        self.individual = []            # Individual files to be backed up, not under the base folders
        self.last_backup_folder = None  # Folder under the backup folder, with the date of the last backup
        self.last_date = None           # Date of the last backup (or None)
        self.modified = False           # If a folder under the base folder has been modified, a backup is needed
        self.normal = []                # The folders that will be backed up if needed (moved, if not)
        # Folder under the backup folder, with the date of the last backup
        self.this_backup_folder = datetime.today().strftime("%Y%m%d")
        self.verbose = verbose_member   # If verbose, no commands will be executed, they will be displayed

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
                        else:
                            # Clean-up the backup drive
                            # Remove outdated backup folders
                            self.cleanup_drive()
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
            # Create an empty ini file
            self._exit('backup.ini file created...')

        if not self.backup:
            self._exit('Please indicate the backup folder in the backup.ini file.')

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
            if self.this_backup_folder:
                file.write(f'{self.this_backup_folder}\n')
            file.write('\n')

            file.write('[Base folders]\n')
            file.write('# These are the top most folders. Subfolders will be analyzed.\n')
            file.write('# Base folders are not backed up themselves.\n')
            for line in self.base_folders:
                file.write(f'{line}\n')
            file.write('\n')

            file.write('[Backup folder]\n')
            file.write('# This is where the backup will be saved.\n')
            if self.backup:
                file.write(f'{self.backup}\n')
            file.write('\n')

            file.write('[Always]\n')
            file.write('# Folders that are always backed up because the content changes anyway.\n')
            for line in self.always:
                file.write(f'{line}\n')
            file.write('\n')

            file.write('[Excluded]\n')
            file.write('# Folders that are never backed up because you don\'t want to back them up.\n')
            for line in self.excluded:
                file.write(f'{line}\n')
            file.write('\n')

            file.write('[Normal]\n')
            file.write('# Folders that are checked before back-up.\n')
            file.write('#   If the folder has been modified, it will be backed up.\n')
            file.write('#   Otherwise, the folder will be moved to the new backup.\n')
            for line in self.normal:
                file.write(f'{line}\n')
            file.write('\n')

            file.write('[Individual files]\n')
            file.write('# Files that you would like to back-up, but are not in any folder you would like to back-up.\n')
            file.write('#     For instance /etc/hosts\n')
            file.write('#     The program has no means of discovering these files, so add them ... individually.\n')
            for line in self.individual:
                file.write(f'{line}\n')

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
                pipe(command)

        command = f'gzip -c "{self.backup}/{self.this_backup_folder}/individual.tar" > ' \
                  f'"{self.backup}/{self.this_backup_folder}/individual.tar.gz"'
        if self.verbose:
            print(command)
        else:
            pipe(command)

        command = f'rm "{self.backup}/{self.this_backup_folder}/individual.tar"'
        if self.verbose:
            print(command)
        else:
            pipe(command)

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
        # Full name to guarantee no file is overwritten
        backup_file_name = path.replace('/', '')
        backup_file_name = backup_file_name.replace('.', '')

        # If the folder was modified since the last backup, create a new tarball
        if self.modified:
            command = f'tar -czf "{self.backup}/{self.this_backup_folder}/{backup_file_name}.tar.gz" "{path}"'
            if self.verbose:
                print(command)
            else:
                pipe(command)

        else:
            # If the folder was not modified, just move the tarball to the next backup_folder
            if self.last_backup_folder \
             and self.last_backup_folder != self.this_backup_folder:
                command = f'mv "{self.backup}/{self.last_backup_folder}/{backup_file_name}.tar.gz" ' \
                          f'"{self.backup}/{self.this_backup_folder}/"'
                if self.verbose:
                    print(command)
                else:
                    pipe(command)

    def _make_tarball(self, path):
        # Only execute gzip if there is a tar file to prevent errors
        b_no_tar = True

        # Full name to guarantee no file is overwritten
        backup_file_name = path.replace('/', '')
        backup_file_name = backup_file_name.replace('.', '')

        if self.verbose:
            print('Make tarball')
        for local_path in listdir(path):
            local_file = f'{path}/{local_path}'
            if self.verbose:
                print(local_file)
            if not isdir(local_file) and '.' != local_path[0]:
                # Make a local path to add to the tar file
                command = f'tar -rf "{self.backup}/{self.this_backup_folder}/{backup_file_name}.tar" "{local_file}"'
                b_no_tar = False
                if self.verbose:
                    print(command)
                else:
                    pipe(command)

        # Only execute gzip if there is a tar file to prevent errors
        if b_no_tar:
            if self.verbose:
                print('No tarball made')
            return

        # Make the tarball
        command = f'gzip -c "{self.backup}/{self.this_backup_folder}/{backup_file_name}.tar" > ' \
                  f'"{self.backup}/{self.this_backup_folder}/{backup_file_name}.tar.gz"'
        if self.verbose:
            print(command)
        else:
            pipe(command)

        # Remove the tar file
        command = f'rm "{self.backup}/{self.this_backup_folder}/{backup_file_name}.tar"'
        if self.verbose:
            print(command)
        else:
            pipe(command)

        if self.verbose:
            print('FIN Make tarball')

    def _exit(self, message):
        self.backup = None              # Backup folder (where the backups will be saved)
        self.checked = False            # If there are new folders found under the base folders, this will be True
        self.last_backup_folder = None  # Folder under the backup folder, with the date of the last backup
        self.last_date = None           # Date of the last backup (or None)
        self.modified = False           # If a folder under the base folder has been modified, a backup is needed
        self.verbose = False            # If verbose, no commands will be executed, they will be displayed
        self.this_backup_folder = None  # Folder under the backup folder, with the date of the last backup
        print(message)
        exit()

    def cleanup_drive(self):
        # Delete all folders except 'laptop' and self.last_backup_folder
        path = self.backup
        for local_path in listdir(path):
            local_file = f'{path}/{local_path}'
            if isdir(local_file):
                if local_path != self.last_backup_folder and local_path != 'laptop':
                    command = f'rm -r "{local_file}"'
                    pipe(command)


if __name__ == '__main__':
    start_time = datetime.now()

    # print command line arguments
    verbose = False
    # verbose = True
    for arg in argv[1:]:
        if '-v' == arg:
            print("Verbose on")
            verbose = True

    backup = Backup(verbose)
    try:
        backup.go()
    except PipeError as err:
        # Prevent __del__ from making a new backup.ini file
        backup.verbose = True
        print(err)

    # If not verbose and no new folders found, make a new backup.ini file with the current date
    backup = None

    stop_time = datetime.now()
    time_delta = stop_time - start_time

    hours, remainder = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print("\nDuration:", f'{hours:02d}:{minutes:02d}:{seconds:02d} and {time_delta.microseconds} microseconds')
