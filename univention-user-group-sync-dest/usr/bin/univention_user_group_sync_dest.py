#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
"""user group sync dest
    data import program"""
#
# Copyright 2013-2019 Univention GmbH
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
import ldap
import os
import re
import sys
import time
import univention.admin.config as config
import univention.admin.modules as udm
import univention.admin.objects
import univention.admin.uldap
import univention.config_registry
import traceback

DB_PATH = '/var/lib/univention-user-group-sync'
DB_ENTRY_FORMAT = re.compile('^[0-9]{11}[.][0-9]{7}$')
LOCK_FD = open(sys.argv[0], 'rb')
LOG_PATH = '/var/log/univention/user-group-sync.log'
PROCESS_FILES_LIMIT = 1000
cool_solution_link = "https://help.univention.com/t/cool-solution-sync-users-and-groups-into-a-second-domain/"

ucr = univention.config_registry.ConfigRegistry()
ucr.load()


# Lock/Unlock this script
def _take_lock():
    '''Lock this script / Prevent double running'''
    fcntl.flock(LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB) # EXclusive and NonBlocking

def _release_lock():
    '''Unlock this script'''
    fcntl.flock(LOCK_FD, fcntl.LOCK_UN) # UNlock

def _log_message(message):
    '''Write a Log Message'''
    t = time.time()
    t_str = time.strftime('%b %d %H:%M:%S', time.localtime(t))
    with open(LOG_PATH, 'a+') as f:
        f.write("%s: %s\n" % (t_str, message, ))

# Temporarily generate a random password
def _random_password(_):
    '''Generates and returns a random password'''
    return os.urandom(33).encode('base64').strip()

# Encode the given Certificate base64 for UDM
def _encode_certificate(certificate):
    '''Encode the given certificate'''
    if not certificate:
        return None
    elif isinstance(certificate, (list,)):
        return certificate[0].encode('base64').strip()
    else:
        return certificate.encode('base64').strip()

def _decode_filename(filename):
    """Decode a unix timestamp formatted into a filename via %019.7f
    returns a <float> unix timestamp"""
    return float(filename)

def _find_files():
    '''Returns all files in folder DB_PATH'''
    for filename in os.listdir(DB_PATH):
        if DB_ENTRY_FORMAT.match(filename):
            timestamp = _decode_filename(filename)
            path = os.path.join(DB_PATH, filename)
            yield (timestamp, path, filename, )

def _decode_data(raw):
    '''Decode the given pickle data'''
    return pickle.loads(raw)

def _read_file(path, append=False):
    '''Read the pickle file found under given path'''
    _log_message("Reading file {}".format(path))
    print("Reading file {}".format(path))
    raw_data = open(path, 'rb').read()
    return _decode_data(raw_data)

# Find the User/Group by replacing the LDAP Base, if needed
def getPosition(user_dn):
    '''Maps the given DN to the LDAP by replacing the base, if defined'''
    position = re.sub(r'(dc\=.*$)', base, user_dn)
    position = re.sub(r'^(uid|cn)=[^,]+,', '', position)
    #Apply OU mapping if configured
    sourceBase = re.search(r'(dc\=.*$)', user_dn).group()
    sourceBase = re.sub(r'^dc\=', '', sourceBase)
    sourceBase = re.sub(r',dc\=', '.', sourceBase)
    ou = ucr.get('ldap/sync/mapping/base2ou/{}'.format(sourceBase))
    if ou:
        position = re.sub(r'({})'.format(base), 'ou={},{}'.format(ou, base), position)
    return position

def _process_file(path, filename):
    '''Read, import and delete a pickle file'''
    data = _read_file(path)
    _import(data)
    os.remove(path)

def _uid_to_dn(uid):
    '''Return the would be DN for <uid>'''
    #Get dn via getPosition
    explode_dn=ldap.dn.str2dn(uid)
    userid='='.join((explode_dn[0][0][0], explode_dn[0][0][1]))
    return '{},{}'.format(userid, getPosition(uid))

