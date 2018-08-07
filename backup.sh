# Open the backup.ini file to see the different sections

# Dry-run the backup utility, use -v (for verbose)
#python3 backup.py -v

# To run the backup utility, use without -v
python3 backup.py

# When new folders are found below the base folders (first level only)
# The program prints the folders.
# The user can copy these folders to different sections within the backup.ini file

# [Always]
# Folders that are always backed up because the content changes anyway.

# [Excluded]
# Folders that are never backed up because you don't want to back them up.

# [Normal]
# Folders that are checked before back-up.
#   If the folder has been modified, it will be backed up.
#   Otherwise, the folder will be moved to the new backup.

# [Individual files]
# Files that you would like to back-up, but are not in any folder you would like to back-up.
#     For instance /etc/hosts
#     The program has no means of discovering these files, so add them ... individually.
