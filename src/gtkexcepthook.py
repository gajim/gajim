import sys
import traceback

import gtk
import pango

from common import i18n
from cStringIO import StringIO


i18n.init()
_ = i18n._
APP = i18n.APP
_exception_in_progress = False

def _info(type, value, tb):
	global _exception_in_progress
	if _exception_in_progress:
		# Exceptions have piled up, so we use the default exception
		# handler for such exceptions
		_excepthook_save(type, value, tb)
		return

	_exception_in_progress = True

	dialog = gtk.MessageDialog(parent = None,
					flags = 0,
					type = gtk.MESSAGE_WARNING,
					buttons = gtk.BUTTONS_CLOSE,
					message_format = _('A programming error has been detected'))

	dialog.format_secondary_text(
		_('It probably is not fatal, but should be reported '
			'to the developers nonetheless.'))
	dialog.set_default_response(gtk.RESPONSE_CLOSE)

	# Details
	textview = gtk.TextView()
	textview.set_editable(False)
	textview.modify_font(pango.FontDescription('Monospace'))
	sw = gtk.ScrolledWindow()
	sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.add(textview)
	frame = gtk.Frame()
	frame.set_shadow_type(gtk.SHADOW_IN)
	frame.add(sw)
	frame.set_border_width(6)
	textbuffer = textview.get_buffer()
	trace = StringIO()
	traceback.print_exception(type, value, tb, None, trace)
	textbuffer.set_text(trace.getvalue())
	textview.set_size_request(
		gtk.gdk.screen_width() / 3,
		gtk.gdk.screen_height() / 4)
	expander = gtk.Expander(_('Details'))
	expander.add(frame)
	dialog.vbox.add(expander)

	dialog.set_position(gtk.WIN_POS_CENTER)

	dialog.show_all()
	dialog.run()
	dialog.destroy()
	_exception_in_progress = False
	
if not sys.stderr.isatty(): # gdb/kdm etc if we use startx this is not True
	#FIXME: maybe always show dialog?
	_excepthook_save = sys.excepthook
	sys.excepthook = _info

# this is just to assist testing (python gtkexcepthook.py)
if __name__ == '__main__':
	_excepthook_save = sys.excepthook
	sys.excepthook = _info
	print x # this always tracebacks

