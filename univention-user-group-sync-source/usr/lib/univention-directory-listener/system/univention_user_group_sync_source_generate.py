#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
"""user group sync source
    listener module"""
#
# Copyright 2013-2022 Univention GmbH
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

__package__ = '' # workaround for PEP 366, pylint: disable-msg=W0622
import pickle
import pwd
import grp
import os
import re
import tempfile
import time
import univention.debug
import univention.uldap
import univention.config_registry
import listener
from typing import Dict, List
name = 'univention_user_group_sync_source_generate'
description = 'Store user and group information to be transferred to another system.'
attributes = []
modrdn = '1'
DB_BASE_PATH = '/var/lib/univention-user-group-sync/'
filter = """\
(&
    (|
        (&
            (objectClass=posixAccount)
            (objectClass=shadowAccount)
        )
        (objectClass=univentionMail)
        (objectClass=sambaSamAccount)
        (objectClass=simpleSecurityObject)
        (objectClass=inetOrgPerson)
        (objectClass=univentionGroup)
    )
    (!(objectClass=univentionHost))
    (!(univentionObjectFlag=hidden))
    (!(uidNumber=0))
    (!(uid=ucs-sync))
    (!(uid=*$))
)""".translate(str.maketrans('', '', '\t\n\r '))
filter_custom = ""

#TODO: getpwnam seems to fail at least sometimes
owning_user_number = pwd.getpwnam('ucs-sync').pw_uid
owning_group_number = grp.getgrnam("root").gr_gid

ucr = univention.config_registry.ConfigRegistry()
ucr.load()

#
def ucr_map_identifier():
    filter_custom = ucr.get('ldap/sync/filter')
    if not filter_custom:
        filter_custom = ""
    return filter_custom
ucr_map_identifier()

# Log Messages
def _log(message: str, level: int):
    """log a <message> (str) with log<level>"""
    message = '[%s] %s' % (name, message, )
    univention.debug.debug(univention.debug.LISTENER, level, message)
def _log_debug(message: str):
    """log a "debug" <message> (str)"""
    return _log(message, univention.debug.ALL)
def _log_info(message: str):
    """log a "info" <message> (str)"""
    return _log(message, univention.debug.INFO)
def _log_process(message: str):
    """log a "process" <message> (str)"""
    return _log(message, univention.debug.PROCESS)
def _log_warn(message: str):
    """log a "warn" <message> (str)"""
    return _log(message, univention.debug.WARN)
def _log_error(message: str):
    """log a "error" <message> (str)"""
    return _log(message, univention.debug.ERROR)

# Format a unix timestamp into a filename
def _format_filename(timestamp: float) -> str:
    """format a unix timestamp into a filename
    guaranteed to generate a unique name for every different <float> timestamp
    (if timestamp is after 2011)"""
    # 17 significant digits capture the full precision of python floats
    # because timestamp is always > 1300000000 this format has 17 significant digits
    # 11 digit seconds work until 5138-11-16
    # 19 == 11 + 7 + 1 because the dot also consumes a character
    return '%019.7f' % (timestamp, )

# Write the given data into a file
def _write_file(filename: str, path: str, data: bytes):
    """write the <data> to <filename> in <DB_PATH> atomically
    does not return before the data is stored on disk (fsync)"""
    temporary_file = tempfile.NamedTemporaryFile(dir=path, delete=False)
    temporary_file.write(data)
    temporary_file.flush()
    os.fsync(temporary_file.fileno())
    temporary_file.close()
    filename = os.path.join(path, filename)
    os.rename(temporary_file.name, filename)
    final_file = open(filename, 'ab')
    os.fsync(final_file.fileno())
    final_file.close()
    listener.setuid(0)
    os.chown(filename, owning_user_number, owning_group_number)
    os.chmod(filename, 0o640)
    listener.unsetuid()

#
def _wait_until_after(timestamp: float):
    """wait until the current (system) time is later than <timestamp>"""
    while time.time() <= timestamp:
        time.sleep(0.01)

