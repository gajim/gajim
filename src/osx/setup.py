from distutils.core import setup, Extension

setup(
	name = 'Gajim',
	version = '0.11',
	description = 'A full featured Jabber client',
	author = 'Gajim Development Team',
	url = 'http://www.gajim.org/',
	download_url = 'http://www.gajim.org/downloads.php',
	license = 'GPL',

	ext_modules=[
	Extension('idle', ['idle.c'],
			  extra_compile_args=['-Wall'],
			  extra_link_args=['-framework', 'IOKit', '-framework', 'Carbon']),
	Extension('nsapp', ['nsapp.m'],
			  extra_compile_args=['-Wall'],
			  extra_link_args=['-framework', 'AppKit', '-framework', 'Cocoa']),
	]
)

# vim: se ts=3: