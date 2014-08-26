#!/usr/bin/python2.6
# vim:set ts=4 sw=4 et:
# pylint: disable-msg=C0103,R0902,R0904,R0912
"""Listener to push local users to global master."""
#
# Copyright 2012 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of the software contained in this package
# as well as the source package itself are made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this package provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use the software under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

# @local
# ucr set multi-master-setup/remote/ldapuri=ldap://10.200.17.40:7389
# ucr set multi-master-setup/remote/basedn=dc=master,dc=dev
# ucr set multi-master-setup/remote/binddn=cn=admin,dc=master,dc=dev
# ucr set multi-master-setup/remote/bindpw=/etc/univention.secret
# ucr set multi-master-setup/remote/position=cn=users,dc=master,dc=dev
# ucr set multi-master-setup/remote/groupdn=cn=DOM1,cn=groups,dc=master,dc=dev
# ucr set multi-master-setup/remote/krbrealm=DOM1.DEV
# ucr set multi-master-setup/remote/suffix=dom1
# (umask 0077 ; echo -n univention >/etc/univention.secret)
# chmod 0400 /etc/univention.secret
# chown listener /etc/univention.secret
#
# @remote:
# udm groups/group create --position "cn=groups,$(ucr get ldap/base)" \
#   --option samba --set name="DOM1"
#
# @local
# udm users/user create --position "cn=users,$(ucr get ldap/base)" \
#   --option posix --option samba --option kerberos --set lastname=test \
#   --set username=test --set password=univention \
#   --set primaryGroup="cn=Domain Users,cn=groups,$(ucr get ldap/base)" \
#   --set unixhome=/home/test
# udm users/user remove --dn uid=test,dc=dom1,dc=dev

__package__ = ''  # workaround for PEP 366

name = 'multi-master-setup'
description = 'Push local users to remote UCS system.'
filter = '''(&
              (|
                (&
                  (objectClass=posixAccount)
                  (objectClass=shadowAccount)
                )
               (objectClass=univentionMail)
               (objectClass=sambaSamAccount)
               (objectClass=simpleSecurityObject)
               (objectClass=inetOrgPerson)
              )
              (!(objectClass=univentionHost))
              (!(uidNumber=0))
              (!(uid=*$))
            )'''.translate(None, '\t\n ')  # filter taken from UDM users/user
attributes = []
modrdn = "True"  # must be a string!

import univention.debug as ud
from listener import configRegistry, setuid, unsetuid
import ldap
import ldap.modlist
import os
import errno
import time
try:
    import cPickle as pickle
except ImportError:
    import pickle


def ucr(key, default=None):
    """Wrapper around configRegistry throwing KeyErrors on undefined keys."""
    if default is None:
        default = ucr.UNIQUE
    value = configRegistry.get(key, default)
    if value is ucr.UNIQUE:
        raise KeyError(key)
    return value
ucr.UNIQUE = object()


class MappingError(Exception):
    """Signal error mapping attribute."""
    pass


