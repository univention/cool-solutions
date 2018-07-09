#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
#
"""user group sync sink
    data import program"""
#
# Copyright 2013-2018 Univention GmbH
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

import cPickle as pickle
import fcntl
import os
import re
import sys

import univention.admin.config
import univention.admin.modules as udm
import univention.admin.objects
import univention.admin.uldap
import univention.config_registry

DATABASE_PATH = '/var/lib/dataport-user-group-sync-sink'
DATABASE_ENTRY_FORMAT = re.compile('^[0-9]{11}[.][0-9]{7}$')

LOCK_FD = open(sys.argv[0], 'rb')
def _take_lock():
	fcntl.flock(LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB) # EXclusive and NonBlocking

def _release_lock():
	fcntl.flock(LOCK_FD, fcntl.LOCK_UN) # UNlock

def _find_files():
	for filename in os.listdir(DATABASE_PATH):
		if DATABASE_ENTRY_FORMAT.match(filename):
			timestamp = _decode_filename(filename)
			path = os.path.join(DATABASE_PATH, filename)
			yield (timestamp, path, )

def _decode_filename(filename):
	"""decode a unix timestamp formatted into a filename via %019.7f
	returns a <float> unix timestamp"""
	return float(filename)

def _decode_data(raw):
	return pickle.loads(raw)

def _read_file(path):
	raw_data = open(path, 'rb').read()
	return _decode_data(raw_data)

def readUCRV(usedUCRVdefaults):
	'''return a dict with the supplied UCRV set to the current value
	or the supplied default value if unset'''
	configRegistry = univention.config_registry.ConfigRegistry()
	configRegistry.load()
	variables = {}
	for (variable, defaultValue, ) in usedUCRVdefaults.items():
		if type(defaultValue) is bool:
			variables[variable] = configRegistry.is_true(variable, defaultValue)
		elif type(defaultValue) is int:
			variables[variable] = int(configRegistry.get(variable, defaultValue))
		else:
			variables[variable] = configRegistry.get(variable, defaultValue)
			if defaultValue is None:
				if variables[variable] is None:
					raise ValueError('Required UCRV %r is unset.' % (variable, ))
	return variables
UCRV = readUCRV({
		'ldap/base': None,
		'ldap/hostdn': None,
		'ldap/master': None,
		'ldap/master/port': 0,
		'dataport/user_group_sync/sink/user_container': None,
		'dataport/user_group_sync/sink/group_container': None,
		})

def _random_password(_):
	return os.urandom(33).encode('base64').strip()

# these will be set by a call to <connectToLdap>
ldapObject = None
configObject = None
positionUser = None
positionGroup = None
udmUserSearch = None
udmUserNew = None
udmModuleUsersUser = None
udmGroupSearch = None
udmGroupNew = None
udmModuleGroupsGroup = None
def _connectToLdap():
	'''establish connection to LDAP via UDM
	create global helper functions
	<udmUserSearch>,
	<udmUserNew>,
	<udmGroupSearch>,
	<udmGroupNew>,
	<ldapObject>
	'''
	global ldapObject, configObject, positionUser, positionGroup
	global  udmUserSearch,  udmUserNew, udmModuleUsersUser
	global udmGroupSearch, udmGroupNew, udmModuleGroupsGroup
	ldapObject = univention.admin.uldap.access(
		host=UCRV['ldap/master'],
		port=UCRV['ldap/master/port'],
		base=UCRV['ldap/base'],
		binddn='cn=admin,' + UCRV['ldap/base'],
		bindpw=open('/etc/ldap.secret', 'rb').read().rstrip('\n'),
		)
	ldapBase = univention.admin.uldap.position(ldapObject.base)
	configObject = {'base': ldapObject.base, }
	udm.update()
	# initialise modules
	udmModuleUsersUser   = udm.get('users/user')
	udmModuleGroupsGroup = udm.get('groups/group')
	udm.init(ldapObject, ldapBase, udmModuleUsersUser)
	udm.init(ldapObject, ldapBase, udmModuleGroupsGroup)
	# position for new objects
	positionUser  = univention.admin.uldap.position(ldapBase.getDn())
	positionGroup = univention.admin.uldap.position(ldapBase.getDn())
	positionUser .setDn(UCRV['dataport/user_group_sync/sink/user_container'])
	positionGroup.setDn(UCRV['dataport/user_group_sync/sink/group_container'])
	# create functions
	udmUserSearch  = lambda *args, **kwargs: udm.lookup(udmModuleUsersUser  , configObject, ldapObject, scope='sub', *args, **kwargs)
	udmGroupSearch = lambda *args, **kwargs: udm.lookup(udmModuleGroupsGroup, configObject, ldapObject, scope='sub', *args, **kwargs)
	udmUserNew  = lambda: udmModuleUsersUser  .object(configObject, ldapObject, positionUser)
	udmGroupNew = lambda: udmModuleGroupsGroup.object(configObject, ldapObject, positionGroup)

