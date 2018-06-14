#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Copyright 2018 Univention GmbH
#
# http://www.univention.de/
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
# <http://www.gnu.org/licenses/>.

import argparse
import gzip
import sys
import pprint

from ldif import LDIFParser
from ldap.filter import escape_filter_chars
from ldap.modlist import addModlist, modifyModlist

import univention.admin.uldap
import univention.admin.objects
import univention.admin.modules
import univention.admin.config
import univention.config_registry

BLACKLIST_ATTRS = ['uid', 'uidNumber', 'sambaSID', 'entryUUID']


def my_pretty_print(obj, indent=2):
	tmp = pprint.pformat(obj)
	for i in tmp.split('\n'):
		print('\t' * indent + i)


class MyRestore():

	def __init__(self, args=None, add_blacklist_attrs=None):
		self.args = args
		self.add_blacklist_attrs = add_blacklist_attrs
		self.unique_member_of = set()
		self.backup_data = None
		self.ldap_data = None
		self.lo, self.position = univention.admin.uldap.getAdminConnection()
		self.co = univention.admin.config.config()
		self.ucr = univention.config_registry.ConfigRegistry()
		self.ucr.load()
		univention.admin.modules.update()
		self.operational_mark = ['directoryOperation', 'dSAOperation', 'distributedOperation']
		self.operational_attributes = set(['entryCSN', 'entrycsn'])
		self.get_operational_attributes()

	def get_backup_data(self):
		print('Checking backup file {0}.'.format(self.args.backup_file))
		with gzip.open(self.args.backup_file, 'rb') as f:
			self.ldif_parser = LDIFParser(f)
			self.ldif_parser.handle = self.ldap_parser_handle
			self.ldif_parser.parse()

	def identify_udm(self, entry):
		try:
			udm_type = entry.get('univentionObjectType', [None])[0]
			univention.admin.modules.update()
			udm = univention.admin.modules.get(udm_type)
			univention.admin.modules.init(self.lo, self.position, udm)
			return udm.object(self.co, self.lo, self.position, dn=self.args.dn, attributes=entry)
		except Exception:
			return None

	def ldap_parser_handle(self, dn, entry):
		if self.args.verbose or self.args.list_dns:
			print('\t{0}: {1}'.format(self.ldif_parser.records_read, dn))
		if self.args.dn:
			if self.args.restore_membership:
				if self.args.dn.lower() in map(str.lower, entry.get('uniqueMember', [])):
					self.unique_member_of.add(dn)
			if self.args.dn.lower() == dn.lower():
				if not self.args.restore_membership:
					self._max_entries = 1
				self.backup_data = entry

	def get_ldap_data(self):
		self.ldap_data = self.lo.get(self.args.dn)

	def get_operational_attributes(self):
		schema = self.lo.search(filter='(objectClass=subschema)', base='cn=subschema', scope='base', attr=['*', '+'])
		for i in schema[0][1].get('attributeTypes'):
			for j in self.operational_mark:
				if j.lower() in i.lower():
					attr = i.split('NAME ')[1].split("'")[1]
					self.operational_attributes.add(attr)
					self.operational_attributes.add(attr.lower())

	def create_modlist(self, new=None, old=None):
		ml = list()
		if new and not old:
			ml = addModlist(new, ignore_attr_types=self.operational_attributes)
		elif new and old:
			ml = modifyModlist(old, new, ignore_attr_types=self.operational_attributes)
		return ml

	def dn_exists(self, dn):
		return bool(self.lo.get(dn))

	def check_blacklist_attrs(self):
		for attr in self.add_blacklist_attrs:
			val = self.backup_data.get(attr, [None])[0]
			if val:
				l_filter = '({0}={1})'.format(attr, escape_filter_chars(val))
				res = self.lo.search(l_filter)
				if res:
					return argparse.Namespace(value=val, attr=attr, dn=res[0][0])
		return None

	# modify

	def update_from_backup(self):
		self.get_ldap_data()
		ml = self.create_modlist(new=self.backup_data, old=self.ldap_data)
		if ml:
			if self.args.verbose or self.args.dry_run:
				print('\tUpdating {0} with modlist:'.format(self.args.dn))
				my_pretty_print(ml)
			if not self.args.dry_run:
				try:
					self.lo.lo.modify_ext_s(self.args.dn, ml)
				except Exception:
					print('ERROR: Modify {0} with attributes'.format(self.args.dn))
					pprint.pprint(ml)
					print('failed with:')
					raise
		else:
			print('No changes from backup data.')

	def update_membership(self):
		if self.args.dry_run:
			udm_object = self.backup_udm_object
		else:
			udm_object = self.ldap_udm_object
		udm_object.open()
		if 'groups' in udm_object:
			udm_object['groups'] = list()
			for grp in self.unique_member_of:
				if self.dn_exists(grp):
					if self.args.verbose or self.args.dry_run:
						print('Adding group {0} to {1}'.format(grp, self.args.dn))
					udm_object['groups'].append(grp)
			if not self.args.dry_run:
				udm_object.modify()

	def add_from_backup(self):
		ml = self.create_modlist(new=self.backup_data)
		if self.args.verbose or self.args.dry_run:
			print('\tAdding {0} with modlist:'.format(self.args.dn))
			my_pretty_print(ml)
		if not self.args.dry_run:
			try:
				self.lo.add(self.args.dn, ml, exceptions=True)
			except Exception:
				print('ERROR: Adding {0} with attributes'.format(self.args.dn))
				pprint.pprint(ml)
				print('failed with:')
				raise

	def delete_in_ldap(self):
		udm_object = self.ldap_udm_object
		if udm_object:
			udm_object.open()
			if self.args.verbose or self.args.dry_run:
				print('\tRemoving {0} from LDAP.'.format(self.args.dn))
			if not self.args.dry_run:
				udm_object.remove()

	# properties

	@property
	def backup_data(self):
		return self.backup_data

	@property
	def backup_udm_object(self):
		return self.identify_udm(self.backup_data)

	@property
	def ldap_udm_object(self):
		self.get_ldap_data()
		return self.identify_udm(self.ldap_data)

	@property
	def unique_member_of(self):
		return self.unique_member_of

	@property
	def ldap_data(self):
		return self.ldap_data


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
