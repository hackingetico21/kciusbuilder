#!/bin/bash

mysqld_safe &

sleep 5

mysql -u root <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '123';
FLUSH PRIVILEGES;
SOURCE /init.sql;
EOF

mysqladmin -uroot -p123 shutdown