def _uids_to_dns(uids):
    '''xxx'''
    return map(_uid_to_dn, uids)

# Process all files in the DB_PATH location
def _process_files():
    '''Process the first <_process_files.limit> files'''
    for (_, path, filename, ) in sorted(_find_files())[:PROCESS_FILES_LIMIT]:
        _process_file(path, filename)

# Check, if the given DN is a User
def _is_user(object_dn, attributes):
    '''Return whether the object is a user'''
    if not attributes:
        if object_dn.startswith('uid='):
            return True
        return False
    elif 'users/user' in attributes.get('univentionObjectType', []):
        return True
    return user_module.identify(object_dn, attributes)

# Check, if the given DN is a Simple Authentication Account
def _is_simpleauth(object_dn, attributes):
    '''Return whether the object is a user'''
    if not attributes:
        if object_dn.startswith('uid='):
            return True
        return False
    elif 'users/ldap' in attributes.get('univentionObjectType', []):
        return True
    return simpleauth_module.identify(object_dn, attributes)

# Check, if the given DN is a Group
def _is_group(object_dn, attributes):
    '''Return whether the object is a group'''
    if not attributes:
        if object_dn.startswith('cn='):
            return True
        return False
    elif 'groups/group' in attributes.get('univentionObjectType', []):
        return True
    return group_module.identify(object_dn, attributes)

# Check, if the given User UID exists in our LDAP
def _user_exists(attributes):
    '''Check, if the given User UID exists in our LDAP'''
    search_filter = univention.admin.filter.expression('uid', attributes['uid'][0])
    result = user_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

# Check, if the given Simple Authentication Account UID exists in our LDAP
def _simpleauth_exists(attributes):
    '''Check, if the given User UID exists in our LDAP'''
    search_filter = univention.admin.filter.expression('uid', attributes['uid'][0])
    result = simpleauth_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

# Check, if the given Group CN exists in our LDAP
def _group_exists(attributes):
    '''Check, if the given Group CN exists in our LDAP'''
    search_filter = univention.admin.filter.expression('cn', attributes['cn'][0])
    result = group_module.lookup(co, lo, search_filter)
    if not result:
        return None
    else:
        return result[0]

def _unset_certificates(attributes):
    '''Ignore Certificate attributes, if sync isn't enabled'''
    attributes.pop('userCertificate;binary', None)
    attributes.pop('univentionCertificateDays', None)
    attributes.pop('univentionCreateRevokeCertificate', None)
    attributes.pop('univentionRenewCertificate', None)
    if attributes.has_key('objectClass') and 'univentionManageCertificates' in attributes['objectClass']:
        attributes['objectClass'].remove('univentionManageCertificates')
    return attributes


# Initialize by creating an LDAP connection and getting UCR configuration
def getLdapConnection():
    '''Create an LDAP connection and initialize UDM User and Group modules'''
    global lo, po, user_module, simpleauth_module, group_module
    lo, po = univention.admin.uldap.getAdminConnection()
    udm.update()
    user_module = udm.get('users/user')
    simpleauth_module = udm.get('users/ldap')
    group_module = udm.get('groups/group')
    udm.init(lo, po, user_module)
    udm.init(lo, po, simpleauth_module)
    udm.init(lo, po, group_module)

def getConfig():
    '''xxx'''
    global co
    co = config.config()

def getUCRV():
    '''Returns the LDAP base'''
    global base
    base = ucr.get('ldap/base')

def getUCRCertificatesEnabled():
    '''Returns whether certificates shall be imported'''
    global certificatesEnabled
    certificatesEnabled = ucr.is_true('ldap/sync/certificates')

