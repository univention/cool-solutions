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

import gzip
import pprint

from ldif import LDIFParser
from ldap.filter import escape_filter_chars
from ldap.modlist import addModlist, modifyModlist

import univention.admin.uldap
import univention.admin.objects
import univention.admin.modules
import univention.admin.config
import univention.config_registry




def my_pretty_print(obj, indent=2):
	tmp = pprint.pformat(obj)
	for i in tmp.split('\n'):
		print(('\t' * indent + i))


def filter_modlist(_input):
	output = []
	filter_values = [
		"entryUUID",
		"structuralObjectClass",
		"creatorsName",
		"createTimestamp",
		"entryCSN",
		"modifiersName",
		"modifyTimestamp",
	]
	for _item in _input:
		if all(x not in filter_values for x in _item):
			output.append(_item)
	return output


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
		self.operational_mark = [b'directoryOperation', b'dSAOperation', b'distributedOperation']
		self.operational_attributes = set([b'entryCSN', b'entrycsn'])

	def get_backup_data(self):
		print('Checking backup file {0}.'.format(self.args.backup_file))
		with gzip.open(self.args.backup_file, 'rb') as f:
			self.ldif_parser = LDIFParser(f)
			self.ldif_parser.handle = self.ldap_parser_handle
			self.ldif_parser.parse()

	def identify_udm(self, entry):
		try:
			udm_type = entry.get('univentionObjectType', [None])[0].decode('utf-8')
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
				if self.args.dn.lower().encode() in map(bytes.lower, entry.get('uniqueMember', [])):
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
					attr = i.split(b'NAME ')[1].split(b"'")[1]
					self.operational_attributes.add(attr)
					self.operational_attributes.add(attr.lower())

	def create_modlist(self, new=None, old=None):
		ml = list()
		if new and not old:
			ml = addModlist(new, ignore_attr_types=self.operational_attributes)
		elif new and old:
			ml = modifyModlist(old, new, ignore_attr_types=self.operational_attributes)
		ml = filter_modlist(ml)
		return ml

	def dn_exists(self, dn):
		return bool(self.lo.get(dn))

	def check_blacklist_attrs(self):
		for attr in self.add_blacklist_attrs:
			val = self.backup_data.get(attr, [None])[0]
			if val:
				l_filter = '({0}={1})'.format(attr, escape_filter_chars(val.decode()))
				res = self.lo.search(l_filter)
				if res:
					return argparse.Namespace(value=val, attr=attr, dn=res[0][0])
		return None

	# modify
	def update_from_backup(self):
		self.get_ldap_data()
		ml = self.create_modlist(new=self.backup_data, old=self.ldap_data)
		ml = filter_modlist(ml)
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
		ml = filter_modlist(ml)
		if self.args.verbose or self.args.dry_run:
			print(('\tAdding {0} with modlist:'.format(self.args.dn)))
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
		return self.__backup_data

	@backup_data.setter
	def backup_data(self, mydata):
		self.__backup_data = mydata

	@property
	def backup_udm_object(self):
		return self.identify_udm(self.backup_data)

	@property
	def ldap_udm_object(self):
		self.get_ldap_data()
		return self.identify_udm(self.ldap_data)

	@property
	def unique_member_of(self):
		return self.__unique_member_of

	@unique_member_of.setter
	def unique_member_of(self, myset):
		self.__unique_member_of = myset

	@property
	def ldap_data(self):
		return self.__ldap_data

	@ldap_data.setter
	def ldap_data(self, myldapdata):
		self.__ldap_data = myldapdata
