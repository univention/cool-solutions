#!/usr/bin/env python3

# Univention Nextcloud Samba share configuration
# listener module

# SPDX-FileCopyrightText: 2018-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only <https://www.gnu.org/licenses/>.

from typing import List, Dict, Optional
from univention.listener import ListenerModuleHandler
from univention.udm import UDM
from univention.udm.exceptions import NoObject, ModifyError


class NextcloudEnableForClassesAndWorkgroups(ListenerModuleHandler):
    """Enable Classes and Workgroups for Nextcloud"""

    class Configuration:
        name = 'nextcloud-enable-for-classes-and-workgroups'
        description = 'Enable Nextcloud for all classes, workgroups, Domain Users <ou>, lehrer-<ou> and schueler-<ou>'
        ldap_filter = '(|(cn=Domain Users *)(cn=lehrer-*)(cn=schueler-*)(ucsschoolRole=school_class:school:*)(ucsschoolRole=workgroup:school:*))'
        attributes = []

    def ensure_nextcloud_enabled(self, dn: str) -> None:
        """Set nextcloudEnabled on group if not set before."""
        with self.as_root():
            # Enable group for nextcloud
            group_mod = UDM.admin().version(3).get('groups/group')
            try:
                group = group_mod.get(dn)
                if group.props.nextcloudEnabled != '1':
                    group.props.nextcloudEnabled = '1'
                    group.save()
                    self.logger.warning('Enabled Nextcloud for %s', dn)
                else:
                    self.logger.info('Group already enabled: %s', dn)
            except NoObject:
                self.logger.warning('Group not found %s', dn)
            except ModifyError as exc:
                self.logger.error('Failed to modify group %s: %s', dn, exc)

    def create(self, dn: str, new: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a create or listener initialize."""
        self.logger.info('create group with dn: %r', dn)
        self.ensure_nextcloud_enabled(dn)

    def modify(
        self,
        dn: str,
        old: Dict[str, List[bytes]],
        new: Dict[str, List[bytes]],
        old_dn: Optional[str],
    ) -> None:
        """Called when the change on the object was a modify."""
        self.logger.info('modify group with dn: %r', dn)
        self.ensure_nextcloud_enabled(dn)

    def remove(self, dn: str, old: Dict[str, List[bytes]]) -> None:
        """Called when the change on the object was a remove."""
        return