# Pickle the given data
def _format_data(object_dn: str, new_attributes: Dict[str, List[bytes]], command: str) -> bytes:
    """encode (serialise) object data"""
    data = (object_dn.encode(), command, new_attributes, )
    return pickle.dumps(data, protocol=2)

# Get attributes and objectClasses to be removed from objects from UCR
def _get_remove_config():
    attributes = ucr.get('ldap/sync/remove/attribute')
    if attributes:
        attributes = attributes.encode('UTF-8')
        attributes: List[bytes] = attributes.split(',')
    objectClasses = ucr.get('ldap/sync/remove/objectClass')
    if objectClasses:
        objectClasses = objectClasses.encode('UTF-8')
        objectClasses: List[bytes] = objectClasses.split(',')
    return attributes, objectClasses

def _get_whitelist_config():
    apply_whitelist: bool = ucr.is_true('ldap/sync/whitelist')

    keep_attributes = [
    # USER
    'cn',
    'createTimestamp',
    'creatorsName',
    'description',
    'displayName',
    'entryCSN',
    'entryDN',
    'entryUUID',
    'gecos',
    'gidNumber',
    'givenName',
    'hasSubordinates',
    'homeDirectory',
    'krb5KDCFlags',
    'krb5Key',
    'krb5KeyVersionNumber',
    'krb5MaxLife',
    'krb5MaxRenew',
    'krb5PrincipalName',
    'loginShell',
    'mailPrimaryAddress',
    'memberOf',
    'modifiersName',
    'modifyTimestamp',
    'objectClass',
    'pwhistory',
    'sambaAcctFlags',
    'sambaBadPasswordCount',
    'sambaBadPasswordTime',
    'sambaNTPassword',
    'sambaPasswordHistory',
    'sambaPrimaryGroupSID',
    'sambaPwdLastSet',
    'sambaSID',
    'shadowLastChange',
    'sn',
    'structuralObjectClass',
    'subschemaSubentry',
    'title',
    'uid',
    'uidNumber',
    'univentionBirthday',
    'univentionObjectType',
    'userPassword',
    'univentionPolicyReference',
    'univentionUserGroupSyncEnabled',

    # GROUP
    'memberUid',
    'sambaGroupType',
    'uniqueMember',
    'univentionGroupType'
    ]
    #keep_attributes = ['uid', 'givenName', 'sn', 'displayName', 'title', 'mailPrimaryAddress', 'description', 'univentionBirthday', 'objectClass', 'userPassword', 'pwhistory']
    attributes = ucr.get('ldap/sync/whitelist/attribute')
    if attributes:
        attributes = attributes.split(',')
        for attr in attributes:
            keep_attributes.append(attr)

    keep_objectClasses = [
    # USER
    b'automount',
    b'sambaSamAccount',
    b'univentionMail',
    b'univentionPerson',
    b'krb5KDCEntry',
    b'organizationalPerson',
    b'top',
    b'inetOrgPerson',
    b'person',
    b'univentionPWHistory',
    b'univentionObject',
    b'krb5Principal',
    b'shadowAccount',
    b'posixAccount',
    b'univentionPolicyReference',
    b'univentionSAMLEnabled',

    # GROUP
    b'sambaGroupMapping'
    ]
    objectClasses = ucr.get('ldap/sync/whitelist/objectClass')
    if objectClasses:
        objectClasses = objectClasses.encode('UTF-8')
        objectClasses = objectClasses.split(',')
        for objectClass in objectClasses:  # TODO: Warum ist objectClass 'int'?
            keep_objectClasses.append(objectClass)

    return apply_whitelist, keep_attributes, keep_objectClasses

# Get prefix from UCR
def _get_prefix() -> str:
    prefix = ucr.get('ldap/sync/prefix')
    return prefix

# Get custom attributes to be modified
def _get_prefix_custom_attrs(attrs: List[str], object_type: str):
    custom_attrs = ucr.get(f'ldap/sync/prefix/{object_type}/attributes')
    if custom_attrs:
        for attr in custom_attrs.split(','):
            if not attr in attrs:
                attrs.append(attr)
    return attrs

