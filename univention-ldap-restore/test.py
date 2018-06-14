import unittest
import mock
import ldap
import ldap.cidict
import mockldap
import ldap.modlist


class mock_ConfigRegistry(object):
	def load(self):
		pass

	def __getitem__(self, a):
		return 'domaincontroller_master'
	pass


class mock_uldap(object):

	def init(self, data=None):
		self.directory = ldap.cidict.cidict()
		self.lo = mockldap.ldapobject.LDAPObject(self.directory)
		self.lo.add_s(
			"cn=subschema", ldap.modlist.addModlist({
				"objectClass": ["top", 'subentry', 'subschema', 'extensibleObject'],
				"attributeTypes": ["( 1.3.6.1.4.1.4203.666.11.1.3.0.40 N  AME 'olcReadOnly' SYNTAX 1.3.6.1.4.1.1466.115.121.1.7 SINGLE-VALUE )"]
			})
		)
		self.lo.add_s("dc=test", ldap.modlist.addModlist({"objectClass": ["top"]}))

	def search(self, filter=None, base=None, scope=None, attr=[]):
		if scope == 'base':
			scope = ldap.SCOPE_BASE
		else:
			scope = ldap.SCOPE_SUBTREE
		if set(attr) == set(['*', '+']):
			attr = None
		if base is None:
			base = 'dc=test'
		return self.lo.search_s(base, scope, filter, attrlist=attr)

	def get(self, dn):
		try:
			return self.lo.search_s(dn, ldap.SCOPE_BASE)
		except ldap.NO_SUCH_OBJECT:
			return None

	def add(self, dn, entry, **kwargs):
		self.lo.add_s(dn, entry)

	def getAdminConnection(self):
		return self, None


uldap_mock = mock_uldap()
modules = {
	'univention.config_registry': mock.Mock,
	'univention.admin': mock.Mock,
	'univention.admin.uldap': mock.Mock,
	'univention.admin.objects': mock.Mock,
	'univention.admin.modules': mock.Mock,
	'univention.admin.config': mock.Mock,
	'univention': mock.PropertyMock(config_registry=mock.Mock)
}


@mock.patch.dict('sys.modules', modules)
@mock.patch('__builtin__.open')
@mock.patch('univention.admin.uldap', uldap_mock)
@mock.patch('univention.config_registry', mock.PropertyMock(ConfigRegistry=mock_ConfigRegistry))
class MyTests(unittest.TestCase):

	def mock_identify_udm(self, t):
		return dict(dummy='test')

	# nothing to do
	@mock.patch('argparse._sys.argv', ['python', '--dn', 'uid=bob,dc=test', '-b', 'a'])
	def test_nothing_found(self, *args):
		from python.restore_ldap_object_from_backup import main
		ret = main()
		assert ret == 0

	# no dn
	@mock.patch('argparse._sys.argv', ['python', '--dn', '-b', 'a'])
	def test_args(self, *args):
		from python.restore_ldap_object_from_backup import main
		with self.assertRaises(SystemExit):
			main()

	# add
	@mock.patch('argparse._sys.argv', ['python', '-d', 'uid=bob,dc=test', '-b', 'a'])
	def test_add(self, *args):
		from python.restore_ldap_object_from_backup import MyRestore
		from python.restore_ldap_object_from_backup import main

		uldap_mock.init()

		def mock_get_backup_data(self):
			self.backup_data = {"uid": ["bob"], "objectClass": ["top"]}

		MyRestore.get_backup_data = mock_get_backup_data
		MyRestore.identify_udm = self.mock_identify_udm
		ret = main()
		assert ret == 0
		r = uldap_mock.get('uid=bob,dc=test')
		assert r[0][0] == 'uid=bob,dc=test'


if __name__ == '__main__':
	unittest.main()
