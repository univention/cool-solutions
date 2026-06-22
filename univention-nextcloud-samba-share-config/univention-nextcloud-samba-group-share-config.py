#!/usr/bin/env python3

# Univention Nextcloud Samba share configuration
# listener module

# SPDX-FileCopyrightText: 2018-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only <https://www.gnu.org/licenses/>.

import contextlib
from typing import Dict, List, Optional  # noqa: F811

import ldap.dn
from univention.config_registry import ConfigRegistry
from univention.listener import ListenerModuleHandler
from univention.nextcloud_samba import common

ucr = ConfigRegistry()
ucr.load()


class NextcloudSambaGroupShareConfig(ListenerModuleHandler):
    """Configure access to Samba group shares in Nextcloud"""

    shares = {}
    mount_name = ""
    group_cn = ""

    class Configuration:
        name = "nextcloud-samba-group-share-config"
        description = "Configure access to Samba shares in Nextcloud"
        ldap_filter = "(&(objectClass=univentionGroup)(objectClass=nextcloudGroup)(nextcloudEnabled=1))"
        attributes = []

    def create(self, dn: str, new: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a create or listener initialize."""
        self.logger.info('create group with dn: %r', dn)
        self.run(dn)

    def modify(
        self,
        dn: str,
        old: Dict[str, List[bytes]],
        new: Dict[str, List[bytes]],
        old_dn: Optional[str],
    ) -> None:
        """Called when the change on the object was a modify."""
        self.logger.info('modify group with dn: %r', dn)
        self.run(dn)

    def remove(self, dn: str, old: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a remove."""
        self.run(dn, True)

    def get_common_settings(self, dn: str):
        """Return settings from Nextcloud."""
        self.group_cn = common.getGroupCn(dn)
        domain_users_match = common.isDomainUsersCn(dn)
        lehrer_match = common.isLehrerCn(dn)
        schueler_match = common.isSchuelerCn(dn)
        base = common.getBase()
        windomain = common.getWinDomain()
        return domain_users_match, lehrer_match, schueler_match, base, windomain

    def run(self, dn: str, remove: bool = False) -> None:
        """Do it"""
        # Stop leaking mounts between different group events
        self.shares = {}
        self.mount_name = ""

        domain_users_match, lehrer_match, schueler_match, base, windomain = self.get_common_settings(dn)

        if domain_users_match:
            self.create_share_marktplatz(domain_users_match, base)
        elif lehrer_match or schueler_match:
            self.create_role_shares(lehrer_match, schueler_match, base)
        else:
            self.handle_non_lehrer_or_schueler(remove)

        if remove:
            mount_id = common.getMountId(self.mount_name)
            common.deleteMount(mount_id)
            return

        if self.shares:
            for mount_name in self.shares:
                share = self.shares[mount_name][0][0]
                share_name = self.shares[mount_name][0][1]
                share_host = common.getShareHost(share)
                mount_id = common.getMountId(mount_name)
                if not mount_id:
                    self.logger.warning("Creating new mount %s ...", mount_name)
                    mount_id = common.createMount(mount_name)
                if not mount_id:
                    self.logger.warning("New mount %s could not be created. Check if Nextcloud container is running or nextcloud-samba-common/occ_path is set correctly in UCR if you are not using an App Center Nextcloud...", mount_name)
                    continue

                common.setMountConfig(mount_id, share_host, share_name, windomain, self.group_cn)
        else:
            self.logger.warning("Nothing to do: no shares were found.")

    def create_role_shares(self, lehrer_match, schueler_match, base: str) -> None:
        """Create shares for lehrer and schueler."""
        ou = ""
        share_name = ""
        if lehrer_match:
            ou = lehrer_match[2][0][1]
            self.mount_name = f"Lehrer {ou}"
            share_name = f"lehrer-{ou.lower()}"
        elif schueler_match:
            ou = schueler_match[2][0][1]
            self.group_cn = f"lehrer-{ou.lower()}"
            self.mount_name = f"Schueler {ou}"
            share_name = f"schueler-{ou.lower()}"
        share = self.lo.get(f"cn={ldap.dn.escape_dn_chars(share_name)},cn=shares,ou={ldap.dn.escape_dn_chars(ou)},{base}")
        if ucr.is_true("nextcloud-samba-group-share-config/configureRoleshares"):
            if share:
                self.shares[self.mount_name] = [(share, share_name)]
        else:
            self.logger.warning(
                "UCR var nextcloud-samba-group-share-config/configureRoleshares is not true: Not creating mount for share %s", self.mount_name,
            )

        if ucr.is_true("nextcloud-samba-group-share-config/configureLehreraustausch"):
            share_name = "Lehrer-Austausch"
            self.mount_name = f"Lehrer-Austausch {ou}"
            # use the provided base parameter
            share = self.lo.get(f"cn={ldap.dn.escape_dn_chars(share_name)},cn=shares,ou={ldap.dn.escape_dn_chars(ou)},{base}")
            if share:
                self.shares[self.mount_name] = [(share, share_name)]

    def create_share_marktplatz(self, match, base: str) -> None:
        """Create Markplatz share for domain users group."""
        share_name = "Marktplatz"
        ou = match[2][0][1]
        self.mount_name = f"Marktplatz {ou}"
        # respect ignore flag before adding any mount
        if ucr.is_true("nextcloud-samba-group-share-config/ignoreMarktplatz"):
            self.logger.warning("UCR var nextcloud-samba-group-share-config/ignoreMarktplatz is true: Not creating mount for share %s", self.mount_name)
            return
        share = self.lo.get(f"cn=Marktplatz,cn=shares,ou={ldap.dn.escape_dn_chars(ou)},{base}")
        if share:
            self.shares[self.mount_name] = [(share, share_name)]

    def handle_non_lehrer_or_schueler(self, remove: bool = False) -> None:
        """If none of schueler/leherer/domain users matches"""
        if not remove:
            share = common.getShareObj(self.lo, self.group_cn)
            if share is False:
                return
        share_name = self.group_cn
        self.mount_name = self.group_cn
        with contextlib.suppress(NameError):
            if share:
                self.shares[self.mount_name] = [(share, share_name)]
