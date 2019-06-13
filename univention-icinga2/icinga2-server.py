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
import stat
import univention.debug
import subprocess

name = 'icinga2-server'
description = 'Create configuration for Icinga2 server'
filter = '(&(univentionIcingaEnabled=TRUE)(|(objectClass=univentionNagiosServiceClass)(objectClass=univentionNagiosTimeperiodClass)(objectClass=univentionHost)))'

__predefinedTimeperiod = 'Univention-Predefined-24x7'
__fallbackContact = 'root@localhost'
__initscript = '/etc/init.d/icinga2'

#
# /etc/nagios/conf.univention.d/services/<SERVICENAME>,<HOSTFQDN>.cfg
# /etc/nagios/conf.univention.d/hosts/<HOSTFQDN>.cfg
# /etc/nagios/conf.univention.d/hostgrps/<GRPNAME>.cfg
# /etc/nagios/conf.univention.d/contacts/<EMAILADDR>.cfg
# /etc/nagios/conf.univention.d/contactgrps/<HOSTFQDN>.cfg
# /etc/nagios/conf.univention.d/timeperiods/<PERIODNAME>.cfg
#

__confdir = '/etc/icinga2/conf.d/conf.univention.d/'
__confsubdirs = ['services', 'hosts', 'hostextinfo', 'hostgrps', 'contacts', 'contactgrps', 'timeperiods']

__servicesdir = __confdir + 'services/'
__hostsdir = __confdir + 'hosts/'
__hostextinfodir = __confdir + 'hostextinfo/'
__hostgrpsdir = __confdir + 'hostgrps/'
__contactsdir = __confdir + 'contacts/'
__contactgrpsdir = __confdir + 'contactgrps/'
__timeperiodsdir = __confdir + 'timeperiods/'

__exthostinfo_mapping = {
	'unknown': {
		'icon_image': 'univention/unknown.gif',
		'vrml_image': 'univention/unknown.gif',
		'statusmap_image': 'univention/unknown.gd2'
	},
	'ipmanagedclient': {
		'icon_image': 'univention/ipmanagedclient.gif',
		'vrml_image': 'univention/ipmanagedclient.gif',
		'statusmap_image': 'univention/ipmanagedclient.gd2'
	},
	'client': {
		'icon_image': 'univention/client.gif',
		'vrml_image': 'univention/client.gif',
		'statusmap_image': 'univention/client.gd2'
	},
	'macos': {
		'icon_image': 'univention/macos.gif',
		'vrml_image': 'univention/macos.gif',
		'statusmap_image': 'univention/macos.gd2'
	},
	'mobileclient': {
		'icon_image': 'univention/mobileclient.gif',
		'vrml_image': 'univention/mobileclient.gif',
		'statusmap_image': 'univention/mobileclient.gd2'
	},
	'thinclient': {
		'icon_image': 'univention/thinclient.gif',
		'vrml_image': 'univention/thinclient.gif',
		'statusmap_image': 'univention/thinclient.gd2'
	},
	'windows': {
		'icon_image': 'univention/windows.gif',
		'vrml_image': 'univention/windows.gif',
		'statusmap_image': 'univention/windows.gd2'
	},
	'memberserver': {
		'icon_image': 'univention/memberserver.gif',
		'vrml_image': 'univention/memberserver.gif',
		'statusmap_image': 'univention/memberserver.gd2'
	},
	'domaincontroller_master': {
		'icon_image': 'univention/domaincontroller_master.gif',
		'vrml_image': 'univention/domaincontroller_master.gif',
		'statusmap_image': 'univention/domaincontroller_master.gd2'
	},
	'domaincontroller_backup': {
		'icon_image': 'univention/domaincontroller_backup.gif',
		'vrml_image': 'univention/domaincontroller_backup.gif',
		'statusmap_image': 'univention/domaincontroller_backup.gd2'
	},
	'domaincontroller_slave': {
		'icon_image': 'univention/domaincontroller_slave.gif',
		'vrml_image': 'univention/domaincontroller_slave.gif',
		'statusmap_image': 'univention/domaincontroller_slave.gd2'
	},
}


__reload = False


