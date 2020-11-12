# -*- coding: utf-8 -*-
#
# Univention domain userquota
#  listener module: management of domain wide user quota settings
#
# Copyright 2013 Univention GmbH
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

import listener
import univention.debug as ud
import subprocess

name = 'univention-domain-userquota'
description = 'Management of domain wide user quota settings'
filter = '(objectClass=domainquotauser)'

fqdn = "%s.%s" % (listener.configRegistry.get('hostname', ''), listener.configRegistry.get('domainname', ''))
delimiter = '$$'
softlimit_percent = int(listener.configRegistry.get('quota/domainuser/softlimitpercent', '5'))


def get_quotas_for_this_host(userobj):
	# check if quota setting applies to this host
	quotas = []
	for quota in userobj.get('domainquota'):
		quota = quota.decode('UTF-8')
		if quota.split(delimiter)[0] == fqdn:
			quotas.append(quota)
	return quotas


def remove_user_quota(username, quota):
	mountpoint = quota.split(delimiter)[1]
	exec_array = ['/usr/sbin/setquota', '-u', username, '0', '0', '0', '0', mountpoint]
	ud.debug(ud.LISTENER, ud.INFO, "remove_user_quota running %s" % exec_array)
	listener.setuid(0)
	try:
		subprocess.call(exec_array)
	finally:
		listener.unsetuid()


def set_user_quota(username, quota):
	unit = quota.split(delimiter)[3]
	multiplier = 1
	if unit == 'MiB':
		multiplier = 1024
	elif unit == 'GiB':
		multiplier = 1024 * 1024

	hardlimit = int(quota.split(delimiter)[2]) * multiplier
	softlimit = hardlimit - int(round(((hardlimit / 100.0) * softlimit_percent)))
	mountpoint = quota.split(delimiter)[1]

	exec_array = ['/usr/sbin/setquota', '-u', username, '%s' % softlimit, '%s' % hardlimit, '0', '0', mountpoint]
	ud.debug(ud.LISTENER, ud.INFO, "set_user_quota running %s" % exec_array)
	listener.setuid(0)
	try:
		subprocess.call(exec_array)
	finally:
		listener.unsetuid()


def handler(dn, new, old):
	if old.get('domainquota'):
		old_quotas = get_quotas_for_this_host(old)
		ud.debug(ud.LISTENER, ud.INFO, "old quotas: %s" % old_quotas)
		for quota in old_quotas:
			remove_user_quota(old.get('uid')[0].decode('UTF-8'), quota)

	if new.get('domainquota'):
		new_quotas = get_quotas_for_this_host(new)
		ud.debug(ud.LISTENER, ud.INFO, "new quotas: %s" % new_quotas)
		for quota in new_quotas:
			set_user_quota(new.get('uid')[0].decode('UTF-8'), quota)