def get_additional_user_mapping():
    '''Apply additional user attribute mapping from UCR'''
    global _translate_user_mapping
    ucr_attributes = ucr.get('ldap/sync/add/user/attribute')
    if not ucr_attributes:
        return

    # Get all available UDM Module attributes
    module_attributes = udm.attributes(user_module)

    #tempvariable = "univentionFreeAttribute1:CarLicense,univentionFreeAttribute2:coconut"
    for attr in ucr_attributes.split(','):
        keep_attribute = attr.split(':', 2)
        if not len(keep_attribute) == 2:
            continue

        # Check if given UDM attribute exists (case-sensitive)
        if not any(attribute['name'] == keep_attribute[1] for attribute in module_attributes):
            _log_message("W: UDM attribute of additional mapping {} doesn't exist. Ignoring mapping".format(keep_attribute))
            print("W: UDM attribute of additional mapping {} doesn't exist. Ignoring mapping".format(keep_attribute))
            continue

        # Add given attribute to mapping
        _translate_user_mapping[keep_attribute[0]] = (keep_attribute[1], univention.admin.mapping.ListToString, )

def get_ucr_process_files_limit():
    '''Apply custom PROCESS_FILES_LIMIT from UCR'''
    global PROCESS_FILES_LIMIT
    ucr_process_files_limit = ucr.get('ldap/sync/process_files_limit')
    if ucr_process_files_limit:
        try:
            PROCESS_FILES_LIMIT = int(ucr_process_files_limit)
        except:
            _log_message('Value specified in UCR variable ldap/sync/process_files_limit is not an integer, ignoring.')
            print('Value specified in UCR variable ldap/sync/process_files_limit is not an integer, ignoring.')

def get_ignore_error():
    '''Returns whether certain errors during import shall be ignored and files causing them removed'''
    global ignore_error_missing_position, ignore_error_missing_position_var, ignore_error_objectClass_difference, ignore_error_objectClass_difference_var

    ignore_error_missing_position_var = 'ldap/sync/ignore_error/missing_position'
    ignore_error_missing_position = ucr.is_true(ignore_error_missing_position_var)

    ignore_error_objectClass_difference_var = 'ldap/sync/ignore_error/objectClass_difference'
    ignore_error_objectClass_difference = ucr.get(ignore_error_objectClass_difference_var)
    if ignore_error_objectClass_difference:
        ignore_error_objectClass_difference = ignore_error_objectClass_difference.split(',')

def _log_ignore_error(ignore_error_var):
    '''Returns whether certain errors during import shall be ignored and files causing them removed'''
    if ignore_error_var == ignore_error_missing_position_var:
        _log_message("Skipping and removing file which contains DN with missing LDAP position because {} is true\n".format(ignore_error_var))
        print("Skipping and removing file which contains DN with missing LDAP position because {} is true\n".format(ignore_error_var))

# LDAP TO UDM MAPPING
## User
_translate_user_mapping = {
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
_translate_user_mapping_ignore = frozenset((
    'userPassword',
))
_translate_user_mapping_direct = frozenset((
    'krb5Key',
    'pwhistory',
    'sambaLMPassword',
    'sambaNTPassword',
    'sambaPasswordHistory',
    'userPassword',
    'objectClass',
    'userCertificate;binary',
    'univentionCertificateDays',
))

## Simple authentication account
_translate_simpleauth_mapping = {
    'uid': ('username', univention.admin.mapping.ListToString, ),
    'description': ('description', univention.admin.mapping.ListToString, ),
    'userPassword': ('password', _random_password, ),
}
_translate_simpleauth_mapping_ignore = frozenset((
    'userPassword',
))
_translate_simpleauth_mapping_direct = frozenset((
    'pwhistory',
    'userPassword',
    'objectClass',
    'userCertificate;binary',
    'univentionCertificateDays',
 ))

## Groups
_translate_group_mapping = {
    'cn': ('name', univention.admin.mapping.ListToString, ),
    'description': ('description', univention.admin.mapping.ListToString, ),
    'uniqueMember': ('users', _uids_to_dns ),
}
_translate_group_mapping_ignore = frozenset((
))

## Maps User LDAP and UDM attributes
def _translate_user(attribute, value):
    '''Maps LDAP attributes to UDM'''
    (attribute, translate, ) = _translate_user_mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )

