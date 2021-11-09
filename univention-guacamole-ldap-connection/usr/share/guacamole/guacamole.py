#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Guacamole
#  univention admin guacamole module
#
# Copyright 2021 Univention GmbH
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

import univention.admin
from univention.admin.layout import Tab, Group
import univention.admin.uldap
import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax
import univention.admin.localization
from univention.admin import configRegistry
from univention.admin.uldap import DN

translation = univention.admin.localization.translation('univention-admin-handlers-guacamole-config')
_ = translation.translate

module = 'guacamole/config'
childs = 0
short_description = _('Guacamole Configuration')
long_description = ''
operations = ['add', 'edit', 'remove', 'search', 'move']
options = {}

property_descriptions = {
	"name": univention.admin.property(
		short_description=_("Name"),
		long_description='',
		syntax=univention.admin.syntax.string_numbers_letters_dots,
		multivalue=False,
		include_in_default_search=True,
		options=[],
		required=True,
		may_change=False,
		identifies=True
	),
	"description": univention.admin.property(
		short_description=_("Description"),
		long_description='',
		syntax=univention.admin.syntax.string,
		multivalue=False,
		include_in_default_search=True,
		options=[],
		required=False,
		may_change=True,
		identifies=False
	),
	"guacConfigProtocol": univention.admin.property(
		short_description=_("Protocol"),
		long_description=_("Remote computer's protocol"),
		syntax=univention.admin.syntax.guacamole_protocol,
		multivalue=False,
		include_in_default_search=True,
		options=[],
		required=False,
		may_change=True,
		identifies=False
	),
	"guacConfigParameter": univention.admin.property(
		short_description=_("Parameter"),
		long_description=_("Connection parameters using the schema foo=bar"),
		syntax=univention.admin.syntax.string,
		multivalue=True,
		include_in_default_search=True,
		options=[],
		required=True,
		may_change=True,
		identifies=False
	),
	'users': univention.admin.property(
		short_description=_('Users'),
		long_description='',
		syntax=univention.admin.syntax.UserDN,
		multivalue=True,
		options=[],
		required=False,
		may_change=True,
		dontsearch=True,
		identifies=False,
		readonly_when_synced=True,
		copyable=True,
	),
	'nestedGroup': univention.admin.property(
		short_description=_('Groups'),
		long_description='',
		syntax=univention.admin.syntax.GroupDN,
		multivalue=True,
		options=[],
		required=False,
		may_change=True,
		dontsearch=True,
		identifies=False,
		readonly_when_synced=True,
		copyable=True,
	),
}

layout = [
	Tab(_("General"), _("Basic settings"), layout=[
		Group(_('Guacamole Configuration'), layout=[
			["name", "description"],
		]),
		Group(_('Members of this Configuration'), layout=[
			'users',
			'nestedGroup'
		]),
		Group(_('Settings'), layout=[
			'guacConfigProtocol',
			'guacConfigParameter'
		]),
	]),
]

mapping = univention.admin.mapping.mapping()
mapping.register('name', 'cn', None, univention.admin.mapping.ListToString)
mapping.register('description', 'description', None, univention.admin.mapping.ListToString)
mapping.register('guacConfigProtocol', 'guacConfigProtocol', None, univention.admin.mapping.ListToString)
mapping.register('guacConfigParameter', 'guacConfigParameter')
mapping.register('users', 'uniqueMember')
mapping.register('nestedGroup', 'seeAlso')


class object(univention.admin.handlers.simpleLdap):
	module = module

	def __init__(self, co, lo, position, dn='', superordinate=None, attributes=None):
		self.co = co
		self.lo = lo
		self.dn = dn
		self.position = position
		self.mapping = mapping
		self.descriptions = property_descriptions
		univention.admin.handlers.simpleLdap.__init__(self, co, lo, position, dn, superordinate)
		self.options = []

	def _ldap_pre_create(self):
		self.dn = '%s=%s,%s' % (mapping.mapName('name'), mapping.mapValue('name', self.info['name']), self.position.getDn())

	def _ldap_addlist(self):
		return [('objectClass', ['top', 'guacConfigGroup',])]


def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):
	searchfilter = univention.admin.filter.conjunction('&', [
				univention.admin.filter.expression('objectClass', 'guacConfigGroup'),
				])

	if filter_s:
		filter_p = univention.admin.filter.parse(filter_s)
		univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
		searchfilter.expressions.append(filter_p)

	res = []
	for dn in lo.searchDn(unicode(searchfilter), base, scope, unique, required, timeout, sizelimit):
		res.append(object(co, lo, None, dn))
	return res

def identify(distinguished_name, attributes, canonical=False):
	return 'guacConfigGroup' in attributes.get('objectClass', [])
