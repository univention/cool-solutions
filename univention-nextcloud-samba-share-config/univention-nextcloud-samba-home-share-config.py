#!/usr/bin/python2.7
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
import re
import subprocess
import time
import univention.nextcloud_samba.common as common
import univention.debug
import univention.admin.uldap
common = common.UniventionNextcloudSambaCommon()

name='nextcloud-samba-home-share-config'
description='Configure access to Samba home shares in Nextcloud'
filter='(&(objectClass=nextcloudGroup)(nextcloudEnabled=1)(cn=Domain Users *))'
attributes=[]
modrdn="1"

def initialize():
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "{}: initialize".format(name))
	return

def handler(dn, new, old, command=''):
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "DN {}".format(dn))
	listener.setuid(0)
	lo, po = univention.admin.uldap.getMachineConnection()

	windomain = common.getWinDomain()
	domain = common.getDomain()
	base = common.getBase()

	domainUsersMatch = common.isDomainUsersCn(dn)

	groupCn = common.getGroupCn(dn)
	domainUsersOuRegex = '^cn=Domain\ Users\ '
	ou = re.sub(domainUsersOuRegex, '', domainUsersMatch.group())
	mountName = "Home {}".format(ou)
	shareName = '$user'

	ouObject = lo.get('ou={},{}'.format(ou, base))
	shareHostDn = ouObject['ucsschoolHomeShareFileServer'][0]
	shareHostCn = lo.get(shareHostDn)['cn'][0]

	shareHost = "{}.{}".format(shareHostCn, domain)

	mountId = common.getMountId(mountName)

	common.setMountConfig(mountId, shareHost, shareName, windomain, groupCn)

def clean():
	return

def postrun():
	return