def writeTimeperiod(filename, name, alias, periods):
	listener.setuid(0)
	try:
		fp = open(filename, 'w')
		fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
		fp.write('#          Please use univention-directory-manager instead.\n')
		fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
		fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
		fp.write('#          stattdessen den Univention Directory Manager.\n')
		fp.write('\n')
		fp.write('object TimePeriod "%s" {\n' % name)
#		fp.write('    timeperiod_name   %s\n' % name)
#		fp.write('    alias             %s\n' % alias)
		fp.write('    import "legacy-timeperiod"\n')
		fp.write('    ranges = {\n')
		if periods[0]:
			fp.write('    "monday"    = "%s"\n' % periods[0])
		if periods[1]:
			fp.write('    "tuesday"   = "%s"\n' % periods[1])
		if periods[2]:
			fp.write('    "wednesday" = "%s"\n' % periods[2])
		if periods[3]:
			fp.write('    "thursday"  = "%s"\n' % periods[3])
		if periods[4]:
			fp.write('    "friday"    = "%s"\n' % periods[4])
		if periods[5]:
			fp.write('    "saturday"  = "%s"\n' % periods[5])
		if periods[6]:
			fp.write('    "sunday"    = "%s"\n' % periods[6])
		fp.write('    }\n')
		fp.write('}\n')
		fp.close()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: timeperiod %s written' % name)
	finally:
		listener.unsetuid()


def handleTimeperiod(dn, new, old):

	global __timeperiodsdir
	conffilename = __timeperiodsdir + '%s.conf'

	if old:
		filename = conffilename % old['cn'][0]
		listener.setuid(0)
		try:
			if os.path.exists(filename):
				os.unlink(filename)
		finally:
			listener.unsetuid()

	if new:
		filename = conffilename % new['cn'][0]
		listener.setuid(0)

		periods = new['univentionNagiosTimeperiod'][0].split('#')

		writeTimeperiod(filename, new['cn'][0], new['description'][0], periods)


def createDefaultTimeperiod():
	global __timeperiodsdir
	global __predefinedTimeperiod
	filename = __timeperiodsdir + __predefinedTimeperiod + '.conf'
	if not os.path.exists(filename):
		periods = ['00:00-24:00', '00:00-24:00', '00:00-24:00', '00:00-24:00', '00:00-24:00', '00:00-24:00', '00:00-24:00']
		writeTimeperiod(filename, __predefinedTimeperiod, __predefinedTimeperiod, periods)


def hostDeleted(new, old):
	"""Checks if a host was enabled for Nagios services and has now been disabled or deleted.
	Returns True if deleted/deactivated and False if not"""

	if not new:
		# host object has been deleted
		return True
	if old and old.get('univentionIcingaEnabled', ['0'])[0] == 'TRUE':
		# old host object had enabled nagios support

		if not new.get('univentionIcingaEnabled', ['0'])[0] == 'TRUE':
			# new host object is not enabled ==> delete nagios host config
			return True
		if not new.get('aRecord'):
			# new host object contains no aRecord ==> delete nagios host config
			return True

	# host object seems to be ok
	return False


def createContact(contact):
	global __contactsdir
	global __predefinedTimeperiod

	listener.setuid(0)
	try:
		filename = '%s%s.conf' % (__contactsdir, contact)
		fp = open(filename, 'w')
		fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
		fp.write('#          Please use univention-admin instead.\n')
		fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
		fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
		fp.write('#          stattdessen den Univention Admin.\n')
		fp.write('\n')
		fp.write('object User "%s" {\n' % contact)
		fp.write('    import "generic-user"\n')
		fp.write('    display_name = "%s"\n' % contact)
		#fp.write('    alias                          Kontakt %s\n' % contact)
		#fp.write('    host_notification_period       %s\n' % __predefinedTimeperiod)
		#fp.write('    service_notification_period    %s\n' % __predefinedTimeperiod)
		#fp.write('    host_notification_options      d,u,r,f\n')
		#fp.write('    service_notification_options   w,u,c,r,f\n')
		#fp.write('    host_notification_commands     notify-host-by-email\n')
		#fp.write('    service_notification_commands  notify-service-by-email\n')
		fp.write('     groups = [ "icingaadmins" ]\n')
		fp.write('     email = "%s"\n' % contact)
		fp.write('}\n')
		fp.close()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: contact %s written' % contact)
	finally:
		listener.unsetuid()


