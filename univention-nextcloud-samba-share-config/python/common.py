#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# common class
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

import pipes
import subprocess
import time
from typing import List

import univention.debug as ud
from ldap.filter import filter_format
from ldap.dn import str2dn
from univention.config_registry import ConfigRegistry
import listener

ucr = ConfigRegistry()
ucr.load()

occ_path_ucr = ucr.get("nextcloud-samba-common/occ_path")
if occ_path_ucr:
    useSSH = True
    ud.debug(ud.LISTENER, ud.WARN, "External Nextcloud".format())
    occ_cmd: List = ["sudo", "-u", "www-data", "php", occ_path_ucr]
    ud.debug(ud.LISTENER, ud.WARN, "occ Command: {}".format(occ_cmd))
    remoteUser = ucr.get("nextcloud-samba-share-config/remoteUser")
    remotePwFile = ucr.get("nextcloud-samba-share-config/remotePwFile")
    remoteHost = ucr.get("nextcloud-samba-share-config/remoteHost")
    applicableGroup = ucr.get("nextcloud-samba-share-config/nextcloudGroup")
    nc_admin = ucr.get("nextcloud-samba-share-config/nc_admin")
else:
    useSSH = False
    ud.debug(ud.LISTENER, ud.WARN, "Univention Nextcloud App")
    occ_cmd: List = ["univention-app", "shell", "nextcloud", "sudo", "-u", "www-data", "/var/www/html/occ"]
    ud.debug(ud.LISTENER, ud.WARN, "occ Command: {}".format(occ_cmd))


def isDomainUsersCn(dn):
    domain_users_dn = str2dn(dn)
    if domain_users_dn[0][0][1].startswith("Domain Users "):
        return domain_users_dn
    return None


# The prefix 'schueler-" assumes ucsschool/ldap/default/groupprefix/students to be default
def isSchuelerCn(dn):
    schueler_users_dn = str2dn(dn)
    if schueler_users_dn[0][0][1].startswith("schueler-"):
        return schueler_users_dn
    return None


# The prefix 'lehrer-" assumes ucsschool/ldap/default/groupprefix/teachers to be default
def isLehrerCn(dn):
    lehrer_users_dn = str2dn(dn)
    if lehrer_users_dn[0][0][1].startswith("lehrer-"):
        return lehrer_users_dn
    return None


def getGroupCn(dn):
    return str2dn(dn)[0][0][1]


def getShareObj(lo, cn):
    timeout = time.time() + 30
    shareObj = lo.search(
        filter_format("(&(objectClass=univentionShareSamba)(cn=%s))", (cn,))
    )
    while not shareObj:
        ud.debug(
            ud.LISTENER,
            ud.WARN,
            "Share {} does not yet exist in LDAP, waiting until it exists with 30s timeout".format(
                cn
            ),
        )
        shareObj = lo.search(
            filter_format("(&(objectClass=univentionShareSamba)(cn=%s))", (cn,))
        )
        time.sleep(1)
        if time.time() > timeout:
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "Share {} does not exist in LDAP after 30s timeout. Share mount won't be created".format(
                    cn
                ),
            )
            return False
    return shareObj[0][1]


def getShareHost(share):
    return b"".join(share["univentionShareHost"]).decode("UTF-8")


def getShareSambaName(share):
    return b"".join(share["univentionShareSambaName"]).decode("UTF-8")


def getBase():
    return ucr.get("ldap/base")


def getDomain():
    return ucr.get("domainname")


def getWinDomain():
    return ucr.get("windows/domain")


# Maybe we can use files_external:export here, which gives us a JSON on stdout
def getMountId(mountName):
    if useSSH:
        getMountIdCmd: List = \
            getSshCommand(remotePwFile, remoteUser, remoteHost) + \
            occ_cmd + ["files_external:list"]
    else:
        getMountIdCmd: List = \
            occ_cmd + ["files_external:list"]

    listener.setuid(0)
    try:
        mountId: bytes = subprocess.check_output(getMountIdCmd)
    finally:
        listener.unsetuid()

    """
    The command files_external:list returns a table like this (as byte string):
    +----------+-------------+---------+---------------------+------------------------------+---------+------------------+-------------------+
    | Mount ID | Mount Point | Storage | Authentication Type | Configuration                | Options | Applicable Users | Applicable Groups |
    +----------+-------------+---------+---------------------+------------------------------+---------+------------------+-------------------+
    | 22       | /zzz        | Local   | None                | datadir: "\/home\/phil\/zzz" |         | All              |                   |
    +----------+-------------+---------+---------------------+------------------------------+---------+------------------+-------------------+

    We want to find the line with the required Mount point and extract the ID
    """
    for line in mountId.decode("UTF-8").split("\n"):
        if mountName in line:
            mountId: str = line.split("| ")[1]

    if isinstance(mountId, str) and mountId:
        ud.debug(
            ud.LISTENER,
            ud.WARN,
            "Mount for {} is already configured with ID {}. Re-setting config if command is not delete...".format(
                mountName, mountId
            ),
        )
    else:
        ud.debug(
            ud.LISTENER, ud.WARN, "No mount for {} configured yet.".format(mountName)
        )
        mountId = False
    return mountId


