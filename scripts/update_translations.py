import os
import sys

def visit(arg, dirname, names):
	if dirname.find('.svn') != -1:
		return
	if dirname.endswith('LC_MESSAGES'):
		if 'gajim.po' in names:
			path_to_po = os.path.join(dirname, 'gajim.po')
			pos = path_to_po.find('po/') + 3 #3 = len('po/')
			name = path_to_po[pos:pos+2]
			os.system('msgmerge -U ../po/'+name+'/LC_MESSAGES/gajim.po ../gajim.pot')
			print name, 'has now:'
			os.system('msgfmt --statistics ' + path_to_po)

if __name__ == '__main__':
	if os.path.basename(os.getcwd()) != 'scripts':
		print 'run me with cwd: scripts'
		sys.exit()

	os.system('xgettext -k_ -kN_ -o gajim.pot ../src/*.py ../src/common/*.py ../src/msg.c')
	path_to_dir = '../po'

	os.path.walk(path_to_dir, visit, None)
