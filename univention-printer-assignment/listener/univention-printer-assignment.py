# -*- coding: utf-8 -*-
#
# univention-printer-assignment
#  listener module
#
# Copyright 2013-2014 Univention GmbH
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

__package__=''  # workaround for PEP 366
import listener
import univention.debug as ud
import univention.config_registry

import re
import os
import subprocess

name='univention-printer-assignment'
description='create windows netlogon scripts for univention-printer-assignment'
filter='(|(objectClass=univentionPrinter)(objectClass=univentionGroup)(&(objectClass=univentionHost)(objectClass=univentionWindows)))'
attributes=[]

ucr = univention.config_registry.ConfigRegistry()
ucr.load()

dn_filter_grp = ucr.get('printer/assignment/dnfilter/groups')
if dn_filter_grp:
	dn_filter_grp = re.compile(dn_filter_grp)

backlog_process_cmd = ucr.get('printer/assignment/cmd/process', '/usr/share/univention-printer-assignment/update-univention-printer-assignment')
backlog_filename = ucr.get('printer/assignment/backlog/file', '/var/lib/univention-printer-assignment/backlog')
backlog_maxcount = int(ucr.get('printer/assignment/backlog/maxcount', '250'))
backlog_count = 0
backlog_cache = set()


def __append_to_backlog(dn):
	""" Append given DN to backlog file """
	global backlog_count
	# if dn is already in backlog_cache, then return
	if dn in backlog_cache:
		return
	# append dn to backlog
	listener.setuid(0)
	try:
		fd = open(backlog_filename, 'a+')
		fd.write('%s\n' % dn)
		fd.close()
		os.chmod(backlog_filename, 0644)
	except Exception as e:
		ud.debug(ud.LISTENER, ud.ERROR, "univention-printer-assignment: failed to append to backlog file %s" % backlog_filename)
		ud.debug(ud.LISTENER, ud.ERROR, "univention-printer-assignment: %s" % str(e))
	finally:
		listener.unsetuid()
	# remember number of entries in backlog file
	backlog_count += 1
	# add DN to backlog cache
	backlog_cache.add(dn)
	ud.debug(ud.LISTENER, ud.INFO, "univention-printer-assignment: added %s to backlog" % dn)


def __process_backlog():
	""" Call backlog handler script to create/update logon scripts """
	ud.debug(ud.LISTENER, ud.PROCESS, "univention-printer-assignment: processing backlog file (entry count: %d)" % backlog_count)
	listener.setuid(0)
	try:
		result = subprocess.call([backlog_process_cmd, backlog_process_cmd, '-f', backlog_filename])
	finally:
		listener.unsetuid()
	if result:
		ud.debug(ud.LISTENER, ud.ERROR, "univention-printer-assignment: processing backlog failed (exitcode %s)" % result)
	else:
		clean()


def __is_relevant(dn, old, new):
	# object has been created or removed (this may also cover some irrelevant objects)
	if not old or not new:
		return True

	if 'univentionPrinter' in new.get('objectClass',[]):
		for attrname in ('cn', 'univentionPrinterSambaName', 'univentionAssignedPrinterSettingsFile'):
			if old.get(attrname, []) != new.get(attrname, []):
				return True

	if 'univentionGroup' in new.get('objectClass',[]):
		if dn_filter_grp and not dn_filter_grp.match(dn):
			return False
		for attrname in ('uniqueMember', 'univentionAssignedPrinter', 'univentionAssignedPrinterDefault'):
			if old.get(attrname, []) != new.get(attrname, []):
				return True

	if 'univentionWindows' in new.get('objectClass',[]):
		for attrname in ('univentionAssignedPrinter', 'univentionAssignedPrinterDefault'):
			if old.get(attrname, []) != new.get(attrname, []):
				return True

	return False


def handler(dn, new, old):
	# if DN is already taken care of then stop immediately
	if dn in backlog_cache:
		return

	# check if object or change is relevant for logon scripts
	if __is_relevant(dn, old, new):
		# special case: group has been removed ==> check all old members
		if not new and 'univentionGroup' in old.get('objectClass', []):
			for memberdn in old.get('uniqueMember', []):
				__append_to_backlog(memberdn)
		else:
			# usual case
			__append_to_backlog(dn)

	# after a certain amount of changes start processing of backlog instantly
	if backlog_count >= backlog_maxcount:
		__process_backlog()


def clean():
	""" Purge/create backlog file and reset backlog counter and backlog cache """
	global backlog_cache, backlog_count
	backlog_cache = set()
	backlog_count = 0
	ud.debug(ud.LISTENER, ud.PROCESS, "univention-printer-assignment: cleaning backlog file %s" % backlog_filename)
	listener.setuid(0)
	try:
		open(backlog_filename, 'w').close()
	except Exception as e:
		ud.debug(ud.LISTENER, ud.ERROR, "univention-printer-assignment: failed to create/truncate backlog file %s" % backlog_filename)
		ud.debug(ud.LISTENER, ud.ERROR, "univention-printer-assignment: %s" % str(e))
	finally:
		listener.unsetuid()


def postrun():
	""" Called after some time to process backlog file """
	__process_backlog()


def initialize():
	pass