def main():
	_take_lock()
	_connectToLdap()
	_process_files()
	_release_lock()

def _process_files():
	'''process the first <_process_files.limit> files'''
	for (_, path, ) in sorted(_find_files())[:_process_files.limit]:
		_process_file(path)
_process_files.limit = 1000

def _process_file(path):
	data = _read_file(path)
	_import(data)
	os.remove(path)

def _user_exists(attributes):
	search_filter = univention.admin.filter.expression('uid', attributes['uid'][0])
	result = udmModuleUsersUser.lookup(configObject, ldapObject, search_filter)
	if not result:
		return None
	else:
		return result[0]

def _group_exists(attributes):
	search_filter = univention.admin.filter.expression('cn', attributes['cn'][0])
	result = udmModuleGroupsGroup.lookup(configObject, ldapObject, search_filter)
	if not result:
		return None
	else:
		return result[0]

def _is_user(object_dn, attributes):
	'''return whether the object is a user'''
	if 'users/user' in attributes.get('univentionObjectType', []):
		return True
	return udmModuleUsersUser.identify(object_dn, attributes)

def _is_group(object_dn, attributes):
	'''return whether the object is a group'''
	if 'groups/group' in attributes.get('univentionObjectType', []):
		return True
	return udmModuleGroupsGroup.identify(object_dn, attributes)

def _import(data):
	'''check object type and dispatch to specific import method'''
	(object_dn, attributes, ) = data
	if attributes: # create/modify
		if _is_user(object_dn, attributes):
			return _import_user(object_dn, attributes)
		if _is_group(object_dn, attributes):
			return _import_group(object_dn, attributes)
		print 'Unknown object type %r' % (object_dn, )
	else: # delete
		return _delete(object_dn)

def _delete(object_dn):
	if object_dn.startswith('uid='):
		return _delete_user(object_dn)
	if object_dn.startswith('cn='):
		return _delete_group(object_dn)
	print 'Unknown object type %r' % (object_dn, )

def _delete_user(user_dn):
	uid = user_dn.split(',', 1)[0].split('=', 1)[1]
	search_filter = univention.admin.filter.expression('uid', uid)
	for existing_user in udmModuleUsersUser.lookup(configObject, ldapObject, search_filter):
		existing_user.remove()

def _delete_group(group_dn):
	cn = group_dn.split(',', 1)[0].split('=', 1)[1]
	search_filter = univention.admin.filter.expression('cn', cn)
	for existing_group in udmModuleGroupsGroup.lookup(configObject, ldapObject, search_filter):
		existing_group.remove()

def _user_should_be_updated(existing_user, attributes):
	return existing_user.position.getDn().endswith(UCRV['dataport/user_group_sync/sink/user_container'])

def _group_should_be_updated(existing_group, attributes):
	return existing_group.position.getDn().endswith(UCRV['dataport/user_group_sync/sink/group_container'])

