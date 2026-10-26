CREATE DATABASE cache_lab;
CREATE USER 'lab'@'%' IDENTIFIED BY 'cache-local';
GRANT ALL ON cache_lab.* TO 'lab'@'%';
CREATE USER 'canal'@'%' IDENTIFIED WITH mysql_native_password BY 'canal-local';
GRANT SELECT, REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'canal'@'%';
CREATE TABLE cache_lab.tb_shop(id BIGINT PRIMARY KEY,name VARCHAR(100));
INSERT INTO cache_lab.tb_shop VALUES(1,'cache-lab-original');
