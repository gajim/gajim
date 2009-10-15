#!/usr/bin/env python
##	otr_windows.py
##
##
## Copyright (C) 2008 Kjell Braden <fnord@pentabarf.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import gtkgui_helpers
from common import gajim

our_fp_text = _('Your fingerprint:\n' \
	'<span weight="bold" face="monospace">%s</span>')
their_fp_text = _('Purported fingerprint for %s:\n' \
	'<span weight="bold" face="monospace">%s</span>')

another_q = _('You may want to authenticate your buddy as well by asking'\
		'your own question.')
smp_query = _('<b>%s is trying to authenticate you using a secret only known '\
		'to him/her and you.</b>')
smp_q_query = _('<b>%s has chosen a question for you to answer to '\
		'authenticate yourself:</b>')
enter_secret = _('Please enter your secret below.')

smp_init = _('<b>You are trying to authenticate %s using a secret only known ' \
		'to him/her and yourself.</b>')
choose_q = _('You can choose a question as a hint for your buddy below.')

class ContactOtrSMPWindow:
	def gw(self, n):
		# shorthand for self.xml.get_widget(n)
		return self.xml.get_widget(n)

	question = None
	
	def __init__(self, fjid, account):
		self.fjid = fjid
		self.account = account

		self.xml = gtkgui_helpers.get_glade('contact_otr_window.glade')
		self.window = self.xml.get_widget('otr_smp_window')

		# the contact may be unknown to gajim if ContactOtrSMPWindow
		# is created very early
		self.contact = gajim.contacts.get_contact_from_full_jid(account, fjid)
		if self.contact:
			self.window.set_title(_('OTR settings for %s') % \
					self.contact.get_full_jid())

		self.ctx = gajim.otr_module.otrl_context_find(
				gajim.connections[self.account].otr_userstates,
				self.fjid.encode(), gajim.get_jid_from_account(
				self.account).encode(), gajim.OTR_PROTO, 1,
				(gajim.otr_add_appdata, self.account))[0]


		# the lambda thing is an anonymous helper that just discards the
		# parameters and calls hide_on_delete on clicking the window's
		# close button
		self.window.connect('delete-event', lambda d,o:
				self.window.hide_on_delete())

		self.gw('smp_cancel_button').connect('clicked', self._on_destroy)
		self.gw('smp_ok_button').connect('clicked', self._apply)
		self.gw('qcheckbutton').connect('toggled', self._toggle)

		self.gw('qcheckbutton').set_no_show_all(False)
		self.gw('qentry').set_no_show_all(False)
		self.gw('desclabel2').set_no_show_all(False)

	def _toggle(self, w, *args):
		self.gw('qentry').set_sensitive(w.get_active())

	def show(self, response):
		# re-initialize if contact was unknown when we
		# initially initialized
		if not self.contact:
			self.__init__(self.fjid, self.account)
		# the contact MUST be known when showing the dialog
		assert(self.contact)

		self.smp_running = False
		self.finished = False

		self.gw('smp_cancel_button').set_sensitive(True)
		self.gw('smp_ok_button').set_sensitive(True)
		self.gw('progressbar').set_fraction(0)
		self.gw('secret_entry').set_text('')

		self.response = response
		self.window.show_all()
		if response:
			self.gw('qcheckbutton').set_sensitive(False)
			if not gajim.otr_v320 or self.question is None:
				self.gw('qcheckbutton').set_active(False)
				self.gw('qcheckbutton').hide()
				self.gw('qentry').hide()
				self.gw('desclabel2').hide()
				self.gw('qcheckbutton').set_sensitive(False)
				self.gw('desclabel1').set_markup((smp_query %
						self.contact.get_full_jid()) +' '+ enter_secret)
			else:
				self.gw('qcheckbutton').set_active(True)
				self.gw('qcheckbutton').show()
				self.gw('qentry').show()
				self.gw('qentry').set_sensitive(True)
				self.gw('qentry').set_editable(False)
				self.gw('desclabel2').show()
				self.gw('qentry').set_text(self.question)

				self.gw('desclabel1').set_markup(smp_q_query %
						self.contact.get_full_jid())
				self.gw('desclabel2').set_markup(enter_secret)
		else:

			if gajim.otr_v320:
				self.gw('qcheckbutton').show()
				self.gw('qcheckbutton').set_active(True)
				self.gw('qcheckbutton').set_mode(True)
				self.gw('qcheckbutton').set_sensitive(True)
				self.gw('qentry').set_sensitive(True)
				self.gw('qentry').show()
				self.gw('qentry').set_text("")

				self.gw('qentry').set_editable(True)
				self.gw('qentry').set_sensitive(
						self.gw('qcheckbutton').get_active())

				self.gw('desclabel2').show()
				self.gw('desclabel1').set_markup((smp_init %
						self.contact.get_full_jid()) + ' ' + choose_q)
				self.gw('desclabel2').set_markup(enter_secret)
			else:
				self.gw('qcheckbutton').hide()
				self.gw('qcheckbutton').set_active(False)
				self.gw('qcheckbutton').set_mode(True)
				self.gw('qcheckbutton').set_sensitive(False)
				self.gw('qentry').set_sensitive(False)
				self.gw('qentry').hide()
				self.gw('qentry').set_text("")
				self.gw('desclabel2').hide()
				self.gw('desclabel1').set_markup((smp_init %
						self.contact.get_full_jid()) + ' ' + enter_secret)



	def _abort(self, text=None):
		self.smp_running = False
		gajim.otr_module.otrl_message_abort_smp(
				gajim.connections[self.account].otr_userstates,
				(gajim.otr_ui_ops, {'account': self.account}), self.ctx)
		if text:
			gajim.otr_ui_ops.gajim_log(text, self.account,
					self.contact.get_full_jid())

	def _finish(self, text):
		self.smp_running = False
		self.finished = True

		self.gw('qcheckbutton').set_active(False)
		self.gw('qcheckbutton').hide()
		self.gw('qentry').hide()
		self.gw('desclabel2').hide()

		self.gw('qcheckbutton').set_sensitive(False)
		self.gw('smp_cancel_button').set_sensitive(False)
		self.gw('smp_ok_button').set_sensitive(True)
		self.gw('progressbar').set_fraction(1)
		gajim.otr_ui_ops.gajim_log(text, self.account,
				self.contact.get_full_jid())
		self.gw('desclabel1').set_markup(text)

		ctrl = gajim.interface.msg_win_mgr.get_control(self.contact.jid,
				self.account)
		if ctrl:
			ctrl.update_otr(True)

		gajim.otr_ui_ops.write_fingerprints({'account': self.account})
		gajim.otr_ui_ops.update_context_list()

	def handle_tlv(self, tlvs):
		if not self.contact:
			self.__init__(self.fjid, self.account)

		if tlvs:
			nextTLV = self.ctx.smstate.nextExpected;

			# check for TLV_SMP_ABORT
			if gajim.otr_module.otrl_tlv_find(tlvs,
			gajim.otr_module.OTRL_TLV_SMP_ABORT) is not None:
				self._finish(_('SMP verifying aborted'))

			elif gajim.otr_v320 and self.ctx.smstate.sm_prog_state \
			== gajim.otr_module.OTRL_SMP_PROG_CHEATED:
				self._finish(_('SMP verifying aborted'))

			# check for TLV_SMP1
			elif gajim.otr_module.otrl_tlv_find(tlvs,
			gajim.otr_module.OTRL_TLV_SMP1) is not None:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT1:
					self._abort()
				else:
					self.question = None
					self.show(True)
					self.gw('progressbar').set_fraction(0.3)

			# check for TLV_SMP1Q
			elif gajim.otr_v320 and gajim.otr_module.otrl_tlv_find(
			tlvs, gajim.otr_module.OTRL_TLV_SMP1Q) is not None:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT1:
					self._abort()
				else:
					tlv = gajim.otr_module.otrl_tlv_find(tlvs,
							gajim.otr_module.OTRL_TLV_SMP1Q)
					self.question = tlv.data
					self.show(True)
					self.gw('progressbar').set_fraction(0.3)

			# check for TLV_SMP2
			elif gajim.otr_module.otrl_tlv_find(tlvs,
			gajim.otr_module.OTRL_TLV_SMP2) is not None:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT2:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT4
					self.gw('progressbar').set_fraction(0.6)

			# check for TLV_SMP3
			elif gajim.otr_module.otrl_tlv_find(tlvs,
			gajim.otr_module.OTRL_TLV_SMP3) is not None:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT3:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT1

					success = False
					if gajim.otr_v320:
						success = (self.ctx.smstate.sm_prog_state ==
								gajim.otr_module.OTRL_SMP_PROG_SUCCEEDED)
					else:
						success = bool(self.ctx.active_fingerprint.trust)

					if success:
						text = _('SMP verifying succeeded')
						if self.question is not None:
							text += ' '+another_q
						self._finish(text)
					else:
						self._finish(_('SMP verifying failed'))

			# check for TLV_SMP4
			elif gajim.otr_module.otrl_tlv_find(tlvs,
			gajim.otr_module.OTRL_TLV_SMP4) is not None:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT4:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT1

					success = False
					if gajim.otr_v320:
						success = (self.ctx.smstate.sm_prog_state ==
								gajim.otr_module.OTRL_SMP_PROG_SUCCEEDED)
					else:
						success = bool(self.ctx.active_fingerprint.trust)

					if success:
						text = _('SMP verifying succeeded')
						if self.question is not None:
							text += ' '+another_q
						self._finish(text)
					else:
						self._finish(_('SMP verifying failed'))

	def _on_destroy(self, widget):
		if self.smp_running:
			self._abort(_('user aborted SMP authentication'))
		self.window.hide_all()

	def _apply(self, widget):
		if self.finished:
			self.window.hide_all()
			return
		secret = self.gw('secret_entry').get_text()
		if self.response:
			gajim.otr_module.otrl_message_respond_smp(
					gajim.connections[self.account].otr_userstates,
					(gajim.otr_ui_ops, {'account': self.account}), self.ctx, secret)
		else:
			if gajim.otr_v320 and self.gw('qcheckbutton').get_active():
				gajim.otr_module.otrl_message_initiate_smp_q(
						gajim.connections[self.account].otr_userstates,
						(gajim.otr_ui_ops, {'account':self.account}), self.ctx,
						self.gw('qentry').get_text(), secret)
			else:
				gajim.otr_module.otrl_message_initiate_smp(
						gajim.connections[self.account].otr_userstates,
						(gajim.otr_ui_ops, {'account':self.account}), self.ctx,
						secret)
			self.gw('progressbar').set_fraction(0.3)
		self.smp_running = True
		widget.set_sensitive(False)

