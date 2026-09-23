#!/bin/bash
set -e

# Prerequisites
sed -i 's/^post_max_size.*$/post_max_size = 20M/g' /etc/php/7.0/apache2/php.ini
sed -i 's/^upload_max_filesize.*$/upload_max_filesize = 20M/g' /etc/php/7.0/apache2/php.ini
systemctl reload apache2.service

ucr set mysql/config/mysqld/innodb_file_format="Barracuda" mysql/config/mysqld/innodb_file_per_table=1 mysql/config/mysqld/innodb_large_prefix=1
systemctl restart mysqld.service
 
# Create a database
## Generate your database password according to your machine password policy and save it in a secret file
eval "$(ucr --shell search machine/password/length machine/password/complexity)"
if [ -z "$machine_password_length" ]; then machine_password_length=20; fi
if [ -z "$machine_password_complexity" ]; then machine_password_complexity="scn"; fi
moodle_db_password="$(pwgen -1 -scn 20 | tee /etc/mysql-moodle.secret)"

## Create your moodle database and moodle database user
mysql -u root --password=$(cat /etc/mysql.secret) -e \
"CREATE DATABASE moodle DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; 
GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,DROP,INDEX,ALTER ON moodle.* TO 'moodle'@'localhost' IDENTIFIED BY '$moodle_db_password';"

# Download Moodle code
tmpdir=$(mktemp -d) # A temporary working directory
wget --show-progress -O $tmpdir/moodle-3.10.tgz https://download.moodle.org/download.php/direct/stable310/moodle-3.10.tgz
tar -xvzf $tmpdir/moodle-3.10.tgz -C /var/www/

## Set the correct folder and file permissions (This might take a few seconds)
chown -R www-data:www-data /var/www/moodle
find /var/www/moodle/ -type f -exec chmod 640 {} \;
find /var/www/moodle/ -type d -exec chmod 750 {} \;

## Create Moodle's data directory
mkdir /var/moodledata
chown -R www-data:www-data /var/moodledata
find /var/moodledata -type f -exec chmod 600 {} \;
find /var/moodledata -type d -exec chmod 700 {} \;

## Remove the temporary working directory again
rm -R $tmpdir

## Secure the Moodle directories by disabling apache2 directory listing
printf "\n\tOptions -Indexes\n\tAcceptPathInfo On\n" > /etc/apache2/conf-available/moodle.conf
a2enconf moodle
systemctl reload apache2

## Create cronjob for automatic user-cleanup
ucr set cron/moodle/command='php /var/www/moodle/admin/cli/cron.php' cron/moodle/time='*/10 * * * *'

# Configure Moodle
# Please set the basic data of your moodle and admin here
moodle_name_full="Moodle @ School"
moodle_name_short="Moodle" # Best just one word
moodle_summary="My Front Page"
moodle_language="en" # Installation and default site language by language code
moodle_web_address="https://master.cool-solutions.intranet/moodle" # It is important that this web address is the address that users will enter into the address bar of their browser to access Moodle. It should also begin with the https protocol.
admin_username="moodle-administrator" # Don't use an username already present inside your LDAP directory
admin_email="moodle-administrator@cool-solutions.intranet"

# Install Moodle
php /var/www/moodle/admin/cli/install.php \
 --non-interactive \
 --agree-license \
 --chmod=0750 \
 --lang="$moodle_language" \
 --wwwroot="$moodle_web_address" \
 --dataroot="/var/moodledata" \
 --dbtype="mariadb" \
 --dbhost="localhost" \
 --dbsocket=1 \
 --dbname="moodle" \
 --dbuser="moodle" \
 --dbpass="$(cat /etc/mysql-moodle.secret)" \
 --fullname="$moodle_name_full" \
 --shortname="$moodle_name_short" \
 --summary="$moodle_summary" \
 --adminuser="$admin_username" \
 --adminemail="$admin_email" \
 --adminpass="univention"

chown www-data:www-data /var/www/moodle/config.php
chmod 640 /var/www/moodle/config.php
chown -R www-data:www-data /var/moodledata
find /var/moodledata -type f -exec chmod 600 {} \;
find /var/moodledata -type d -exec chmod 700 {} \;
