#!/bin/sh
set -eu
# First deployment only. Existing volumes always win over bundled snapshots.
if [ -z "$(ls -A /restore/redis)" ]; then
  cp /snapshot/redis.rdb /restore/redis/dump.rdb
  # Redis with appendonly=yes ignores a standalone dump.rdb when no AOF exists.
  # Load RDB first, then materialize AOF before starting the normal Redis service.
  redis-server --port 0 --unixsocket /tmp/restore.sock --unixsocketperm 700 \
    --dir /restore/redis --dbfilename dump.rdb --appendonly no \
    --daemonize yes --pidfile /tmp/restore.pid --logfile /tmp/restore.log
  trap 'redis-cli -s /tmp/restore.sock shutdown nosave >/dev/null 2>&1 || true' EXIT
  before=$(redis-cli -s /tmp/restore.sock DBSIZE)
  [ "$before" -gt 0 ] || { echo 'Refusing an empty Redis snapshot'; exit 1; }
  redis-cli -s /tmp/restore.sock CONFIG SET appendonly yes >/dev/null
  attempt=0
  while :; do
    info=$(redis-cli -s /tmp/restore.sock INFO persistence | tr -d '\r')
    if [ -s /restore/redis/appendonlydir/appendonly.aof.manifest ] &&
       echo "$info" | grep -q '^aof_rewrite_in_progress:0$' &&
       echo "$info" | grep -q '^aof_last_bgrewrite_status:ok$'; then
      break
    fi
    attempt=$((attempt+1))
    [ "$attempt" -lt 60 ] || { cat /tmp/restore.log; exit 1; }
    sleep 1
  done
  redis-cli -s /tmp/restore.sock shutdown save >/dev/null
  trap - EXIT
  chown -R redis:redis /restore/redis
  echo "Restored $before Redis keys and materialized AOF."
else
  [ -s /restore/redis/appendonlydir/appendonly.aof.manifest ] || {
    echo 'Existing Redis volume has no AOF manifest. Refusing to skip an incomplete restore.'
    exit 1
  }
  echo 'Redis volume already initialized; leaving all existing data intact.'
fi
if [ -z "$(ls -A /restore/uploads)" ]; then
  cp -a /snapshot/uploads/. /restore/uploads/
  echo 'Restored initial uploads.'
else
  echo 'Uploads already initialized; leaving all existing files intact.'
fi
