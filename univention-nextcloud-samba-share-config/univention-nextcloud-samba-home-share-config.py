#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2018-2026 Univention GmbH
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
        config = self.get_config(dn)
        if not config:
            return
        mount_id, share_host, share_name, windomain, group_cn, mount_name = config
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
        config = self.get_config(dn)
        if not config:
            return
        mount_id, share_host, share_name, windomain, group_cn, mount_name = config
        common.setMountConfig(mount_id, share_host, share_name, windomain, group_cn)

    def remove(self, dn: str, old: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a remove."""
        config = self.get_config(dn)
        if not config:
            return
        mount_id, share_host, share_name, windomain, group_cn, mount_name = config
        mount_id = common.getMountId(mount_name)
        common.deleteMount(mount_id)

    def get_config(self, dn: str):
        windomain = common.getWinDomain()
        domain = common.getDomain()
        base = common.getBase()

        domain_users_match = common.isDomainUsersCn(dn)
        # The ldap_filter also matches a plain "Domain Users" group (no OU
        # suffix); isDomainUsersCn requires the trailing space, so guard against
        # None before relying on the OU component of the DN.
        if not domain_users_match:
            self.logger.info('%r is not a "Domain Users <OU>" group, skipping', dn)
            return None

        group_cn = common.getGroupCn(dn)
        ou = domain_users_match[2][0][1]
        mount_name = f"Home {ou}"
        share_name = "$user"
        with self.as_root():
            ou_object = self.lo.get(f"ou={ldap.dn.escape_dn_chars(ou)},{base}")

        # The listener fires for every "Domain Users <OU>" group in the domain.
        # On a school server that only holds its own OU, the home share file
        # server of a foreign OU cannot be resolved. Skip instead of crashing,
        # which used to spam the listener log with the full old/new dumps.
        file_server = ou_object.get("ucsschoolHomeShareFileServer")
        if not file_server:
            self.logger.info('No home share file server for OU %r (foreign OU?), skipping %r', ou, dn)
            return None
        share_host_dn = file_server[0].decode("UTF-8")

        with self.as_root():
            host_object = self.lo.get(share_host_dn)
        if not host_object.get("cn"):
            self.logger.info('Home share file server %r not resolvable here, skipping %r', share_host_dn, dn)
            return None
        share_host_cn = host_object["cn"][0].decode("UTF-8")

        share_host = f"{share_host_cn}.{domain}"

        mount_id = common.getMountId(mount_name)
        if not mount_id:
            self.logger.warning('Creating new mount %s ...', mount_name)
            mount_id = common.createMount(mount_name)

        return mount_id, share_host, share_name, windomain, group_cn, mount_name
