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
import ijson
import copy


class iterStore:
	""" A store holding an array of things, and providing an iterator interface.

		External representation of these 'things' is defined in the 'klass' class
		which has to be a subclass of 'SanisObject'.

		Internal representation is an array holding only the values (and no keys).

		iterStore is being filled by reading a whole JSON file, using the

			`self.read_json_file(file)`

		method. Note that this does not parse the whole file into (possibly too big)
		memory structures, as Python's `json` module would do. The method uses Python's
		`ijson` module which parses the input stream object-by-object, generating callbacks
		for every completed object.

		iterStore can hold the full data in an array (in memory). At any time while
		filling the store (or even already at the start) we can call

			`self.switch_to_filestore()`

		which will turn the memory-consuming array into a file-backed array where
		array elements are represented by tab-delimited plain text lines. (Yes, this
		forbids using linefeeds and tabs in the cell contents, but who wants that
		anyway?)

		iterStore implements the Iterator API, so the caller can loop over the objects
		currently stored here as if it were a real array.

		For convenience, iterStore implements a method to search through the objects, calling

			`self.find(key,value)`

		This function can search for values in every key. Search is done sequentially, but if the
		key is the first attribute mentioned in the _attributes property of the SanisObject class,
		then the search benefits from an internal index.
	"""

	data = []
	fname = None
	temp_base = ''		# where to create temp file (if needed)

	# status-holding variables. Used while filling the store AND while reading it.
	fhandle = None
	pos = 0

	# Indexed access if we search for the first attribute of the attribute mapping.
	keyattr = ''
	keyidx = {}		# key = value of the first attribute, value = record number.

	def __init__(self, klass, jsonfile=None, temp_base=None):
		""" Initialize a store object for elements of the 'klass' class.
			If jsonfile is given: read it immediately.
			If temp_base is given: use it as prefix for temp file (if ever needed)
		"""

		self.klass = klass
		self.keyattr = next(iter(klass._attribs))

		self.data = []
		self.fname = None
		self.fhandle = None
		self.pos = 0
		self.keyidx = {}

		if temp_base:
			self.temp_base = temp_base

		if jsonfile:
			self.read_json_file(jsonfile)

	def __del__(self):

		if self.fhandle:
			self.fhandle.close()
		if self.fname:
			os.unlink(self.fname)

	def __iter__(self):
		""" start iterating over the data """

		self.__internal_iter_start__()

		return self

	def __next__(self):
		""" return the next element in the 'external' representation """

		return self.klass.bless(self.__internal_next__())

	def __internal_iter_start__(self):
		""" To call __internal_next__ as the NEXT function of an iteration
			we make an internal 'start iteration' function which is callable
			HERE without using the iterator interface.
		"""

		if self.fname:
			# always close the temp file before starting to read it again
			if self.fhandle:
				self.fhandle.close()
				self.fhandle = None
			self.fhandle = open(self.fname, 'r')
		else:
			self.pos = 0

	def __internal_next__(self):
		""" An internal NEXT function that hides the internals of the current
			storage mode (memory or file). This is used by the public __next__()
			API by the callers. The internal function is used when it is not needed
			to convert the full data into the external representation (such as in the
			find() and find_all() methods).
		"""

		if self.fname:
			line = self.fhandle.readline()
			if not line:
				raise StopIteration
			element = line.rstrip('\n').split('\t')
		else:
			if self.pos >= len(self.data):
				raise StopIteration
			element = self.data[self.pos]
			self.pos += 1
		return element

	def switch_to_filestore(self):
		""" Switch store mode to temp file store. """

		fname = '%sstore_%s.tmp' % (self.temp_base, self.klass.__name__.lower())
		print('switch_to_filestore: %s' % fname)

		self.fname = fname
		with open(fname, 'w') as fhandle:
			if len(self.data):
				for item in self.data:
					print('\t'.join(item), file=fhandle)
				# empty the array of arrays: this helps garbage-collecting the memory!
				idx = len(self.data)
				while idx > 0:
					idx -= 1
					del self.data[idx]

	def read_json_file(self, fname):
		""" Read a JSON file into the store. Note that this function should
			not be invoked multiple times. (not needed for the current use)

			Objects are only included into the store if they pass the
			validate_object method of the given class.

			If a given object definition contains field names in the '_arrays' parameter
			then it means we have to split the object into multiple ones with one
			element of the fieldname array each.
		"""

		with open(fname, 'rb') as input:
			for j_obj in ijson.items(input, 'item'):
				for obj in self.iterate_object(j_obj):
					if self.klass.validate_object(obj):
						self.append_object(self.klass.parse_object(obj))

		if self.fhandle:
			self.fhandle.close()
			self.fhandle = None

	def iterate_object(self, obj):
		""" This expands a given object with embedded arrays into single objects
			where each array is replaced by one of the array elements. If there are
			no '_arrays' definitions in the base class, the function simply returns
			its input object, wrapped into an array.
		"""

		if not len(self.klass._arrays):
			return [obj, ]

		inputobj = [obj, ]
		result = []
		# this can get multidimensional if we want it...
		for akey in self.klass._arrays:
			for obj in inputobj:
				avar = copy.deepcopy(self.klass.extract_value(obj, akey))
				if isinstance(avar, list):
					for aseg in avar:
						tmp_obj = copy.deepcopy(obj)
						# this currently only works for toplevel keys. If akey is a nested key
						# then this must be able to set nested attributes too.
						tmp_obj[akey] = aseg
						result.append(tmp_obj)
				else:
					# if this is not an array: keep the object unexpanded.
					result.append(obj)
			inputobj = result
		return result

	def append_object(self, data):
		""" Expects an array and appends it to the (inner) data array.
			The first element of 'data' is considered the key of the given
			record, and stored in a dict `keyidx` for later use.
		"""

		self.keyidx[data[0]] = self.pos
		self.pos += 1

		if self.fname:
			if not self.fhandle:
				self.fhandle = open(self.fname, 'a')
			print('\t'.join(data), file=self.fhandle)
		else:
			self.data.append(data)
			if self.klass._memory_threshold:
				if len(self.data) > self.klass._memory_threshold:
					self.switch_to_filestore()

	def length(self):
		""" return how much elements we have in the index """

		return len(self.keyidx.keys())

	def find(self, val, key=None):
		""" Find an object by a key/value pair. """

		# if key is our 'key attribute': search by index.
		# (also if key is not specified)
		if key == self.keyattr or key is None:
			if val in self.keyidx:
				num = self.keyidx[val]
				if self.fname:
					if self.fhandle:
						self.fhandle.close()
						self.fhandle = None
					self.fhandle = open(self.fname, 'r')
					z = num
					while z > 0:
						self.fhandle.readline()
						z -= 1
					line = self.fhandle.readline().rstrip('\n')
					return self.klass.bless(line.split('\t'))
				else:
					return self.klass.bless(self.data[num])
			else:
				return None
		else:
			for element in self:
				if key in element and element[key] == val:
					return element
			return None

	def find_all(self, key, val):
		""" Find all occurrences of key == val and return them in an array.
			This operation may be somewhat expensive because it must be
			carried out sequentially until the end of the data array (or file,
			for that matter).
		"""

		result = []

		for element in self:
			if key in element and element[key] == val:
				result.append(element)

		return result

	def resolve(self, key, retval=None):
		""" Searches for 'key' in the (indexed) key column of the store,
			and extracts a property denoted by retval.
		"""

		element = self.find(self.keyattr, key)
		if element:
			return self.klass.extract(element, retval)

		return None

	def sorted(self, key):
		""" returns another iterator out of self, keyed by the named key. We need this
			function to get the input data sorted by a human-recognizable attribute
			instead of the GUID.
		"""

		def key_func(obj):
			return obj[key]

		return sorted(self, key=key_func)

	def remove(self, key):
		""" We have already filtered away some elements by using the 'validate_object'
			method directly while reading JSON. But there are situations where we cannot
			know in advance if a given element has to be ignored. To make it clean we
			need the possibility to remove elements from the store, and to re-run the
			validation loop. We know when we can call this function: only while no iterator
			looping is in progress, so we don't have to care for synchronization or multithreading.
		"""

		# only if key exists
		if key in self.keyidx:
			recno = self.keyidx.pop(key)
			if len(self.data):
				self.data.pop(recno)
			if self.fname:
				with open(self.fname) as inp:
					with open('%s.new' % self.fname, 'w') as out:
						n = 0
						# read until line is empty (means EOF)
						while True:
							line = inp.readline()
							if not line:
								break
							# skip the line we want to delete
							if n != recno:
								out.write(line)
							n += 1
				# rename .new to the original file
				os.replace('%s.new' % self.fname, self.fname)
			# We have to renumber all references in keyidx which are greater than recno!!!
			for key, idx in self.keyidx.items():
				if idx > recno:
					self.keyidx[key] = idx - 1

	# --------------- D e b u g g i n g -------------------
	# Strictly not needed: these functions help examining the
	# contents of the store, and should never be used in the
	# productive business logic.

	def print_data(self):
		""" DEBUG print the data contained in this store to STDOUT """

		print('Store [%s] has %d elements:' % (self.klass.__name__, self.length()))

		# Invoke the iterator interface
		num = 0
		for element in self:
			num += 1
			print('[%d] %s' % (num, element))

	def print_csv(self, fname):
		""" DEBUG output the current data into a CSV with fixed format:
			really COMMA-separated, and all fields quoted. Just for
			easy generation of debug input data.

			Note that this is really only for debugging: it will contain our
			store-internal attribute names as headings!
		"""

		with open(fname, 'w', encoding='utf-8') as fhandle:
			print(','.join('"%s"' % x for x in self.klass._attribs.keys()), file=fhandle)
			self.__internal_iter_start__()
			try:
				while True:
					element = self.__internal_next__()
					print(','.join('"%s"' % x for x in element), file=fhandle)
			except StopIteration:
				return