class Handler(object):
    """Listener to push local users to global master."""
    def __init__(self):
        self.l_host = 'localhost'
        self.l_port = 7389
        try:
            self.l_basedn = ucr('ldap/base')
            self.l_pending = ucr('multi-master-setup/local/pending',
                    '/var/lib/multi-master-setup')
            self.r_ldapuri = ucr('multi-master-setup/remote/ldapuri')
            self.r_binddn = ucr('multi-master-setup/remote/binddn')
            self.r_basedn = ucr('multi-master-setup/remote/basedn')
            self.r_groupdn = ucr('multi-master-setup/remote/groupdn')
            self.r_suffix = ucr('multi-master-setup/remote/suffix',
                    ucr('windows/domain'))
            self.r_krbrealm = ucr('multi-master-setup/remote/krbrealm')
            r_position = ucr('multi-master-setup/remote/position')
            pwfile = ucr('multi-master-setup/remote/bindpw')
        except KeyError, ex:
            ud.debug(ud.LISTENER, ud.ERROR, 'Unconfigured %s' % (ex,))
            raise
        try:
            with open('/etc/ldap.secret', 'r') as f_pw:
                self.l_bindpw = f_pw.read().rstrip('\n')
            with open(pwfile, 'r') as f_pw:
                self.r_bindpw = f_pw.read().rstrip('\n')
        except IOError, ex:
            ud.debug(ud.LISTENER, ud.ERROR, 'Missing %s' % (ex,))
            raise
        self.l_binddn = 'cn=admin,%s' % (self.l_basedn,)
        self.r_position = ldap.dn.str2dn(r_position)
        self.pending = True
        ud.debug(ud.LISTENER, ud.ALL, 'mmp.init()')

    @property
    def l(self):
        """Local LDAP connection."""
        try:
            return self.__l
        except AttributeError:
            l_ldapuri = 'ldap://%s:%d' % (self.l_host, self.l_port)
            self.__l = ldap.initialize(l_ldapuri)
            _id, _err = self.__l.simple_bind_s(self.l_binddn, self.l_bindpw)
            return self.__l

    @property
    def r(self):
        """Remote LDAP connection."""
        try:
            return self.__r
        except AttributeError:
            self.__r = ldap.initialize(self.r_ldapuri)
            _id, _err = self.__r.simple_bind_s(self.r_binddn, self.r_bindpw)
            return self.__r

    def map_dn(self, l_dn):
        """Translate local Distinguished Name to remote dn."""
        l_rdn = ldap.dn.str2dn(l_dn)
        l_user_rdn = l_rdn[0]
        if len(l_user_rdn) != 1:
            raise ValueError('Multi valued rdn not supported')
        key, l_value, typ = l_user_rdn[0]
        r_value = '%s_%s' % (l_value, self.r_suffix)
        r_user_rdn = [(key, r_value, typ)]
        r_rdn = [r_user_rdn] + self.r_position
        r_dn = ldap.dn.dn2str(r_rdn)
        return r_dn

    def map_uid(self, value):
        """Translate local User Identifier to remote uid."""
        return '%s_%s' % (value, self.r_suffix)

    def map_gidNumber(self, _value):
        """Translate local Group Identifier Number to remote gidNumber."""
        return self.__map_group(self.r_groupdn)[0]

    def map_sambaPrimaryGrooupSID(self, _value):
        """Translate local Samba Primary Group Security Ientifier to remote
        sambaPrimaryGroupSID."""
        return self.__map_group(self.r_groupdn)[1]

    def map_krb5PrincipalName(self, value):
        """Translate local Kerberos 5 Principal Name to remote
        krb5PrincipalName."""
        principal, _domain = value.split('@', 1)
        return '%s_%s@%s' % (principal, self.r_suffix, self.r_krbrealm)

    def map_homeDirectory(self, value):
        """Translate local Home Directory to remote homeDirectory."""
        l_prefix, l_dirname = os.path.split(value)
        return os.path.join(l_prefix, self.r_suffix, l_dirname)

    def __map_group(self, group_dn):
        """Fetch remote group identifiers."""
        try:
            r = self.r
            attrlist = ['gidNumber', 'sambaSID']
            res = r.search_ext_s(group_dn, ldap.SCOPE_BASE, attrlist=attrlist)
            assert len(res) == 1
            dn, attrs = res[0]
            assert dn == group_dn
            for key, values in attrs.items():
                if key == 'gidNumber':
                    gid = values[0]  # int
                elif key == 'sambaSID':
                    sid = values[0]
            return gid, sid
        except ldap.LDAPError:
            raise
        except (TypeError, ValueError, NameError):
            raise MappingError('group_dn')

    def allocate_uidNumber(self):
        """Allocate remote User Identifier Number for local uidNumber."""
        base = 'cn=uidNumber,cn=temporary,cn=univention,%s' % (self.r_basedn,)
        try:
            r = self.r
            while True:
                # 1. Determine last value
                attrlist = ['univentionLastUsedValue']
                res = r.search_ext_s(base, ldap.SCOPE_BASE, attrlist=attrlist)
                assert len(res) == 1
                dn, attrs = res[0]
                assert dn == base
                for key, values in attrs.items():
                    if key == 'univentionLastUsedValue':
                        last_uid = int(values[0])
                        break
                else:
                    raise TypeError('Missing "univentionLastUsedValue"')
                next_uid = last_uid + 1
                # 2. Validate last value is still unused
                while True:
                    filter_ = '(uidNumber=%d)' % (next_uid,)
                    attrlist = ['uidNumber']
                    try:
                        res = r.search_ext_s(self.r_basedn, ldap.SCOPE_SUBTREE,
                                filter_, attrlist, attrsonly=1, sizelimit=1)
                        if len(res) == 0:
                            break
                    except ldap.NO_SUCH_OBJECT:
                        break
                    next_uid = next_uid + 1
                # 3. Update last used value
                r_modlist = [
                        (ldap.MOD_DELETE, 'univentionLastUsedValue',
                            ['%s' % (last_uid,)]),
                        (ldap.MOD_ADD, 'univentionLastUsedValue',
                            ['%s' % (next_uid,)]),
                        ]
                try:
                    _res = r.modify_ext_s(dn, r_modlist)
                    break
                except ldap.NO_SUCH_ATTRIBUTE:
                    ud.debug(ud.LISTENER, ud.ALL,
                            'Concurrent access to univentionLastUsedValue:' + \
                                    ' last=%d next=%d' % (last_uid, next_uid))
        except ldap.LDAPError:
            raise
        except (TypeError, ValueError), ex:
            ud.debug(ud.LISTENER, ud.ERROR, 'mmp.map_uidNumber(): %r' % (ex,))
            raise MappingError('uidNumber')
        return '%s' % (next_uid,)

    def translate_data(self, l_data):
        """Translate local user to remote user."""
        r_data = {}
        for key, l_values in l_data.items():
            # skip (mostly operational) attributes
            if key in self.translate_data.SKIP:
                continue
            try:
                field = getattr(self, 'map_%s' % (key,))
            except AttributeError:
                r_values = l_values
            else:
                r_values = [field(v) for v in l_values]
            r_data[key] = r_values
        return r_data
    translate_data.SKIP = set((
        'entryUUID',
        'entryDN',
        'entryCSN',
        'creatorsName',
        'createTimestamp',
        'modifiersName',
        'modifyTimestamp',
        'structuralObjectClass',
        'hasSubordinates',
        'subschemaSubentry',
        'uidNumber',
        ))

    def handle_add(self, l_dn, l_new):
        """Handle changeType: add."""
        r_dn = self.map_dn(l_dn)
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.handler_add(dn=%s|%s)' % (l_dn, r_dn))
        r_new = self.translate_data(l_new)
        r_new['uidNumber'] = [self.allocate_uidNumber()]
        r_modlist = ldap.modlist.addModlist(r_new)
        try:
            r = self.r
            _res = r.add_ext_s(r_dn, r_modlist)
        except ldap.ALREADY_EXISTS, ex:
            res = r.search_ext_s(r_dn, ldap.SCOPE_BASE)
            assert len(res) == 1
            dn, attrs = res[0]
            assert dn == r_dn
            r_new['uidNumber'] = attrs['uidNumber']
            r_modlist = ldap.modlist.modifyModlist(attrs, r_new)
            try:
                _res = r.modify_ext_s(r_dn, r_modlist)
            except ldap.NO_SUCH_OBJECT, ex2:
                ud.debug(ud.LISTENER, ud.ERROR,
                        'Error adding "%s": %s, %s' % (r_dn, ex, ex2))
                return
        # Update group membership
        r_modlist = [
                (ldap.MOD_ADD, 'uniqueMember', r_dn),
                (ldap.MOD_ADD, 'memberUid', r_new['uid'][0]),
                ]
        try:
            r = self.r
            _res = r.modify_ext_s(self.r_groupdn, r_modlist)
        except ldap.TYPE_OR_VALUE_EXISTS, ex:
            ud.debug(ud.LISTENER, ud.WARN,
                    'User "%s" already in group "%s": %s' % \
                            (r_dn, self.r_groupdn, ex))

    def handle_delete(self, l_dn, _l_old):
        """Handle changeType: delete."""
        r_dn = self.map_dn(l_dn)
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.handler_delete(dn=%s|%s)' % (l_dn, r_dn))
        try:
            r = self.r
            # get old UID number
            res = r.search_ext_s(r_dn, ldap.SCOPE_BASE)
            assert len(res) == 1
            dn, attrs = res[0]
            assert dn == r_dn
            r_uid = attrs['uid'][0]
            # now delete
            _res = r.delete_ext_s(r_dn)
        except ldap.NO_SUCH_OBJECT:
            return
        # Update group membership
        r_modlist = [
                (ldap.MOD_DELETE, 'uniqueMember', r_dn),
                (ldap.MOD_DELETE, 'memberUid', r_uid),
                ]
        try:
            r = self.r
            _res = r.modify_ext_s(self.r_groupdn, r_modlist)
        except ldap.NO_SUCH_ATTRIBUTE, ex:
            ud.debug(ud.LISTENER, ud.WARN,
                    'User "%s" already not in group "%s": %s' % \
                            (r_dn, self.r_groupdn, ex))

    def handle_modify(self, l_dn, l_old, l_new):
        """Handle changeType: modify."""
        r_dn = self.map_dn(l_dn)
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.handler_modify(dn=%s|%s)' % (l_dn, r_dn))
        r_old = self.translate_data(l_old)
        r_new = self.translate_data(l_new)
        r_modlist = ldap.modlist.modifyModlist(r_old, r_new)
        try:
            r = self.r
            _res = r.modify_ext_s(r_dn, r_modlist)
        except ldap.NO_SUCH_OBJECT, ex:
            r_new['uidNumber'] = [self.allocate_uidNumber()]
            r_modlist = ldap.modlist.addModlist(r_new)
            try:
                _res = r.add_ext_s(r_dn, r_modlist)
            except ldap.ALREADY_EXISTS, ex2:
                ud.debug(ud.LISTENER, ud.ERROR,
                        'Error modifying "%s": %s, %s' % (r_dn, ex, ex2))
                return
            # Update group membership
            r_modlist = [
                    (ldap.MOD_ADD, 'uniqueMember', r_dn),
                    (ldap.MOD_ADD, 'memberUid', r_new['uid'][0]),
                    ]
            try:
                _res = r.modify_ext_s(self.r_groupdn, r_modlist)
            except ldap.TYPE_OR_VALUE_EXISTS, ex:
                ud.debug(ud.LISTENER, ud.WARN,
                        'User "%s" already in group "%s": %s' % \
                                (r_dn, self.r_groupdn, ex))

    def handle_modify_rdn(self, l_old_dn, l_old, l_new_dn, l_new):
        """Handle changeType: modrdn."""
        r_old_dn = self.map_dn(l_old_dn)
        r_new_dn = self.map_dn(l_new_dn)
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.handler_modify_rdn(dn=%s|%s dn=%s|%s)' % \
                        (l_old_dn, r_old_dn, l_new_dn, r_new_dn))
        r_dn = ldap.dn.str2dn(r_new_dn)
        r_new_rdn = ldap.dn.dn2str(r_dn[:1])
        r_new_super = ldap.dn.dn2str(r_dn[1:])
        try:
            r = self.r
            _res = r.rename_s(r_old_dn, r_new_rdn, r_new_super)
        except ldap.NO_SUCH_OBJECT, ex:
            ud.debug(ud.LISTENER, ud.ERROR,
                    'mmp.handler_modify_rdn(): %r' % (ex,))
            raise
        except ldap.ALREADY_EXISTS, ex:
            ud.debug(ud.LISTENER, ud.ERROR,
                    'mmp.handler_modify_rdn(): %r' % (ex,))
            raise
        # Update group membership
        r_old_uid = self.map_uid(l_old['uid'][0])
        r_new_uid = self.map_uid(l_new['uid'][0])
        r_modlist = [
                (ldap.MOD_DELETE, 'uniqueMember', r_old_dn),
                (ldap.MOD_ADD, 'uniqueMember', r_new_dn),
                (ldap.MOD_DELETE, 'memberUid', r_old_uid),
                (ldap.MOD_ADD, 'memberUid', r_new_uid),
                ]
        try:
            r = self.r
            _res = r.modify_ext_s(self.r_groupdn, r_modlist)
        except ldap.NO_SUCH_ATTRIBUTE, ex:
            ud.debug(ud.LISTENER, ud.WARN,
                    'Fix inconsistend group manually "%s": %s' % \
                            (self.r_groupdn, ex))
        except ldap.TYPE_OR_VALUE_EXISTS, ex:
            ud.debug(ud.LISTENER, ud.WARN,
                    'User "%s" in group "%s": %s' % \
                            (r_dn, self.r_groupdn, ex))


    # Public Listener functions

    def process_pending(self):
        """Process pending transactions."""
        ud.debug(ud.LISTENER, ud.INFO, 'mmp.process_pending()')
        assert self.l_pending > '/'
        for _dirpath, dirnames, filenames in os.walk(self.l_pending):
            for filename in sorted(filenames, key=lambda f: float(f[:7])):
                if not filename.endswith('.pickle'):
                    continue
                self.pending = True
                fn = os.path.join(self.l_pending, filename)
                try:
                    with open(fn, 'rb') as f:
                        p = pickle.Unpickler(f)
                        funcname, args = p.load()
                        func = getattr(self, funcname)
                except (IOError, pickle.PicklingError, AttributeError):
                    ud.debug(ud.LISTENER, ud.ERROR,
                            'Failed to read pending updates: %s' % (fn,))
                    break
                try:
                    func(*args)
                    os.unlink(fn)
                except ldap.LDAPError:
                    ud.debug(ud.LISTENER, ud.ERROR,
                            'Failed to process pending updates: %s' % (fn,))
                    break
            else:
                self.pending = False
            del dirnames[:]
        return self.pending

    def initialize(self):
        """Initialize the module once on first start or after clean."""
        ud.debug(ud.LISTENER, ud.INFO, 'mmp.initialize()')
        # Create directory for storing failed changes, which is accessible by
        # normal listener
        listener_uid = os.geteuid()
        listener_gid = os.getegid()
        setuid(0)
        try:
            try:
                os.makedirs(self.l_pending, mode=0700)
            except OSError, ex:
                if ex.errno != errno.EEXIST:
                    raise
            os.chown(self.l_pending, listener_uid, listener_gid)
        finally:
            unsetuid()
        self.process_pending()

    def handler(self, dn, new, old, command=''):
        """Handle changes to 'dn'."""
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.handler(dn=%s %snew %sold cmd=%s)' % \
                        (dn, new and ' ' or '!', old and ' ' or '!', command))
        if 'm' == command:  # modify
            assert new is not None
            assert old is not None
            func, args = self.handle_modify, (dn, old, new)
        elif 'a' == command:  # add
            assert new is not None
            assert old is None
            try:
                old_dn, old = self.__modrdn  # pylint: disable-msg=E0203
                del self.__modrdn
            except AttributeError:
                func, args = self.handle_add, (dn, new)
            else:
                func, args = self.handle_modify_rdn, (old_dn, old, dn, new)
        elif 'd' == command:  # delete
            assert new is None
            assert old is not None
            func, args = self.handle_delete, (dn, old)
        elif 'r' == command:  # modrdn
            assert new is None
            assert old is not None
            # will be called again with command='a'
            self.__modrdn = (dn, old)
            return
        elif 'z' == command:  # unknown
            return
        elif 'n' == command:
            if 'cn=Subschema' == dn:  # schema change
                return
            else:  # initialization
                assert new is not None
                assert old is None
                func, args = self.handle_add, (dn, new)
        else:
            ud.debug(ud.LISTENER, ud.ERROR,
                    'mmp.handler(dn=%s, command=%s)' % (dn, command))
            return

        try:
            if not self.pending:
                func(*args)
        except ldap.SERVER_DOWN:
            ud.debug(ud.LISTENER, ud.ERROR,
                    'mmp.handler(): LDAP failed, saving')
            self.pending = True

        if self.pending:
            now = time.time()
            fn = os.path.join(self.l_pending, '%f.pickle' % (now,))
            with open(fn, 'wb') as f:
                p = pickle.Pickler(f, -1)
                funcname = func.__func__.__name__
                p.dump((funcname, args))

    def clean(self):
        """
        Handle request to clean-up the module.
        Remove all pending changes.
        """
        ud.debug(ud.LISTENER, ud.INFO, 'mmp.clean()')
        assert self.l_pending > '/'
        for dirpath, _dirnames, filenames in os.walk(self.l_pending):
            for filename in filenames:
                if not filename.endswith('.pickle'):
                    continue
                try:
                    os.unlink(os.path.join(dirpath, filename))
                except OSError, ex:
                    ud.debug(ud.LISTENER, ud.WARN, ex)
            else:
                self.pending = False

    def prerun(self):
        """Transition from not-prepared to prepared state."""
        ud.debug(ud.LISTENER, ud.ALL, 'mmp.prerun()')
        if self.pending:
            self.process_pending()

    def postrun(self):
        """Transition from prepared-state to not-prepared."""
        ud.debug(ud.LISTENER, ud.ALL, 'mmp.postrun()')
        self.__disconnect()

    def setdata(self, key, value):
        """Initialize module with listener configuration data."""
        ud.debug(ud.LISTENER, ud.ALL,
                'mmp.setdata(key=%s, value=%s)' % \
                        (key, setdata.HIDE.get(key, value)))
        handlers = {
                'basedn': 'l_basedn',
                'binddn': 'l_binddn',
                'bindpw': 'l_bindpw',
                'ldapserver': 'l_host',
                }
        try:
            var = handlers['key']
            setattr(self, var, value)
        except KeyError:
            pass
        self.__disconnect()
    setdata.HIDE = {'bindpw': '<HIDDEN>'}

    def __disconnect(self):
        """Force LDAP reconnect."""
        try:
            try:
                _id = self.__l.unbind()
            except ldap.LDAPError:
                pass
            del self.__l
        except AttributeError:
            pass
        try:
            try:
                _id = self.__r.unbind()
            except ldap.LDAPError:
                pass
            del self.__r
        except AttributeError:
            pass

__handler = Handler()
initialize = __handler.initialize
handler = __handler.handler
clean = __handler.clean
prerun = __handler.prerun
postrun = __handler.postrun
setdata = __handler.setdata
#filters = [(__handler.l_basedn, ldap.SCOPE_SUBTREE,
#    '(objectclass=sambaSamAccount)')]
