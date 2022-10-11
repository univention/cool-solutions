#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# UCR hook
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

import sys

import univention.admin.uldap
import univention.nextcloud_samba.common as common
from univention.config_registry import ConfigRegistry

ucr = ConfigRegistry()
ucr.load()

lo, po = univention.admin.uldap.getMachineConnection(ldap_master=False)

commonShares = ucr.get('ucsschool/userlogon/commonshares')
if not commonShares:
	sys.exit(1)

commonShares = commonShares.split(',')
if 'Marktplatz' in commonShares:
	commonShares.remove('Marktplatz')
windomain = common.getWinDomain()
remoteUser = ucr.get('nextcloud-samba-share-config/remoteUser')
remotePwFile = ucr.get('nextcloud-samba-share-config/remotePwFile')
remoteHost = ucr.get('nextcloud-samba-share-config/remoteHost')
applicableGroup = ucr.get('nextcloud-samba-share-config/nextcloudGroup')

for shareCn in commonShares:
	# share = lo.search("(&(objectClass=univentionShareSamba)(cn={}))".format(shareCn))
	share = common.getShareObj(lo, shareCn)
	if share is False:
		break

	if share:
		# Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
		#ud.debug(ud.LISTENER, ud.WARN, "Making sure files_external app is enabled")
		#enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
		#subprocess.call(enableAppCmd, shell=True)

		#shareHost = ''.join(share[0][1]['univentionShareHost'])
		#shareSambaName = ''.join(share[0][1]['univentionShareSambaName'])
		shareHost = common.getShareHost(share)
		shareSambaName = common.getShareSambaName(share)
		mountName = shareSambaName
		mountId = common.getMountId(mountName)
		if not mountId:
			print("Creating new mount {} ...".format(mountName))
			mountId = common.createMount(mountName)

		common.setMountConfig(mountId, shareHost, shareSambaName, windomain, applicableGroup)
	else:
		print("Nothing to do: no share was found for CN {}".format(shareCn))
