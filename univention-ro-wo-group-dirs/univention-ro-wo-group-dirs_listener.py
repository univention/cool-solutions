# -*- coding: utf-8 -*-
#
# Univention Nagios
#  listener module: update configuration of local Nagios server
#
# Copyright 2004-2019 Univention GmbH
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

__package__ = ''  # workaround for PEP 366
import listener
import os
import re
import univention.debug
import subprocess
import time
import univention.admin.uldap
from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()

listener.setuid(0)
lo, po = univention.admin.uldap.getMachineConnection()
listener.unsetuid()

name='univention-ro-wo-group-dirs'
description='Configure read-only and write-only dirs in class and workgroup shares'
filter='(|(ucsschoolRole=school_class_share:school:*)(ucsschoolRole=workgroup_share:school:*))'
attributes=[]
modrdn="1"

def initialize():
	univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "{}: initialize".format(name))
	return

def createDir(path, dir, ownerGroup, mode, acl):
	listener.setuid(0)
	#univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "PATH: {} ; ownerGroup: {} ; mode: {} ; acl: {}".format(path, ownerGroup, mode, acl))
	timeout = time.time() + 30
	while not os.path.isdir(path):
		univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "univention-ro-wo-group-dirs - Root path does not exist yet, waiting for it with 30s timeout: {}".format(path))
		time.sleep(1)
		if time.time() > timeout:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "univention-ro-wo-group-dirs - Root path did not appear within 30s, skipping: {}".format(path))
			return

	if not os.path.isdir(dir):
		univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, "univention-ro-wo-group-dirs - Creating dir: {}".format(dir))
		os.mkdir(dir)
	if os.path.isdir(dir):
		os.chown(dir, 0, ownerGroup)
		os.chmod(dir, mode)
		subprocess.call(['setfacl', '-m', acl, dir])
	listener.unsetuid()

def handler(dn, new, old, command=''):
	ou = re.search(r'ou=[a-zA-Z0-9_]*', dn).group()
	ou = re.sub(r'ou=', '', ou)
	newGroupName = new['cn'][0]
	if old:
		oldGroupName = old['cn'][0]

	#Lehrmaterial
	path = new['univentionSharePath'][0]
	dir = '{}/Lehrmaterial'.format(path)
	ownerGroup = 'lehrer-{}'.format(ou)
	ownerGidNumber = int(lo.search('cn={}'.format(ownerGroup))[0][1]['gidNumber'][0])
	mode = 775
	acl = 'user::rwx,user:root:rwx,group::rwx,group:{}:rwx,group:{}:r-x,mask::rwx,other::---,default:user::rwx,default:user:root:rwx,default:group::---,default:group:{}:rwx,default:group:{}:r-x,default:mask::rwx,default:other::---'.format(ownerGroup, newGroupName, ownerGroup, newGroupName)
	createDir(path, dir, ownerGidNumber, mode, acl)

	#Abgabe
	path = new['univentionSharePath'][0]
	dir = '{}/Abgabe'.format(path)
	ownerGroup = 'lehrer-{}'.format(ou)
	ownerGidNumber = int(lo.search('cn={}'.format(ownerGroup))[0][1]['gidNumber'][0])
	mode = 775
	acl = 'user::rwx,user:root:rwx,group::rwx,group:{}:rwx,group:{}:r-x,mask::rwx,other::---,default:user::rwx,default:user:root:rwx,default:group::---,default:group:{}:rwx,default:group:{}:r-x,default:mask::rwx,default:other::---'.format(ownerGroup, newGroupName, ownerGroup, newGroupName)
	createDir(path, dir, ownerGidNumber, mode, acl)

def clean():
	return

def postrun():
	return
