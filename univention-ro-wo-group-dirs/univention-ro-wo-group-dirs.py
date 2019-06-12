#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# univention-ro-wo-group-dirs
# Create Abgabe and Lehrmaterial directories in class and workgroup shares
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

import os
import re
import subprocess
import time
import sys
import univention.admin.uldap
from univention.config_registry import ConfigRegistry
from univention.config_registry.frontend import ucr_update

ucr = ConfigRegistry()
ucr.load()

lo, po = univention.admin.uldap.getMachineConnection()

def createDir(path, dir, ownerGroup, mode, acl):
	#univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "PATH: {} ; ownerGroup: {} ; mode: {} ; acl: {}".format(path, ownerGroup, mode, acl))
	timeout = time.time() + 30
	while not os.path.isdir(path):
		print("univention-ro-wo-group-dirs - Root path does not exist yet, waiting for it with 30s timeout: {}".format(path))
		time.sleep(1)
		if time.time() > timeout:
			print("univention-ro-wo-group-dirs - Root path did not appear within 30s, skipping: {}".format(path))
			return

	if not os.path.isdir(dir):
		print("univention-ro-wo-group-dirs - Creating dir: {}".format(dir))
		os.mkdir(dir)
	if os.path.isdir(dir):
		os.chown(dir, 0, ownerGroup)
		os.chmod(dir, mode)
		subprocess.call(['setfacl', '-bm', acl, dir])

def main(dn, path, groupName):
	ou = re.search(r'ou=[a-zA-Z0-9_]*', dn).group()
	ou = re.sub(r'ou=', '', ou)

	#Lehrmaterial
	roName = ucr.get('group-dirs/ro/name')
	if not roName:
		roName = "Lehrmaterial"
	dir = '{}/{}'.format(path, roName)
	ownerGroup = 'lehrer-{}'.format(ou)
	ownerGidNumber = int(lo.search('cn={}'.format(ownerGroup))[0][1]['gidNumber'][0])
	mode = 775
	acl = 'user::rwx,user:root:rwx,group::rwx,group:{}:rwx,group:{}:r-x,mask::rwx,other::---,default:user::rwx,default:user:root:rwx,default:group::---,default:group:{}:rwx,default:group:{}:r-x,default:mask::rwx,default:other::---'.format(ownerGroup, groupName, ownerGroup, groupName)
	createDir(path, dir, ownerGidNumber, mode, acl)

	#Abgabe
	woName = ucr.get('group-dirs/wo/name')
	if not woName:
		woName = "Abgabe"
	dir = '{}/{}'.format(path, woName)
	ownerGroup = 'lehrer-{}'.format(ou)
	ownerGidNumber = int(lo.search('cn={}'.format(ownerGroup))[0][1]['gidNumber'][0])
	mode = 775
	acl = 'user::rwx,user:root:rwx,group::rwx,group:{}:rwx,group:{}:-wx,mask::rwx,other::---,default:user::rwx,default:user:root:rwx,default:group::---,default:group:{}:rwx,default:group:{}:-wx,default:mask::rwx,default:other::---'.format(ownerGroup, groupName, ownerGroup, groupName)
	createDir(path, dir, ownerGidNumber, mode, acl)

if __name__ == '__main__':
	filter = '(|(ucsschoolRole=school_class_share:school:*)(ucsschoolRole=workgroup_share:school:*))'

	if ucr.is_true('cron/univention-ro-wo-group-dirs/running'):
		print('univention-ro-wo-group-dirs.py is already running, exiting')
		sys.exit(0)
	else:
		changes = {"cron/univention-ro-wo-group-dirs/running": "true"}
		ucr_update(ucr, changes)

	shares = lo.search(filter)
	for share in shares:
		dn = share[0]
		sharePath = share[1]['univentionSharePath'][0]
		groupName = share[1]['cn'][0]
		try:
			main(dn, sharePath, groupName)
		except Exception as e:
			print('univention-ro-wo-group-dirs.py: Error while processing DN: {} with sharePath: {} and groupName: {} Exception was: {}'.format(dn, sharePath, groupName, e))
			continue
	changes = {"cron/univention-ro-wo-group-dirs/running": "false"}
	ucr_update(ucr, changes)
	sys.exit(0)
