#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention Nextcloud Samba share configuration
# UCR hook
#
# Copyright 2018 Univention GmbH
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

#__package__='' 	# workaround for PEP 366

#import listener
import subprocess
import time
import univention.debug
import univention.admin.uldap
from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()
lo, po = univention.admin.uldap.getMachineConnection(ldap_master=False)

commonShares = ucr.get('ucsschool/userlogon/commonshares').split(',')
commonShares.remove('Marktplatz')
windomain = ucr.get('windows/domain')
remoteUser = ucr.get('nextcloud-samba-share-config/remoteUser')
remotePwFile = ucr.get('nextcloud-samba-share-config/remotePwFile')
remoteHost = ucr.get('nextcloud-samba-share-config/remoteHost')
applicableGroup = ucr.get('nextcloud-samba-share-config/nextcloudGroup')

for shareCn in commonShares:
	share = lo.search("(&(objectClass=univentionShareSamba)(cn={}))".format(shareCn))

	if share:
		# Enable files_external Nextcloud app; moved to postinst, too much overhead to do this on every single change
		#univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "Making sure files_external app is enabled")
		#enableAppCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ app:enable files_external"
		#subprocess.call(enableAppCmd, shell=True)

		shareHost = ''.join(share[0][1]['univentionShareHost'])
		shareSambaName = ''.join(share[0][1]['univentionShareSambaName'])
		getMountIdCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:list | grep '\/{}' | awk '{{print $2}}'".format(remotePwFile, remoteUser, remoteHost, shareCn)

		try:
			id, foo = subprocess.check_output(getMountIdCmd, shell=True)
			print("Mount for {} is already configured. Re-setting config...".format(shareCn))
		except:
			print("No mount for {} configured yet. Configuring...".format(shareCn))

			createMountCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:create '/{}' smb 'password::sessioncredentials'".format(remotePwFile, remoteUser, remoteHost, shareCn)
			subprocess.call(createMountCmd, shell=True)
			id, foo = subprocess.check_output(getMountIdCmd, shell=True)

		addHostCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} host {}".format(remotePwFile, remoteUser, remoteHost, id, shareHost)
		addShareRootCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} share '/'".format(remotePwFile, remoteUser, remoteHost, id)
		addShareNameCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} root '{}'".format(remotePwFile, remoteUser, remoteHost, id, shareCn)
		addShareDomainCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:config {} domain '{}'".format(remotePwFile, remoteUser, remoteHost, id, windomain)
		#removeAllApplicableCmd = "univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:applicable --remove-all {}".format(id)
		checkApplicableGroupCmd = "univention-ssh {} {}@{} univention-app shell nextcloud sudo -u www-data /var/www/html/occ group:list | grep -E '\-\ {}:'".format(remotePwFile, remoteUser, remoteHost, applicableGroup)
		addApplicableGroupCmd = 'univention-ssh --no-split {} {}@{} "univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:applicable --add-group \'{}\' {}"'.format(remotePwFile, remoteUser, remoteHost, applicableGroup, id)

		subprocess.call(addHostCmd, shell=True)
		subprocess.call(addShareRootCmd, shell=True)
		subprocess.call(addShareNameCmd, shell=True)
		subprocess.call(addShareDomainCmd, shell=True)
		ret = subprocess.call(checkApplicableGroupCmd, shell=True)
		timeout = time.time() + 15
		while ret != 0:
			print("Group {} does not yet exist in Nextcloud, waiting till it exists with 15s timeout".format(applicableGroup))
			time.sleep(2)
			ret = subprocess.call(checkApplicableGroupCmd, shell=True)
			if time.time() > timeout:
				break
		if ret == 0:
			subprocess.call(addApplicableGroupCmd, shell=True)
			print("Finished share mount configuration for share {}".format(shareCn))
		else:
			print("Group {} for share {} was not found in Nextcloud. Check ldapBaseGroups in Nextcloud ldap config.".format(applicableGroup, shareCn))
	else:
		print("Nothing to do: no share was found for group {}".format(shareCn))
