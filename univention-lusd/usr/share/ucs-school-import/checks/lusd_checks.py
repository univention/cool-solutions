# -*- coding: utf-8 -*-
#
# Copyright 2022 Univention GmbH
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
Configuration checks for gpg settings in LUSD import.
"""

import os.path
import gnupg
from ucsschool.importer.exceptions import InitialisationError
from ucsschool.importer.utils.configuration_checks import ConfigurationChecks


class LUSDImportGPGConfigurationChecks(ConfigurationChecks):
    gpg_import_cmdline = "gpg --homedir {gpghome!r} --import <keyfile>"

    def test_00_required_config_keys(self):
        for attr in ("gpghome", "passphrase_file"):
            if not self.config.get(attr):
                raise InitialisationError(
                    "No {!r} was specified in the configuration.".format(attr)
                )

    def test_01_gpghome(self):
        if not os.path.exists(self.config["gpghome"]):
            raise InitialisationError(
                "Path {!r} does not exist.".format(self.config["gpghome"])
            )
        if not os.path.isdir(self.config["gpghome"]):
            raise InitialisationError(
                "Path {!r} is not a directory.".format(self.config["gpghome"])
            )
        if not os.path.exists(
            os.path.join(self.config["gpghome"], "private-keys-v1.d")
        ):
            cmdline = self.gpg_import_cmdline.format(gpghome=self.config["gpghome"])
            raise InitialisationError(
                "Please import private PGP key (cmdline: {!r}).".format(cmdline)
            )

    def test_02_gpg_seckey(self):
        gpg = gnupg.GPG(gnupghome=self.config["gpghome"])
        if not gpg.list_keys(True):
            cmdline = self.gpg_import_cmdline.format(gpghome=self.config["gpghome"])
            raise InitialisationError(
                "Please import private PGP key (cmdline: {!r}).".format(cmdline)
            )

    def test_03_gpg_passphrase_file(self):
        if not os.path.exists(self.config["passphrase_file"]):
            raise InitialisationError(
                "Passphrase file {!r} does not exist.".format(
                    self.config["passphrase_file"]
                )
            )
        try:
            with open(self.config["passphrase_file"], "r") as fp:
                passphrase = fp.read().strip()
        except IOError as exc:
            raise InitialisationError(
                "Reading passphrase file {!r}: {}".format(
                    self.config["passphrase_file"], exc
                )
            )
        if not passphrase:
            raise InitialisationError(
                "Passphrase file {!r} is empty.".format(self.config["passphrase_file"])
            )
