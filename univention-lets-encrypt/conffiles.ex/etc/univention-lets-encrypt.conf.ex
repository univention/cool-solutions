@%@BCWARNING=; @%@
key = @%@univention-lets-encrypt/value@%@

@!@
for value in configRegistry.get('univention-lets-encrypt/key', []):
	print 'key = %s' % value
@!@
