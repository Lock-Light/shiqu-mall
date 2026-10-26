#!/bin/sh
set -eu
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 <<'SQL'
CREATE DATABASE IF NOT EXISTS hmdp_0 CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS hmdp_1 CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'hmdp'@'%' IDENTIFIED BY 'plus-local';
GRANT ALL PRIVILEGES ON hmdp_0.* TO 'hmdp'@'%';
GRANT ALL PRIVILEGES ON hmdp_1.* TO 'hmdp'@'%';
SQL
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 < /seed/hmdp_0.sql
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 < /seed/hmdp_1.sql
