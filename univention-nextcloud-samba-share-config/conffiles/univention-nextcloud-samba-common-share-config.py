#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# UCR hook
#
# Copyright 2018-2025 Univention GmbH
#
# https://www.univention.de/
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

common_shares = ucr.get("ucsschool/userlogon/commonshares")
if not common_shares:
    sys.exit(1)

common_shares = common_shares.split(",")
if "Marktplatz" in common_shares:
    common_shares.remove("Marktplatz")
windomain = common.getWinDomain()
remote_user = ucr.get("nextcloud-samba-share-config/remoteUser")
remote_pw_file = ucr.get("nextcloud-samba-share-config/remotePwFile")
remote_host = ucr.get("nextcloud-samba-share-config/remoteHost")
applicable_group = ucr.get("nextcloud-samba-share-config/nextcloudGroup")
nc_admin = ucr.get("nextcloud-samba-share-config/nc_admin")

for share_cn in common_shares:
    # share = lo.search("(&(objectClass=univentionShareSamba)(cn={}))".format(share_cn))
    share = common.getShareObj(lo, share_cn)
    if share is False:
        break

    if share:
        # Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
        # ud.debug(ud.LISTENER, ud.WARN, "Making sure files_external app is enabled")
        # enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
        # subprocess.call(enableAppCmd, shell=True)

        # share_host = ''.join(share[0][1]['univentionShareHost'])
        # share_samba_name = ''.join(share[0][1]['univentionShareSambaName'])
        share_host = common.getShareHost(share)
        share_samba_name = common.getShareSambaName(share)
        mount_name = share_samba_name
        mount_id = common.getMountId(mount_name)
        if not mount_id:
            print("Creating new mount {} ...".format(mount_name))
            mount_id = common.createMount(mount_name)

        common.setMountConfig(
            mount_id, share_host, share_samba_name, windomain, applicable_group
        )
    else:
        print("Nothing to do: no share was found for CN {}".format(share_cn))
