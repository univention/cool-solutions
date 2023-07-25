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


class Codes():
	""" We make an extra object class that holds the enumerations of valid object types,
		as they ar known in SANIS (mostly german). We do this so we can use (import) this
		class in all other sources, just to be consistent across the whole process.
	"""

	@classmethod
	def valid_user_roles(self):
		""" return the (SANIS) role names and the mappings to ucs@school roles. """

		return({
			'Lehr':		'teacher',
			'Lern':		'student',
		})

	@classmethod
	def roles_requiring_groups(self):
		""" Returns an array of (Sanis) roles that can only be imported if the given user
			is at least member of one group.
		"""

		return([
			'Lern',
		])

	@classmethod
	def valid_group_types(self):
		""" This enumerates the (SANIS) group types we have to process as classes.
			Any other groups / group assignments have to be ignored.
		"""

		return([
			'Klasse',
		])

	@classmethod
	def valid_org_types(self):
		""" Return the organization types that we have to process. """

		return([
			'Schule',
		])


class SanisObject():
	""" Base class for all SANIS objects. These objects are read from the SANIS API, and converted
		(mapped) from JSON into an internal representation that will only hold the attributes
		needed by the SANIS import tool. """

	# attribute mapping: key=UCS name, value=Sanis (json) name. Note that the first element
	# in this attribute mapping is automatically used as a KEY in the store. The JSON attribute
	# names can contain dots (.) to denote nested structures.
	_attribs = {}

	# This is a helper to expand nested arrays. This variable should list all virtual
	# paths to be resolved from arrays into each of their elements. Currently we need
	# only one level, but who knows...
	_arrays = []

	# Automatic switchover from memory to file storage is done if we have read more
	# than this many objects. A threshold of zero means 'no limit'.
	_memory_threshold = 0

	def __init__(self):
		""" Currently all methods are static, so we don't need initialization here. """
		pass

	@classmethod
	def parse_object(self, obj):
		""" parses a JSON object (dict) into the internal data structure. Note that starting
			with python 3.6, the keys of dicts are guaranteed to remain in the order they were
			inserted, so the matching between self._attribs.keys() (or items) and the internal
			data model (array without attribute names) will always work.
		"""

		result = []

		for (okey, ikey) in self._attribs.items():
			result.append(self.extract_value(obj, ikey))

		return result

	@classmethod
	def validate_object(self, obj):
		""" Return true if the given object is to be included in the dataset.
			This can be overridden in the derived classes, but it is required
			to call the inherited function beforehand.
		"""

		# Generic check: we do not accept objects whose key property is empty.
		keyarg = next(iter(self._attribs))
		jsonkey = self._attribs[keyarg]
		if not self.extract_value(obj, jsonkey):
			return False

		return True

	@classmethod
	def extract_value(self, obj, key):
		""" Extract a value keyed by 'key' from a JSON object. This can delve recursively
			into nested structures. Notexistance of any structure level leaves the
			result as empty string.
		"""

		value = ''
		keys = key.split('.')
		try:
			tmp_obj = obj
			while len(keys):
				if len(keys) > 1:
					tmp_obj = tmp_obj[keys[0]]
				else:
					value = tmp_obj[keys[0]]
				keys.pop(0)
		except Exception:
			pass
		return value

	@classmethod
	def replace_value(self, obj, key, value):
		""" Correct the to-be-processed input data. Key must be one that was already resolved
			by extract_value(). (using the same algorithm here, and each failure shall be
			silently ignored.)
		"""

		keys = key.split('.')
		try:
			tmp_obj = obj
			while len(keys):
				if len(keys) > 1:
					tmp_obj = tmp_obj[keys[0]]
				else:
					tmp_obj[keys[0]] = value
				keys.pop(0)
		except Exception:
			pass

	@classmethod
	def bless(self, data):
		""" return an object of the class denoted by the own object class """
		return dict(zip(self._attribs.keys(), data))

	@classmethod
	def extract(self, data, retval=None):
		""" Extract a field from the (already parsed) data. Data is expected
			to be a blessed instance (a dict). If retval is None, return the
			second data value.
		"""

		if retval:
			return data[retval]

		return list(data.values())[2]

# -----------------------------------------------------------------------------
#
#	C l a s s e s   d e r i v e d   f r o m   s a n i s O b j e c t
#
# -----------------------------------------------------------------------------


class Person(SanisObject):

	_attribs = {
		'id':				'person.id',
		'familienname':		'person.name.familienname',
		'vorname':			'person.name.vorname',
		'geburtsdatum':		'person.geburt.datum',
		'stammorg':			'person.stammorganisation',
	}

	# This class overloads the 'extract' function, just to see if it works.
	@classmethod
	def extract(self, data, retval=None):

		# Any other 'retval's are resolved by the base classe.
		if retval is None:
			return '%(familienname)s, %(vorname)s' % data

		return super().extract(data, retval)


