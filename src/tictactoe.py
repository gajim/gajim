from common import stanza_session
from common import xmpp

import pygtk
pygtk.require('2.0')
import gtk
from gtk import gdk
import cairo

# implements <http://pidgin-games.sourceforge.net/xep/tictactoe.html#invite>

games_ns = 'http://jabber.org/protocol/games'

class InvalidMove(Exception):
	pass

class TicTacToeSession(stanza_session.StanzaSession):
	def begin(self, rows = 3, cols = 3, role_s = 'x'):
		self.rows = rows
		self.cols = cols

		self.role_s = role_s

		if self.role_s == 'x':
			self.role_o = 'o'
		else:
			self.role_o = 'x'

		self.send_invitation()

		self.next_move_id = 1
		self.received = self.wait_for_invite_response

	def send_invitation(self):
		msg = xmpp.Message()

		invite = msg.NT.invite
		invite.setNamespace(games_ns)

		game = invite.NT.game
		game.setAttr('var', games_ns + '/tictactoe')

		x = xmpp.DataForm(typ='submit')

		game.addChild(node=x)

		self.send(msg)

	def read_invitation(self, msg):
		invite = msg.getTag('invite', namespace=games_ns)
		game = invite.getTag('game')
		x = game.getTag('x', namespace='jabber:x:data')

		form = xmpp.DataForm(node=x)

		if form.getField('role'):
			self.role_o = form.getField('role').getValues()[0]
		else:
			self.role_o = 'x'

		if form.getField('rows'):
			self.rows = int(form.getField('rows').getValues()[0])
		else:
			self.rows = 3

		if form.getField('cols'):
			self.cols = int(form.getField('cols').getValues()[0])
		else:
			self.cols = 3

		if form.getField('strike'):
			self.strike = int(form.getField('strike').getValues()[0])
		else:
			self.strike = 3

	# received an invitation
	def invited(self, msg):
		self.read_invitation(msg)

		# XXX prompt user
		#   "accept, reject, ignore"

		# the number of the move about to be made
		self.next_move_id = 1

		# display the board
		self.board = TicTacToeBoard(self, self.rows, self.cols)

		# accept the invitation, join the game
		response = xmpp.Message()

		join = response.NT.join
		join.setNamespace(games_ns)

		self.send(response)

		if self.role_o == 'x':
			self.role_s = 'o'

			self.their_turn()
		else:
			self.role_s = 'x'
			self.role_o = 'o'

			self.our_turn()

	def is_my_turn(self):
		# XXX not great semantics
		return self.received == self.ignore

	# just sent an invitation, expecting a reply
	def wait_for_invite_response(self, msg):
		if msg.getTag('join', namespace=games_ns):
			self.board = TicTacToeBoard(self, self.rows, self.cols)

			if self.role_s == 'x':
				self.our_turn()
			else:
				self.their_turn()

		elif msg.getTag('decline', namespace=games_ns):
			self.XXX()

	# silently ignores any received messages
	def ignore(self, msg):
		pass

	def wait_for_move(self, msg):
		turn = msg.getTag('turn', namespace=games_ns)
		move = turn.getTag('move', namespace='http://jabber.org/protocol/games/tictactoe')

		row = int(move.getAttr('row'))
		col = int(move.getAttr('col'))
		id = int(move.getAttr('id'))

		if id != self.next_move_id:
			print 'unexpected move id, lost a move somewhere?'
			raise

		try:
			self.board.mark(row, col, self.role_o)
		except InvalidMove, e:
			print 'received invalid move'
			return

		# check win conditions
		if self.board.check_for_strike(self.role_o, row, col, self.strike):
			self.lost()
		elif self.board.full():
			self.drawn()
		else:
			self.next_move_id += 1

			self.our_turn()

	def our_turn(self):
		# ignore messages until we've made our move
		self.received = self.ignore
		self.board.win.set_title(self.board.title + ': your turn')

	def their_turn(self):
		self.received = self.wait_for_move
		self.board.win.set_title(self.board.title + ': their turn')

	# called when the board receives input
	def move(self, row, col):
		try:
			self.board.mark(row, col, self.role_s)
		except InvalidMove, e:
			print 'you made an invalid move'
			return

		self.send_move(row, col)

		# check win conditions
		if self.board.check_for_strike(self.role_s, row, col,self.strike):
			self.won()
		elif self.board.full():
			self.drawn()
		else:
			self.next_move_id += 1

			self.their_turn()

	def send_move(self, row, column):
		msg = xmpp.Message()
		msg.setType('chat')

		turn = msg.NT.turn
		turn.setNamespace(games_ns)

		move = turn.NT.move
		move.setNamespace(games_ns+'/tictactoe')

		move.setAttr('row', str(row))
		move.setAttr('col', str(column))
		move.setAttr('id', str(self.next_move_id))

		self.send(msg)

