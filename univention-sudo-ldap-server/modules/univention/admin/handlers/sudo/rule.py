#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Copyright 2004-2015 Univention GmbH
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

from univention.admin.layout import Tab, Group
import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax

translation = univention.admin.localization.translation('univention.admin.handlers.sudo')
_ = translation.translate

module = 'sudo/rule'
superordinate = 'settings/cn'
childs = False
short_description = _(u'sudo rule')
long_description = _(u'Rules to control sudo-ldap behaviour')
operations = ['add', 'edit', 'remove', 'search']

options = {
	'default': univention.admin.option(
		short_description='',
		objectClasses=['top', 'sudoRole'],
	),
}

property_descriptions = {
	'name': univention.admin.property(
		short_description=_(u'Name'),
		long_description=_(u'Unique name for the rule'),
		syntax=univention.admin.syntax.string,
		required=True,
		identifies=True,
	),
	'description': univention.admin.property(
		short_description=_(u'Description'),
		long_description=_(u'Description of the rule'),
		syntax=univention.admin.syntax.string,
	),
	'users': univention.admin.property(
		short_description=_(u'Users'),
		long_description=_(u'Users and groups this rule is for'),
		syntax=univention.admin.syntax.string,
		multivalue=True,
		required=True,
	),
	'hosts': univention.admin.property(
		short_description=_(u'Hosts'),
		long_description=_(u'Hostnames this rule is for'),
		syntax=univention.admin.syntax.string,
		multivalue=True,
		required=True,
	),
	'command': univention.admin.property(
		short_description=_(u'Command'),
		long_description=_(u'Commands allowed/refused by this rule'),
		syntax=univention.admin.syntax.string,
		multivalue=True,
		required=True,
	),
}

layout = [
	Tab(_(u'General'), _(u'Basic Settings'), layout=[
		Group(_('Sudo Rule'), layout=[
			["name", "description", ]
		]),
		Group(_('Affected users'), layout=[
			["users", ],
			["hosts", ],
		]),
		Group(_('Allowed commands'), layout=[
			["command", ],
		]),
	])
]

mapping = univention.admin.mapping.mapping()
mapping.register('name', 'cn', None, univention.admin.mapping.ListToString)
mapping.register('description', 'description', None, univention.admin.mapping.ListToString)
mapping.register('users', 'sudoUser')
mapping.register('hosts', 'sudoHost')
mapping.register('command', 'sudoCommand')


class object(univention.admin.handlers.simpleLdap):
	module = module

	if not hasattr(univention.admin.handlers.simpleLdap, '_ldap_dn'):
		def _ldap_pre_create(self):
			self.dn = '%s=%s,%s' % (mapping.mapName('name'), mapping.mapValue('name', self.info['name']), self.position.getDn())

		def _ldap_addlist(self):
			al = [('objectClass', [b'top', b'sudoRole'])]
			return al


try:
	lookup = object.lookup
except AttributeError:  # TODO: remove; which UCS version needs to be supported?
	try:
		unicode
	except NameError:
		unicode = str

	def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):
		searchfilter = univention.admin.filter.conjunction('&', [
			univention.admin.filter.expression('objectClass', 'sudoRole'),
		])

		if filter_s:
			filter_p = univention.admin.filter.parse(filter_s)
			univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
			searchfilter.expressions.append(filter_p)

		res = []
		for dn in lo.searchDn(unicode(searchfilter), base, scope, unique, required, timeout, sizelimit):
			res.append(object(co, lo, None, dn))
		return res


try:
	identify = object.identify
except AttributeError:
	def identify(distinguished_name, attributes, canonical=False):
		return b'sudoRole' in attributes.get('objectClass', [])