## Maps User LDAP and UDM attributes
def _translate_user_update(attribute, value):
    '''Maps LDAP attributes to UDM'''
    if attribute in _translate_user_mapping_ignore:
        return (None, None, )
    return _translate_user(attribute, value)

## Maps Simple Authentication Account LDAP and UDM attributes
def _translate_simpleauth(attribute, value):
    '''Maps LDAP attributes to UDM'''
    (attribute, translate, ) = _translate_simpleauth_mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )

## Maps Simple Authentication Account LDAP and UDM attributes
def _translate_simpleauth_update(attribute, value):
    '''Maps LDAP attributes to UDM'''
    if attribute in _translate_simpleauth_mapping_ignore:
        return (None, None, )
    return _translate_simpleauth(attribute, value)

## Maps Group LDAP and UDM attributes
def _translate_group(attribute, value):
    '''Maps LDAP attributes to UDM'''
    (attribute, translate, ) = _translate_group_mapping.get(attribute, (None, None, ))
    if translate is not None:
        value = translate(value)
    return (attribute, value, )

## Maps Group LDAP and UDM attributes
def _translate_group_update(attribute, value):
    '''Maps LDAP attributes to UDM'''
    if attribute in _translate_group_mapping_ignore:
        return (None, None, )
    return _translate_group(attribute, value)

## Run direct update
def _direct_update(attributes, mapping, user_dn):
    if _is_user(user_dn, attributes):
        user = _user_exists(attributes)
    elif _is_simpleauth(user_dn, attributes):
        user = _simpleauth_exists(attributes)
    else:
        _log_message('E: During _direct_update. Unknown user type: %s %s' % (command, object_dn))
        exit()
    if user is None:
        _log_message("I: Ignoring modify for non-existent %r" % user_dn)
        print("I: Ignoring modify for non-existent %r" % user_dn)
        return
    user.open()
    modlist = []
    for (attribute, new_values, ) in attributes.items():
        if attribute in mapping:
            old_values = user.oldattr.get(attribute, [])
            if new_values != old_values:
                if attribute == 'objectClass':
                    _log_message("W: Different objectClasses detected NEW {} vs. OLD {}".format(new_values, old_values))
                    print("W: Different objectClasses detected NEW {} vs. OLD {}".format(new_values, old_values))
                    if ignore_error_objectClass_difference:
                        for objectClass in ignore_error_objectClass_difference:
                            if objectClass in new_values and objectClass not in old_values:
                                _log_message("W: Ignoring difference in objectClass as specified in {} : {}".format(ignore_error_objectClass_difference_var, objectClass))
                                print("W: Ignoring difference in objectClass as specified in {} : {}".format(ignore_error_objectClass_difference_var, objectClass))
                                new_values.remove(objectClass)
                            elif objectClass in old_values and not objectClass in new_values:
                                _log_message("W: Ignoring difference in objectClass as specified in {} : {}".format(ignore_error_objectClass_difference_var, objectClass))
                                print("W: Ignoring difference in objectClass as specified in {} : {}".format(ignore_error_objectClass_difference_var, objectClass))
                                new_values.append(objectClass)
                modlist.append((attribute, old_values, new_values, ))
    try:
        lo.modify(user.position.getDn(), modlist)
    except:
        _log_message("E: During User.modify_ldap: %s" % traceback.format_exc())
        print "E: During User.modify_ldap: %s" % traceback.format_exc()
        exit()


