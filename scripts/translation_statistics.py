import os
import sys


def get_output(app, param=None):
	if param:
		command = app + ' ' + param
	else:
		command = app
	try:
		child_stdout = os.popen(command)
	except:
		print 'Plz relax, and let python do the job. Exiting.. :('
		sys.exit()

	output = child_stdout.readlines()
	child_stdout.close()
	
	return output


def visit(arg, dirname, names):
	if dirname.find('.svn') != -1:
		return
	if dirname.endswith('LC_MESSAGES'):
		if 'gajim.po' in names:
			path_to_po = os.path.join(dirname, 'gajim.po')
			param = '--statistics ' + path_to_po
			print path_to_po, 'has:'
			get_output('msgfmt', param) # msgfmt doesn't use stdout?!


if __name__ == '__main__':
	if len(sys.argv) != 2:
		print sys.argv[0], 'po_DIRECTORY'
		sys.exit(0)

	path_to_dir = sys.argv[1]

	os.path.walk(path_to_dir, visit, None)
