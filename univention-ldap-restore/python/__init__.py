#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright 2018-2022 Univention GmbH
#
# https://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <https://www.gnu.org/licenses/>.

import argparse
import sys
import univention.config_registry

from .restore_ldap_object_from_backup import MyRestore


BLACKLIST_ATTRS = ['uid', 'uidNumber', 'sambaSID', 'entryUUID']


def main():

	# exit if we are not on master
	ucr = univention.config_registry.ConfigRegistry()
	ucr.load()
	if ucr['server/role'] != "domaincontroller_master":
		print('This script can only be run on a domaincontroller master.')
		sys.exit(0)

	# arg parser
	usage = '%(prog)s --dn [DN] -b [backup file]'
	description = '%(prog)s is a program to revive deleted LDAP objects from a backup file'
	epilog = 'Known limitations:\n'
	epilog += '  * Objects added from backup always get a new entryUUID and an new samba SID'
	parser = argparse.ArgumentParser(usage=usage, description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('-b', '--backup-file', help='gz ldif backup file (/var/univention-backup/ldap-backup_20180604.ldif.gz)')
	parser.add_argument('-d', '--dn', help='LDAP DN to look for in backup')
	parser.add_argument('-l', '--list-dns', action='store_true', help='list all LDAP DNs from backup and exit')
	parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
	parser.add_argument('-m', '--restore-membership', action='store_true', help='restore uniqueMember of DN')
	parser.add_argument('-r', '--delete-missing', action='store_true', help='delete LDAP object if object is not in backup')
	parser.add_argument('-n', '--dry-run', action='store_true', help='dry run, make no changes in LDAP')
	args = parser.parse_args()
	if not args.list_dns and not args.dn:
		parser.error('--dn is mandatory!')
	if not args.backup_file:
		parser.error('--backup-file is mandatory!')

	# get data
	rst = MyRestore(args=args, add_blacklist_attrs=BLACKLIST_ATTRS)
	rst.get_backup_data()
	rst.get_ldap_data()

	# list dn's and exit
	if args.list_dns:
		sys.exit(0)

	# verbose output
	if rst.backup_data and args.verbose:
		print('\tFound DN {0} in backup with:'.format(args.dn))
		my_pretty_print(rst.backup_data)
		print('\tWith unique member in:')
		my_pretty_print(list(rst.unique_member_of))

	# do it
	if rst.backup_data:
		if not rst.backup_udm_object:
			print('ERROR: Could not identify UDM object from backup data!')
			sys.exit(1)
		if rst.ldap_data:
			# update
			print('Object found in LDAP, updating LDAP object {0} from backup.'.format(args.dn))
			rst.update_from_backup()
		else:
			# add
			print('Object not found in LDAP, adding object {0} from backup.'.format(args.dn))
			ret = rst.check_blacklist_attrs()
			if ret:
				print('ERROR: An object with the same {0} ({1}) already exists as {2} in the LDAP directory, exiting!'.format(ret.attr, ret.value, ret.dn))
				sys.exit(1)
			rst.add_from_backup()
		# and update groups
		if args.restore_membership and rst.unique_member_of:
			print('Updating membership (adding {0} to groups {1}).'.format(args.dn, ', '.join(list(rst.unique_member_of))))
			rst.update_membership()
	else:
		if rst.ldap_data and args.delete_missing:
			# object not in backup but in ldap -> delete
			print('Delete LDAP object {0} as no object could be found in backup.'.format(args.dn))
			rst.delete_in_ldap()
		else:
			print('Nothing found in backup and LDAP, nothing to do.')

	return 0


if __name__ == '__main__':
	main()
	sys.exit(0)