# CREATE
## Handle ldap.DECODING_ERROR
def _ldap_decoding_error(object_type, operation, object_dn):
    _log_message("E: LDAP DECODING_ERROR during {}.{}. There might be an illegal character in the DN. Please refer to the cool solution for allowed characters: {}\n\n{}\n\n{}".format(object_type, operation, cool_solution_link, object_dn, traceback.format_exc()))
    print("E: LDAP DECODING_ERROR during {}.{}. There might be an illegal character in the DN. Please refer to the cool solution for allowed characters: {}\n\n{}\n\n{}".format(object_type, operation, cool_solution_link, object_dn, traceback.format_exc()))
    exit()

## Create a non-existent User
def _create_user(user_dn, attributes):
    '''Creates a new user based on the given attributes'''
    existing_user = _user_exists(attributes)
    if existing_user is not None:
        _log_message("I: Ignoring new %r for existing %r" % (user_dn, existing_user.position.getDn(), ))
        print("I: Ignoring new %r for existing %r" % (user_dn, existing_user.position.getDn(), ))
        return

    _log_message("Create User: %r" % user_dn)
    user_position = getPosition(user_dn)
    user_position_obj = univention.admin.uldap.position(base)
    try:
        user_position_obj.setDn(user_position)
    except ldap.DECODING_ERROR:
        _ldap_decoding_error("User", "Create", user_position)
    user = user_module.object(co, lo, user_position_obj)
    user.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, ) = _translate_user(attribute, values)
        if attribute is not None:
            user[attribute] = values
    try:
        user.create()
        _direct_update(attributes, _translate_user_mapping_direct, user_dn)

        # Re-Add restored user to his previous groups
        if "univentionUserGroupSyncEnabled" in attributes and attributes["univentionUserGroupSyncEnabled"] == ["TRUE"] and "memberOf" in attributes:
            for source_group_dn in attributes['memberOf']:
                source_group_cn = ldap.dn.str2dn(source_group_dn)[0][0][1]
                source_group_attributes = {'cn': [source_group_cn],
                    'uniqueMember': [ user_dn ],
                    'univentionUserGroupSyncResync': [ 'TRUE' ]}
                _modify_group(source_group_dn, source_group_attributes)
    except:
        if lo.get(user_position):
            _log_message("E: During User.create: %s" % traceback.format_exc())
            print("E: During User.create: %s" % traceback.format_exc())
        else:
            _log_message("E: during User.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            print("E: during User.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            if ignore_error_missing_position:
                _log_ignore_error(ignore_error_missing_position_var)
                return
        exit()

## Create a new Simple Authentication Account, if it doesn't exist yet
def _create_simpleAuth(simpleauth_dn, attributes):
    '''Creates a new Simple Authentication Account based on the given attributes'''
    existing_simpleauth = _simpleauth_exists(attributes)
    if existing_simpleauth is not None:
        _log_message("I: Ignoring new %r for existing %r" % (simpleauth_dn, existing_simpleauth.position.getDn(), ))
        print("I: Ignoring new %r for existing %r" % (simpleauth_dn, existing_simpleauth.position.getDn(), ))
        return

    _log_message("Create User: %r" % simpleauth_dn)
    simpleauth_position = getPosition(simpleauth_dn)
    simpleauth_position_obj = univention.admin.uldap.position(base)
    try:
        simpleauth_position_obj.setDn(simpleauth_position)
    except ldap.DECODING_ERROR:
        _ldap_decoding_error("SimpleAuth", "Create", simpleauth_position)
    simpleauth = simpleauth_module.object(co, lo, simpleauth_position_obj)
    simpleauth.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_simpleauth(attribute, values)
        if attribute is not None:
            simpleauth[attribute] = values
    try:
        simpleauth.create()
        _direct_update(attributes, _translate_simpleauth_mapping_direct, simpleauth_dn)
    except:
        if lo.get(user_position):
            _log_message("E: During SimpleAuth.create: %s" % traceback.format_exc())
            print("E: During SimpleAuth.create: %s" % traceback.format_exc())
        else:
            _log_message("E: during SimpleAuth.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            print("E: during SimpleAuth.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            if ignore_error_missing_position:
                _log_ignore_error(ignore_error_missing_position_var)
                return
        exit()

## Create a new Group, if it doesn't exist yet
def _create_group(group_dn, attributes):
    '''Creates a new group based on the given attributes'''
    existing_group = _group_exists(attributes)
    if existing_group is not None:
        _log_message("I: Ignoring new %r for existing %r" % (group_dn, existing_group.position.getDn(), ))
        print("I: Ignoring new %r for existing %r" % (group_dn, existing_group.position.getDn(), ))
        return

    _log_message("Create Group: %r" % group_dn)
    group_position = getPosition(group_dn)
    group_position_obj = univention.admin.uldap.position(base)
    try:
        group_position_obj.setDn(group_position)
    except ldap.DECODING_ERROR:
        _ldap_decoding_error("Group", "Create", group_position)

    group = group_module.object(co, lo, group_position_obj)
    group.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_group(attribute, values)
        if attribute is not None:
            group[attribute] = values
    try:
        group.create()
    except:
        if lo.get(user_position):
            _log_message("E: During Group.create: %s" % traceback.format_exc())
            print("E: During Group.create: %s" % traceback.format_exc())
        else:
            _log_message("E: during Group.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            print("E: during Group.create. The object's position does not exist: {}\n{}".format(user_position, traceback.format_exc()))
            if ignore_error_missing_position:
                _log_ignore_error(ignore_error_missing_position_var)
                return
        exit()


# DELETE
## Delete the given User / Simple Authentication Account
def _delete_user(user_dn):
    '''Delete the given User'''
    _log_message("Delete User: %r" % user_dn)
    uid = user_dn.split(',', 1)[0].split('=', 1)[1]
    search_filter = univention.admin.filter.expression('uid', uid)
    for lists in user_module.lookup(co, lo, search_filter), simpleauth_module.lookup(co, lo, search_filter):
        for existing_user in lists:
            try:
                existing_user.remove()
            except:
                _log_message("E: During User.remove: %s" % traceback.format_exc())
                print("E: During User.remove: %s" % traceback.format_exc())

## Delete the given Group
def _delete_group(group_dn):
    '''Delete the given Group'''
    _log_message("Delete Group: %r\n" % group_dn)
    cn = group_dn.split(',', 1)[0].split('=', 1)[1]
    search_filter = univention.admin.filter.expression('cn', cn)
    for existing_group in group_module.lookup(co, lo, search_filter):
        try:
            existing_group.remove()
        except:
            _log_message("E: During Group.remove: %s" % traceback.format_exc())
            print("E: During Group.remove: %s" % traceback.format_exc())


# MODIFY
## Modify an User
def _modify_user(user_dn, attributes):
    '''Updates existing user based on changes'''
    user = _user_exists(attributes)
    if user is None:
        _log_message("I: Ignoring modify for non-existent %r" % user_dn)
        print("I: Ignoring modify for non-existent %r" % user_dn)
        return

    _log_message("Modify User: %r" % user_dn)
    changes = False
    user.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_user_update(attribute, values)
        if attribute is not None:
            if user[attribute] != values:
                user[attribute] = values
                changes = True
    if changes:
        try:
            user.modify()
        except:
            _log_message('E: During User.modify_changes: %s' % traceback.format_exc())
            print 'E: During User.modify_changes: %s' % traceback.format_exc()
            exit()
    _direct_update(attributes, _translate_user_mapping_direct, user_dn)

## Modify a Simple Authentication Account
def _modify_simpleAuth(simpleauth_dn, attributes):
    '''Updates existing simple authentication account based on changes'''
    simpleauth = _simpleauth_exists(attributes)
    if simpleauth is None:
        _log_message("I: Ignoring modify for non-existent %r" % simpleauth_dn)
        print("I: Ignoring modify for non-existent %r" % simpleauth_dn)
        return

    _log_message("Modify SimpleAuth: %r" % simpleauth_dn)
    changes = False
    simpleauth.open()
    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_simpleauth_update(attribute, values)
        if attribute is not None:
            if simpleauth[attribute] != values:
                simpleauth[attribute] = values
                changes = True
    if changes:
        try:
            simpleauth.modify()
        except:
            _log_message('E: During SimpleAuth.modify_changes: %s' % traceback.format_exc())
            print 'E: During SimpleAuth.modify_changes: %s' % traceback.format_exc()
            exit()
    _direct_update(attributes, _translate_simpleauth_mapping_direct, simpleauth_dn)

## Modify a Group
def _modify_group(group_dn, attributes):
    '''Updates existing Group based on changes'''
    group = _group_exists(attributes)
    if group is None:
        _log_message("I: Ignoring modify for non-existent %r" % group_dn)
        print("I: Ignoring modify for non-existent %r" % group_dn)
        return

    _log_message("Modify Group: %r" % group_dn)
    changes = False
    group.open()

    # If called by _create_user. Re-Add restored user to a previous group
    if 'univentionUserGroupSyncResync' in attributes:
        attributes['uniqueMember'].extend(group['users'])
        attributes.pop('univentionUserGroupSyncResync')

    for (attribute, values, ) in attributes.items():
        (attribute, values, )= _translate_group_update(attribute, values)
        if attribute is not None:
            if group[attribute] != values:
                group[attribute] = values
                changes = True
    if changes:
        try:
            group.modify()
        except:
            _log_message("E: During Group.modify_changes: %s" % traceback.format_exc())
            print "E: During Group.modify_changes: %s" % traceback.format_exc()
            exit()


# Imports the given object
def _import(data):
    '''check object type and dispatch to specific import method'''
    (object_dn, command, attributes, ) = data

    # Ignore Certificate attributes, if not enabled
    if attributes and not certificatesEnabled:
        attributes = _unset_certificates(attributes)

    if command == 'a' or command == 'n': # Add
        if _is_user(object_dn, attributes):
            return _create_user(object_dn, attributes)
        if _is_simpleauth(object_dn, attributes):
            return _create_simpleAuth(object_dn, attributes)
        if _is_group(object_dn, attributes):
            return _create_group(object_dn, attributes)
        _log_message("E: Unknown object type (a/n): %r" % object_dn)
        return
    elif command == 'd': # Delete
        if _is_user(object_dn, attributes):
            return _delete_user(object_dn)
        if _is_simpleauth(object_dn, attributes):
            return _delete_user(object_dn)
        if _is_group(object_dn, attributes):
            return _delete_group(object_dn)
        _log_message("E: Unknown object type (d): %r" % object_dn)
        return
    elif command == 'r': # Rename / Move
        # Two-Phrased operation. Next command will be an Add for this object at a new location
        if _is_user(object_dn, attributes):
            return _delete_user(object_dn)
        if _is_simpleauth(object_dn, attributes):
            return _delete_user(object_dn)
        if _is_group(object_dn, attributes):
            return _delete_group(object_dn)
        _log_message("E: Unknown object type (r): %r" % object_dn)
        return
    elif command == 'm': # Modify
        if _is_user(object_dn, attributes):
            return _modify_user(object_dn, attributes)
        if _is_simpleauth(object_dn, attributes):
            return _modify_simpleAuth(object_dn, attributes)
        if _is_group(object_dn, attributes):
            return _modify_group(object_dn, attributes)
        _log_message("E: Unknown object type (m): %r" % object_dn)
        return
    else:
        _log_message('E: During _import. Unknown Command %s: %s' % (command, object_dn))
        print('E: During _import. Unknown Command %s: %s' % (command, object_dn))
        return


# Execute
def main():
    _take_lock()
    getLdapConnection()
    getConfig()
    getUCRV()
    getUCRCertificatesEnabled()
    get_additional_user_mapping()
    get_ucr_process_files_limit()
    get_ignore_error()
    _process_files()
    _release_lock()

if __name__ == "__main__":
    main()
