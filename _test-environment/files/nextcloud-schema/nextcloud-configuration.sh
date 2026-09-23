#!/bin/bash

set -e
set -x

ldap_config_id=$1
config_path=$2

# create new config in the nextlcoud container
univention-app shell nextcloud sudo -u www-data php /var/www/html/occ ldap:create-empty-config

# read config and configure ldap
while read line
do
	univention-app shell nextcloud sudo -u www-data php /var/www/html/occ ldap:set-config $ldap_config_id $line
done < $config_path

# test configuration
# (not ldap:search: it iterates every configured LDAP backend, including the App
# Center's own default self-integration config that Nextcloud auto-registers against
# its *own* domain on install -- a separate, pre-existing config unrelated to this one
# that would otherwise fail the whole command if it has any connectivity trouble of its
# own. ldap:test-config only exercises the one backend we actually configured here.)
univention-app shell nextcloud sudo -u www-data php /var/www/html/occ ldap:test-config $ldap_config_id