def removeContactIfUnused(contact):
	global __contactsdir

	contact_filename = os.path.join(__contactsdir, "%s.conf" % contact)
	if os.path.exists(contact_filename):
		listener.setuid(0)
		try:
			# check if email address is still in use
			result = os.system('grep -c "%s" %s* 2> /dev/null > /dev/null' % (contact, __contactgrpsdir))
			if result == 1:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: removing contact %s' % contact_filename)
				os.unlink(contact_filename)
			else:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: contact %s is in use' % contact_filename)
		finally:
			listener.unsetuid()


def createContactGroup(grpname, contactlist):
	global __contactgrpsdir
	global __contactsdir

	listener.setuid(0)
	try:
		filename = '%s%s.conf' % (__contactgrpsdir, grpname)
		fp = open(filename, 'w')
		fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
		fp.write('#          Please use univention-admin instead.\n')
		fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
		fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
		fp.write('#          stattdessen den Univention Admin.\n')
		fp.write('\n')
		fp.write('object UserGroup "%s"{\n' % grpname)
		fp.write('    display_name = "%s"\n' % grpname)
		#fp.write('    alias                Gruppe %s\n' % grpname)
		#fp.write('    members              %s\n' % ', '.join(contactlist))
		fp.write('}\n')
		fp.close()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: contactgroup %s written: members=%s' % (grpname, contactlist))
		# create missing contacts
		for contact in contactlist:
			if not os.path.exists(os.path.join(__contactsdir, '%s.conf' % contact)):
				createContact(contact)

		# create default timeperiod if missing
		createDefaultTimeperiod()

	finally:
		listener.unsetuid()


def updateContactGroup(fqdn, new, old):
	cg_old = [__fallbackContact]
	cg_new = [__fallbackContact]
	if old and 'univentionNagiosEmail' in old and old['univentionNagiosEmail']:
		cg_old = old['univentionNagiosEmail']
	if new and 'univentionNagiosEmail' in new and new['univentionNagiosEmail']:
		cg_new = new['univentionNagiosEmail']

	if hostDeleted(new, old):
		# host deleted --> remove contact group

		cg_filename = os.path.join(__contactgrpsdir, 'cg-%s.conf' % fqdn)
		if os.path.exists(cg_filename):
			listener.setuid(0)
			try:
				os.unlink(cg_filename)
			finally:
				listener.unsetuid()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: removed contactgroup for host %s' % fqdn)

		# remove old contacts if unused
		for contact in cg_old:
			removeContactIfUnused(contact)
	else:
		# host has been updated
		createContactGroup('cg-%s' % fqdn, cg_new)

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: wrote contactgroup for host %s' % fqdn)

		# find deleted contacts
		for contact in cg_old:
			if contact not in cg_new:
				removeContactIfUnused(contact)


def readHostGroup(grpname):
	global __hostgrpsdir
	grp_filename = os.path.join(__hostgrpsdir, '%s.conf' % grpname)

	listener.setuid(0)
	try:
		if not os.path.exists(grp_filename):
			return []
		fp = open(grp_filename, 'r')
		content = fp.read()
		fp.close()
		res = re.findall(r'match\(\"(?:(?:[a-zA-Z]|[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]).)*(?:[A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])"', content)
		members = []
		if res:
			members = []
			for member in res:
				member = re.sub(r'match\(', '', member)
				member = re.sub(r'\"', '', member)
				members.append(member)
		return members
	finally:
		listener.unsetuid()


def writeHostGroup(grpname, members):
	global __hostgrpsdir
	grp_filename = os.path.join(__hostgrpsdir, '%s.conf' % grpname)

	listener.setuid(0)
	try:
		fp = open(grp_filename, 'w')
		fp.write('object HostGroup "%s" {\n' % grpname)
		fp.write('    display_name = "%s"\n' % grpname)
		#fp.write('    alias              Hostgroup %s\n' % grpname)
		for member in members:
			fp.write('    assign where match("{}", host.name)\n'.format(member))
		fp.write('}')
		fp.close()
	finally:
		listener.unsetuid()


