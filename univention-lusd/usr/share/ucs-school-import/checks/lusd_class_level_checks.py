# -*- coding: utf-8 -*-
#
# Copyright 2019-2022 Univention GmbH
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

"""
Configuration checks for class_level in LK LUSD import.
"""

import re
from ucsschool.importer.exceptions import InitialisationError
from ucsschool.importer.utils.configuration_checks import ConfigurationChecks


class LUSDImportClassLevelConfigurationChecks(ConfigurationChecks):
	def test_00_required_config_keys(self):
		for attr in ('class_level'):
			if not self.config.get(attr):
				raise InitialisationError('No {!r} was specified in the configuration.'.format(attr))

	def test_01_class_level(self):
		if not isinstance(self.config['class_level'], dict):
			raise InitialisationError('Configuration key "class_level" must point to a mapping.')
		for attr in ('key', 'mapping', 'unknown_is_error'):
			if not self.config['class_level'].get(attr):
				raise InitialisationError('No {!r} was specified in the "class_level" configuration.'.format(attr))
		if self.config['class_level']['key'] not in self.config['csv']['mapping'].values():
			raise InitialisationError(
				'"class_level:key" {!r} is missing in in the "csv:mapping" configuration.'.format(
					self.config['class_level']['key']
				))
		if not isinstance(self.config['class_level']['mapping'], dict):
			raise InitialisationError('Configuration key "class_level:mapping" must point to a mapping.')
		for k in self.config['class_level']['mapping'].keys():
			try:
				re.compile(k)
			except re.error as exc:
				raise InitialisationError(
					'Configuration "class_level:mapping:{}" is not a valid regular expression: {}'.format(k, exc)
				)