# Get user attributes to be taken into consideration
def _get_username_prefix_config():
    # Attributes which contain the uid of the object in some way
    attrs = ['uid', 'krb5PrincipalName', 'homeDirectory', 'entryDN']
    # Attributes which contain DNs other than the DN of the object itself
    other_dn_attrs: List[str] = ['memberOf', 'creatorsName', 'modifiersName']
    attrs = _get_prefix_custom_attrs(attrs, 'user')
    return attrs, other_dn_attrs

# Get group attributes to be taken into consideration
def _get_group_name_prefix_config():
    # Attributes which contain the cn of the object in some way
    attrs = ['cn', 'entryDN']
    # Attributes which contain DNs other than the DN of the object itself
    other_dn_attrs = ['uniqueMember', 'creatorsName', 'modifiersName']
    # Attributes to which the prefix can just be added
    other_attrs = ['memberUid']
    attrs = _get_prefix_custom_attrs(attrs, 'group')
    return attrs, other_dn_attrs, other_attrs

def _get_remove_if_univentionUserGroupSyncEnabled_removed_config() -> bool:
    return ucr.is_true('ldap/sync/remove/deactivated_user')

# Apply prefix to attributes which contain the uid or cn of the current object
def _add_prefix_to_attrs(name: bytes, new_attributes: Dict[str, List[bytes]], prefix: str, attrs: List[str], object_dn: str):
    prefixed_new_attributes = {}
    for attr in attrs:
        if attr in new_attributes:
            prefixed_new_attributes[attr] = []
            for attr_item in new_attributes[attr]:
                prefixed_attr_item = re.sub(name, prefix.encode('UTF-8')+name, attr_item)
                prefixed_new_attributes[attr].append(prefixed_attr_item)
            new_attributes[attr] = prefixed_new_attributes[attr]
        else:
            _log_warn(f"Couldn't remove non-existent attribute '{attr}' from object with DN {object_dn}")
    return new_attributes

# Apply prefix to DNs different from the one of the edited object itself
def _add_prefix_to_dns(new_attributes: Dict[str, List[bytes]], prefix: str, attrs: List[str], get_regex: str, remove_regex: str, name_attr: str, object_dn: str):
    prefixed_new_attributes = {}
    for attr in attrs:
        if attr in new_attributes:
            prefixed_new_attributes[attr] = []
            for attr_item in new_attributes[attr]:
                other_dn_id_match = re.match(get_regex, attr_item.decode('UTF-8'))
                if other_dn_id_match:
                    other_dn_id = re.sub(remove_regex, '', other_dn_id_match.group())
                    other_dn_with_prefix = re.sub(get_regex, f'{name_attr}={prefix}{other_dn_id}', attr_item.decode('UTF-8'))
                    prefixed_new_attributes[attr].append(other_dn_with_prefix.encode('UTF-8'))
            new_attributes[attr] = prefixed_new_attributes[attr]
        else:
            _log_warn(f"Couldn't remove non-existent attribute '{attr}' from object with DN {object_dn}")
    return new_attributes

# Just apply prefix to given attributes without any regex matching
def _just_add_prefix(new_attributes: Dict[str, List[bytes]], prefix: str, attrs: List[str], object_dn: str):
    prefixed_new_attributes = {}
    for attr in attrs:
        if attr in new_attributes:  # if 'key' in Dict[str, List[bytes]]
            prefixed_new_attributes[attr] = []
            for attr_item in new_attributes[attr]:
                prefixed_attr_item = prefix.encode('UTF-8') + attr_item
                prefixed_new_attributes[attr].append(prefixed_attr_item)
            new_attributes[attr] = prefixed_new_attributes[attr]
        else:
            _log_warn(f"Couldn't remove non-existent attribute '{attr}' from object with DN {object_dn}")
    return new_attributes

