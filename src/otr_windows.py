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

our_fp_text = """Your fingerprint:
<span weight="bold" face="monospace">%s</span>"""

their_fp_text = """Purported fingerprint for %s:
<span weight="bold" face="monospace">%s</span>"""

class ContactOtrSMPWindow:

	def gw(self, n):
		""" shorthand for self.xml.get_widget(n)"""
		return self.xml.get_widget(n)

	def __init__(self, fjid, account):
		self.fjid = fjid
		self.account = account

		self.xml = gtkgui_helpers.get_glade("contact_otr_window.glade")
		self.window = self.xml.get_widget("otr_smp_window")


		# the contact may be unknown to gajim if ContactOtrSMPWindow is created very early
		self.contact = gajim.contacts.get_contact_from_full_jid(account, fjid)
		if self.contact:
			self.window.set_title("OTR settings for %s"%
				self.contact.get_full_jid())

		self.ctx = gajim.otr_module.otrl_context_find(
			gajim.connections[self.account].otr_userstates,
			self.fjid.encode(), gajim.get_jid_from_account(self.account).encode(),
			gajim.OTR_PROTO, 1, (gajim.otr_add_appdata, self.account))[0]

		self.gw("smp_cancel_button").connect("clicked", self._on_destroy)
		self.gw("smp_ok_button").connect("clicked", self._apply)

	def show(self, response):
		# re-initialize if contact was unknown when we initially initialized
		if not self.contact:
			self.__init__(self.fjid, self.account)
		assert(self.contact) # the contact MUST be known when showing the dialog

		self.smp_running = False
		self.finished = False

		self.response = response
		if response:
			self.gw("desc_label").set_markup("<b>%s is trying to authenticate you "
				"using a secret only known to him/her and you.</b> Please enter your secret "
				"below."% self.contact.get_full_jid())
		else:
			self.gw("desc_label").set_markup("<b>You are trying to authenticate %s "
				"using a secret only known to him/her and yourself.</b> Please enter your "
				"secret below."% self.contact.get_full_jid())

		self.window.show_all()

	def _abort(self, text=None):
		self.smp_running = False
		gajim.otr_module.otrl_message_abort_smp(gajim.connections[self.account].otr_userstates,
				(gajim.otr_ui_ops, {'account':self.account}), self.ctx)
		if text:
			gajim.otr_ui_ops.gajim_log(text, self.account, self.contact.get_full_jid())

	def _finish(self, text):
		self.smp_running = False
		self.finished = True
		self.gw("smp_cancel_button").set_sensitive(False)
		self.gw("smp_ok_button").set_sensitive(True)
		self.gw("progressbar").set_fraction(1)
		gajim.otr_ui_ops.gajim_log(text, self.account, self.contact.get_full_jid())
		self.gw("desc_label").set_markup(text)
		for ctrl in gajim.interface.msg_win_mgr.get_chat_controls(self.contact.jid, self.account):
			ctrl.update_ui()
		gajim.otr_ui_ops.write_fingerprints({'account':self.account})

	def handle_tlv(self, tlvs):
		if not self.contact:
			self.__init__(self.fjid, self.account)

		if tlvs:
			nextTLV = self.ctx.smstate.nextExpected;
			tlv = gajim.otr_module.otrl_tlv_find(tlvs, gajim.otr_module.OTRL_TLV_SMP1)
			if tlv:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT1:
					self._abort()
				else:
					self.show(True)
					self.gw("progressbar").set_fraction(0.3)
			tlv = gajim.otr_module.otrl_tlv_find(tlvs, gajim.otr_module.OTRL_TLV_SMP2)
			if tlv:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT2:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT4;
					self.gw("progressbar").set_fraction(0.6)
			tlv = gajim.otr_module.otrl_tlv_find(tlvs, gajim.otr_module.OTRL_TLV_SMP3)
			if tlv:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT3:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT1;
					if self.ctx.active_fingerprint.trust:
						self._finish("SMP verifying succeeded")
					else:
						self._finish("SMP verifying failed")
			tlv = gajim.otr_module.otrl_tlv_find(tlvs, gajim.otr_module.OTRL_TLV_SMP4)
			if tlv:
				if nextTLV != gajim.otr_module.OTRL_SMP_EXPECT4:
					self._abort()
				else:
					self.ctx.smstate.nextExpected = gajim.otr_module.OTRL_SMP_EXPECT1;
					if self.ctx.active_fingerprint.trust:
						self._finish("SMP verifying succeeded")
					else:
						self._finish("SMP verifying failed")
			tlv = gajim.otr_module.otrl_tlv_find(tlvs, gajim.otr_module.OTRL_TLV_SMP_ABORT)
			if tlv:
				self._finish("SMP verifying aborted")

	def _on_destroy(self, widget):
		if self.smp_running:
			self._abort("user aborted SMP authentication")
		self.window.hide_all()

	def _apply(self, widget):
		if self.finished:
			self.window.hide_all()
			return
		secret = self.gw("secret_entry").get_text()
		if self.response:
			gajim.otr_module.otrl_message_respond_smp(gajim.connections[self.account].otr_userstates,
					(gajim.otr_ui_ops, {'account':self.account}), self.ctx, secret)
		else:
			gajim.otr_module.otrl_message_initiate_smp(gajim.connections[self.account].otr_userstates,
					(gajim.otr_ui_ops, {'account':self.account}), self.ctx, secret)
			self.gw("progressbar").set_fraction(0.3)
		self.smp_running = True
		widget.set_sensitive(False)


