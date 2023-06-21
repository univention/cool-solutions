import os
import datetime
import ijson
import copy

class iterStore:
	""" A store holding an array of things, and providing an iterator interface.

		External representation of these 'things' is defined in the 'klass' class
		which has to be a subclass of 'sanisObject'.

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
		key is the first attribute mentioned in the _attributes property of the sanisObject class,
		then the search benefits from an internal index.

	"""

	data = []
	fname = None
	temp_base = ''		# where to create temp file (if needed)

	# status-holding variables. Used while filling the store AND while reading it.
	file = None
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
		self.keyattr = klass._attribs.keys().__iter__().__next__()

		self.data = []
		self.fname = None
		self.file = None
		self.pos = 0
		self.keyidx = {}

		if temp_base:
			self.temp_base = temp_base

		if jsonfile:
			self.read_json_file(jsonfile)

	def __del__(self):

		if self.file:
			self.file.close()
		if self.fname:
			os.unlink(self.fname)

	def __iter__(self):
		""" start iterating over the data """

		if self.fname:
			# always close the temp file before starting to read it again
			if self.file:
				self.file.close()
				self.file = None
			self.file = open(self.fname,'r')
		else:
			self.pos = 0
		return self

	def __next__(self):
		""" return the next element in the 'external' representation """

		return self.klass.bless(self.__internal_next__())

	def __internal_next__(self):
		""" An internal NEXT function that hides the internals of the current
			storage mode (memory or file). This is used by the public __next__()
			API by the callers. The internal function is used when it is not needed
			to convert the full data into the external representation (such as in the
			find() and find_all() methods).
		"""

		if self.fname:
			line = self.file.readline()
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
		with open(fname, 'w') as file:
			if len(self.data):
				for item in self.data:
					print('\t'.join(item),file=file)
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

		if self.file:
			self.file.close()
			self.file = None

	def iterate_object(self, obj):
		""" This expands a given object with embedded arrays into single objects
			where each array is replaced by one of the array elements. If there are
			no '_arrays' definitions in the base class, the function simply returns
			its input object, wrapped into an array.
		"""

		if not len(self.klass._arrays):
			return [obj,]

		input = [obj,]
		result = []
		# this can get multidimensional if we want it...
		for akey in self.klass._arrays:
			for obj in input:
				avar = copy.deepcopy(self.klass.extract_value(obj,akey))
				if isinstance(avar,list):
					for aseg in avar:
						tmp_obj = copy.deepcopy(obj)
						# this currently only works for toplevel keys. If akey is a nested key
						# then this must be able to set nested attributes too.
						tmp_obj[akey] = aseg
						result.append(tmp_obj)
				else:
					# if this is not an array: keep the object unexpanded.
					result.append(obj)
			input = result
		return result

	def append_object(self, data):
		""" Expects an array and appends it to the (inner) data array.
			The first element of 'data' is considered the key of the given
			record, and stored in a dict `keyidx` for later use.
		"""

		self.keyidx[data[0]] = self.pos
		self.pos += 1

		if self.fname:
			if not self.file:
				self.file = open(self.fname,'a')
			print('\t'.join(data),file=self.file)
		else:
			self.data.append(data)
			if self.klass._memory_threshold:
				if len(self.data) > self.klass._memory_threshold:
					self.switch_to_filestore()

	def print_data(self):
		""" DEBUG print the data contained in this store. """

		print('Store [%s] has %d elements:' % (self.klass.__name__,self.length()))

		# Invoke the iterator interface
		num = 0
		for element in self:
			num += 1
			print('[%d] %s' % (num,element))

	def length(self):
		""" return how much elements we have in the index """

		return len(self.keyidx.keys())

	def find(self, key, val):
		""" Find an object by a key/value pair. """

		# if key is our 'key attribute': search by index.
		if key == self.keyattr:
			if val in self.keyidx:
				num = self.keyidx[val]
				if self.fname:
					if self.file:
						self.file.close()
						self.file = None
					self.file = open(self.fname,'r')
					z = num
					while z > 0:
						self.file.readline()
						z -= 1
					line = self.file.readline().rstrip('\n')
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

	def resolve(self,key,retval=None):
		""" Searches for 'key' in the (indexed) key column of the store,
			and extracts a property denoted by retval.
		"""

		element = self.find(self.keyattr,key)
		if element:
			return self.klass.extract(element,retval)

		return None

