#!/bin/sh
# Official MySQL entrypoint sources this file: isolate shell flags and MYSQL_PWD.
(
set -eu
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql -uroot --default-character-set=utf8mb4 <<SQL
CREATE DATABASE IF NOT EXISTS hmdp_0 CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS hmdp_1 CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'hmdp'@'%' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
GRANT ALL PRIVILEGES ON hmdp_0.* TO 'hmdp'@'%';
GRANT ALL PRIVILEGES ON hmdp_1.* TO 'hmdp'@'%';
SQL

)