# Apply prefix to user
def _add_prefix_to_user(object_dn_with_prefix: str, new_attributes: Dict[str, List[bytes]], prefix: str, command: str, old_attributes: Dict[str, List[bytes]], attrs: List[str], other_dn_attrs: List[str], object_dn: str):
    uid_regex = '^uid=[a-zA-Z0-9-_.]*'
    if command == 'd' or command == 'r':
        object_dn_with_prefix = re.sub(uid_regex, 'uid={}{}'.format(prefix, old_attributes['uid'][0].decode('UTF-8')), object_dn_with_prefix)
        return object_dn_with_prefix, new_attributes
    else:
        username = new_attributes['uid'][0]
        object_dn_with_prefix = re.sub(uid_regex, 'uid={}{}'.format(prefix, new_attributes['uid'][0].decode('UTF-8')), object_dn_with_prefix)
        new_attributes = _add_prefix_to_attrs(username, new_attributes, prefix, attrs, object_dn)
        new_attributes = _add_prefix_to_dns(new_attributes, prefix, other_dn_attrs, '^cn=[a-zA-Z0-9-_. ]*', '^cn=', 'cn', object_dn)
    return object_dn_with_prefix, new_attributes

# Apply prefix to group
def _add_prefix_to_group(object_dn_with_prefix: str, new_attributes: Dict[str, List[bytes]], prefix: str, command: str, old_attributes: Dict[str, List[bytes]], attrs: List[str], other_dn_attrs: List[str], other_attrs: List[str], object_dn: str):
    cn_regex = '^cn=[a-zA-Z0-9-_. ]*'
    if command == 'd' or command == 'r':
        object_dn_with_prefix = re.sub(cn_regex, 'cn={}{}'.format(prefix, old_attributes['cn'][0].decode('UTF-8')), object_dn_with_prefix)
        return object_dn_with_prefix, new_attributes
    else:
        group_name = new_attributes['cn'][0]
        object_dn_with_prefix = re.sub(cn_regex, 'cn={}{}'.format(prefix, new_attributes['cn'][0].decode('UTF-8')), object_dn_with_prefix)
        new_attributes = _add_prefix_to_attrs(group_name, new_attributes, prefix, attrs, object_dn)
        new_attributes = _add_prefix_to_dns(new_attributes, prefix, other_dn_attrs, '^uid=[a-zA-Z0-9-_.]*', '^uid=', 'uid', object_dn)
        new_attributes = _just_add_prefix(new_attributes, prefix, other_attrs, object_dn)
    return object_dn_with_prefix, new_attributes

