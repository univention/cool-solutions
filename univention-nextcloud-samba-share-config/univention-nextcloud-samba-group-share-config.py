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

from __future__ import absolute_import

import re

import univention.admin.uldap
import univention.debug as ud
import univention.nextcloud_samba.common as common
from univention.config_registry import ConfigRegistry

import listener

ucr = ConfigRegistry()
ucr.load()

name = 'nextcloud-samba-group-share-config'
description = 'Configure access to Samba shares in Nextcloud'
filter = '(&(objectClass=nextcloudGroup)(nextcloudEnabled=1))'
attributes = []
modrdn = "1"


def handler(dn, new, old, command=''):
	ud.debug(ud.LISTENER, ud.WARN, "DN {}".format(dn))
	listener.setuid(0)
	try:
		lo, po = univention.admin.uldap.getMachineConnection()
	finally:
		listener.unsetuid()

	windomain = common.getWinDomain()

	domainUsersMatch = common.isDomainUsersCn(dn)
	lehrerMatch = common.isLehrerCn(dn)
	schuelerMatch = common.isSchuelerCn(dn)

	groupCn = common.getGroupCn(dn)

	shares = {}
	share = None

	if domainUsersMatch:
		shareName = "Marktplatz"
		domainUsersOuRegex = r'^cn=Domain\ Users\ '
		ou = re.sub(domainUsersOuRegex, '', domainUsersMatch.group())
		mountName = "Marktplatz {}".format(ou)
		base = common.getBase()
		share = lo.get("cn=Marktplatz,cn=shares,ou={},{}".format(ou, base))
		if share:
			shares[mountName] = [(share, shareName)]
		if ucr.is_true('nextcloud-samba-group-share-config/ignoreMarktplatz'):
			ud.debug(ud.LISTENER, ud.WARN, "UCR var nextcloud-samba-group-share-config/ignoreMarktplatz is true: Not creating mount for share {}".format(mountName))
			return
	elif lehrerMatch or schuelerMatch:
		lehrerOuRegex = '^cn=lehrer-'
		schuelerOuRegex = '^cn=schueler-'
		if lehrerMatch:
			ou = re.sub(lehrerOuRegex, '', lehrerMatch.group())
			mountName = "Lehrer {}".format(ou)
			shareName = "lehrer-{}".format(ou)
		elif schuelerMatch:
			ou = re.sub(schuelerOuRegex, '', schuelerMatch.group())
			groupCn = 'lehrer-{}'.format(ou)
			mountName = "Schueler {}".format(ou)
			shareName = "schueler-{}".format(ou)
		base = common.getBase()
		share = lo.get("cn={},cn=shares,ou={},{}".format(shareName, ou, base))
		if ucr.is_true('nextcloud-samba-group-share-config/configureRoleshares'):
			if share:
				shares[mountName] = [(share, shareName)]
		else:
			ud.debug(ud.LISTENER, ud.WARN, "UCR var nextcloud-samba-group-share-config/configureRoleshares is not true: Not creating mount for share {}".format(mountName))

		if ucr.is_true('nextcloud-samba-group-share-config/configureLehreraustausch'):
			shareName = "Lehrer-Austausch"
			mountName = "Lehrer-Austausch {}".format(ou)
			share = lo.get("cn={},cn=shares,ou={},{}".format(shareName, ou, base))
			if share:
				shares[mountName] = [(share, shareName)]
	else:
		if command != 'd':
			share = common.getShareObj(lo, groupCn)
			if share is False:
				return
		shareName = groupCn
		mountName = groupCn
		if share:
			shares[mountName] = [(share, shareName)]

	if command == 'd':
		mountId = common.getMountId(mountName)
		common.deleteMount(mountId)
		return

	if shares:
		for mountName in shares:
			# Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
			#ud.debug(ud.LISTENER, ud.WARN, "Making sure files_external app is enabled")
			#enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
			#subprocess.call(enableAppCmd, shell=True)
			share = shares[mountName][0][0]
			shareName = shares[mountName][0][1]
			shareHost = common.getShareHost(share)
			mountId = common.getMountId(mountName)
			if not mountId:
				ud.debug(ud.LISTENER, ud.WARN, "Creating new mount {} ...".format(mountName))
				mountId = common.createMount(mountName)
			if not mountId:
				ud.debug(ud.LISTENER, ud.WARN, "New mount {} could not be created. Check if Nextcloud container is running or nextcloud-samba-common/occ_path is set correctly in UCR if you are not using an App Center Nextcloud...".format(mountName))
				continue

			common.setMountConfig(mountId, shareHost, shareName, windomain, groupCn)
	else:
		ud.debug(ud.LISTENER, ud.WARN, "Nothing to do: no shares were found: {}".format(mountName))
