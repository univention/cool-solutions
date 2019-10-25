# -*- coding: utf-8 -*-
#
# Univention domain quota
#  Syntax extensions for user domain quota
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

import univention.admin.localization
import univention.admin.syntax

from univention.admin.syntay import UCS_Server

translation = univention.admin.localization.translation('univention.admin.syntax.domainquota')
_ = translation.translate


class siprefix(univention.admin.syntax.select):
	size = 'OneThird'
	choices = [
		('MiB', _('MiB')),
		('GiB', _('GiB')),
	]
	default = 'GiB'


class OneThirdAbsolutePath(univention.admin.syntax.absolutePath):
	size = "OneThird"


class OneThirdInteger(univention.admin.syntax.integer):
	size = "OneThird"
	max_length = 3

	@classmethod
	def parse(self, text):
		if len(text) > self.max_length:
			raise univention.admin.uexceptions.valueError(_("Maximum length for Quota is %s characters") % self.max_length)
		return super(univention.admin.syntax.integer, self).parse(text)


class domainquota(complex):
	subsyntaxes = ((_('Host'), UCS_Server), (_('Path'), OneThirdAbsolutePath), (_('Quota'), OneThirdInteger), (_('Unit'), siprefix))
	all_required = True
