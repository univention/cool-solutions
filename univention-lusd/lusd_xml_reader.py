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
XML reader for importing users.
"""

import re
import base64
from six import iteritems
import xmltodict
import gnupg
from ucsschool.importer.models.import_user import ImportUser
from ucsschool.importer.exceptions import UcsSchoolImportError, UcsSchoolImportFatalError
from ucsschool.importer.reader.http_api_csv_reader import HttpApiCsvReader
try:
    from typing import Dict
    from typing.re import Pattern
except ImportError:
    pass


class DecryptionError(UcsSchoolImportFatalError):
    pass


class EmptyXMLLevel(UcsSchoolImportFatalError):
    pass


class RegularExpressionMissingNamedGroup(UcsSchoolImportError):
    pass


class RegularExpressionNoMatch(UcsSchoolImportError):
    pass


class XmlReader(HttpApiCsvReader):
    """
    Reads XML files and turns flat subtrees to ImportUser objects.
    """
    xml_item_path = ('NetzwerknutzerDaten', 'DatenTable')  # branches to descend to find list of items

    def __init__(self):
        super(XmlReader, self).__init__()
        # cache and compile class_level configuration
        if 'class_level' in self.config:
            self.class_level_key = self.config['class_level']['key']
            self.class_level_mapping = dict(
                (re.compile(k), v) for k, v in iteritems(self.config['class_level']['mapping'])
            )  # type: Dict[Pattern, str]
            self.class_level_unknown_is_error = self.config['class_level']['unknown_is_error']
            self.class_level_config = True
        else:
            self.class_level_config = False
        if 'lusd_normalize_classes' in self.config:
            self.lusd_normalize_classes = self.config['lusd_normalize_classes']
        else:
            self.lusd_normalize_classes = False
        if 'lusd_normalize_classes' in self.config:
            self.lusd_normalize_classes = self.config['lusd_normalize_classes']
        else:
            self.lusd_normalize_classes = False
        if 'lusd_fix_no_class_in_input_data' in self.config:
                self.lusd_fix_no_class_in_input_data = True
                self.lusd_fix_no_class_in_input_data_key_name = self.config['lusd_fix_no_class_in_input_data']['key_name']
                self.lusd_fix_no_class_in_input_data_class_name = self.config['lusd_fix_no_class_in_input_data']['class_name']
        else:
            self.lusd_fix_no_class_in_input_data = False

    def read(self, *args, **kwargs):
        """
        Generate dicts from a PGP encrypted XML file.

        :param args: ignored
        :param dict kwargs: ignored
        :return: iterator over list of dicts
        :rtype: Iterator
        """
        decrypted_xml = self.decrypt_pgp_file()
# HIER!
        fixed_xml = self.fix_xml(decrypted_xml)

        # walk XML tree
        self.logger.debug('Reading XML...')
        doc = xmltodict.parse(fixed_xml, encoding='utf-8')
        # descend tree until level of items
        items = doc
        for level in self.xml_item_path:
            items = items.get(level)
            if not items:
                raise EmptyXMLLevel('Found no items in {!r}, when descending XML path {!r}.'.format(
                    level, self.xml_item_path))
        for item in items:
            self.logger.debug('Found item: %r', item)
            self.entry_count += 1
            if self.lusd_fix_no_class_in_input_data:
                if not self.lusd_fix_no_class_in_input_data_key_name in item.keys():
                    self.logger.warning('Adding pseudo class {} to item {}'.format(self.lusd_fix_no_class_in_input_data_class_name, item))
                    item.update({self.lusd_fix_no_class_in_input_data_key_name: self.lusd_fix_no_class_in_input_data_class_name})
            self.input_data = item.values()
            if not self.fieldnames:
                self.fieldnames = item.keys()
            yield {
                key.strip(): (value or '').strip()
                for key, value in iteritems(item)
            }

    def handle_input(self, mapping_key, mapping_value, csv_value, import_user):
        """
        * normalize class names
        * transform values of property `class_level:key` using mapping in
            `class_level:mapping`
        """
        if mapping_value == 'school_classes':
            # only use class names after slash Task 16300
            if self.lusd_normalize_classes:
                lusd_class_regex = '.*\/'
                csv_value = re.sub(lusd_class_regex, '', csv_value)
            if self.lusd_normalize_classes:
                csv_value = re.sub('^-\/', '', csv_value)
                csv_value = re.sub('\/', '-', csv_value)
            # remove umlauts
            csv_value = ImportUser.normalize(csv_value)
            # school_classes will also be handled by HttpApiCsvReader.handle_input()
            # new csv_value will be used there.
            # True will be returned by super().handle_input() call below
        if self.class_level_config:
            if mapping_value == self.class_level_key:
                # transform value using mapping in class_level:mapping
                new_value = csv_value
                for k, v in iteritems(self.class_level_mapping):
                    m = k.match(csv_value)
                    if m and v == '$class_level':
                        try:
                            new_value = m.groupdict()['class_level']
                        except KeyError:
                            msg = 'The RE {!r} matched {!r}={!r}, but the named group "class_level" was not in the RE.'.format(
                                k.pattern, self.class_level_key, csv_value)
                            if self.class_level_unknown_is_error:
                                raise RegularExpressionMissingNamedGroup(msg)
                            else:
                                self.logger.warning(msg)
                        break
                    elif m and v == 'ignore':
                        self.logger.info('Ignoring %r=%r.', self.class_level_key, csv_value)
                        break
                    elif m:
                        new_value = v
                        break
                else:
                    msg = 'No RE in "class_level:mapping" matched {!r}={!r}.'.format(self.class_level_key, csv_value)
                    if self.class_level_unknown_is_error:
                        raise RegularExpressionNoMatch(msg)
                    else:
                        self.logger.warning(msg)
                if new_value != csv_value:
                    if hasattr(import_user, self.class_level_key):
                        setattr(import_user, self.class_level_key, new_value)
                    else:
                        import_user.udm_properties[self.class_level_key] = new_value
                    return True
                else:
                    # no transformation if data, let csv_reader.map() handle saving the data into import_user
                    return False
        return super(XmlReader, self).handle_input(mapping_key, mapping_value, csv_value, import_user)

    def decrypt_pgp_file(self):
        """
        Decrypts PGP encrypted data in :py:attr:`self.filename`.

        :return: decrypted data
        :rtype: str
        """
        self.logger.info('Reading passphrase from %r...', self.config['passphrase_file'])
        with open(self.config['passphrase_file'], 'r') as fp:
            # base64 → byte → string
            passphrase = base64.b64decode(fp.read().strip()).decode('UTF-8')
        self.logger.info('Decrypting %r...', self.filename)
        gpg = gnupg.GPG(gnupghome=self.config['gpghome'])
        with open(self.filename, 'rb') as fpr:
#            status = gpg.decrypt_file(fpr, passphrase=passphrase)
            data = fpr.read()                                   # NEW
            str_data = data.decode('UTF-8')                     # NEW 
            status = gpg.decrypt(str_data, passphrase=passphrase) #NEW
            self.logger.info('GnuPG decryption status: %r', status.status)
            if not status.ok:
                raise DecryptionError('Could not decrypt %r: %s', self.filename, status.stderr)
        return status.data

    @staticmethod
    def fix_xml(xml_str):
        """
        Fixes bad "encoding" property in `xml_str`.

        :param str xml_str: XML string
        :return: text with fixed "encoding" property
        :rtype: str
        """
        return xml_str.replace('<?xml version="1.0" encoding="utf-16"?>', '<?xml version="1.0" encoding="utf-8"?>')
