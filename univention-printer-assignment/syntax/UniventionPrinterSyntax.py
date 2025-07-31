# SPDX-FileCopyrightText: 2024-2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

from univention.admin.syntax import select, UDM_Objects


class UniventionPrinterSyntax(UDM_Objects):
    """UDM syntax class for selecting Univention printer objects.

    This syntax provides a selection interface for printer shares within
    UDM. It filters printer objects based on the
    'univentionPrinter' object class and displays them using their name attribute.

    Used by extended printer attributes to allow users to select from available
    printers in the UDM interface.
    """

    udm_modules = ('shares/printer', )
    label = '%(name)s'
    empty_value = False
    udm_filter = "(objectclass=univentionPrinter)"
    simple = True