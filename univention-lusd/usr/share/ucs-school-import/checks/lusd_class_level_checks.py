# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2022-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

"""
Configuration checks for class_level in LUSD import.
"""

import re
from ucsschool.importer.exceptions import InitialisationError
from ucsschool.importer.utils.configuration_checks import ConfigurationChecks


class LUSDImportClassLevelConfigurationChecks(ConfigurationChecks):
    def test_00_required_config_keys(self):
        for attr in ["class_level"]:
            if not self.config.get(attr):
                raise InitialisationError(
                    "No {!r} was specified in the configuration.".format(attr)
                )

        def test_01_class_level(self):
            if not isinstance(self.config["class_level"], dict):
                raise InitialisationError(
                    'Configuration key "class_level" must point to a mapping.'
                )
            for attr in ("key", "mapping", "unknown_is_error"):
                if not self.config["class_level"].get(attr):
                    raise InitialisationError(
                        'No {!r} was specified in the "class_level" configuration.'.format(
                            attr
                        )
                    )
                if (
                    self.config["class_level"]["key"]
                    not in self.config["csv"]["mapping"].values()
                ):
                    raise InitialisationError(
                        '"class_level:key" {!r} is missing in in the "csv:mapping" configuration.'.format(
                            self.config["class_level"]["key"]
                        )
                    )
                if not isinstance(self.config["class_level"]["mapping"], dict):
                    raise InitialisationError(
                        'Configuration key "class_level:mapping" must point to a mapping.'
                    )
                for k in self.config["class_level"]["mapping"].keys():
                    try:
                        re.compile(k)
                    except re.error as exc:
                        raise InitialisationError(
                            'Configuration "class_level:mapping:{}" is not a valid regular expression: {}'.format(
                                k, exc
                            )
                        )