def deleteHostGroup(grpname):
	global __hostgrpsdir
	grp_filename = os.path.join(__hostgrpsdir, '%s.conf' % grpname)

	listener.setuid(0)
	try:
		if os.path.exists(grp_filename):
			os.unlink(os.path.join(__servicesdir, grp_filename))
	finally:
		listener.unsetuid()


def removeFromHostGroup(grpname, fqdn):
	old_members = readHostGroup(grpname)
	if old_members:
		new_members = []
		# replacement for:    new_members = filter(lambda x: x != fqdn, old_members)
		new_members = [item for item in old_members if item != fqdn]

		if new_members:
			writeHostGroup(grpname, new_members)
		else:
			deleteHostGroup(grpname)


def addToHostGroup(grpname, fqdn):
	members = readHostGroup(grpname)
	if fqdn not in members:
		members.append(fqdn)
	writeHostGroup(grpname, members)


def handleService(dn, new, old):
	global __servicesdir
	global __contactgrpsdir
	if old:
		listener.setuid(0)
		try:
			for fn in os.listdir(__servicesdir):
				if fn.find("%s," % old['cn'][0]) == 0:
					os.unlink(os.path.join(__servicesdir, fn))
		finally:
			listener.unsetuid()

	if new:
		listener.setuid(0)
		try:
			if 'univentionNagiosHostname' in new and new['univentionNagiosHostname']:
				for host in new['univentionNagiosHostname']:
					filename = os.path.join(__servicesdir, '%s,%s.conf' % (new['cn'][0], host))
					fp = open(filename, 'w')
					fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
					fp.write('#          Please use univention-admin instead.\n')
					fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
					fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
					fp.write('#          stattdessen den Univention Admin.\n')
					fp.write('\n')
					fp.write('object Service  "%s"{\n' % new['cn'][0])
					fp.write('    host_name = "%s"\n' % host)
					#fp.write('    service_description     %s\n' % new['cn'][0])

					if 'univentionNagiosUseNRPE' in new and new['univentionNagiosUseNRPE'] and new['univentionNagiosUseNRPE'][0] == '1':
						fp.write('    check_command = "nrpe"\n')
						fp.write('    vars.nrpe_command = "{}"\n'.format(new['cn'][0]))
					else:
						if 'univentionIcingaCheckCommand' in new and 'univentionIcingaCheckArgs' in new and new['univentionIcingaCheckArgs'] and new['univentionIcingaCheckArgs'][0]:
							fp.write('    check_command = "%s"\n' % (new['univentionIcingaCheckCommand'][0]))
							for checkArg in new['univentionIcingaCheckArgs']:
								try:
									checkVar, checkVarValue = checkArg.split('=')
									fp.write('    {} = "{}"\n'.format(checkVar, checkVarValue))
								except Exception as e:
									univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: Could not write CheckArgs for service {} CheckArgs: {} Exception: {}'.format(new['cn'], new['univentionIcingaCheckArgs'], e))
						if 'univentionIcingaCheckCommand' in new:
							fp.write('    check_command = "%s"\n' % new['univentionIcingaCheckCommand'][0])
						else:
							univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: No check command was set for {} - icinga2 will report an error'.format(new['cn'][0]))

					fp.write('    check_interval = %sm\n' % new['univentionNagiosNormalCheckInterval'][0])
					fp.write('    retry_interval = %sm\n' % new['univentionNagiosRetryCheckInterval'][0])
					fp.write('    max_check_attempts = "%s"\n' % new['univentionNagiosMaxCheckAttempts'][0])
					fp.write('    check_period = "%s"\n' % new['univentionNagiosCheckPeriod'][0])
					#fp.write('    notification_interval = "%s"\n' % new['univentionNagiosNotificationInterval'][0])
					#fp.write('    notification_period  = "%s"\n' % new['univentionNagiosNotificationPeriod'][0])
					#fp.write('    notification_options = "%s"\n' % new['univentionNagiosNotificationOptions'][0])
					#fp.write('    contact_groups = "cg-%s"\n' % host)
					fp.write('}\n')
					fp.close()

					cg_filename = os.path.join(__contactgrpsdir, 'cg-%s.conf' % host)
					if not os.path.exists(cg_filename):
						univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: handleService: contactgrp for host %s does not exist - using fallback' % host)

						createContactGroup('cg-%s' % host, [__fallbackContact])
						listener.setuid(0)

		finally:
			listener.unsetuid()


