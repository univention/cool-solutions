#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# common class
#
# Copyright 2018-2019 Univention GmbH
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

from __future__ import absolute_import

import re
import subprocess
import time

from ldap.filter import filter_format

import univention.debug as ud
from univention.config_registry import ConfigRegistry

import listener

ucr = ConfigRegistry()
ucr.load()

occ_path_ucr = ucr.get('nextcloud-samba-common/occ_path', False)
if occ_path_ucr:
	occ_path = "sudo -u www-data {}".format(occ_path_ucr)
else:
	occ_path = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ"


def isDomainUsersCn(dn):
	domainUsersRegex = r'^cn=Domain\ Users\ [A-Za-z0-9_]*'
	domainUsersMatch = re.match(domainUsersRegex, dn)
	return domainUsersMatch


def isSchuelerCn(dn):
	schuelerRegex = '^cn=schueler-[A-Za-z0-9_]*'
	schuelerMatch = re.match(schuelerRegex, dn)
	return schuelerMatch


def isLehrerCn(dn):
	lehrerRegex = '^cn=lehrer-[A-Za-z0-9_]*'
	lehrerMatch = re.match(lehrerRegex, dn)
	return lehrerMatch


def getGroupCn(dn):
	groupCnRegex = '^cn=([^,]*)'
	groupCnMatch = re.match(groupCnRegex, dn)
	groupCn = re.sub('^cn=', '', groupCnMatch.group())
	return groupCn


def getShareObj(lo, cn):
	timeout = time.time() + 30
	shareObj = lo.search(filter_format("(&(objectClass=univentionShareSamba)(cn={}))", (cn,)))
	while not shareObj:
		ud.debug(ud.LISTENER, ud.WARN, "Share {} does not yet exist in LDAP, waiting until it exists with 30s timeout".format(cn))
		shareObj = lo.search(filter_format("(&(objectClass=univentionShareSamba)(cn={}))", (cn,)))
		time.sleep(1)
		if time.time() > timeout:
			ud.debug(ud.LISTENER, ud.WARN, "Share {} does not exist in LDAP after 30s timeout. Share mount won't be created".format(cn))
			return False
	return shareObj[0][1]


def getShareHost(share):
	return b''.join(share['univentionShareHost']).decode('UTF-8')


def getShareSambaName(share):
	return b''.join(share['univentionShareSambaName']).decode('UTF-8')


def getBase():
	return ucr.get('ldap/base')


def getDomain():
	return ucr.get('domainname')


def getWinDomain():
	return ucr.get('windows/domain')


def getMountId(mountName):
	getMountIdCmd = r"{} files_external:list | grep '\/{}' | awk '{{print $2}}'".format(occ_path, mountName)
	listener.setuid(0)
	try:
		mountId = subprocess.check_output(getMountIdCmd, shell=True)
	finally:
		listener.unsetuid()
	mountId = re.search('[0-9]+', mountId.decode('UTF-8'))
	if mountId:
		mountId = mountId.group()
		ud.debug(ud.LISTENER, ud.WARN, "Mount for {} is already configured. Re-setting config if command is not delete...".format(mountName))
	else:
		ud.debug(ud.LISTENER, ud.WARN, "No mount for {} configured yet.".format(mountName))
		mountId = False
	return mountId


def getSshCommand(remoteUser, remotePwFile, remoteHost):
	return "univention-ssh {} {}@{} ".format(remotePwFile, remoteUser, remoteHost)


def createMount(mountName, useSSH=False, remoteUser=None, remotePwFile=None, remoteHost=None):
	if useSSH:
		sshCommand = getSshCommand()
	else:
		sshCommand = ""

	createMountCmd = "{}{} files_external:create '/{}' smb 'password::sessioncredentials'".format(sshCommand, occ_path, mountName)
	listener.setuid(0)
	try:
		subprocess.call(createMountCmd, shell=True)
	finally:
		listener.unsetuid()
	mountId = getMountId(mountName)
	return mountId


