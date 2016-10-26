#
# Regular cron jobs for the univention-lets-encrypt package
#
0 4	* * *	root	[ -x /usr/bin/univention-lets-encrypt_maintenance ] && /usr/bin/univention-lets-encrypt_maintenance