def getUniventionComputerType(new):
	if not new or 'objectClass' not in new:
		return 'unknown'

	if new and 'objectClass' in new:
		if 'univentionClient' in new['objectClass']:
			if 'posixAccount' in new['objectClass'] or 'shadowAccount' in new['objectClass']:
				return 'client'
			else:
				return 'ipmanagedclient'
		elif 'univentionMacOSClient' in new['objectClass']:
			return 'macos'
		elif 'univentionMobileClient' in new['objectClass']:
			return 'mobileclient'
		elif 'univentionThinClient' in new['objectClass']:
			return 'thinclient'
		elif 'univentionWindows' in new['objectClass']:
			return 'windows'
		elif 'univentionWindows' in new['objectClass']:
			return 'windows'
		elif 'univentionMemberServer' in new['objectClass']:
			return 'memberserver'
		elif 'univentionDomainController' in new['objectClass']:
			if 'univentionServerRole' in new:
				for role in ['master', 'backup', 'slave']:
					if role in new['univentionServerRole']:
						return 'domaincontroller_%s' % role
	return 'unknown'


def createHostExtInfo(fqdn, new):
	global __exthostinfo_mapping
	global __hostextinfodir

	fn = os.path.join(__hostextinfodir, '%s.conf' % fqdn)

	if new:
		hosttype = getUniventionComputerType(new)
		if hosttype not in __exthostinfo_mapping:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: createHostExtInfo: unknown host type "%s" of %s' % (hosttype, fqdn))
			return

		listener.setuid(0)
		try:
			fp = open(fn, 'w')
			fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
			fp.write('#          Please use univention-admin instead.\n')
			fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
			fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
			fp.write('#          stattdessen den Univention Admin.\n')
			fp.write('\n')
			fp.write('define hostextinfo {\n')
			fp.write('    host_name               %s\n' % fqdn)
			fp.write('    icon_image              %s\n' % __exthostinfo_mapping[hosttype]['icon_image'])
			fp.write('    vrml_image              %s\n' % __exthostinfo_mapping[hosttype]['vrml_image'])
			fp.write('    statusmap_image         %s\n' % __exthostinfo_mapping[hosttype]['statusmap_image'])
			fp.write('}\n')
			fp.close()

		finally:
			listener.unsetuid()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: extended info for host %s written' % fqdn)


def removeHostExtInfo(fqdn):
	global __hostextinfodir
	fn = os.path.join(__hostextinfodir, '%s.conf' % fqdn)
	if os.path.exists(fn):
		listener.setuid(0)
		try:
			os.unlink(fn)
		finally:
			listener.unsetuid()


def removeHost(fqdn):
	global __hostextinfodir
	fn = os.path.join(__hostsdir, '%s.conf' % fqdn)
	if os.path.exists(fn):
		listener.setuid(0)
		try:
			os.unlink(fn)
		finally:
			listener.unsetuid()


