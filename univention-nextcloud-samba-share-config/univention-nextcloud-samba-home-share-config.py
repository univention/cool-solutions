#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2018-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only <https://www.gnu.org/licenses/>.

from typing import Dict, List, Optional

import ldap.dn
import univention.nextcloud_samba.common as common
from univention.listener import ListenerModuleHandler


class NextcloudSambaHomeShareConfig(ListenerModuleHandler):
    """Configure access to Samba home shares in Nextcloud"""

    class Configuration:
        name = "nextcloud-samba-home-share-config"
        description = 'Configure access to Samba home shares in Nextcloud'
        ldap_filter = '(&(objectClass=nextcloudGroup)(nextcloudEnabled=1)(cn=Domain Users*))'
        attributes = []

    def create(self, dn: str, new: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a create or listener initialize."""
        self.logger.info('create group with dn: %r', dn)
        mount_id, share_host, share_name, windomain, group_cn, mount_name = self.get_config(dn)
        common.setMountConfig(mount_id, share_host, share_name, windomain, group_cn)

    def modify(
        self,
        dn: str,
        old: Dict[str, List[bytes]],
        new: Dict[str, List[bytes]],
        old_dn: Optional[str],
    ) -> None:
        """Called when the change on the object was a modify."""
        self.logger.info('modify group with dn: %r', dn)
        mount_id, share_host, share_name, windomain, group_cn, mount_name = self.get_config(dn)
        common.setMountConfig(mount_id, share_host, share_name, windomain, group_cn)

    def remove(self, dn: str, old: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a remove."""
        mount_id, share_host, share_name, windomain, group_cn, mount_name = self.get_config(dn)
        mount_id = common.getMountId(mount_name)
        common.deleteMount(mount_id)

    def get_config(self, dn: str):
        windomain = common.getWinDomain()
        domain = common.getDomain()
        base = common.getBase()

        domain_users_match = common.isDomainUsersCn(dn)

        group_cn = common.getGroupCn(dn)
        ou = domain_users_match[2][0][1]
        mount_name = f"Home {ou}"
        share_name = "$user"
        with self.as_root():
            ou_object = self.lo.get(f"ou={ldap.dn.escape_dn_chars(ou)},{base}")
        share_host_dn = ou_object["ucsschoolHomeShareFileServer"][0].decode("UTF-8")

        with self.as_root():
            share_host_cn = self.lo.get(share_host_dn)["cn"][0].decode("UTF-8")

        share_host = f"{share_host_cn}.{domain}"

        mount_id = common.getMountId(mount_name)
        if not mount_id:
            self.logger.warning('Creating new mount %s ...', mount_name)
            mount_id = common.createMount(mount_name)

        return mount_id, share_host, share_name, windomain, group_cn, mount_name
