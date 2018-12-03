#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# listener module
#
# Copyright 2018 Univention GmbH
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

__package__='' 	# workaround for PEP 366

import listener
import re
import univention.debug
import univention.admin.uldap

name='nextcloud-enable-for-classes-and-workgroups'
description='Enable Nextcloud for all classes, workgroups and Domain Users <ou>'
filter='(|(cn=Domain Users *)(objectClass=ucsschoolGroup))'
attributes=[]

def initialize():
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "{}: initialize".format(name))
	return

def handler(dn, new, old):
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "DN {}".format(dn))
	listener.setuid(0)
	lo, po = univention.admin.uldap.getAdminConnection()

	domainUsersRegex = '^cn=Domain\ Users\ [A-Za-z0-9_]*'
	domainUsersOuRegex = '^cn=Domain\ Users\ '
	domainUsersMatch = re.match(domainUsersRegex, dn)

	try:
		groupRole = lo.getAttr(dn, 'ucsschoolRole')[0]
		if not groupRole.startswith('school_class:school') and not groupRole.startswith('workgroup:school'):
			return
	except:
		if not domainUsersMatch:
			return

	#Enable group for nextcloud
	nextcloudEnabled = lo.getAttr(dn, 'nextcloudEnabled')
	if not nextcloudEnabled:
		modlist = [('objectClass', '', 'nextcloudGroup'), ('nextcloudEnabled', '', '1')]
		lo.modify(dn, modlist)
		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, "Enabled Nextcloud for {}".format(dn))

	listener.unsetuid()

def clean():
	return

def postrun():
	return
