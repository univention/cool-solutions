#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
"""user group sync source
    udm hook"""
#
# Copyright 2019 Univention GmbH
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

from univention.admin.hook import simpleHook
import univention.debug as ud
import subprocess

class ResyncListenerModuleIfAttributeIsSet(simpleHook):
    type = 'ResyncListenerModuleIfAttributeIsSet'

    def hook_ldap_post_modify(self, obj):
        """Resync listener module univention_user_group_sync_source_generate if univentionUserGroupSyncEnabled is set for an object."""
        ext_attr_name = 'univentionUserGroupSyncEnabled'
        class_name = 'univentionUserGroupSync'
        listener_module = 'univention_user_group_sync_source_generate'

        if obj.info.get(ext_attr_name) == 'TRUE' and obj.oldinfo.get(ext_attr_name) == 'FALSE':
            ud.debug(ud.ADMIN, ud.WARN, "Resyncing listener module {} because univentionUserGroupSyncEnabled was set".format(listener_module))
            subprocess.call(['univention-directory-listener-ctrl', 'resync', listener_module])
