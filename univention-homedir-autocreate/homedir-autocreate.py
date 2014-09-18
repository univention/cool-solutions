# -*- coding: utf-8 -*-
#
# Univention homedir autocreation
#  listener module
#
# Copyright (C) 2009-2010 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Binary versions of this file provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

__package__='' 	# workaround for PEP 366

import listener
import os
import univention.debug
from univention.config_registry import ConfigRegistry
ucr = ConfigRegistry()
ucr.load()

name='homedir-autocreate'
description='Generate homedir on usercreation'
filter='(&(|(&(objectClass=posixAccount)(objectClass=shadowAccount))(objectClass=univentionMail)(objectClass=sambaSamAccount)(objectClass=simpleSecurityObject)(&(objectClass=person)(objectClass=organizationalPerson)(objectClass=inetOrgPerson)))(!(uidNumber=0))(!(uid=*$)))'
attributes=[]

PATH_SU = '/bin/su'
PATH_MKDIR = '/bin/mkdir'
PATH_CHOWN = '/bin/chown'
PATH_CHMOD = '/bin/chmod'

def initialize():
	univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, '%s: initialize' % name)
	return

def handler(dn, new, old):
	# create users homedir only on user creation
	if not old and new:
		# if homeDirectoy is not set OR ( homeDirectoy is missing and not '/dev/null' ) then ....
		if not new.get('homeDirectory') or ( new.get('homeDirectory',['/'])[0] != '/dev/null' and not os.path.exists( new.get('homeDirectory',['/'])[0] ) ):
			if not new.get('automountInformation'):
				# check for uid
				if new.get('uid'):
					listener.setuid(0)
					try:
						univention.debug.debug(univention.debug.LISTENER, univention.debug.WARN, '%s: starting %s for %s %s' % (name, PATH_SU, new.get('uid')[0], str(new.get('homeDirectory',[]))))
						listener.run( PATH_SU, [ PATH_SU, '-c', 'echo', '-', new.get('uid')[0] ] )
						univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, '%s: finished %s for %s %s' % (name, PATH_SU, new.get('uid')[0], str(new.get('homeDirectory',[]))))
					finally:
						listener.unsetuid()
			elif ucr['hostname'] in new.get('automountInformation',[ucr['hostname']])[0]:
				if new.get('uid'):
					listener.setuid(0)
					path = new.get('automountInformation',[ucr['hostname']])[0].split(':')[1]
					listener.run( PATH_MKDIR, [ PATH_MKDIR, path ] )
					listener.run( PATH_CHOWN, [ PATH_CHOWN, new.get('uid')[0], path ] )
					listener.run( PATH_CHMOD, [ PATH_CHMOD, '0700', path ] )
			else:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, '%s: not on this server %s %s' % (name, PATH_SU, new.get('uid')[0], str(new.get('homeDirectory',[]))))
				

def clean():
	return

def postrun():
	return
