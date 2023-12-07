# -*- coding: utf-8 -*-
#
# Copyright 2017-2023 Univention GmbH
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
# you and Univention.
#
# This program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <https://www.gnu.org/licenses/>.
#

from __future__ import absolute_import
from univention.listener import ListenerModuleHandler
import univention.admin.uexceptions


class MoodleGroupSetter(ListenerModuleHandler):
	class Configuration(object):
		name = 'MoodleGroupSetter'
		description = 'Configures the Moodle Teacher and Student as extended attributes'
		ldap_filter = '(&(ucsschoolRole=school_class*)(objectClass=ucsschoolGroup))'
		attributes = ['memberUid', 'objectClass', 'univentionFreeAttribute20', 'univentionFreeAttribute19']

	def create(self, dn, new):
		self.logger.debug('dn: %r', dn)
		changes=[]
		if not 'univentionFreeAttributes'.encode('utf-8') in new['objectClass']:
			changes.append(('objectClass','','univentionFreeAttributes'.encode('utf-8')))
		if 'memberUid' in new:
			for i in new['memberUid']:
				self.logger.debug('memberUID: %s', i)
				try:
					result = self.lo.search(filter='(&(uid=%s)(ucsschoolRole=student*))'%i.decode('utf-8'), attr=['dn'])
					if (len(result)!=0):
						changes.append(('univentionFreeAttribute20','',i ))
					result = self.lo.search(filter='(&(uid=%s)(ucsschoolRole=teacher*))'%i.decode('utf-8'), attr=['dn'])
					if (len(result)!=0):
						changes.append(('univentionFreeAttribute19','',i ))
				
				except:
					self.logger.error('Ldap Search error for user: %s'%i.decode('utf-8'))
		self.logger.debug('Changes: %s',changes)

		if len(changes)!=0:
			try:
				self.lo.modify(dn=dn,changes=changes,ignore_license=True)
			except Exception as e:
				self.logger.error('Write Error with Exception: %s', e)

	def modify(self, dn, old, new, old_dn):
		self.logger.error('dn: %r', dn)
		self.logger.error('changed attributes: %r', self.diff(old, new))
		self.logger.error('old attributes: %r', old)

		changes=[]
		if not 'univentionFreeAttributes'.encode('utf-8') in new['objectClass']:
			changes.append(('objectClass','','univentionFreeAttributes'.encode('utf-8')))

		currentdiff=self.diff(old, new)
		if 'memberUid' in currentdiff:
			memberdiff=currentdiff['memberUid']
			if memberdiff[0] == None:
				removed = set()
				added = set(memberdiff[1])
			elif memberdiff[1] == None:
				removed = set(memberdiff[0])
				added = set()
			else:
				removed = set(memberdiff[0])-set(memberdiff[1])
				added = set(memberdiff[1])-set(memberdiff[0])
			if len(added)!=0:
				for i in added:
					student=False
					teacher=False
					self.logger.debug('memberUID: %s', i)
					try:
						result = self.lo.search(filter='(&(uid=%s)(ucsschoolRole=student*))'%i.decode('utf-8'), attr=['dn'])
						if (len(result)!=0):
							changes.append(('univentionFreeAttribute20','',i ))
						result = self.lo.search(filter='(&(uid=%s)(ucsschoolRole=teacher*))'%i.decode('utf-8'), attr=['dn'])
						if (len(result)!=0):
							changes.append(('univentionFreeAttribute19','',i ))
					except:
						self.logger.error('Ldap Search error for user: %s'%i.decode('utf-8'))
			if len(removed)!=0:
				for i in removed:
					if 'univentionFreeAttribute19' in old and i in old['univentionFreeAttribute19']:
						changes.append(('univentionFreeAttribute19',i,'' ))
					if 'univentionFreeAttribute20' in old and i in old['univentionFreeAttribute20']:
						changes.append(('univentionFreeAttribute20',i,'' ))
			
		if len(changes)!=0:
			try:
				self.lo.modify(dn=dn,changes=changes,ignore_license=True)
			except Exception as e:
				self.logger.error('Write Error with Exception: %s', e)

		#diff more unique members
		#is student -> Attribute 20
		#is teacher -> Attribute 19
		#diff removed uniqe members
		#is student -> Attribute 20
		#is teacher -> Attribute 19
		#write

	def remove(self, dn, old):
		self.logger.debug('dn: %r', dn)
