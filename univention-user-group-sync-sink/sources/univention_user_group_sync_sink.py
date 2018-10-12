#!/usr/bin/python2.7
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
import univention.admin.config as config
import univention.admin.modules as udm
import univention.admin.objects
import univention.admin.uldap
import univention.config_registry

DB_PATH = '/var/lib/univention-user-group-sync-sink'
DB_ENTRY_FORMAT = re.compile('^[0-9]{11}[.][0-9]{7}$')
LOCK_FD = open(sys.argv[0], 'rb')

ucr = univention.config_registry.ConfigRegistry()
ucr.load()

# Lock/Unlock this script
def _take_lock():
    '''Lock this script / Prevent double running'''
    fcntl.flock(LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB) # EXclusive and NonBlocking

def _release_lock():
    '''Unlock this script'''
    fcntl.flock(LOCK_FD, fcntl.LOCK_UN) # UNlock

# Map OUs
def readOUMappingList():
    '''Create a list of all OU mappings'''
    global ouMappingList
    ouMappingList = []
    for key in ucr.keys():
        if key.startswith('ldap/sync/sink/mapping/ou/'):
            ouMappingList.append(re.sub(r'ldap\/sync\/sink\/mapping\/ou\/', r'', key))

def applyOUMapping(dn):
    '''Apply all OU mapping entries to the given DN'''
    for ou in ouMappingList:
        if re.match(r'.*ou\={}'.format(ou), dn):
            dn = re.sub(r'ou\={}'.format(ou), r'ou={}'.format(ucr.get('ldap/sync/sink/mapping/ou/{}'.format(ou))), dn)
    return dn

# Initialize by creating an LDAP connection and getting UCR configuration
def getLdapConnection():
    '''Create an LDAP connection and initialize UDM User and Group modules'''
    global lo, po, user_module, group_module
    lo, po = univention.admin.uldap.getAdminConnection()
    udm.update()
    user_module = udm.get('users/user')
    group_module = udm.get('groups/group')
    udm.init(lo, po, user_module)
    udm.init(lo, po, group_module)

def getConfig():
    '''xxx'''
    global co
    co = config.config()

def getUCRV():
    '''Returns the LDAP base'''
    global base
    base = ucr.get('ldap/base')

# Process all files in the DB_PATH location
def _process_files():
    '''Process the first <_process_files.limit> files'''
    for (_, path, filename, ) in sorted(_find_files())[:_process_files.limit]:
        _process_file(path, filename)
_process_files.limit = 1000

def _find_files():
    '''Returns all files in folder DB_PATH'''
    for filename in os.listdir(DB_PATH):
        if DB_ENTRY_FORMAT.match(filename):
            timestamp = _decode_filename(filename)
            path = os.path.join(DB_PATH, filename)
            yield (timestamp, path, filename, )

def _decode_filename(filename):
    """Decode a unix timestamp formatted into a filename via %019.7f
    returns a <float> unix timestamp"""
    return float(filename)

def _process_file(path, filename):
    '''Read, import and delete a pickle file'''
    data = _read_file(path)
    _import(data)
    os.remove(path)
    print filename # Important to remove the remote file too

def _read_file(path):
    '''Read the pickle file found under given path'''
    raw_data = open(path, 'rb').read()
    return _decode_data(raw_data)

def _decode_data(raw):
    '''Decode the given pickle data'''
    return pickle.loads(raw)

# Find the User/Group by replacing the LDAP Base and mapping the OUs, if needed
def getPosition(user_dn):
    '''Maps the given DN to the LDAP by replacing the base and OU, if defined'''
    position = re.sub(r'(dc\=.*$)', base, user_dn)
    position = re.sub(r'^(uid|cn)=[a-zA-Z0-9-_]*,', '', position)
    position = applyOUMapping(position)
    return position

# Temporarily generate a random password
def _random_password(_):
    '''Generates and returns a random password'''
    return os.urandom(33).encode('base64').strip()

# Check, if the given DN is a User
def _is_user(object_dn, attributes):
    '''Return whether the object is a user'''
    if 'users/user' in attributes.get('univentionObjectType', []):
        return True
    return user_module.identify(object_dn, attributes)

# Check, if the given User UID exists in our LDAP
def _user_exists(attributes):
    '''Check, if the given User UID exists in our LDAP'''
    search_filter = univention.admin.filter.expression('uid', attributes['uid'][0])
    result = user_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

# Create a new User, if it doesn't exist yet
def createUser(position, attributes):
    '''Creates a new user based on the given attributes'''
    user = user_module.object(co, lo, position)
    user.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_user(attribute, values)
        if attribute is not None:
            user[attribute] = values
    user.create()

# Delete the given User/Group
def _delete(object_dn):
    '''Delete the given User/Group'''
    if object_dn.startswith('uid='):
        return _delete_user(object_dn)
    if object_dn.startswith('cn='):
        return _delete_group(object_dn)
    print 'E: Unknown object type (d): %r' % (object_dn, )

def _delete_user(user_dn):
    '''Delete the given User'''
    uid = user_dn.split(',', 1)[0].split('=', 1)[1]
    search_filter = univention.admin.filter.expression('uid', uid)
    for existing_user in user_module.lookup(co, lo, search_filter):
        existing_user.remove()

def _delete_group(group_dn):
    '''Delete the given Group'''
    cn = group_dn.split(',', 1)[0].split('=', 1)[1]
    search_filter = univention.admin.filter.expression('cn', cn)
    for existing_group in group_module.lookup(co, lo, search_filter):
        existing_group.remove()

# Check, xxx
def _user_should_be_updated(existing_user, attributes, user_position):
    '''xxx'''
    return existing_user.position.getDn().endswith(str(user_position))