def deleteMount(mountId, useSSH=False):
	if useSSH:
		sshCommand = getSshCommand()
	else:
		sshCommand = ""

	deleteMountCmd = "{}{} files_external:delete --yes {}".format(sshCommand, occ_path, mountId)
	ud.debug(ud.LISTENER, ud.WARN, "Deleting mount with ID {}".format(mountId))
	listener.setuid(0)
	try:
		subprocess.call(deleteMountCmd, shell=True)
	finally:
		listener.unsetuid()
	ud.debug(ud.LISTENER, ud.WARN, "Deleted mount with ID {}".format(mountId))


def setMountConfig(mountId, shareHost, shareName, windomain, groupCn, useSSH=False, remoteUser=None, remotePwFile=None, remoteHost=None, applicableGroup=None):
	if useSSH:
		sshCommand = getSshCommand()
	else:
		sshCommand = ""

	addHostCmd = "{}{} files_external:config {} host {}".format(sshCommand, occ_path, mountId, shareHost)
	addShareRootCmd = "{}{} files_external:config {} share '/'".format(sshCommand, occ_path, mountId)
	addShareNameCmd = "{}{} files_external:config {} root '{}'".format(sshCommand, occ_path, mountId, shareName)
	addShareDomainCmd = "{}{} files_external:config {} domain '{}'".format(sshCommand, occ_path, mountId, windomain)
	#checkApplicableGroupCmd = "{}{} group:list | grep -E '\-\ {}:'".format(sshCommand, occ_path, groupCn)
	checkApplicableGroupCmd = "{}{} group:adduser '{}' nc_admin".format(sshCommand, occ_path, groupCn)
	checkLdapApplicableGroupCmd = "{}{} ldap:search --group '{}'".format(sshCommand, occ_path, groupCn)
	cleanupApplicableGroupCmd = "{}{} group:removeuser '{}' nc_admin".format(sshCommand, occ_path, groupCn)
	addApplicableGroupCmd = "{}{} files_external:applicable --add-group '{}' {}".format(sshCommand, occ_path, groupCn, mountId)
	addNcAdminApplicableUserCmd = "{}{} files_external:applicable --add-user 'nc_admin' {}".format(sshCommand, occ_path, mountId)

	listener.setuid(0)
	try:
		subprocess.call(addHostCmd, shell=True)
		subprocess.call(addShareRootCmd, shell=True)
		subprocess.call(addShareNameCmd, shell=True)
		subprocess.call(addShareDomainCmd, shell=True)
		ret = subprocess.call(checkApplicableGroupCmd, shell=True)
		timeout = time.time() + 600
		while ret != 0:
			ud.debug(ud.LISTENER, ud.WARN, "Group {} does not yet exist in Nextcloud, waiting until it exists with 600s timeout".format(groupCn))
			ud.debug(ud.LISTENER, ud.WARN, "Performing LDAP search via occ for group {} to make Nextcloud aware of it".format(groupCn))
			subprocess.call(checkLdapApplicableGroupCmd, shell=True)
			ret = subprocess.call(checkApplicableGroupCmd, shell=True)
			if time.time() > timeout:
				break
		if ret == 0:
			subprocess.call(addApplicableGroupCmd, shell=True)
			subprocess.call(cleanupApplicableGroupCmd, shell=True)
			ud.debug(ud.LISTENER, ud.WARN, "Finished share mount configuration for share {}".format(groupCn))
		else:
			ud.debug(ud.LISTENER, ud.WARN, "Group {} for share {} was not found in Nextcloud. Check ldapBaseGroups in Nextcloud ldap config. Adding nc_admin as applicable user to hide share mount from all other users.".format(groupCn, shareName))
			subprocess.call(addNcAdminApplicableUserCmd, shell=True)
	finally:
		listener.unsetuid()