class ContactOtrWindow:

	def gw(self, n):
		""" shorthand for self.xml.get_widget(n)"""
		return self.xml.get_widget(n)

	def __init__(self, contact, account, ctrl=None):
		self.contact = contact
		self.account = account
		self.ctrl = ctrl

		self.ctx = gajim.otr_module.otrl_context_find(
			gajim.connections[self.account].otr_userstates,
			self.contact.get_full_jid().encode(),
			gajim.get_jid_from_account(self.account).encode(),
			gajim.OTR_PROTO, 1, (gajim.otr_add_appdata, self.account))[0]

		self.xml = gtkgui_helpers.get_glade("contact_otr_window.glade")
		self.window = self.xml.get_widget("otr_settings_window")

		self.gw("settings_cancel_button").connect("clicked", self._on_destroy)
		self.gw("settings_ok_button").connect("clicked", self._apply)
		self.gw("otr_default_checkbutton").connect("toggled",
				self._otr_default_checkbutton_toggled)

		self.window.set_title("OTR settings for %s"%
			self.contact.get_full_jid())

		# always set the label containing our fingerprint
		self.gw("our_fp_label").set_markup(our_fp_text%
			gajim.otr_module.otrl_privkey_fingerprint(
				gajim.connections[self.account].otr_userstates,
				gajim.get_jid_from_account(self.account).encode(),
				gajim.OTR_PROTO))

		if self.ctx.msgstate != gajim.otr_module.OTRL_MSGSTATE_ENCRYPTED:
			# make the fingerprint widgets insensitive when not encrypted
			for widget in self.gw("otr_fp_vbox").get_children():
				widget.set_sensitive(False)
			# show that the fingerprint is unknown
			self.gw("their_fp_label").set_markup(
				their_fp_text%(self.contact.get_full_jid(),
				"unknown"))
			self.gw("verified_combobox").set_active(-1)
		else:
			# make the fingerprint widgets sensitive when encrypted
			for widget in self.gw("otr_fp_vbox").get_children():
				widget.set_sensitive(True)
			# show their fingerprint
			self.gw("their_fp_label").set_markup(
				their_fp_text%(self.contact.get_full_jid(),
				gajim.otr_module.otrl_privkey_hash_to_human(
					self.ctx.active_fingerprint.fingerprint)))
			# set the trust combobox
			if self.ctx.active_fingerprint.trust:
				self.gw("verified_combobox").set_active(1)
			else:
				self.gw("verified_combobox").set_active(0)

		otr_flags = gajim.config.get_per("contacts", self.contact.jid,
			"otr_flags")

		if otr_flags >= 0:
			self.gw("otr_default_checkbutton").set_active(0)
			for w in self.gw("otr_settings_vbox").get_children():
				w.set_sensitive(True)
		else:
			# per-user settings not available, using default settings
			otr_flags = gajim.config.get_per("accounts", self.account,
				"otr_flags")
			self.gw("otr_default_checkbutton").set_active(1)
			for w in self.gw("otr_settings_vbox").get_children():
				w.set_sensitive(False)

		self.gw("otr_policy_allow_v1_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_ALLOW_V1)
		self.gw("otr_policy_allow_v2_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_ALLOW_V2)
		self.gw("otr_policy_require_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_REQUIRE_ENCRYPTION)
		self.gw("otr_policy_send_tag_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_SEND_WHITESPACE_TAG)
		self.gw("otr_policy_start_on_tag_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_WHITESPACE_START_AKE)
		self.gw("otr_policy_start_on_error_checkbutton").set_active(
			otr_flags & gajim.otr_module.OTRL_POLICY_ERROR_START_AKE)

		self.window.show_all()

	def _on_destroy(self, widget):
		self.window.destroy()

	def _apply(self, widget):
		# -1 when nothing is selected (ie. the connection is not encrypted)
		trust_state = self.gw("verified_combobox").get_active()
		if  trust_state == 1 and not self.ctx.active_fingerprint.trust:
			gajim.otr_module.otrl_context_set_trust(
				self.ctx.active_fingerprint, "verified")
			gajim.otr_ui_ops.write_fingerprints({'account':self.account})
		elif trust_state == 0:
			gajim.otr_module.otrl_context_set_trust(
				self.ctx.active_fingerprint, "")
			gajim.otr_ui_ops.write_fingerprints({'account':self.account})

		if not self.ctrl:
			self.ctrl = gajim.interface.msg_win_mgr.get_control(
					self.contact.jid, self.account)
		if self.ctrl:
			self.ctrl.update_ui()

		if self.gw("otr_default_checkbutton").get_active():
			# default is enabled, so remove any user-specific settings if available
			gajim.config.set_per("contacts", self.contact.jid, "otr_flags", -1)
		else:
			# build the flags using the checkboxes
			flags = 0
			flags += self.gw("otr_policy_allow_v1_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_ALLOW_V1
			flags += self.gw("otr_policy_allow_v2_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_ALLOW_V2
			flags += self.gw("otr_policy_require_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_REQUIRE_ENCRYPTION
			flags += self.gw("otr_policy_send_tag_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_SEND_WHITESPACE_TAG
			flags += self.gw("otr_policy_start_on_tag_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_WHITESPACE_START_AKE
			flags += self.gw("otr_policy_start_on_error_checkbutton").get_active() \
				and gajim.otr_module.OTRL_POLICY_ERROR_START_AKE
			
			gajim.config.add_per("contacts", self.contact.jid)
			gajim.config.set_per("contacts", self.contact.jid, "otr_flags", flags)

		self._on_destroy(widget)

	def _otr_default_checkbutton_toggled(self, widget):
		for w in self.gw("otr_settings_vbox").get_children():
			w.set_sensitive(not widget.get_active())
