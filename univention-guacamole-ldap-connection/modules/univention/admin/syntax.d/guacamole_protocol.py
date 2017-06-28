class guacamole_protocol(select):
	choices = [
		('', ''),
		('rdp', 'RDP'),
		('ssh', 'SSH'),
		('vnc', 'VNC'),
	]
	default = ''
	size = 'OneThird'