class ContactOtrWindow:
	def gw(self, n):
		# shorthand for self.xml.get_widget(n)
		return self.xml.get_widget(n)

	def __init__(self, fjid, account, ctrl=None, fpr=None):
		self.fjid = fjid
		self.jid = gajim.get_room_and_nick_from_fjid(self.fjid)[0]
		self.account = account
		self.ctrl = ctrl
		self.fpr = fpr

		self.ctx = gajim.otr_module.otrl_context_find(
				gajim.connections[self.account].otr_userstates, self.fjid.encode(),
				gajim.get_jid_from_account(self.account).encode(), gajim.OTR_PROTO,
				1, (gajim.otr_add_appdata, self.account))[0]

		if self.fpr is None:
			self.fpr = self.ctx.active_fingerprint

		self.xml = gtkgui_helpers.get_glade('contact_otr_window.glade')
		self.window = self.xml.get_widget('otr_settings_window')

		self.gw('settings_cancel_button').connect('clicked', self._on_destroy)
		self.gw('settings_ok_button').connect('clicked', self._apply)
		self.gw('otr_default_checkbutton').connect('toggled',
				self._otr_default_checkbutton_toggled)

		self.window.set_title(_('OTR settings for %s') % self.fjid)

		# always set the label containing our fingerprint
		self.gw('our_fp_label').set_markup(our_fp_text % \
				gajim.otr_module.otrl_privkey_fingerprint(
						gajim.connections[self.account].otr_userstates,
						gajim.get_jid_from_account(self.account).encode(),
						gajim.OTR_PROTO))

		if self.fpr is None:
			# make the fingerprint widgets insensitive
			# when not encrypted
			for widget in self.gw('otr_fp_vbox').get_children():
				widget.set_sensitive(False)
			# show that the fingerprint is unknown
			self.gw('their_fp_label').set_markup(their_fp_text % (self.fjid,
					_('unknown')))
			self.gw('verified_combobox').set_active(-1)
		else:
			# make the fingerprint widgets sensitive when encrypted
			for widget in self.gw('otr_fp_vbox').get_children():
				widget.set_sensitive(True)
			# show their fingerprint
			self.gw('their_fp_label').set_markup(their_fp_text %
						(self.fjid, gajim.otr_module.otrl_privkey_hash_to_human(
								self.fpr.fingerprint))
					)
			# set the trust combobox
			if self.fpr.trust:
				self.gw('verified_combobox').set_active(1)
			else:
				self.gw('verified_combobox').set_active(0)

		otr_flags = gajim.config.get_per('contacts', self.jid,
				'otr_flags')

		if otr_flags >= 0:
			self.gw('otr_default_checkbutton').set_active(0)
			for w in self.gw('otr_settings_vbox').get_children():
				w.set_sensitive(True)
		else:
			# per-user settings not available,
			# using default settings
			otr_flags = gajim.config.get_per('accounts', self.account, 'otr_flags')
			self.gw('otr_default_checkbutton').set_active(1)
			for w in self.gw('otr_settings_vbox').get_children():
				w.set_sensitive(False)

		self.gw('otr_policy_allow_v1_checkbutton').set_active(
				otr_flags & gajim.otr_module.OTRL_POLICY_ALLOW_V1)
		self.gw('otr_policy_allow_v2_checkbutton').set_active(
				otr_flags & gajim.otr_module.OTRL_POLICY_ALLOW_V2)
		self.gw('otr_policy_require_checkbutton').set_active(
				otr_flags & gajim.otr_module.OTRL_POLICY_REQUIRE_ENCRYPTION)
		self.gw('otr_policy_send_tag_checkbutton').set_active(
				otr_flags &  gajim.otr_module.OTRL_POLICY_SEND_WHITESPACE_TAG)
		self.gw('otr_policy_start_on_tag_checkbutton').set_active(
				otr_flags & gajim.otr_module.OTRL_POLICY_WHITESPACE_START_AKE)
		self.gw('otr_policy_start_on_error_checkbutton').set_active(
				otr_flags & gajim.otr_module.OTRL_POLICY_ERROR_START_AKE)

		self.window.show_all()

	def _on_destroy(self, widget):
		self.window.destroy()

	def _apply(self, widget):
		# -1 when nothing is selected
		# (ie. the connection is not encrypted)
		trust_state = self.gw('verified_combobox').get_active()
		if trust_state == 1 and not self.fpr.trust:
			gajim.otr_module.otrl_context_set_trust(self.fpr, 'verified')
			gajim.otr_ui_ops.write_fingerprints({'account': self.account})
			gajim.otr_ui_ops.update_context_list()
		elif trust_state == 0:
			gajim.otr_module.otrl_context_set_trust(self.fpr, '')
			gajim.otr_ui_ops.write_fingerprints({'account': self.account})
			gajim.otr_ui_ops.update_context_list()

		if not self.ctrl:
			self.ctrl = gajim.interface.msg_win_mgr.get_control(self.jid,
					self.account)
		if self.ctrl:
			self.ctrl.update_otr(True)

		if self.gw('otr_default_checkbutton').get_active():
			# default is enabled, so remove any user-specific
			# settings if available
			gajim.config.set_per('contacts', self.jid, 'otr_flags', -1)
		else:
			# build the flags using the checkboxes
			flags = 0
			flags += self.gw('otr_policy_allow_v1_checkbutton').get_active() and \
					gajim.otr_module.OTRL_POLICY_ALLOW_V1

			flags += self.gw('otr_policy_allow_v2_checkbutton').get_active() and \
					gajim.otr_module.OTRL_POLICY_ALLOW_V2

			flags += self.gw('otr_policy_require_checkbutton').get_active() and \
					gajim.otr_module.OTRL_POLICY_REQUIRE_ENCRYPTION

			flags += self.gw('otr_policy_send_tag_checkbutton').get_active() and \
					gajim.otr_module.OTRL_POLICY_SEND_WHITESPACE_TAG

			flags += self.gw('otr_policy_start_on_tag_checkbutton').get_active() \
					and gajim.otr_module.OTRL_POLICY_WHITESPACE_START_AKE
			flags += self.gw('otr_policy_start_on_error_checkbutton').get_active()\
					and gajim.otr_module.OTRL_POLICY_ERROR_START_AKE
			
			gajim.config.add_per('contacts', self.jid)
			gajim.config.set_per('contacts', self.jid, 'otr_flags', flags)

		self._on_destroy(widget)

	def _otr_default_checkbutton_toggled(self, widget):
		for w in self.gw('otr_settings_vbox').get_children():
			w.set_sensitive(not widget.get_active())