def handleHost(dn, new, old):
	global __hostsdir
	global __contactgrpsdir
	global __predefinedTimeperiod

	# avoid additional ldap requests - building fqdn by combining "cn" and baseconfig variable "domainname"
	host = ''
	oldfqdn = 'unknown'
	newfqdn = 'unknown'

	olddomain = listener.baseConfig['domainname']
	if old and 'associatedDomain' in old and old['associatedDomain']:
		olddomain = old['associatedDomain'][0]
	if old:
		if 'cn' in old and old['cn']:
			host = old['cn'][0]
			oldfqdn = host + '.' + olddomain
		else:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: unable to determine old fqdn for %s' % str(dn))
			host = 'unknown'
			oldfqdn = host + '.unknown'
	old_host_filename = os.path.join(__hostsdir, '%s.conf' % oldfqdn)

	newdomain = listener.baseConfig['domainname']
	if new and 'associatedDomain' in new and new['associatedDomain']:
		newdomain = new['associatedDomain'][0]
	if new:
		if 'cn' in new and new['cn']:
			host = new['cn'][0]
			newfqdn = host + '.' + newdomain
		else:
			univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: unable to determine new fqdn for %s' % str(dn))
			host = 'unknown'
			newfqdn = host + '.unknown'
	new_host_filename = os.path.join(__hostsdir, '%s.conf' % newfqdn)

	# determine grpname
	# default: AllHosts
	# if host object resides within ou or container then parts of ou/container's dn is used as groupname
	grpname = 'AllHosts'
	ldapbase = listener.baseConfig['ldap/base']
	result = re.search('^cn=%s(,.*?)?,%s$' % (host, ldapbase), dn)
	if result and result.group(1):
		grpname = re.sub(',\w+=', '_', result.group(1))[1:]

	# fqdn changed ==> remove old entry and create new ones
	if oldfqdn != newfqdn and new and old:
		listener.setuid(0)
		try:
			if os.path.exists(old_host_filename):
				os.unlink(old_host_filename)
		finally:
			listener.unsetuid()
		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: fqdn changed: host %s deleted' % oldfqdn)

		# remove contact group and contacts
		updateContactGroup(oldfqdn, {}, old)

		# remove host from hostgroup
		removeFromHostGroup(grpname, oldfqdn)

		# remove ext host info
		removeHostExtInfo(oldfqdn)

	# check if host has been deleted or nagios support disabled
	if hostDeleted(new, old):
		listener.setuid(0)
		try:
			if os.path.exists(old_host_filename):
				os.unlink(old_host_filename)
		finally:
			listener.unsetuid()
		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: host %s deleted' % oldfqdn)

		# remove contact group and contacts
		updateContactGroup(oldfqdn, new, old)

		# remove host from hostgroup
		removeFromHostGroup(grpname, oldfqdn)

		removeHostExtInfo(oldfqdn)

		removeHost(oldfqdn)

	elif new:
		if not ('aRecord' in new and new['aRecord']):
			univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: missing aRecord (%s)' % dn)
			return

		listener.setuid(0)
		try:
			fp = open(new_host_filename, 'w')
			fp.write('# Warning: This file is auto-generated and might be overwritten.\n')
			fp.write('#          Please use univention-admin instead.\n')
			fp.write('# Warnung: Diese Datei wurde automatisch generiert und wird\n')
			fp.write('#          automatisch ueberschrieben. Bitte benutzen Sie\n')
			fp.write('#          stattdessen den Univention Admin.\n')
			fp.write('\n')
			fp.write('object Host "%s" {\n' % newfqdn)
			#fp.write('    host_name               %s\n' % newfqdn)
			#if 'description' in new and new['description']:
		#		fp.write('    alias                   %s (%s)\n' % (newfqdn, new['description'][0]))
		#	else:
		#		fp.write('    alias                   %s\n' % newfqdn)
			fp.write('    address = "%s"\n' % new['aRecord'][0])
			if 'univentionNagiosParent' in new and new['univentionNagiosParent']:
				fp.write('    parents = "%s"\n' % ', '.join(new['univentionNagiosParent']))

			#if listener.baseConfig.is_true("nagios/server/hostcheck/enable", False):
			fp.write('    check_command = "hostalive"\n')

			fp.write('    max_check_attempts = "10"\n')
			#fp.write('    contact_groups          cg-%s\n' % newfqdn)

			if 'univentionIcingaHostVars' in new:
				for hostVar in new['univentionIcingaHostVars']:
					try:
						hostVar, hostVarValue = hostVar.split('=')
						fp.write('    {} = "{}"\n'.format(hostVar, hostVarValue))
					except Exception as e:
						univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: Could not write hostVars for host {} hostVars: {} Exception: {}'.format(new['cn'], new['univentionIcingaHostVars'], e))

			notification_interval = 0
			if "nagios/server/hostcheck/notificationinterval" in listener.baseConfig and listener.baseConfig["nagios/server/hostcheck/notificationinterval"]:
				notification_interval = listener.baseConfig["nagios/server/hostcheck/notificationinterval"]

			#fp.write('    notification_interval   %s\n' % notification_interval)
			#fp.write('    notification_period     %s\n' % __predefinedTimeperiod)
			#fp.write('    notification_options    d,u,r\n')
			fp.write('}\n')
			fp.close()

		finally:
			listener.unsetuid()

		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: host %s written' % newfqdn)

		if oldfqdn == newfqdn:
			updateContactGroup(newfqdn, new, old)
		else:
			updateContactGroup(newfqdn, new, {})

		addToHostGroup(grpname, newfqdn)

		#createHostExtInfo(newfqdn, new)


