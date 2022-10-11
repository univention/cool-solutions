#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# listener module
#
# Copyright 2018-2019 Univention GmbH
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
import univention.debug
import univention.admin.uldap
from typing import List, Dict

name='nextcloud-enable-for-classes-and-workgroups'
description='Enable Nextcloud for all classes, workgroups, Domain Users <ou>, lehrer-<ou> and schueler-<ou>'
filter='(|(cn=Domain Users *)(cn=lehrer-*)(cn=schueler-*)(ucsschoolRole=school_class:school:*)(ucsschoolRole=workgroup:school:*))'
attributes=[]
modrdn="1"

def initialize() -> None:
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "{}: initialize".format(name))
	return

def handler(
	dn: str,
	new: dict[str, List[bytes]],
	old: dict[str, List[bytes]],
	command: str = '') -> None:
	if command == 'd':
		return
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "DN {}".format(dn))
	listener.setuid(0)
	lo, po = univention.admin.uldap.getAdminConnection()
	listener.unsetuid()

	#Enable group for nextcloud
	nextcloudEnabled = lo.getAttr(dn, 'nextcloudEnabled')
	if not nextcloudEnabled:
		modlist = [('objectClass', '', 'nextcloudGroup'), ('nextcloudEnabled', '', '1')]
		lo.modify(dn, modlist)
		univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Enabled Nextcloud for {}".format(dn))

def clean():
	return

def postrun():
	return
