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
# <https://www.gnu.org/licenses/>.

from typing import List

import ldap.dn
import univention.admin.uldap
import univention.debug as ud
import univention.nextcloud_samba.common as common
from univention.config_registry import ConfigRegistry
import listener

ucr = ConfigRegistry()
ucr.load()

name = "nextcloud-samba-group-share-config"
description = "Configure access to Samba shares in Nextcloud"
filter = "(&(objectClass=nextcloudGroup)(nextcloudEnabled=1))"
attributes = []  # type: List
modrdn = "1"


def handler(dn, new, old, command=""):
    ud.debug(ud.LISTENER, ud.WARN, "DN {}".format(dn))
    listener.setuid(0)
    try:
        lo, po = univention.admin.uldap.getMachineConnection()
    finally:
        listener.unsetuid()

    windomain = common.getWinDomain()

    domain_users_match = common.isDomainUsersCn(dn)
    lehrer_match = common.isLehrerCn(dn)
    schueler_match = common.isSchuelerCn(dn)

    group_cn = common.getGroupCn(dn)

    shares = {}
    share = None

    if domain_users_match:
        share_name = "Marktplatz"
        ou = domain_users_match[2][0][1]
        mount_name = "Marktplatz {}".format(ou)
        base = common.getBase()
        share = lo.get("cn=Marktplatz,cn=shares,ou={},{}".format(ldap.dn.escape_dn_chars(ou), base))
        if share:
            shares[mount_name] = [(share, share_name)]
        if ucr.is_true("nextcloud-samba-group-share-config/ignoreMarktplatz"):
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "UCR var nextcloud-samba-group-share-config/ignoreMarktplatz is true: Not creating mount for share {}".format(
                    mount_name
                ),
            )
            return
    elif lehrer_match or schueler_match:
        if lehrer_match:
            ou = lehrer_match[2][0][1]
            mount_name = "Lehrer {}".format(ou)
            share_name = "lehrer-{}".format(ou)
        elif schueler_match:
            ou = schueler_match[2][0][1]
            group_cn = "lehrer-{}".format(ou)
            mount_name = "Schueler {}".format(ou)
            share_name = "schueler-{}".format(ou)
        base = common.getBase()
        share = lo.get("cn={},cn=shares,ou={},{}".format(ldap.dn.escape_dn_chars(share_name), ldap.dn.escape_dn_chars(ou), base))
        if ucr.is_true("nextcloud-samba-group-share-config/configureRoleshares"):
            if share:
                shares[mount_name] = [(share, share_name)]
        else:
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "UCR var nextcloud-samba-group-share-config/configureRoleshares is not true: Not creating mount for share {}".format(
                    mount_name
                ),
            )

        if ucr.is_true("nextcloud-samba-group-share-config/configureLehreraustausch"):
            share_name = "Lehrer-Austausch"
            mount_name = "Lehrer-Austausch {}".format(ou)
            share = lo.get("cn={},cn=shares,ou={},{}".format(ldap.dn.escape_dn_chars(share_name), ldap.dn.escape_dn_chars(ou), base))
            if share:
                shares[mount_name] = [(share, share_name)]
    else:
        if command != "d":
            share = common.getShareObj(lo, group_cn)
            if share is False:
                return
        share_name = group_cn
        mount_name = group_cn
        if share:
            shares[mount_name] = [(share, share_name)]

    if command == "d":
        mount_id = common.getMountId(mount_name)
        common.deleteMount(mount_id)
        return

    if shares:
        for mount_name in shares:
            # Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
            # ud.debug(ud.LISTENER, ud.WARN, "Making sure files_external app is enabled")
            # enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
            # subprocess.call(enableAppCmd, shell=True)
            share = shares[mount_name][0][0]
            share_name = shares[mount_name][0][1]
            share_host = common.getShareHost(share)
            mount_id = common.getMountId(mount_name)
            if not mount_id:
                ud.debug(
                    ud.LISTENER, ud.WARN, "Creating new mount {} ...".format(mount_name)
                )
                mount_id = common.createMount(mount_name)
            if not mount_id:
                ud.debug(
                    ud.LISTENER,
                    ud.WARN,
                    "New mount {} could not be created. Check if Nextcloud container is running or nextcloud-samba-common/occ_path is set correctly in UCR if you are not using an App Center Nextcloud...".format(
                        mount_name
                    ),
                )
                continue

            common.setMountConfig(mount_id, share_host, share_name, windomain, group_cn)
    else:
        ud.debug(
            ud.LISTENER,
            ud.WARN,
            "Nothing to do: no shares were found: {}".format(mount_name),
        )