def getSshCommand(remotePwFile: str, remoteUser: str, remoteHost: str) -> List:
    return ["univention-ssh", "--no-split", remotePwFile, remoteUser + "@" + remoteHost]


def createMount(mountName):
    if useSSH:
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        createMountCmd: List = sshCommand + \
            occ_cmd + ["files_external:create"] + \
            [pipes.quote(mountName)] + ["smb", "password::sessioncredentials"]
    else:
        createMountCmd: List = occ_cmd + ["files_external:create"] + \
            [mountName] + ["smb", "password::sessioncredentials"]

    listener.setuid(0)
    try:
        subprocess.call(createMountCmd)
    finally:
        listener.unsetuid()

    mountId = getMountId(mountName)
    return mountId


def deleteMount(mountId):
    if useSSH:
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        deleteMountCmd: List = sshCommand + \
            occ_cmd + ["files_external:delete", "--yes", mountId]
    else:
        deleteMountCmd: List = \
            occ_cmd + ["files_external:delete", "--yes", mountId]

    ud.debug(ud.LISTENER, ud.WARN, "Deleting mount with ID {}".format(mountId))

    listener.setuid(0)
    try:
        subprocess.call(deleteMountCmd)
    finally:
        listener.unsetuid()

    ud.debug(ud.LISTENER, ud.WARN, "Deleted mount with ID {}".format(mountId))


def setMountConfig(
    mountId, shareHost, shareName, windomain, groupCn, applicableGroup=None
):
    if useSSH:
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        addHostCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", mountId, "host", shareHost]
        addShareRootCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", mountId, "share", "/"]
        # Handle Nextcloud variables so it doesnt show up with '' in the share name
        if shareName == "$user":
            share_root_value = shareName
        else:
            share_root_value = pipes.quote(shareName)
        addShareNameCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", mountId, "root", share_root_value]
        addShareDomainCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", mountId, "domain",
             windomain]
        checkApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["group:adduser", pipes.quote(groupCn), nc_admin]
        checkLdapApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["ldap:search", "--group", pipes.quote(groupCn)]
        cleanupApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["group:removeuser", pipes.quote(groupCn), nc_admin]
        addApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["files_external:applicable", "--add-group", pipes.quote(groupCn), mountId]
        addNcAdminApplicableUserCmd: List = sshCommand + occ_cmd + \
            ["files_external:applicable", "--add-user", nc_admin, mountId]
    else:
        addHostCmd: List = occ_cmd + \
            ["files_external:config", mountId, "host", shareHost]
        addShareRootCmd: List = occ_cmd + \
            ["files_external:config", mountId, "share", "/"]
        # Handle Nextcloud variables so it doesnt show up with '' in the share name
        if shareName == "$user":
            share_root_value = shareName
        else:
            share_root_value = pipes.quote(shareName)
        addShareNameCmd: List = occ_cmd + \
            ["files_external:config", mountId, "root", share_root_value]
        addShareDomainCmd: List = occ_cmd + \
            ["files_external:config", mountId, "domain",
             windomain]
        checkApplicableGroupCmd: List = occ_cmd + \
            ["group:adduser", groupCn, "Administrator"]
        checkLdapApplicableGroupCmd: List = occ_cmd + \
            ["ldap:search", "--group", groupCn]
        cleanupApplicableGroupCmd: List = occ_cmd + \
            ["group:removeuser", groupCn, "Administrator"]
        addApplicableGroupCmd: List = occ_cmd + \
            ["files_external:applicable", "--add-group", groupCn, mountId]
        addNcAdminApplicableUserCmd: List = occ_cmd + \
            ["files_external:applicable", "--add-user", "Administrator", mountId]

    listener.setuid(0)
    try:
        subprocess.call(addHostCmd)
        subprocess.call(addShareRootCmd)
        subprocess.call(addShareNameCmd)
        subprocess.call(addShareDomainCmd)
        ret = subprocess.call(checkApplicableGroupCmd)
        timeout = time.time() + 600
        while ret != 0:
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "Group {} does not yet exist in Nextcloud, waiting until it exists with 600s timeout".format(
                    groupCn
                ),
            )
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "Performing LDAP search via occ for group {} to make Nextcloud aware of it".format(
                    groupCn
                ),
            )
            subprocess.call(checkLdapApplicableGroupCmd)
            ret = subprocess.call(checkApplicableGroupCmd)
            if time.time() > timeout:
                break
        if ret == 0:
            subprocess.call(addApplicableGroupCmd)
            subprocess.call(cleanupApplicableGroupCmd)
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "Finished share mount configuration for share {}".format(groupCn),
            )
        else:
            ud.debug(
                ud.LISTENER,
                ud.WARN,
                "Group {} for share {} was not found in Nextcloud. Check ldapBaseGroups in Nextcloud ldap config. Adding nc_admin as applicable user to hide share mount from all other users.".format(
                    groupCn, shareName
                ),
            )
            subprocess.call(addNcAdminApplicableUserCmd)
    finally:
        listener.unsetuid()