class Organisation(SanisObject):

	_attribs = {
		'id':				'id',
		'kennung':			'kennung',
		'name':				'name',
		'namensergaenzung':	'namensergaenzung',
		'kuerzel':			'kuerzel',
	}

	@classmethod
	def validate_object(self, obj):

		if not super().validate_object(obj):
			return False

		# ignore organizations that are not schools.
		# WHY CAN'T I LOOK AT THE 'codelisten' TO SEE WHAT IS VALID HERE?!?
		if self.extract_value(obj, 'typ') not in Codes.valid_org_types():
			return False

		return True


class Kontext(SanisObject):

	# 'personenkontexte' is an array and should therefore yield multiple
	# store objects.

	_arrays = [
		'personenkontexte'
	]

	_attribs = {
		'id':			'personenkontexte.id',
		'org_id':		'personenkontexte.organisation.id',
		'rolle':		'personenkontexte.rolle',
		'status':		'personenkontexte.personenstatus',
		'person_id':	'person.id',
	}


class Klassen(SanisObject):

	_attribs = {
		'id':				'gruppe.id',
		'org_id':			'gruppe.orgid',		# this is the school
		'typ':				'gruppe.typ',
		'referrer':			'gruppe.referrer',
		'bezeichnung':		'gruppe.bezeichnung',
		'laufzeit_von':		'gruppe.laufzeit.vonlernperiode',
		'laufzeit_bis':		'gruppe.laufzeit.bislernperiode',
	}

	@classmethod
	def validate_object(self, obj):

		if not super().validate_object(obj):
			return False

		# ignore groups that are not classes.
		# WHY CAN'T I LOOK AT THE 'codelisten' TO SEE WHAT IS VALID HERE?!?
		if self.extract_value(obj, 'gruppe.typ') not in Codes.valid_group_types():
			return False

		return True


class Mitglieder(SanisObject):

	_arrays = [
		'gruppenzugehoerigkeiten',
	]

	_attribs = {
		'id':				'gruppenzugehoerigkeiten.id',
		'referrer':			'gruppenzugehoerigkeiten.referrer',		# <- do we need this?
		'ktid':				'gruppenzugehoerigkeiten.ktid',			# context ID: this is the link to the user
		'von':				'gruppenzugehoerigkeiten.von',
		'bis':				'gruppenzugehoerigkeiten.bis',
		'rolle':			'gruppenzugehoerigkeiten.rollen',		# overrides the 'Basisrolle' of 'Personenkontext'
		# some redundant group properties: save us some recurson cycles
		# and help debugging selection criteria
		'group_name':		'gruppe.bezeichnung',
		'group_id':			'gruppe.id',
		'group_type':		'gruppe.typ',
	}

	@classmethod
	def validate_object(self, obj):
		""" This repeats the validation of the 'Klassen' class because this
			parser reads the same data.
		"""

		if not super().validate_object(obj):
			return False

		# ignore group memberships which don't relate to classes.
		# WHY CAN'T I LOOK AT THE 'codelisten' TO SEE WHAT IS VALID HERE?!?
		if self.extract_value(obj, 'gruppe.typ') not in Codes.valid_group_types():
			return False

		# For the (slightly convoluted) combination of multiple roles into one
		# group membership (and the possible contradiction with the context's
		# role): Ignore any group membership that ucs@school cannot handle.

		# STEP #1: filter out roles that we're not about to process
		myroles = [x for x in self.extract_value(obj, 'gruppenzugehoerigkeiten.rollen') if x in Codes.valid_user_roles().keys()]

		# STEP #2: reject this membership if there are multiple roles remaining
		# Sorry, we cannot do it here because we don't have the context (which user and which
		# school this membership is about) -> so we MUST do this in the validation function
		# of sanisImport, just to print a meaningful diagnostic message.
		#if len(myroles) > 1:
		#	print('Membership [%s] [%s] ignored: multiple roles: %s' % (self.extract_value(obj,'gruppe.bezeichnung'),self.extract_value(obj,'gruppenzugehoerigkeiten.ktid'),myroles))
		#	return False

		# STEP #3: reject this membership if there are no roles remaining. Note that this is a different
		#	condition than in step #2: here it simply means that this group membership is not relevant.
		if len(myroles) == 0:
			return False

		# STEP #4: replace the input array by a single string. Note that we propagate memberships with
		#	multiple roles: it is deferred to the 'validate' function of the sanisImport class to
		#	recognise and log this condition. (this will accomplish what STEP #2 could not do)
		self.replace_value(obj, 'gruppenzugehoerigkeiten.rollen', ','.join(myroles))

		# FIXME do we have to honor 'von' and 'bis' validities, and if so, how?

		return True
