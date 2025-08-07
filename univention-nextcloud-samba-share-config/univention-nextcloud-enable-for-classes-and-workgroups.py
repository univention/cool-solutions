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

import univention.admin.uldap
import univention.debug as ud
import listener

name = "nextcloud-enable-for-classes-and-workgroups"
description = "Enable Nextcloud for all classes, workgroups, Domain Users <ou>, lehrer-<ou> and schueler-<ou>"
filter = "(|\
            (cn=Domain Users *)\
            (cn=lehrer-*)\
            (cn=schueler-*)\
            (ucsschoolRole=school_class:school:*)\
            (ucsschoolRole=workgroup:school:*)\
        )"
attributes = []  # type: List
modrdn = "1"


def handler(dn, new, old, command=''):
    if command == "d":
        return
    ud.debug(ud.LISTENER, ud.WARN, "DN {}".format(dn))
    listener.setuid(0)
    try:
        lo, po = univention.admin.uldap.getAdminConnection()
    finally:
        listener.unsetuid()

    # Enable group for nextcloud
    nextcloudEnabled = lo.getAttr(dn, "nextcloudEnabled")
    objectClasses = lo.getAttr(dn, "objectClass")

    # Check what needs to be added
    modlist = []

    # Add objectClass if not present
    if b"nextcloudGroup" not in objectClasses:
        modlist.append(("objectClass", b"", b"nextcloudGroup"))

    # Add nextcloudEnabled if not present or not set to 1
    if not nextcloudEnabled or nextcloudEnabled[0] != b"1":
        if nextcloudEnabled:
            # Replace existing value
            modlist.append(("nextcloudEnabled", nextcloudEnabled[0], b"1"))
        else:
            # Add new attribute
            modlist.append(("nextcloudEnabled", b"", b"1"))

    # Only modify if thers something to change
    if modlist:
        lo.modify(dn, modlist)
        ud.debug(ud.LISTENER, ud.WARN, "Enabled Nextcloud for {}".format(dn))
    else:
        ud.debug(ud.LISTENER, ud.INFO, "Nextcloud already enabled for {}".format(dn))