#
def handler(object_dn: str, new_attributes: Dict[str, List[bytes]], old_attributes: Dict[str, List[bytes]], command: str):
    """called for each uniqueMember-change on a group"""
    _log_debug(f"handler for: {object_dn} {command}")
    _wait_until_after(handler.last_time)
    timestamp = time.time()
    filename = _format_filename(timestamp)

    remove_if_univentionUserGroupSyncEnabled_removed = _get_remove_if_univentionUserGroupSyncEnabled_removed_config()
    resync = False
    if 'univentionUserGroupSyncEnabled' in new_attributes and 'univentionUserGroupSyncEnabled' in old_attributes:
        if remove_if_univentionUserGroupSyncEnabled_removed:
            if new_attributes['univentionUserGroupSyncEnabled'] == [b'FALSE'] and old_attributes['univentionUserGroupSyncEnabled'] == [b'TRUE']:
                _log_warn('Object was deactivated for sync, deleting in destination...')
                command = 'd'
        if new_attributes['univentionUserGroupSyncEnabled'] == [b'TRUE'] and old_attributes['univentionUserGroupSyncEnabled'] == [b'FALSE']:
            _log_warn('Object was activated for sync, adding in destination...')
            command = 'n'
            resync = True
    elif 'univentionUserGroupSyncEnabled' in new_attributes and not 'univentionUserGroupSyncEnabled' in old_attributes:
        if new_attributes['univentionUserGroupSyncEnabled'] == [b'TRUE']:
            _log_warn('Object was activated for sync, adding in destination...')
            command = 'n'

    # Apply custom filter, if set and command is not delete or rename
    filter_custom = ucr_map_identifier()
    if filter_custom.strip() and command != 'd' and command != 'r':
        ldap = _connect_ldap()
        if not ldap.search(filter=filter_custom, base=object_dn):
            return

    #Remove univention-user-group-sync attribute and objectClass if set
    if 'univentionUserGroupSyncEnabled' in new_attributes:
        new_attributes['objectClass'].remove(b'univentionUserGroupSync')
        if not resync:
            new_attributes.pop('univentionUserGroupSyncEnabled')

    #Remove attributes and objectClasses not present in whitelist, if whitelist exists
    apply_whitelist, keep_attributes, keep_objectClasses = _get_whitelist_config()
    if apply_whitelist:
        if keep_attributes:
            for attribute in new_attributes.keys():
                if not attribute in keep_attributes:
                    new_attributes.pop(attribute)
        if keep_objectClasses and 'objectClass' in new_attributes:
            for objectClass in new_attributes['objectClass']:
                if objectClass not in keep_objectClasses:
                    new_attributes['objectClass'].remove(objectClass)

    #Remove other attributes and objectClass specified via ucr
    remove_attributes, remove_objectClasses = _get_remove_config()
    if remove_attributes:
        for attribute in remove_attributes:
            if attribute in new_attributes:
                new_attributes.pop(attribute)
    if remove_objectClasses and 'objectClass' in new_attributes:
        for objectClass in remove_objectClasses:
            if objectClass in new_attributes['objectClass']:
                new_attributes['objectClass'].remove(objectClass)

    # Apply prefix specified via ucr
    object_dn_with_prefix = object_dn
    prefix = _get_prefix()
    user_prefix_attrs, user_other_dn_attrs = _get_username_prefix_config()
    group_prefix_attrs, group_other_dn_attrs, group_other_attrs = _get_group_name_prefix_config()
    if prefix:
        if object_dn.startswith('uid='):
            object_dn_with_prefix, new_attributes = _add_prefix_to_user(object_dn_with_prefix, new_attributes, prefix, command, old_attributes, user_prefix_attrs, user_other_dn_attrs, object_dn)
        elif object_dn.startswith('cn='):
            object_dn_with_prefix, new_attributes = _add_prefix_to_group(object_dn_with_prefix, new_attributes, prefix, command, old_attributes, group_prefix_attrs, group_other_dn_attrs, group_other_attrs, object_dn)

    # Deliver removed attributes
    if command == 'm':
        for attribute in old_attributes:
            if attribute not in new_attributes:
                new_attributes[attribute] = []


    data = _format_data(object_dn_with_prefix, new_attributes, command)
    _write_file(filename, DB_BASE_PATH, data)

    if command == 'n':
        timestamp = time.time()
        filename = _format_filename(timestamp)
        data = _format_data(object_dn_with_prefix, new_attributes, 'm')
        _write_file(filename, DB_BASE_PATH, data)
    handler.last_time = timestamp
handler.last_time = 1300000000

# Initialize by creating an LDAP connection
def _connect_ldap():
    '''Create an LDAP connection'''
    return univention.uldap.access(
        host=_connect_ldap.ldapserver,
        base=_connect_ldap.basedn,
        binddn=_connect_ldap.binddn,
        bindpw=_connect_ldap.bindpw,
        start_tls=2
    )
_connect_ldap.ldapserver = None
_connect_ldap.basedn = None
_connect_ldap.binddn = None
_connect_ldap.bindpw = None

def setdata(key, value):
    """called multiple times to set the LDAP configuration"""
    if key == 'basedn':
        _connect_ldap.basedn = value
    elif key == 'binddn':
        _connect_ldap.binddn = value
    elif key == 'bindpw':
        _connect_ldap.bindpw = value
    elif key == 'ldapserver':
        _connect_ldap.ldapserver = value

def initialize():
    """called for initial (or re)-sync"""

def clean():
    """called before resync"""

def prerun():
    """called before a batch of handler calls (until next postrun)"""

def postrun():
    """called 15s after the last handler call"""
