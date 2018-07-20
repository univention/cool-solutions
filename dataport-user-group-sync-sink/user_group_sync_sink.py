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

ucr = univention.config_registry.ConfigRegistry()
ucr.load()

DB_PATH = '/var/lib/dataport-user-group-sync-sink'
DB_ENTRY_FORMAT = re.compile('^[0-9]{11}[.][0-9]{7}$')

LOCK_FD = open(sys.argv[0], 'rb')

def _take_lock():
    fcntl.flock(LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB) # EXclusive and NonBlocking

def _release_lock():
    fcntl.flock(LOCK_FD, fcntl.LOCK_UN) # UNlock

def readOUMappingList():
    global ouMappingList
    ouMappingList = []
    for key in ucr.keys():
        if key.startswith('dataport/user_group_sync/sink/mapping/'):
            ouMappingList.append(re.sub(r'dataport\/user_group_sync\/sink\/mapping\/', r'', key))

def getLdapConnection():
    global lo, po, user_module, group_module
    lo, po = univention.admin.uldap.getAdminConnection()
    udm.update()
    user_module = udm.get('users/user')
    group_module = udm.get('groups/group')
    udm.init(lo, po, user_module)
    udm.init(lo, po, group_module)

def getConfig():
    global co
    co = config.config()

def getUCRV():
    global base
    base = ucr.get('ldap/base')


#process files
def _process_files():
    '''process the first <_process_files.limit> files'''
    for (_, path, ) in sorted(_find_files())[:_process_files.limit]:
        _process_file(path)
_process_files.limit = 1000

def _find_files():
    for filename in os.listdir(DB_PATH):
        print filename
        if DB_ENTRY_FORMAT.match(filename):
            timestamp = _decode_filename(filename)
            path = os.path.join(DB_PATH, filename)
            yield (timestamp, path, )

def _decode_filename(filename):
    """decode a unix timestamp formatted into a filename via %019.7f
    returns a <float> unix timestamp"""
    return float(filename)

def _process_file(path):
    data = _read_file(path)
    #oldDN = data[0]
    _import(data)
    os.remove(path)

def _read_file(path):
    raw_data = open(path, 'rb').read()
    return _decode_data(raw_data)

def _decode_data(raw):
    return pickle.loads(raw)

#####


#DN editing

def applyOUMapping(dn):
    for ou in ouMappingList:
        if re.match(r'.*ou\={}'.format(ou), dn):
            dn = re.sub(r'ou\={}'.format(ou), r'ou={}'.format(ucr.get('dataport/user_group_sync/sink/mapping/{}'.format(ou))), dn)
    return dn

def getPosition(user_dn):
    position = re.sub(r'(dc\=.*$)', base, user_dn)
    position = re.sub(r'^(uid|cn)=[a-zA-Z0-9-_]*,', '', position)
    position = applyOUMapping(position)
    return position

#####


#User creation/modification/del

def _random_password(_):
    return os.urandom(33).encode('base64').strip()

def _is_user(object_dn, attributes):
    '''return whether the object is a user'''
    if 'users/user' in attributes.get('univentionObjectType', []):
        return True
    return user_module.identify(object_dn, attributes)

def _user_exists(attributes):
    search_filter = univention.admin.filter.expression('uid', attributes['uid'][0])
    result = user_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

def createUser(position, attributes):
    user = user_module.object(co, lo, position)
    user.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_user(attribute, values)
        if attribute is not None:
            user[attribute] = values
    user.create()

def _user_should_be_updated(existing_user, attributes, user_position):
    return existing_user.position.getDn().endswith(str(user_position))

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
    lo.modify(user.position.getDn(), modlist)
_update_user.direct = frozenset((
    'krb5Key',
    'pwhistory',
    'sambaLMPassword',
    'sambaNTPassword',
    'sambaPasswordHistory',
    'userPassword',
    ))

def _import_user(user_dn, attributes):
    existing_user = _user_exists(attributes)
    user_position = getPosition(user_dn)
    with open('/var/log/val-debug.log', 'a') as f:
        f.write(user_position)
    user_position_obj = univention.admin.uldap.position(base)
    user_position_obj.setDn(user_position)
    if existing_user is None:
        createUser(user_position_obj, attributes)
        existing_user = _user_exists(attributes)
    if _user_should_be_updated(existing_user, attributes, user_position):
        _update_user(existing_user, attributes)
    else:
        print 'Ignoring new %r for existing %r' % (user_dn, existing_user.position.getDn(), )


#Groups
def _is_group(object_dn, attributes):
    '''return whether the object is a group'''
    if 'groups/group' in attributes.get('univentionObjectType', []):
        return True
    return group_module.identify(object_dn, attributes)

def _group_exists(attributes):
    search_filter = univention.admin.filter.expression('cn', attributes['cn'][0])
    result = group_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

def _create_group(position, attributes):
    group = group_module.object(co, lo, position)
    group.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_group(attribute, values)
        if attribute is not None:
            group[attribute] = values
    group.create()

def _group_should_be_updated(existing_group, attributes, group_dn):
    return existing_group.position.getDn().endswith(str(group_dn))

def _uid_to_dn(uid):
    '''return the would be DN for <uid>'''
#Get dn via ldap search
    #dn = lo.search("uid={}".format(uid))
    #return dn[0][0]

#Get dn via getPosition
    userid = re.sub(r',cn.*', r'', uid)
    return '{},{}'.format(userid, getPosition(uid))

def _uids_to_dns(uids):
    return map(_uid_to_dn, uids)

def _translate_group(attribute, value):
    (attribute, translate, ) = _translate_group.mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )
_translate_group.mapping = {
    'cn': ('name', univention.admin.mapping.ListToString, ),
    'uniqueMember': ('users', _uids_to_dns ),
    }

def _translate_group_update(attribute, value):
    if attribute in _translate_group_update.ignore:
        return (None, None, )
    return _translate_group(attribute, value)
_translate_group_update.ignore = frozenset((
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

def _import_group(group_dn, attributes):
    existing_group = _group_exists(attributes)
    group_position = getPosition(group_dn)
    group_position_obj = univention.admin.uldap.position(base)
    group_position_obj.setDn(group_position)
    if existing_group is None:
        _create_group(group_position_obj, attributes)
        existing_group = _group_exists(attributes)
    if _group_should_be_updated(existing_group, attributes, group_position):
        _update_group(existing_group, attributes)
    else:
        print 'Ignoring new %r for existing %r' % (group_dn, existing_group.position.getDn(), )

def _import(data):
    '''check object type and dispatch to specific import method'''
    (object_dn, attributes, ) = data
    object_position = getPosition(object_dn)

    if attributes: # create/modify
        if _is_user(object_dn, attributes):
            return _import_user(object_dn, attributes)
        if _is_group(object_dn, attributes):
            return _import_group(object_dn, attributes)
        print 'Unknown object type %r' % (object_dn, )
    else: # delete
        return _delete(object_dn)


####

def main():
    _take_lock()
    readOUMappingList()
    getLdapConnection()
    getConfig()
    getUCRV()
    _process_files()
    _release_lock()

if __name__ == "__main__":
    main()
