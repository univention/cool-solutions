#!/usr/bin/python2.7
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

__package__='' 	# workaround for PEP 366

import listener
import re
import subprocess
import time
import univention.debug
import univention.admin.uldap
from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()

class UniventionNextcloudSambaCommon(object):

	def isDomainUsersCn(self, dn):
		domainUsersRegex = '^cn=Domain\ Users\ [A-Za-z0-9_]*'
		domainUsersOuRegex = '^cn=Domain\ Users\ '
		domainUsersMatch = re.match(domainUsersRegex, dn)
		return domainUsersMatch

	def isSchuelerCn(self, dn):
		schuelerRegex = '^cn=schueler-[A-Za-z0-9_]*'
		schuelerOuRegex = '^cn=schueler-'
		schuelerMatch = re.match(schuelerRegex, dn)
		return schuelerMatch

	def isLehrerCn(self, dn):
		lehrerRegex = '^cn=lehrer-[A-Za-z0-9_]*'
		lehrerOuRegex = '^cn=lehrer-'
		lehrerMatch = re.match(lehrerRegex, dn)
		return lehrerMatch

	def getGroupCn(self, dn):
		groupCnRegex = '^cn=([^,]*)'
		groupCnMatch = re.match(groupCnRegex, dn)
		groupCn = re.sub('^cn=', '', groupCnMatch.group())
		return groupCn

	def getShareDn(self, lo, cn):
		timeout = time.time() + 30
		shareObj = lo.search("(&(objectClass=univentionShareSamba)(cn={}))".format(cn))
		while not shareObj:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Share {} does not yet exist in LDAP, waiting until it exists with 30s timeout".format(cn))
			shareObj = lo.search("(&(objectClass=univentionShareSamba)(cn={}))".format(cn))
			if time.time() > timeout:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Share {} does not exist in LDAP after 30s timeout. Share mount won't be created".format(cn))
				break
		return shareObj[0][0]

	def getShareHost(self, share):
		shareHost = ''.join(share['univentionShareHost'])
		return shareHost

	def getShareSambaName(self, share):
		shareSambaName = ''.join(share['univentionShareSambaName'])
		return shareSambaName

	def getBase(self):
		base = ucr.get('ldap/base')
		return base

	def getDomain(self):
		domainname = ucr.get('domainname')
		return domainname

	def getWinDomain(self):
		winDomain = ucr.get('windows/domain')
		return winDomain

	def getMountId(self, mountName):
		getMountIdCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:list | grep '\/{}' | awk '{{print $2}}'".format(mountName)
		listener.setuid(0)
		mountId = subprocess.check_output(getMountIdCmd, shell=True)
		listener.unsetuid()
		mountId = re.search('[0-9]+', mountId).group()
		if mountId:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Mount for {} is already configured. Re-setting config if command is not delete...".format(mountName))
		else:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "No mount for {} configured yet. Configuring...".format(mountName))
			mountId = self.createMount(mountName)
		return mountId

	def getSshCommand(self, remoteUser, remotePwFile, remoteHost):
		sshCommand = "univention-ssh {} {}@{} ".format(remotePwFile, remoteUser, remoteHost)
		return sshCommand

	def createMount(self, mountName, useSSH=False, remoteUser=None, remotePwFile=None, remoteHost=None):
		if useSSH == True:
			sshCommand = self.getSshCommand()
		else:
			sshCommand = ""

		createMountCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:create '/{}' smb 'password::sessioncredentials'".format(sshCommand, mountName)
		listener.setuid(0)
		subprocess.call(createMountCmd, shell=True)
		listener.unsetuid()
		mountId = self.getMountId(mountName)
		return mountId

	def deleteMount(self, mountId, useSSH=False):
		if useSSH == True:
			sshCommand = self.getSshCommand()
		else:
			sshCommand = ""

		deleteMountCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:delete --yes {}".format(sshCommand, mountId)
		univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Deleting mount with ID {}".format(mountId))
		listener.setuid(0)
		subprocess.call(deleteMountCmd, shell=True)
		listener.unsetuid()

	def setMountConfig(self, mountId, shareHost, shareName, windomain, groupCn, useSSH=False, remoteUser=None, remotePwFile=None, remoteHost=None, applicableGroup=None):
		if useSSH == True:
			sshCommand = self.getSshCommand()
		else:
			sshCommand = ""

		addHostCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} host {}".format(sshCommand, mountId, shareHost)
		addShareRootCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} share '/'".format(sshCommand, mountId)
		addShareNameCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} root '{}'".format(sshCommand, mountId, shareName)
		addShareDomainCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} domain '{}'".format(sshCommand, mountId, windomain)
		#checkApplicableGroupCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ group:list | grep -E '\-\ {}:'".format(sshCommand, groupCn)
		checkApplicableGroupCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ group:adduser '{}' nc_admin".format(sshCommand, groupCn)
		checkLdapApplicableGroupCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ ldap:search --group '{}'".format(sshCommand, groupCn)
		cleanupApplicableGroupCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ group:removeuser '{}' nc_admin".format(sshCommand, groupCn)
		addApplicableGroupCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:applicable --add-group '{}' {}".format(sshCommand, groupCn, mountId)
		addNcAdminApplicableUserCmd = "{}univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:applicable --add-user 'nc_admin' {}".format(sshCommand, mountId)

		listener.setuid(0)
		subprocess.call(addHostCmd, shell=True)
		subprocess.call(addShareRootCmd, shell=True)
		subprocess.call(addShareNameCmd, shell=True)
		subprocess.call(addShareDomainCmd, shell=True)
		ret = subprocess.call(checkApplicableGroupCmd, shell=True)
		timeout = time.time() + 600
		while ret != 0:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Group {} does not yet exist in Nextcloud, waiting until it exists with 600s timeout".format(groupCn))
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Performing LDAP search via occ for group {} to make Nextcloud aware of it".format(groupCn))
			subprocess.call(checkLdapApplicableGroupCmd, shell=True)
			ret = subprocess.call(checkApplicableGroupCmd, shell=True)
			if time.time() > timeout:
				break
		if ret == 0:
			subprocess.call(addApplicableGroupCmd, shell=True)
			subprocess.call(cleanupApplicableGroupCmd, shell=True)
			listener.unsetuid()
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Finished share mount configuration for share {}".format(groupCn))
		else:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Group {} for share {} was not found in Nextcloud. Check ldapBaseGroups in Nextcloud ldap config. Adding nc_admin as applicable user to hide share mount from all other users.".format(groupCn, shareName))
			subprocess.call(addNcAdminApplicableUserCmd, shell=True)
			listener.unsetuid()
