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
Configuration checks for lusd_fix_no_class_in_input_data in LK LUSD import.
"""

import re
from ucsschool.importer.exceptions import InitialisationError
from ucsschool.importer.utils.configuration_checks import ConfigurationChecks


class LUSDImportFixNoClassInInputDataConfigurationChecks(ConfigurationChecks):
	def test_00_required_config_keys(self):
		if not self.config.get('lusd_fix_no_class_in_input_data'):
			raise InitialisationError('No lusd_fix_no_class_in_input_data was specified in the configuration.')

	def test_01_lusd_fix_no_class_in_input_data(self):
		if not isinstance(self.config['lusd_fix_no_class_in_input_data'], dict):
			raise InitialisationError('Configuration key "lusd_fix_no_class_in_input_data" must contain a configuration for key_name and class_name.')
		for attr in ('key_name', 'class_name'):
			if not self.config['lusd_fix_no_class_in_input_data'].get(attr):
				raise InitialisationError('No {!r} was specified in the "lusd_fix_no_class_in_input_data" configuration.'.format(attr))
