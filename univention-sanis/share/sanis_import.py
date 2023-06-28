#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Cool solutions -- SANIS import
#
# Like what you see? Join us!
# https://www.univention.com/about-us/careers/vacancies/
#
# Copyright 2023 Univention GmbH
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
# <https://www.gnu.org/licenses/>.

import os
import stat
import re
import subprocess
import json
import base64
from urllib import request
from univention.config_registry import ConfigRegistry

from sanis_tools import iterStore
from sanis_models import Person, Organisation, Kontext, Klassen, Mitglieder


class NoSchoolException(BaseException):
	pass


class DataExtractException(BaseException):
	pass


class SanisImport:

	api_url = None				# SANIS API URL
	token_url = None			# URL to acquire auth token
	cred_file = None			# file name to read credentials from

	token = None				# current auth token
	temp_base = None			# base for temp files

	pers_store = None			# personen
	org_store = None			# organisationen
	cont_store = None			# personenkontexte
	grp_store = None			# gruppen
	memb_store = None			# gruppenmitgliedschaften

	tempfiles = []				# to be cleaned up

	commands = []				# lines to be written into script

	# ucs@school roles mapped to the role strings in SANIS
	roles_to_prepare = {
		'teacher':		'Lehr',
		'student':		'Lern',
	}

	# Mapping of CSV attributes to their source attributes. currently all of these
	# attributes come from the person store. 'classes' are retrieved from group memberships
	# and also stored into the person record directly before exporting.
	headers = {
		'ID':			'id',
		'Vorname':		'vorname',
		'Familienname':	'familienname',
		'Geburtstag':	'geburtsdatum',
		'Klassen':		'classes',
	}

	# Start lines for the import script.
	script_header = [
		'#!/bin/bash',
		'',
		'# Importskript für SANIS Lehrer- und Schülerbestände',
		'',
	]

	def __init__(self, api_url, token_url, cred_file, verbose=False):
		""" Prepare object for use. Any errors throw exceptions and are not handled here. """

		self.api_url = api_url
		self.token_url = token_url
		self.cred_file = cred_file
		self.verbose = verbose

		self.token = self.get_token()

		# invent a prefix for temp files. Can be a directory or only a filename prefix.
		# Will be used here for JSON files as well as in the stores when switching
		# to file store. All temp files are cleaned up.
		self.temp_base = '/tmp/sanis_import_%d_' % os.getpid()

	def read_input_data(self):
		""" Read all data from SANIS API and store them in (internal) store objects.

			Note that we (temporarily?) save any JSON files in beautified form
			into files in current directory. If the debugging phase is over we
			should not need that anymore.
		"""

		# --------------- person -----------------
		pers_file = self.fetch_data('/personen')
		self.pers_store = iterStore(Person, pers_file, temp_base=self.temp_base)
		if self.verbose:
			self.pers_store.print_data()
		self.dump_json(pers_file, 'sanis_personen.json')

		# -------- "personenkontexte" --------------
		# Note that the 'personen' dataset already contains all of the data
		# needed by the 'personenkontext' logic. Therefore it is useless to
		# fetch the same data again here. Instead, we use the 'pers_file'
		# which we already have fetched.
		self.cont_store = iterStore(Kontext, pers_file, temp_base=self.temp_base)
		if self.verbose:
			self.cont_store.print_data()

		# ---------- schools (organizations) ------
		org_file = self.fetch_data('/organisationen')
		self.org_store = iterStore(Organisation, org_file, temp_base=self.temp_base)
		# too much debug
		#if verbose:
		#	self.org_store.print_data()
		self.dump_json(org_file, 'sanis_organisationen.json')

		# ------------ groups (only classes) -------------
		grp_file = self.fetch_data('/gruppen')
		self.grp_store = iterStore(Klassen, grp_file, temp_base=self.temp_base)
		if self.verbose:
			self.grp_store.print_data()
		self.dump_json(grp_file, 'sanis_gruppen.json')

		# ----------- membership ------------------
		# Just as for 'personenkontexte', the 'gruppenmitgliedschaften' membership
		# relations are already fully fetched by the '/gruppen' entry point.
		self.memb_store = iterStore(Mitglieder, grp_file, temp_base=self.temp_base)
		if self.verbose:
			self.memb_store.print_data()

	def _data_line(self, data):
		""" Returns one data line, according to the headers. Line is formatted
			according to a format specification which is easily readable without
			further conversion:

			*	delimited by comma
			*	all fields enclosed in double quotes
			*	if a field is an array: also delimit elements by commas.
			*	always the full count of columns, even if they are empty
		"""

		tmpa = []
		for element in data:
			if isinstance(element, list):
				element = ','.join(element)
			tmpa.append(element)

		# FIXME do we need to adjust the length of tmpa, given our input logic
		#		will always produce full-length arrays?

		return ','.join('"%s"' % x for x in tmpa)

	def extract_school_data(self, school, sanis_id):
		""" Extract CSV files to be imported for one school.

			Data is extracted by matching the organization with this <sanis_id>. Note
			that we shhould never use the 'stammorganisation' property because it is
			rather meaningless in multi-school roles, and will be determined/adjusted
			by the SiSoPi import logic whenever needed.

			Extract is saved into files with fixed names, and an internal array
			of strings will already collect the importer calls which will finally
			be written into the script to be created.

			Any consistency error will lead to an exception being thrown, so the
			user is explicitly warned about the data not being valid.
		"""

		for role, sanis_role in self.roles_to_prepare.items():
			print('Preparing data: [school=%s] [role=%s]' % (school, role))
			out_filename = 'import_%s_%s.csv' % (school, role)
			with open(out_filename, 'w') as out_handle:
				print(self._data_line(self.headers.keys()), file=out_handle)
				# find all contexts related to this SANIS ORG_ID
				for context in self.cont_store.find_all('org_id', sanis_id):
					# process only those with active status
					if context['status'] != 'aktiv':
						continue
					# process only those with the requested role
					if context['rolle'] != sanis_role:
						continue
					person = self.pers_store.find(context['person_id'])
					# We have some persons without birthdate: fix it with a constant!
					if person['geburtsdatum'] == '':
						person['geburtsdatum'] = '1999-09-09'
					# FIXME retrieve group memberships and store them in person['classes']
					person['classes'] = ['1a']		# this is to not create invalid students (must have at least one class)
					record = []
					for attr, iattr in self.headers.items():
						if iattr in person:
							record.append(person[iattr])
						else:
							record.append('-')
					print(self._data_line(record), file=out_handle)

			# We don't immediately write these commands into the to-be-executed script. This
			# is intentional: if anything fails while trying to write these files, the script
			# will not be written, and the user should not even think about executing any
			# import with these partly-damaged data.
			self.commands.append('/usr/share/ucs-school-import/scripts/ucs-school-user-import \\')
			self.commands.append('   --dry-run \\')
			self.commands.append('   --source_uid sanis \\')
			self.commands.append('   --conffile temp_config.json \\')
			self.commands.append('   --school %s \\' % school)
			self.commands.append('   --user_role %s \\' % role)
			self.commands.append('   --infile %s \\' % out_filename)
			self.commands.append('   --set output:new_user_passwords=passwords_%s_%s.csv' % (school, role))
			self.commands.append('')

	def write_command_script(self, out_filename):
		""" Write all the collected commands into the script to be executed. """

		with open(out_filename, 'w') as out_handle:
			for line in self.script_header:
				print(line, file=out_handle)
			for line in self.commands:
				print(line, file=out_handle)

		# ug+rwx
		os.chmod(out_filename, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXGRP | stat.S_IRGRP | stat.S_IWGRP )

	def __del__(self):
		""" Cleanup on program end. Currently only removes temp files. """

		for fname in self.tempfiles:
			try:
				os.unlink(fname)
			except BaseException:
				pass

	def get_token(self):
		""" Acquire a token from the login server.

			We currently do not care about how long this token is valid. If we really
			run into the problem that our data requests take too long -> we should
			implement kind of error handling in the request methods.
		"""

		# FIXME implement sensible error handling

		with open(self.cred_file, 'rb') as cred:
			clid = cred.readline().strip()
			clpw = cred.readline().strip()

		req = request.Request(self.token_url, data=b'grant_type=client_credentials', method='POST')
		# Preemptively add credentials
		req.add_header('Authorization', 'Basic %s' % base64.b64encode(b'%s:%s' % (clid, clpw)).decode('utf-8'))

		with request.urlopen(req) as resp:
			rtxt = resp.read()
			return json.loads(rtxt)['access_token']

	def fetch_data(self, entrypoint):
		""" Fetch a dataset from the SANIS entry point. Will be kept in a cache file while
			the program is running. (We read these cache files multiple times, therefore
			fetching directy and passing a stream does not make sense here)

			Returns the name of the file.
		"""

		# Resultfiles are now cleaned up
		resfile = '%sapi_%s.json' % (self.temp_base, entrypoint.translate({ord(i): None for i in '/_-.'}))

		# binary mode is correct here: response is expected to be UTF8-encoded, and the
		# file can hold this data without de-/reencoding
		with open(resfile, 'wb') as ofile:
			req = request.Request('%s%s' % (self.api_url, entrypoint))
			req.add_header('Authorization', 'Bearer %s' % self.token)
			with request.urlopen(req) as resp:
				while True:
					buf = resp.read(1024)
					if not len(buf):
						break
					ofile.write(buf)

		# All files created here are candidates for autodeletion on exit, so
		# add them to the tempfiles list.
		self.tempfiles.append(resfile)

		return resfile

	def create_config(self, inputfiles, outputfile):
		""" Merges JSON config files together and write the results as JSON
			into outfilename. Note inputfiles are processed in order: later
			files can override earlier files.

			Input files are allowed to contain comments; these are stripped
			before we try to parse the files.
		"""

		data = {}		# all data merged in

		for inputfile in inputfiles:
			with open(inputfile, 'r') as inp_handle:
				temp_lines = [re.sub('//.*', '', x.strip()) for x in inp_handle.readlines()]
				temp_dict = json.loads('\n'.join(temp_lines))
				data.update(temp_dict)
		with open(outputfile, 'w') as out_handle:
			json.dump(data, out_handle, indent=4)

	def get_school_mapping(self):
		""" Read local UCR variables that configure this import. We need:

			sanis_import/school_name_attribute=<attributename>
				this names the SANIS attribute of organizations we want to match
				against local schools. If this is not defined we assume 'kennung'.

			sanis_import/school/<local_school_name>=<value_of_school_mapping_attribute>
				this is the mapping which is used to match a local school to a
				school in SANIS.

			Function returns a dict with key = <school name in ucs> and val = <org id in Sanis>
			which can directly be used to iterate over schools for preparing the data.
		"""

		# for key in sorted(x for x in configRegistry if x.startswith('security/packetfilter/package/')):
		result = {}
		ucr = ConfigRegistry()
		ucr.load()
		attrname = ucr.get('sanis_import/school_name_attribute', 'kennung')
		for key in sorted([x for x in ucr if x.startswith('sanis_import/school/')]):
			shortkey = re.sub('^sanis_import/school/', '', key)
			# FIXME call @school library check does this school exists
			# check if we can match this school to a SANIS organization
			school = self.org_store.find(ucr[key], key=attrname)
			if school is None:
				raise NoSchoolException('Keine SANIS Organisation mit [%s] = [%s] gefunden' % (attrname, ucr[key]))
			result[shortkey] = school['id']

		return result

	def resolve_contexts(self):
		""" Resolve the list of GUIDs of the 'personenkontexte' data
			into the real objects. Current structure is:

				[context_id, org_id, pers_id, role]

			the org_id and pers_id are being looked up and replaced by the
			identifying string of the organization resp. prerson:

				[context_id, org_name, pers_name, role]

			Because we fetch the contexts from the 'personen' entrypoint we know for sure
			that ALL roles of ONE user are guaranteed to appear as one contiguous block. Therefore
			we do not need to iterate over all contexts just to find the ones for one user.
		"""

		for kontext in self.cont_store:
				org = self.org_store.resolve(kontext['org_id'], 'name')
				pers = self.pers_store.resolve(kontext['person_id'])
				print('pers: [%s] %s, role: %s at: %s' % (kontext['person_id'], pers, kontext['rolle'], org))

	def dump_stores_to_csv(self):
		""" Dump some selected stores into CSV files. This shall help to manually create some sets
			of import data for testing.
		"""

		self.pers_store.print_csv('store_users.csv')
		self.cont_store.print_csv('store_contexts.csv')
		self.org_store.print_csv('store_schools.csv')

	def dump_json(self, inputfile, outputfile):
		""" Only for debugging and/or auditing: print a beautified version of the JSON
			input data into the current directory.
			Currently too cumbersome to do this with pythonic json libs, we simply use
			command line with 'jq'. (should not eat too much memory, as we don't use
			the -s = slurp switch)
		"""

		with open(outputfile, 'w') as out_handle:
			subprocess.run(['/usr/bin/jq', '.', inputfile], stdout=out_handle)
