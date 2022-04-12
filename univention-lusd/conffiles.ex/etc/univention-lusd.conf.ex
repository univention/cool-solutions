@%@BCWARNING=; @%@
key = @%@univention-lusd/value@%@

@!@
for value in configRegistry.get('univention-lusd/key', []):
	print('key = %s' % value)
@!@
