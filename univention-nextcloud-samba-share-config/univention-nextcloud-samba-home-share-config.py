#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# listener module
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

from typing import List

import ldap.dn
import univention.admin.uldap
import univention.debug as ud
import univention.nextcloud_samba.common as common
import listener

name = "nextcloud-samba-home-share-config"
description = "Configure access to Samba home shares in Nextcloud"
filter = "(&(objectClass=univentionGroup)(objectClass=nextcloudGroup)(nextcloudEnabled=1)(cn=Domain Users*))"
attributes = []  # type: List
modrdn = "1"


def handler(dn, new, old, command=""):
    ud.debug(ud.LISTENER, ud.WARN, "DN {}".format(dn))

    # Skip Builtin groups
    if ",cn=Builtin," in dn:
        ud.debug(ud.LISTENER, ud.INFO, "Skipping Builtin group: {}".format(dn))
        return

    listener.setuid(0)
    try:
        lo, po = univention.admin.uldap.getMachineConnection()
    finally:
        listener.unsetuid()

    windomain = common.getWinDomain()
    domain = common.getDomain()
    base = common.getBase()

    domain_users_match = common.isDomainUsersCn(dn)

    group_cn = common.getGroupCn(dn)
    ou = domain_users_match[2][0][1]
    mount_name = "Home {}".format(ou)
    share_name = "$user"

    ou_object = lo.get("ou={},{}".format(ldap.dn.escape_dn_chars(ou), base))
    share_host_dn = ou_object["ucsschoolHomeShareFileServer"][0].decode("UTF-8")
    share_host_cn = lo.get(share_host_dn)["cn"][0].decode("UTF-8")

    share_host = "{}.{}".format(share_host_cn, domain)

    mount_id = common.getMountId(mount_name)
    if not mount_id:
        ud.debug(ud.LISTENER, ud.WARN, "Creating new mount {} ...".format(mount_name))
        mount_id = common.createMount(mount_name)

    if command == "d":
        mount_id = common.getMountId(mount_name)
        common.deleteMount(mount_id)
        return

    common.setMountConfig(mount_id, share_host, share_name, windomain, group_cn)
