# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2022-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

"""
Configuration checks for lusd_fix_no_class_in_input_data in LK LUSD import.
"""

from ucsschool.importer.exceptions import InitialisationError
from ucsschool.importer.utils.configuration_checks import ConfigurationChecks


class LUSDImportFixNoClassInInputDataConfigurationChecks(ConfigurationChecks):
    def test_00_required_config_keys(self):
        if not self.config.get("lusd_fix_no_class_in_input_data"):
            raise InitialisationError(
                "No lusd_fix_no_class_in_input_data was specified in the configuration."
            )

    def test_01_lusd_fix_no_class_in_input_data(self):
        if not isinstance(self.config["lusd_fix_no_class_in_input_data"], dict):
            raise InitialisationError(
                'Configuration key "lusd_fix_no_class_in_input_data" must contain a configuration for key_name and class_name.'  # noqa: E501
            )
        for attr in ("key_name", "class_name"):
            if not self.config["lusd_fix_no_class_in_input_data"].get(attr):
                raise InitialisationError(
                    'No {!r} was specified in the "lusd_fix_no_class_in_input_data" configuration.'.format(
                        attr
                    )
                )