def handler(dn, new, old):

	global __reload

#	univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: IN dn=%s' % str(dn))
#	univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: IN old=%s' % str(old))
#	univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: IN new=%s' % str(new))

	if ((old and 'objectClass' in old and 'univentionNagiosServiceClass' in old['objectClass']) or
		(new and 'objectClass' in new and 'univentionNagiosServiceClass' in new['objectClass'])):
		handleService(dn, new, old)
		__reload = True

	elif ((old and 'objectClass' in old and 'univentionNagiosHostClass' in old['objectClass']) or
		(new and 'objectClass' in new and 'univentionNagiosHostClass' in new['objectClass'])):
		# check if the nagios related attributes were changed
		for attr in ['aRecord', 'associatedDomain', 'uid', 'cn', 'description', 'univentionNagiosParent', 'univentionIcingaEnabled', 'univentionIcingaCheckArgs', 'univentionIcingaHostEnabled', 'univentionIcingaHostVars', 'univentionNagiosEmail']:
			if not (new.get(attr, None) == old.get(attr, None)):
				handleHost(dn, new, old)
				__reload = True
				break

	elif ((old and 'objectClass' in old and 'univentionNagiosTimeperiodClass' in old['objectClass']) or
		(new and 'objectClass' in new and 'univentionNagiosTimeperiodClass' in new['objectClass'])):
		handleTimeperiod(dn, new, old)
		__reload = True


def initialize():
	global __confsubdirs
	dirs = ['']
	dirs.extend(__confsubdirs)

	for dir in dirs:
		dirname = os.path.join('/etc/icinga2/conf.d/conf.univention.d/', dir)
		univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: creating dir: %s' % dirname)
		if not os.path.exists(dirname):
			listener.setuid(0)
			try:
				os.mkdir(dirname)
			finally:
				listener.unsetuid()


def deleteTree(dirname):
	if os.path.exists(dirname):
		for f in os.listdir(dirname):
			fn = os.path.join(dirname, f)
			mode = os.stat(fn)[stat.ST_MODE]
			if stat.S_ISDIR(mode):
				deleteTree(fn)
			else:
				os.unlink(fn)
		os.rmdir(dirname)


def clean():
	dirname = '/etc/icinga2/conf.d/conf.univention.d/'
	if os.path.exists(dirname):
		listener.setuid(0)
		try:
			deleteTree(dirname)
		finally:
			listener.unsetuid()


def postrun():
	global __reload

	if __reload:
		global __initscript
		initscript = __initscript
		# restart nagios if not running and nagios/server/autostart is set to yes/true/1
		# otherwise if nagios is running, ask nagios to reload config
		p = subprocess.Popen(('pidof', '/usr/lib/x86_64-linux-gnu/icinga2/sbin/icinga2'), stdout=subprocess.PIPE)
		pidlist, stderr = p.communicate()
		listener.setuid(0)
		null = open(os.path.devnull, 'w')
		try:
			retcode = subprocess.call(('icinga2', 'daemon', '-C'), stdout=null, stderr=null)
		finally:
			null.close()
		listener.unsetuid()
		if not pidlist.strip():
			if retcode == 0:
				if listener.baseConfig.is_true("icinga2/server/autostart", False):
					univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: icinga2 not running - restarting server')

					listener.setuid(0)
					try:
						listener.run(initscript, ['icinga2', 'restart'], uid=0)
					finally:
						listener.unsetuid()
			else:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: icinga2 reported an error. Please restart icinga2 manually: "systemctl restart icinga2.service".')
				listener.unsetuid()

		else:
			if retcode == 0:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.INFO, 'ICINGA2-SERVER: reloading server')
				listener.setuid(0)
				try:
					listener.run(initscript, ['icinga2', 'reload'], uid=0)
				finally:
					listener.unsetuid()
			else:
				univention.debug.debug(univention.debug.LISTENER, univention.debug.ERROR, 'ICINGA2-SERVER: icinga2 reported an error. Please restart icinga2 manually: "systemctl restart icinga2.service".')
				listener.unsetuid()
		__reload = False
