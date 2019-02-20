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
from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()

common = common.UniventionNextcloudSambaCommon()

name='nextcloud-samba-group-share-config'
description='Configure access to Samba shares in Nextcloud'
filter='(&(objectClass=nextcloudGroup)(nextcloudEnabled=1))'
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

	domainUsersMatch = common.isDomainUsersCn(dn)
	lehrerMatch = common.isLehrerCn(dn)

	groupCn = common.getGroupCn(dn)

	shares = []

	if domainUsersMatch:
		shareName = "Marktplatz"
		domainUsersOuRegex = '^cn=Domain\ Users\ '
		ou = re.sub(domainUsersOuRegex, '', domainUsersMatch.group())
		mountName = "Marktplatz {}".format(ou)
		base = common.getBase()
		share = lo.get("cn=Marktplatz,cn=shares,ou={},{}".format(ou, base))
		if share:
			shares.append(share)
		if ucr.is_true('nextcloud-samba-group-share-config/ignoreMarktplatz'):
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "UCR var nextcloud-samba-group-share-config/ignoreMarktplatz is true: Not creating mount for share {}".format(mountName))
			return
	elif lehrerMatch:
		lehrerOuRegex = '^cn=lehrer-'
		ou = re.sub(lehrerOuRegex, '', lehrerMatch.group())
		shareName = "Schueler {}".format(ou)
		mountName = "schueler-{}".format(ou)
		base = common.getBase()
		share = lo.get("cn={},cn=shares,ou={},{}".format(mountName, ou, base))
		if ucr.is_true('nextcloud-samba-group-share-config/configureRoleshares'):
			if share:
				shares.append(share)
		else:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "UCR var nextcloud-samba-group-share-config/configureRoleshares is not true: Not creating mount for share {}".format(mountName))

		if ucr.is_true('nextcloud-samba-group-share-config/configureLehreraustausch'):
			shareName = "Lehrer-Austausch"
			mountName = "Lehrer-Austausch {}".format(ou)
			share = lo.get("cn={},cn=shares,ou={},{}".format(shareName, ou, base))
			if share:
				shares.append(share)
	else:
		shareDn = common.getShareDn(lo, groupCn)
		share = lo.get(shareDn)
		if share:
			shares.append(share)
		shareName = groupCn
		mountName = groupCn

	#if command is 'd':
		#mountId = common.getMountId(mountName)
		#common.removeMount(mountId)

	if shares:
		for share in shares:
			# Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
			#univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Making sure files_external app is enabled")
			#enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
			#subprocess.call(enableAppCmd, shell=True)
			shareHost = common.getShareHost(share)
			shareSambaName = common.getShareSambaName(share)
			mountId = common.getMountId(mountName)

			common.setMountConfig(mountId, shareHost, shareName, windomain, groupCn)
	else:
		univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Nothing to do: no shares were found: {}".format(mountName))

def clean():
	return

def postrun():
	return