class TicTacToeBoard:
	def check_for_strike(self, p, r, c, strike):
		# up and down, left and right
		tallyI = 0
		tally_ = 0

		# right triangles: L\ , F/
		tallyL = 0
		tallyF = 0

		# convert real columns to internal columns
		r -= 1
		c -= 1

		for d in xrange(-strike, strike):
			# vertical check
			try:
				tallyI = tallyI + 1 if self.board[r+d][c] == p else 0
			except IndexError:
				pass

			# horizontal check
			try:
				tally_ = tally_ + 1 if self.board[r][c+d] == p else 0
			except IndexError:
				pass

			# diagonal checks
			try:
				tallyL = tallyL + 1 if self.board[r+d][c+d] == p else 0
			except IndexError:
				pass

			try:
				tallyF = tallyF + 1 if self.board[r+d][c-d] == p else 0
			except IndexError:
				pass

			if any([t == strike for t in (tallyL, tallyF, tallyI, tally_)]):
				return True

		return False

	def __init__(self, session, rows, cols):
		self.session = session

		self.rows = rows
		self.cols = cols

		self.board = [ [None] * self.cols for r in xrange(self.rows) ]

		self.setup_window()

	# is the board full?
	def full(self):
		for r in xrange(self.rows):
			for c in xrange(self.cols):
				if self.board[r][c] == None:
					return False

		return True

	def setup_window(self):
		self.win = gtk.Window()

		self.title = 'tic-tac-toe with %s' % self.session.jid

		self.win.set_title(self.title)
		self.win.set_app_paintable(True)

		self.win.add_events(gdk.BUTTON_PRESS_MASK)
		self.win.connect('button-press-event', self.clicked)
		self.win.connect('expose-event', self.expose)

		self.win.show_all()

	def clicked(self, widget, event):
		if not self.session.is_my_turn():
			return

		(height, width) = widget.get_size()

		# convert click co-ordinates to row and column

		row_height = height	// self.rows
		col_width = width	// self.cols

		row    = int(event.y // row_height) + 1
		column = int(event.x // col_width) + 1

		self.session.move(row, column)

	# this actually draws the board
	def expose(self, widget, event):
		win = widget.window

		cr = win.cairo_create()

		cr.set_source_rgb(1.0, 1.0, 1.0)

		cr.set_operator(cairo.OPERATOR_SOURCE)
		cr.paint()

		(width, height) = widget.get_size()

		row_height = height // self.rows
		col_width  = width	// self.cols

		for i in xrange(self.rows):
			for j in xrange(self.cols):
				if self.board[i][j] == 'x':
					self.draw_x(cr, i, j, row_height, col_width)
				elif self.board[i][j] == 'o':
					self.draw_o(cr, i, j, row_height, col_width)

	def draw_x(self, cr, row, col, row_height, col_width):
		cr.set_source_rgb(0, 0, 0)

		top = row_height * (row + 0.2)
		bottom = row_height * (row + 0.8)

		left = col_width * (col + 0.2)
		right = col_width * (col + 0.8)

		cr.set_line_width(row_height / 5)

		cr.move_to(left, top)
		cr.line_to(right, bottom)

		cr.move_to(right, top)
		cr.line_to(left, bottom)

		cr.stroke()

	def draw_o(self, cr, row, col, row_height, col_width):
		cr.set_source_rgb(0, 0, 0)

		x = col_width * (col + 0.5)
		y = row_height * (row + 0.5)

		cr.arc(x, y, row_height/4, 0, 2.0*3.2) # slightly further than 2*pi

		cr.set_line_width(row_height / 5)
		cr.stroke()

	# mark a move on the board
	def mark(self, row, column, player):
		if self.board[row-1][column-1]:
			raise InvalidMove
		else:
			self.board[row-1][column-1] = player

		self.win.queue_draw()
