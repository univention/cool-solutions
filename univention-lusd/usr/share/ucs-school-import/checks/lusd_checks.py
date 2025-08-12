# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2022-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

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
