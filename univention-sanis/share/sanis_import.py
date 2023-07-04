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
import datetime
import stat
import re
import subprocess
import json
import base64
import copy
from urllib import request
from univention.config_registry import ConfigRegistry

from sanis_tools import iterStore
from sanis_models import Person, Organisation, Kontext, Klassen, Mitglieder


class NoSchoolException(BaseException):
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

	tempfiles = []				# files to be cleaned up
	commands = []				# lines to be written into script

	config_file = None			# never to be used as a config. Will only be written for debugging.
	conf_data = {}				# the contents of config_file. Used as starting point for job configs.

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
		'#',
		'',
		'cd $(dirname $0)',
		'(',
	]

	script_footer = [
		'',
		') 2>&1 | tee $(basename $0).log',
	]

	def __init__(self, api_url, token_url, cred_file, dry_run=False):
		""" Prepare object for use. Any errors throw exceptions and are not handled here. """

		self.api_url = api_url
		self.token_url = token_url
		self.cred_file = cred_file
		self.dry_run = dry_run

		today = str(datetime.datetime.now())
		purpose = 'TEST-Import' if dry_run else 'produktiven Import'
		self.script_header[3] = '# (erzeugt %s für %s)' % (today, purpose)

		self.token = self.get_token()

		# invent a prefix for temp files. Can be a directory or only a filename prefix.
		# Will be used here for JSON files as well as in the stores when switching
		# to file store. All temp files are cleaned up.
		self.temp_base = '/tmp/sanis_import_%d_' % os.getpid()

	def read_input_data(self):
		""" Read all data from SANIS API and store them in (internal) store objects.
			if 'dry_run' is on: save all intermediary files into the current directory
		"""

		print('Lese Daten von SANIS...')

		# --------------- person -----------------
		pers_file = self.fetch_data('/personen')
		self.pers_store = iterStore(Person, pers_file, temp_base=self.temp_base)
		print('      gefiltert: %d Benutzer.' % self.pers_store.length())
		if self.dry_run:
			self.pers_store.print_csv('store_personen.csv')
			self.dump_json(pers_file, 'sanis_personen.json')

		# -------- "personenkontexte" --------------
		# Note that the 'personen' dataset already contains all of the data
		# needed by the 'personenkontext' logic. Therefore it is useless to
		# fetch the same data again here. Instead, we use the 'pers_file'
		# which we already have fetched.
		self.cont_store = iterStore(Kontext, pers_file, temp_base=self.temp_base)
		print('      gefiltert: %d Personenkontexte.' % self.cont_store.length())
		if self.dry_run:
			self.cont_store.print_csv('store_personenkontexte.csv')

		# ---------- schools (organizations) ------
		org_file = self.fetch_data('/organisationen')
		self.org_store = iterStore(Organisation, org_file, temp_base=self.temp_base)
		print('      gefiltert: %d Schulen.' % self.org_store.length())
		if self.dry_run:
			self.org_store.print_csv('store_organisationen.csv')
			self.dump_json(org_file, 'sanis_organisationen.json')

		# ------------ groups (only classes) -------------
		grp_file = self.fetch_data('/gruppen')
		self.grp_store = iterStore(Klassen, grp_file, temp_base=self.temp_base)
		print('      gefiltert: %d Klassen.' % self.grp_store.length())
		if self.dry_run:
			self.grp_store.print_csv('store_gruppen.csv')
			self.dump_json(grp_file, 'sanis_gruppen.json')

		# ----------- membership ------------------
		# Just as for 'personenkontexte', the 'gruppenmitgliedschaften' membership
		# relations are already fully fetched by the '/gruppen' entry point.
		self.memb_store = iterStore(Mitglieder, grp_file, temp_base=self.temp_base)
		print('      gefiltert: %d Gruppenzugehörigkeiten.' % self.memb_store.length())
		if self.dry_run:
			self.memb_store.print_csv('store_gruppenzugehoerigkeiten.csv')

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

		try:
			for role, sanis_role in self.roles_to_prepare.items():
				print('   Schule=%s  Rolle=%s ... ' % (school, role), end='')
				out_filename = 'import_%s_%s.csv' % (school, role)
				records = 0
				with open(out_filename, 'w') as out_handle:
					print(self._data_line(self.headers.keys()), file=out_handle)
					# Build a mapping of valid groups (GUID -> name) of this school.
					groups = {}
					for group in self.grp_store.find_all('org_id', sanis_id):
						groups[group['id']] = group['bezeichnung']
					# find all person contexts related to this SANIS ORG_ID -> users
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
						# get classes of this user.
						classes = []
						for klass in self.memb_store.find_all('ktid', context['id']):
							classes.append(klass['group_name'])
						person['classes'] = classes
						# Skip students without at least one class
						if role == 'student' and len(classes) == 0:
							# DEBUG?
							# print('  No classes for [%(familienname)s, %(vorname)s], skipping user.' % person)
							continue
						record = []
						for attr, iattr in self.headers.items():
							if iattr in person:
								record.append(person[iattr])
							else:
								record.append('-')
						print(self._data_line(record), file=out_handle)
						records += 1
				print('%d Sätze' % records)

				# The commandline importer does not accept multiple assignments into the same tuple
				# (in our case: output:user_import_summary and output:new_user_passwords), it only
				# takes the last one. This explains why my commandline with these variables does
				# not work. The solution that I now prefer is: generate separate config files with
				# ALL arguments included.

				job_config_file = 'config_%s_%s.json' % (school, role)
				if self.dry_run:
					job_config_file = 'test_%s' % job_config_file
				config = {
					'dry_run':			self.dry_run,
					'source_uid':		'sanis',
					'school':			school,
					'user_role':		role,
					# This is the CSV data file we've written right now. Note that the 'infile' cmdline parameter
					# is coded into the input {} tuple, even if the 'type' element can only be 'CSV' for now.
					'input': {
						'filename':		out_filename,
					},
				}

				if self.dry_run:
					config['output'] = {
						'user_import_summary':	'summary_%s_%s.csv' % (school, role),
						'new_user_passwords':	'passwords_%s_%s.csv' % (school, role),
					}
				else:
					config['output'] = {
						'user_import_summary':	'/var/lib/ucs-school-import/summary/%%Y/%%m/summary-%%Y-%%m-%%d-%%H-%%M-%%S_%s_%s.csv' % (school, role),
						'new_user_passwords':	'/var/lib/ucs-school-import/passwords-%%Y-%%m-%%d-%%H-%%M-%%S_%s_%s.csv' % (school, role),
					}

				# Mix this 'config' into the basic config, and write this into the job-specific config file.
				# NOTE the order: first the basic data, then mix in job-specific things (allows overriding
				# global configs!)
				jobconfig = copy.deepcopy(self.config_data)
				jobconfig.update(config)
				with open(job_config_file, 'w') as out_handle:
					json.dump(jobconfig, out_handle, indent=4)

				# We don't immediately write these commands into the to-be-executed script. This
				# is intentional: if anything fails while trying to write these files, the script
				# will not be written, and the user should not even think about executing any
				# import with these partly-damaged data.
				self.commands.append('   /usr/share/ucs-school-import/scripts/ucs-school-user-import \\')
				self.commands.append('      --conffile %s \\' % job_config_file)
				self.commands.append('      2>&1 | tee import_%s_%s.log' % (school, role))
				self.commands.append('')
		except BaseException as e:
			print('FEHLER: Beim Erzeugen der Daten ist ein Fehler aufgetreten:')
			print(str(e))
			return False
		return True

	def write_command_script(self, out_filename):
		""" Write all the collected commands into the script to be executed.
			Returns True if successful.
		"""

		try:
			with open(out_filename, 'w') as out_handle:
				for line in self.script_header:
					print(line, file=out_handle)
				for line in self.commands:
					print(line, file=out_handle)
				for line in self.script_footer:
					print(line, file=out_handle)

			# ug+rwx = 0770
			os.chmod(out_filename, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXGRP | stat.S_IRGRP | stat.S_IWGRP)

			print('')
			print('Der Skript für den %s ist fertig und kann mit' % ("Import-Test" if self.dry_run else "Import"))
			print('')
			print('  ./%s' % out_filename)
			print('')
			print('aufgerufen werden.')
			return True
		except BaseException as e:
			print('FEHLER: der Skript "%s" konnte nicht erzeugt werden:')
			print(str(e))
			return False

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

		# 'credential file missing' has already been handled.
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

		# print what we're about to read
		print('   %s%s:' % (entrypoint[1].upper(), entrypoint[2:].lower()))

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

		# Quickest form to count: call jq '. | length'
		count = int(subprocess.run(['/usr/bin/jq', '. | length', resfile], capture_output=True).stdout)
		print('      gelesen: %d Sätze.' % count)

		return resfile

	def create_config(self, inputfiles, outputfile):
		""" Merges JSON config files together and write the results as JSON
			into outfilename. Note inputfiles are processed in order: later
			files can override earlier files.

			Input files are allowed to contain comments; these are stripped
			before we try to parse the files.

			This function captures the output file name: the object later wants
			to generate the import command using this config.
		"""

		self.config_file = outputfile

		data = {}		# all data merged in

		for inputfile in inputfiles:
			with open(inputfile, 'r') as inp_handle:
				temp_lines = [re.sub('//.*', '', x.strip()) for x in inp_handle.readlines()]
				try:
					temp_dict = json.loads('\n'.join(temp_lines))
				except json.JSONDecodeError as e:
					print('FEHLER: Die Datei "%s" ist fehlerhaft:' % inputfile)
					print(str(e))
					return False
				data.update(temp_dict)
		# This file will now only saved to disk for debugging purposes. The real
		# configs are later generated, with this data as a starting point.
		with open(outputfile, 'w') as out_handle:
			json.dump(data, out_handle, indent=4)
		self.config_data = data
		return True

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
				raise NoSchoolException('FEHLER: Keine SANIS Organisation mit [%s] = [%s] gefunden' % (attrname, ucr[key]))
			result[shortkey] = school['id']
		if len(result) == 0:
			raise NoSchoolException('FEHLER: Sie haben noch keine Schulen für den Import konfiguriert.')

		return result

	def dump_json(self, inputfile, outputfile):
		""" Only for debugging and/or auditing: print a beautified version of the JSON
			input data into the current directory.
			Currently too cumbersome to do this with pythonic json libs, we simply use
			command line with 'jq'. (should not eat too much memory, as we don't use
			the -s = slurp switch)
		"""

		with open(outputfile, 'w') as out_handle:
			subprocess.run(['/usr/bin/jq', '.', inputfile], stdout=out_handle)
