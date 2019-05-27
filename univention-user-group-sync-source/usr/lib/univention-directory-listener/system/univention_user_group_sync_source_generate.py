#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
"""user group sync source
    listener module"""
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

__package__ = '' # workaround for PEP 366, pylint: disable-msg=W0622
import cPickle as pickle
import pwd
import grp
import os
import tempfile
import time
import univention.debug
import univention.uldap
import univention.config_registry
import listener

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
)""".translate(None, '\t\n\r ')
filter_custom = ""

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
def _log(message, level):
    """log a <message> (str) with log<level>"""
    message = '[%s] %s' % (name, message, )
    univention.debug.debug(univention.debug.LISTENER, level, message)
def _log_debug(message):
    """log a "debug" <message> (str)"""
    return _log(message, univention.debug.ALL)
def _log_info(message):
    """log a "info" <message> (str)"""
    return _log(message, univention.debug.INFO)
def _log_process(message):
    """log a "process" <message> (str)"""
    return _log(message, univention.debug.PROCESS)
def _log_warn(message):
    """log a "warn" <message> (str)"""
    return _log(message, univention.debug.WARN)
def _log_error(message):
    """log a "error" <message> (str)"""
    return _log(message, univention.debug.ERROR)

# Format a unix timestamp into a filename
def _format_filename(timestamp):
    """format a unix timestamp into a filename
    guaranteed to generate a unique name for every different <float> timestamp
    (if timestamp is after 2011)"""
    # 17 significant digits capture the full precision of python floats
    # because timestamp is always > 1300000000 this format has 17 significant digits
    # 11 digit seconds work until 5138-11-16
    # 19 == 11 + 7 + 1 because the dot also consumes a character
    return '%019.7f' % (timestamp, )

# Write the given data into a file
def _write_file(filename, path, data):
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
    os.chmod(filename, 0640)
    listener.unsetuid()

#
def _wait_until_after(timestamp):
    """wait until the current (system) time is later than <timestamp>"""
    while time.time() <= timestamp:
        time.sleep(0.01)

# Pickle the given data
def _format_data(object_dn, new_attributes, command):
    """encode (serialise) object data"""
    data = (object_dn, command, new_attributes, )
    return pickle.dumps(data, protocol=2)

#
def handler(object_dn, new_attributes, old_attributes, command):
    """called for each uniqueMember-change on a group"""
    _log_debug("handler for: %r %r" % (object_dn, command, ))
    _wait_until_after(handler.last_time)
    timestamp = time.time()
    filename = _format_filename(timestamp)

    #Remove univention-user-group-sync attribute and objectClass if set
    if 'univentionUserGroupSyncEnabled' in new_attributes:
        new_attributes.pop('univentionUserGroupSyncEnabled')
        new_attributes['objectClass'].remove('univentionUserGroupSync')

    # Deliver removed attributes
    if command == 'm':
        for attribute in old_attributes:
            if attribute not in new_attributes:
                new_attributes[attribute] = []
    data = _format_data(object_dn, new_attributes, command)

    # Apply custom filter, if set
    filter_custom = ucr_map_identifier()
    if filter_custom.strip() and command != 'd' and command != 'r':
        ldap = _connect_ldap()
        if not ldap.search(filter=filter_custom, base=object_dn):
            return

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