def _import_user(user_dn, attributes):
	existing_user = _user_exists(attributes)
	if existing_user is None:
		_create_user(attributes)
		existing_user = _user_exists(attributes)
	if _user_should_be_updated(existing_user, attributes):
		_update_user(existing_user, attributes)
	else:
		print 'Ignoring new %r for existing %r' % (user_dn, existing_user.position.getDn(), )

def _uid_to_dn(uid):
	'''return the would be DN for <uid>'''
	return 'uid=%s,%s' % (uid, UCRV['dataport/user_group_sync/sink/user_container'], )

def _uids_to_dns(uids):
	return map(_uid_to_dn, uids)

def _import_group(group_dn, attributes):
	existing_group = _group_exists(attributes)
	if existing_group is None:
		_create_group(attributes)
		existing_group = _group_exists(attributes)
	if _group_should_be_updated(existing_group, attributes):
		_update_group(existing_group, attributes)
	else:
		print 'Ignoring new %r for existing %r' % (group_dn, existing_group.position.getDn(), )

def _translate_user(attribute, value):
	(attribute, translate, ) = _translate_user.mapping.get(attribute, (None, None, ))
	if translate is not None:
		value = translate(value)
	return (attribute, value, )
_translate_user.mapping = {
	'givenName': ('firstname', univention.admin.mapping.ListToString, ),
	'sn': ('lastname', univention.admin.mapping.ListToString, ),
	'uid': ('username', univention.admin.mapping.ListToString, ),
	'userPassword': ('password', _random_password, ),
	}
def _translate_user_update(attribute, value):
	if attribute in _translate_user_update.ignore:
		return (None, None, )
	return _translate_user(attribute, value)
_translate_user_update.ignore = frozenset((
	'userPassword',
	))

def _translate_group(attribute, value):
	(attribute, translate, ) = _translate_group.mapping.get(attribute, (None, None, ))
	if translate is not None:
		value = translate(value)
	return (attribute, value, )
_translate_group.mapping = {
	'cn': ('name', univention.admin.mapping.ListToString, ),
	'memberUid': ('users', _uids_to_dns, ),
	}

def _translate_group_update(attribute, value):
	if attribute in _translate_group_update.ignore:
		return (None, None, )
	return _translate_group(attribute, value)
_translate_group_update.ignore = frozenset((
	))

def _create_user(attributes):
	user = udmUserNew()
	user.open()
	for (attribute, values, ) in attributes.items():
		(attribute, values, )= _translate_user(attribute, values)
		if attribute is not None:
			user[attribute] = values
	user.create()

def _create_group(attributes):
	group = udmGroupNew()
	group.open()
	for (attribute, values, ) in attributes.items():
		(attribute, values, )= _translate_group(attribute, values)
		if attribute is not None:
			group[attribute] = values
	group.create()

def _update_user(user, attributes):
	changes = False
	user.open()
	for (attribute, values, ) in attributes.items():
		(attribute, values, )= _translate_user_update(attribute, values)
		if attribute is not None:
			if user[attribute] != values:
				user[attribute] = values
				changes = True
	if changes:
		user.modify()
	modlist = []
	for (attribute, new_values, ) in attributes.items():
		if attribute in _update_user.direct:
			old_values = user.oldattr.get(attribute, [])
			if new_values != old_values:
				modlist.append((attribute, old_values, new_values, ))
	ldapObject.modify(user.position.getDn(), modlist)
_update_user.direct = frozenset((
	'krb5Key',
	'pwhistory',
	'sambaLMPassword',
	'sambaNTPassword',
	'sambaPasswordHistory',
	'userPassword',
	))

def _update_group(group, attributes):
	changes = False
	group.open()
	for (attribute, values, ) in attributes.items():
		(attribute, values, )= _translate_group_update(attribute, values)
		if attribute is not None:
			if group[attribute] != values:
				group[attribute] = values
				changes = True
	if changes:
		group.modify()

if __name__ == "__main__":
	main()
