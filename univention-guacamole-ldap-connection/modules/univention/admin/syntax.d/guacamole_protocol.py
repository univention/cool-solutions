class guacamole_protocol(select):
	choices = [
		('', ''),
		('rdp', 'RDP'),
		('ssh', 'SSH'),
		('telnet','Telnet'),
		('vnc', 'VNC'),
	]
	default = ''
	size = 'OneThird'
