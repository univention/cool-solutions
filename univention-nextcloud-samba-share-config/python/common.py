#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# common class
#
# Copyright 2018-2026 Univention GmbH
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

import logging
import shlex
import subprocess
import time
from typing import List

import listener
from ldap.dn import str2dn
from ldap.filter import filter_format
from univention.config_registry import ucr

# Child of the high-level listener root logger, so messages are forwarded to
# the listener log the same way the modules' self.logger is.
logger = logging.getLogger("listener module.nextcloud_samba.common")

occ_path_ucr = ucr.get("nextcloud-samba-common/occ_path")
if occ_path_ucr:
    useSSH = True
    occ_cmd: List = ["sudo", "-u", "www-data", "php", occ_path_ucr]
    remoteUser = ucr.get("nextcloud-samba-share-config/remoteUser")
    remotePwFile = ucr.get("nextcloud-samba-share-config/remotePwFile")
    remoteHost = ucr.get("nextcloud-samba-share-config/remoteHost")
    applicableGroup = ucr.get("nextcloud-samba-share-config/nextcloudGroup")
    nc_admin = ucr.get("nextcloud-samba-share-config/nc_admin")
else:
    useSSH = False
    occ_cmd: List = ["univention-app", "shell", "nextcloud", "sudo", "-u", "www-data", "/var/www/html/occ"]


# "Domain Users <OU>" is the fixed UCS@school per-OU primary group name and is
# not configurable (unlike the schueler-/lehrer- prefixes below, which follow
# ucsschool/ldap/default/groupprefix/*).
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
        logger.warning(
            "Share %s does not yet exist in LDAP, waiting until it exists with 30s timeout", cn
        )
        shareObj = lo.search(
            filter_format("(&(objectClass=univentionShareSamba)(cn=%s))", (cn,))
        )
        time.sleep(1)
        if time.time() > timeout:
            logger.warning(
                "Share %s does not exist in LDAP after 30s timeout. Share mount won't be created", cn
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
            # strip() removes the table column padding, otherwise the ID would
            # carry trailing spaces into the occ calls
            mountId: str = line.split("| ")[1].strip()

    if isinstance(mountId, str) and mountId:
        logger.info(
            "Mount for %s is already configured with ID %s. Re-setting config if command is not delete...",
            mountName, mountId,
        )
    else:
        logger.info("No mount for %s configured yet.", mountName)
        mountId = False
    return mountId


def getSshCommand(remotePwFile: str, remoteUser: str, remoteHost: str) -> List:
    return ["univention-ssh", "--no-split", remotePwFile, remoteUser + "@" + remoteHost]


def createMount(mountName):
    if useSSH:
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        createMountCmd: List = sshCommand + \
            occ_cmd + ["files_external:create"] + \
            [shlex.quote(mountName)] + ["smb", "password::sessioncredentials"]
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
        # univention-ssh runs the arguments through a remote shell, so every
        # variable value has to be shell-quoted.
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        deleteMountCmd: List = sshCommand + \
            occ_cmd + ["files_external:delete", "--yes", shlex.quote(mountId)]
    else:
        # Local occ runs as an argv list without a shell, so quoting would end
        # up literally in the value. Pass everything as-is.
        deleteMountCmd: List = \
            occ_cmd + ["files_external:delete", "--yes", mountId]

    logger.info("Deleting mount with ID %s", mountId)

    listener.setuid(0)
    try:
        subprocess.call(deleteMountCmd)
    finally:
        listener.unsetuid()

    logger.info("Deleted mount with ID %s", mountId)


def setMountConfig(
    mountId, shareHost, shareName, windomain, groupCn, applicableGroup=None
):
    # Nextcloud's SMB storage takes the share name in the "share" field and a
    # path inside it in "root". Split shareName at the first "/": the leading
    # segment is the SMB share, the remainder (if any) is the subfolder.
    shareField, _, subFolder = shareName.partition("/")
    rootField = "/" + subFolder
    if useSSH:
        # univention-ssh space-joins the arguments and runs them through a
        # remote shell (even with --no-split), so every variable value has to be
        # shell-quoted. Fixed command tokens ("host", "share", ...) do not.
        sshCommand = getSshCommand(remotePwFile, remoteUser, remoteHost)
        addHostCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", shlex.quote(mountId), "host", shlex.quote(shareHost)]
        addShareRootCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", shlex.quote(mountId), "share", shlex.quote(shareField)]
        addShareNameCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", shlex.quote(mountId), "root", shlex.quote(rootField)]
        addShareDomainCmd: List = sshCommand + occ_cmd + \
            ["files_external:config", shlex.quote(mountId), "domain",
             shlex.quote(windomain)]
        checkApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["group:adduser", shlex.quote(groupCn), shlex.quote(nc_admin)]
        checkLdapApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["ldap:search", "--group", shlex.quote(groupCn)]
        cleanupApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["group:removeuser", shlex.quote(groupCn), shlex.quote(nc_admin)]
        addApplicableGroupCmd: List = sshCommand + occ_cmd + \
            ["files_external:applicable", "--add-group", shlex.quote(groupCn), shlex.quote(mountId)]
        addNcAdminApplicableUserCmd: List = sshCommand + occ_cmd + \
            ["files_external:applicable", "--add-user", shlex.quote(nc_admin), shlex.quote(mountId)]
    else:
        # No shell parses the argv list here (subprocess -> docker exec), so
        # quoting would end up literally in the Nextcloud config. Pass every
        # value as-is (host, share root, $user paths, group name, ...).
        addHostCmd: List = occ_cmd + \
            ["files_external:config", mountId, "host", shareHost]
        addShareRootCmd: List = occ_cmd + \
            ["files_external:config", mountId, "share", shareField]
        addShareNameCmd: List = occ_cmd + \
            ["files_external:config", mountId, "root", rootField]
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
            logger.warning(
                "Group %s does not yet exist in Nextcloud, waiting until it exists with 600s timeout",
                groupCn,
            )
            logger.info(
                "Performing LDAP search via occ for group %s to make Nextcloud aware of it",
                groupCn,
            )
            subprocess.call(checkLdapApplicableGroupCmd)
            ret = subprocess.call(checkApplicableGroupCmd)
            if time.time() > timeout:
                break
        if ret == 0:
            subprocess.call(addApplicableGroupCmd)
            subprocess.call(cleanupApplicableGroupCmd)
            logger.info("Finished share mount configuration for share %s", groupCn)
        else:
            logger.warning(
                "Group %s for share %s was not found in Nextcloud. Check ldapBaseGroups in Nextcloud ldap config. Adding nc_admin as applicable user to hide share mount from all other users.",
                groupCn, shareName,
            )
            subprocess.call(addNcAdminApplicableUserCmd)
    finally:
        listener.unsetuid()
