#!/usr/bin/env bash
# Backs up the database and uploaded images. Run it from cron, e.g. every night at 02:30:
#   30 2 * * * /path/to/iniyavan/backup.sh >> /var/log/engtutor-backup.log 2>&1
# Options: --dir /somewhere (or BACKUP_DIR in .env), --keep-days 14. Copy the folder off the server too.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/manage.sh" backup "$@"