# Maps LDAP and UDM attributes
def _translate_user(attribute, value):
    '''Maps LDAP attributes to UDM'''
    (attribute, translate, ) = _translate_user.mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )
_translate_user.mapping = {
    'givenName': ('firstname', univention.admin.mapping.ListToString, ),
    'sn': ('lastname', univention.admin.mapping.ListToString, ),
    'uid': ('username', univention.admin.mapping.ListToString, ),
    'description': ('description', univention.admin.mapping.ListToString, ),
    'title': ('title', univention.admin.mapping.ListToString, ),
    'mailPrimaryAddress': ('mailPrimaryAddress', univention.admin.mapping.ListToString, ),
    'displayName': ('displayName', univention.admin.mapping.ListToString, ),
    'univentionBirthday': ('birthday', univention.admin.mapping.ListToString, ),
    'userPassword': ('password', _random_password, ),
}

def _translate_user_update(attribute, value):
    '''Maps LDAP attributes to UDM'''
    if attribute in _translate_user_update.ignore:
        return (None, None, )
    return _translate_user(attribute, value)
_translate_user_update.ignore = frozenset((
    'userPassword',
))

# Update User object
def _update_user(user, attributes):
    '''Updates existing user based on changes'''
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
    lo.modify(user.position.getDn(), modlist)
_update_user.direct = frozenset((
    'krb5Key',
    'pwhistory',
    'sambaLMPassword',
    'sambaNTPassword',
    'sambaPasswordHistory',
    'userPassword',
))

# Import a non-existent User
def _import_user(user_dn, attributes):
    '''Imports a new User or updates an existent User'''
    existing_user = _user_exists(attributes)
    user_position = getPosition(user_dn)
    with open('/var/log/univention-user-group-sync.log', 'a') as f:
        f.write(user_position)
    user_position_obj = univention.admin.uldap.position(base)
    user_position_obj.setDn(user_position)
    if existing_user is None:
        createUser(user_position_obj, attributes)
        existing_user = _user_exists(attributes)
    if _user_should_be_updated(existing_user, attributes, user_position):
        _update_user(existing_user, attributes)
    else:
        print 'I: Ignoring new %r for existing %r' % (user_dn, existing_user.position.getDn(), )


# Check, if the given DN is a Group
def _is_group(object_dn, attributes):
    '''Return whether the object is a group'''
    if 'groups/group' in attributes.get('univentionObjectType', []):
        return True
    return group_module.identify(object_dn, attributes)

# Check, if the given Group CN exists in our LDAP
def _group_exists(attributes):
    '''Check, if the given Group CN exists in our LDAP'''
    search_filter = univention.admin.filter.expression('cn', attributes['cn'][0])
    result = group_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

# Create a new Group, if it doesn't exist yet
def _create_group(position, attributes):
    '''Creates a new group based on the given attributes'''
    group = group_module.object(co, lo, position)
    group.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_group(attribute, values)
        if attribute is not None:
            group[attribute] = values
    group.create()

# Check, xxx
def _group_should_be_updated(existing_group, attributes, group_dn):
    '''xxx'''
    return existing_group.position.getDn().endswith(str(group_dn))

# 
def _uid_to_dn(uid):
    '''Return the would be DN for <uid>'''
    #Get dn via getPosition
    userid = re.sub(r',cn.*', r'', uid)
    return '{},{}'.format(userid, getPosition(uid))

def _uids_to_dns(uids):
    '''xxx'''
    return map(_uid_to_dn, uids)

# Maps LDAP and UDM attributes
def _translate_group(attribute, value):
    '''Maps LDAP attributes to UDM'''
    (attribute, translate, ) = _translate_group.mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )
_translate_group.mapping = {
    'cn': ('name', univention.admin.mapping.ListToString, ),
    'description': ('description', univention.admin.mapping.ListToString, ),
    'uniqueMember': ('users', _uids_to_dns ),
}

def _translate_group_update(attribute, value):
    '''Maps LDAP attributes to UDM'''
    if attribute in _translate_group_update.ignore:
        return (None, None, )
    return _translate_group(attribute, value)
_translate_group_update.ignore = frozenset((
))

# Update Group object
def _update_group(group, attributes):
    '''Updates existing Group based on changes'''
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

# Import a non-existent Group
def _import_group(group_dn, attributes):
    '''Imports a new Group or updates an existent Group'''
    existing_group = _group_exists(attributes)
    group_position = getPosition(group_dn)
    with open('/var/log/univention-user-group-sync.log', 'a') as f:
        f.write(group_position)
    group_position_obj = univention.admin.uldap.position(base)
    group_position_obj.setDn(group_position)
    if existing_group is None:
        _create_group(group_position_obj, attributes)
        existing_group = _group_exists(attributes)
    if _group_should_be_updated(existing_group, attributes, group_position):
        _update_group(existing_group, attributes)
    else:
        print 'I: Ignoring new %r for existing %r' % (group_dn, existing_group.position.getDn(), )

# Imports the given object
def _import(data):
    '''check object type and dispatch to specific import method'''
    (object_dn, attributes, ) = data
    object_position = getPosition(object_dn)

    if attributes: # create/modify
        if _is_user(object_dn, attributes):
            return _import_user(object_dn, attributes)
        if _is_group(object_dn, attributes):
            return _import_group(object_dn, attributes)
        print 'E: Unknown object type (c/m): %r' % (object_dn, )
    else: # delete
        return _delete(object_dn)

# Execute
def main():
    _take_lock()
    readOUMappingList()
    getLdapConnection()
    getConfig()
    getUCRV()
    print 'E: Example xx'
    _process_files()
    _release_lock()

if __name__ == "__main__":
    main()
