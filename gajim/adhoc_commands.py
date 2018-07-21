# -*- coding: utf-8 -*-
## src/adhoc_commands.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

# FIXME: think if we need caching command list. it may be wrong if there will
# be entities that often change the list, it may be slow to fetch it every time

from gi.repository import Gtk

import nbxmpp
from gajim.common import app
from gajim.common.modules import dataforms
from gajim.common import ged

from gajim import gtkgui_helpers
from gajim.gtk import HigDialog
from gajim import dataforms_widget


class CommandWindow:
    """
    Class for a window for single ad-hoc commands session

    Note, that there might be more than one for one account/jid pair in one
    moment.

    TODO: Maybe put this window into MessageWindow? consider this when it will
    be possible to manage more than one window of one.
    TODO: Account/jid pair in MessageWindowMgr.
    TODO: GTK 2.10 has a special wizard-widget, consider using it...
    """

    def __init__(self, account, jid, commandnode=None):
        """
        Create new window
        """

        # an account object
        self._con = app.connections[account]
        self.jid = jid
        self.commandnode = commandnode
        self.data_form_widget = None
        self.stage_finish_cb = None
        self.stage_back_button_cb = None
        self.stage_forward_button_cb = None
        self.stage_execute_button_cb = None
        self.stage_close_button_cb = None
        self.stage_restart_button_cb = None
        self.stage_window_delete_cb = None

        # retrieving widgets from xml
        self.xml = gtkgui_helpers.get_gtk_builder('adhoc_commands_window.ui')
        self.window = self.xml.get_object('adhoc_commands_window')
        self.window.connect('delete-event',
            self.on_adhoc_commands_window_delete_event)
        for name in ('restart_button', 'back_button', 'forward_button',
        'execute_button', 'finish_button', 'close_button', 'stages_notebook',
        'retrieving_commands_stage_vbox', 'retrieving_commands_spinner',
        'command_list_stage_vbox', 'command_treeview',
        'sending_form_stage_vbox', 'sending_form_spinner',
        'notes_label', 'no_commands_stage_vbox',
        'error_stage_vbox', 'error_description_label'):
            setattr(self, name, self.xml.get_object(name))

        self.command_store = Gtk.ListStore(str, str)
        self.command_treeview.set_model(self.command_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Command", renderer, text=0)
        self.command_treeview.append_column(column)

        app.ged.register_event_handler(
            'adhoc-command-error', ged.CORE, self._on_command_error)
        app.ged.register_event_handler(
            'adhoc-command-list', ged.CORE, self._on_command_list)
        app.ged.register_event_handler('adhoc-command-action-response',
                                       ged.CORE,
                                       self._on_action_response)

        self.initiate()

    def initiate(self):

        self.commandlist = None   # a list of (commandname, commanddescription)

        # command's data
        self.sessionid = None
        self.dataform = None
        self.allow_stage3_close = False

        # creating data forms widget
        if self.data_form_widget:
            self.sending_form_stage_vbox.remove(self.data_form_widget)
            self.data_form_widget.destroy()
        self.data_form_widget = dataforms_widget.DataFormWidget()
        self.data_form_widget.show()
        self.sending_form_stage_vbox.pack_start(self.data_form_widget, True, True, 0)

        if self.commandnode:
            # Execute command
            self.stage3()
        else:
            # setting initial stage
            self.stage1()

        # displaying the window
        self.window.set_title(_('Ad-hoc Commands - Gajim'))
        self.xml.connect_signals(self)
        self.window.show_all()

        self.restart_button.set_sensitive(False)

    # These functions are set up by appropriate stageX methods.
    def stage_finish(self, *anything):
        if self.stage_finish_cb:
            self.stage_finish_cb(*anything)

    # Widget callbacks...
    def on_back_button_clicked(self, *anything):
        if self.stage_back_button_cb:
            return self.stage_back_button_cb(*anything)
        return False

    def on_forward_button_clicked(self, *anything):
        if self.stage_forward_button_cb:
            return self.stage_forward_button_cb(*anything)
        return False

    def on_execute_button_clicked(self, *anything):
        if self.stage_execute_button_cb:
            return self.stage_execute_button_cb(*anything)
        return False

    def on_finish_button_clicked(self, *anything):
        if self.stage_finish_button_cb:
            return self.stage_finish_button_cb(*anything)
        return False

    def on_close_button_clicked(self, *anything):
        if self.stage_close_button_cb:
            return self.stage_close_button_cb(*anything)
        return False

    def on_restart_button_clicked(self, *anything):
        if self.stage_restart_button_cb:
            return self.stage_restart_button_cb(*anything)
        return False

    def on_adhoc_commands_window_destroy(self, *anything):
        app.ged.remove_event_handler(
            'adhoc-command-error', ged.CORE, self._on_command_error)
        app.ged.remove_event_handler(
            'adhoc-command-list', ged.CORE, self._on_command_list)
        app.ged.remove_event_handler('adhoc-command-action-response',
                                     ged.CORE,
                                     self._on_action_response)

    def on_adhoc_commands_window_delete_event(self, *anything):
        if self.stage_window_delete_cb:
            return self.stage_window_delete_cb(self.window)
        return False

    def __del__(self):
        print('Object has been deleted.')

# stage 1: waiting for command list
    def stage1(self):
        """
        Prepare the first stage. Request command list, set appropriate state of
        widgets
        """
        # close old stage...
        self.stage_finish()

        # show the stage
        self.stages_notebook.set_current_page(
                self.stages_notebook.page_num(
                        self.retrieving_commands_stage_vbox))

        # set widgets' state
        self.close_button.set_sensitive(True)
        self.back_button.set_sensitive(False)
        self.forward_button.set_sensitive(False)
        self.execute_button.set_sensitive(False)
        self.finish_button.set_sensitive(False)

        # request command list
        self._con.get_module('AdHocCommands').request_command_list(self.jid)
        self.retrieving_commands_spinner.start()

        # setup the callbacks
        self.stage_finish_cb = self.stage1_finish
        self.stage_close_button_cb = self.stage1_close_button_clicked
        self.stage_restart_button_cb = self.stage1_restart_button_clicked
        self.stage_window_delete_cb = \
            self.stage1_adhoc_commands_window_delete_event

    def stage1_finish(self):
        self.retrieving_commands_spinner.stop()

    def stage1_close_button_clicked(self, widget):
        # cancelling in this stage is not critical, so we don't
        # show any popups to user
        self.stage_finish()
        self.window.destroy()

    def stage1_restart_button_clicked(self, widget):
        self.stage_finish()
        self.restart()

    def stage1_adhoc_commands_window_delete_event(self, widget):
        self.stage1_finish()
        return True

# stage 2: choosing the command to execute
    def stage2(self):
        """
        Populate the command list
        """
        # close old stage
        self.stage_finish()

        assert len(self.commandlist)>0

        self.stages_notebook.set_current_page(
            self.stages_notebook.page_num(self.command_list_stage_vbox))

        self.close_button.set_sensitive(True)
        self.back_button.set_sensitive(False)
        self.forward_button.set_sensitive(True)
        self.execute_button.set_sensitive(False)
        self.finish_button.set_sensitive(False)

        # build the commands list
        self.command_store.clear()
        for (commandnode, commandname) in self.commandlist:
            self.command_store.append([commandname, commandnode])
        self.command_treeview.get_selection().select_iter(self.command_store.get_iter_first())

        self.stage_finish_cb = self.stage2_finish
        self.stage_close_button_cb = self.stage2_close_button_clicked
        self.stage_restart_button_cb = self.stage2_restart_button_clicked
        self.stage_forward_button_cb = self.stage2_forward_button_clicked
        self.stage_window_delete_cb = None

    def stage2_finish(self):
        """
        Save selected command to self.commandnode
        """
        model, treeiter = self.command_treeview.get_selection().get_selected()
        self.commandnode = model[treeiter][1]

    def stage2_close_button_clicked(self, widget):
        self.stage_finish()
        self.window.destroy()

    def stage2_restart_button_clicked(self, widget):
        self.stage_finish()
        self.restart()

    def stage2_forward_button_clicked(self, widget):
        self.stage3()

    def on_check_commands_1_button_clicked(self, widget):
        self.stage1()

# stage 3: command invocation
    def stage3(self):
        # close old stage
        self.stage_finish()

        self.form_status = None

        self.stages_notebook.set_current_page(
                self.stages_notebook.page_num(
                        self.sending_form_stage_vbox))

        self.restart_button.set_sensitive(True)
        self.close_button.set_sensitive(True)
        self.back_button.set_sensitive(False)
        self.forward_button.set_sensitive(False)
        self.execute_button.set_sensitive(False)
        self.finish_button.set_sensitive(False)

        self.stage3_submit_form()

        self.stage_finish_cb = None
        self.stage_back_button_cb = self.stage3_back_button_clicked
        self.stage_forward_button_cb = self.stage3_forward_button_clicked
        self.stage_execute_button_cb = self.stage3_execute_button_clicked
        self.stage_finish_button_cb = self.stage3_finish_button_clicked
        self.stage_close_button_cb = self.stage3_close_button_clicked
        self.stage_restart_button_cb = self.stage3_restart_button_clicked
        self.stage_window_delete_cb = self.stage3_close_button_clicked

    def stage3_can_close(self, cb):
        if self.form_status == 'completed':
            cb()
            return

        def on_yes(button):
            self._con.get_module('AdHocCommands').send_cancel(
                self.jid, self.commandnode, self.sessionid)
            dialog.destroy()
            cb()

        dialog = HigDialog(self.window, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.YES_NO, _('Cancel confirmation'),
            _('You are in process of executing command. Do you really want to '
            'cancel it?'), on_response_yes=on_yes)
        dialog.popup()

    def stage3_close_button_clicked(self, widget):
        """
        We are in the middle of executing command. Ask user if he really want to
        cancel the process, then cancel it
        """
        # this works also as a handler for window_delete_event, so we have to
        # return appropriate values
        if self.allow_stage3_close:
            return False

        def on_ok():
            self.allow_stage3_close = True
            self.window.destroy()

        self.stage3_can_close(on_ok)

        return True # Block event, don't close window

    def stage3_restart_button_clicked(self, widget):
        def on_ok():
            self.restart()

        self.stage3_can_close(on_ok)

    def stage3_back_button_clicked(self, widget):
        self.stage3_submit_form('prev')

    def stage3_forward_button_clicked(self, widget):
        self.stage3_submit_form('next')

    def stage3_execute_button_clicked(self, widget):
        self.stage3_submit_form('execute')

    def stage3_finish_button_clicked(self, widget):
        self.stage3_submit_form('complete')

    def stage3_submit_form(self, action='execute'):
        self.data_form_widget.set_sensitive(False)

        if self.data_form_widget.get_data_form():
            df = self.data_form_widget.get_data_form()
            if not df.is_valid():
                app.interface.raise_dialog(
                    'invalid-form', transient_for=self.window)
                self.data_form_widget.set_sensitive(True)
                return
            self.data_form_widget.data_form.type_ = 'submit'
        else:
            self.data_form_widget.hide()

        self.close_button.set_sensitive(True)
        self.back_button.set_sensitive(False)
        self.forward_button.set_sensitive(False)
        self.execute_button.set_sensitive(False)
        self.finish_button.set_sensitive(False)

        self.sending_form_spinner.start()
        self._con.get_module('AdHocCommands').send_command(
            self.jid, self.commandnode, self.sessionid,
            self.data_form_widget.data_form, action)

    def stage3_next_form(self, command):
        if not isinstance(command, nbxmpp.Node):
            self.stage5(error=_('Service sent malformed data'), senderror=True)
            return

        self.sending_form_spinner.stop()

        if not self.sessionid:
            self.sessionid = command.getAttr('sessionid')
        elif self.sessionid != command.getAttr('sessionid'):
            self.stage5(error=_('Service changed the session identifier.'),
                    senderror=True)
            return

        self.form_status = command.getAttr('status')

        self.commandnode = command.getAttr('node')
        if command.getTag('x'):
            self.dataform = dataforms.ExtendForm(node=command.getTag('x'))

            self.data_form_widget.set_sensitive(True)
            try:
                self.data_form_widget.selectable = True
                self.data_form_widget.data_form = self.dataform
            except dataforms.Error:
                self.stage5(error=_('Service sent malformed data'),
                    senderror=True)
                return
            self.data_form_widget.show()
            if self.data_form_widget.title:
                self.window.set_title(_('%s - Ad-hoc Commands - Gajim') % \
                        self.data_form_widget.title)
        else:
            self.data_form_widget.hide()

        actions = command.getTag('actions')
        if actions:
            # actions, actions, actions...
            self.close_button.set_sensitive(True)
            self.back_button.set_sensitive(actions.getTag('prev') is not None)
            self.forward_button.set_sensitive(
                actions.getTag('next') is not None)
            self.execute_button.set_sensitive(True)
            self.finish_button.set_sensitive(actions.getTag('complete') is not \
                None)
        else:
            self.close_button.set_sensitive(True)
            self.back_button.set_sensitive(False)
            self.forward_button.set_sensitive(False)
            self.execute_button.set_sensitive(True)
            self.finish_button.set_sensitive(False)

        if self.form_status == 'completed':
            self.close_button.set_sensitive(True)
            self.back_button.hide()
            self.forward_button.hide()
            self.execute_button.hide()
            self.finish_button.hide()
            self.close_button.show()
            self.stage_window_delete_cb = self.stage3_close_button_clicked

        note = command.getTag('note')
        if note:
            self.notes_label.set_text(note.getData())
            self.notes_label.set_no_show_all(False)
            self.notes_label.show()
        else:
            self.notes_label.set_no_show_all(True)
            self.notes_label.hide()

    def restart(self):
        self.commandnode = None
        self.initiate()

# stage 4: no commands are exposed
    def stage4(self):
        """
        Display the message. Wait for user to close the window
        """
        # close old stage
        self.stage_finish()

        self.stages_notebook.set_current_page(
            self.stages_notebook.page_num(self.no_commands_stage_vbox))

        self.close_button.set_sensitive(True)
        self.back_button.set_sensitive(False)
        self.forward_button.set_sensitive(False)
        self.execute_button.set_sensitive(False)
        self.finish_button.set_sensitive(False)

        self.stage_finish_cb = None
        self.stage_close_button_cb = self.stage4_close_button_clicked
        self.stage_restart_button_cb = self.stage4_restart_button_clicked
        self.stage_window_delete_cb = None

    def stage4_close_button_clicked(self, widget):
        self.window.destroy()

    def stage4_restart_button_clicked(self, widget):
        self.restart()

    def on_check_commands_2_button_clicked(self, widget):
        self.stage1()

# stage 5: an error has occurred
    def stage5(self, error=None, errorid=None, senderror=False):
        """
        Display the error message. Wait for user to close the window
        """
        # FIXME: sending error to responder
        # close old stage
        self.stage_finish()

        assert errorid or error

        if errorid:
            # we've got error code, display appropriate message
            try:
                errorname = nbxmpp.NS_STANZAS + ' ' + str(errorid)
                errordesc = nbxmpp.ERRORS[errorname][2]
                error = errordesc
                del errorname, errordesc
            except KeyError:        # when stanza doesn't have error description
                error = _('Service returned an error.')
        elif error:
            # we've got error message
            pass
        else:
            # we don't know what's that, bailing out
            assert False

        self.stages_notebook.set_current_page(
            self.stages_notebook.page_num(self.error_stage_vbox))

        self.close_button.set_sensitive(True)
        self.back_button.hide()
        self.forward_button.hide()
        self.execute_button.hide()
        self.finish_button.hide()

        self.error_description_label.set_text(error)

        self.stage_finish_cb = None
        self.stage_close_button_cb = self.stage5_close_button_clicked
        self.stage_restart_button_cb = self.stage5_restart_button_clicked
        self.stage_window_delete_cb = None

    def stage5_close_button_clicked(self, widget):
        self.window.destroy()

    def stage5_restart_button_clicked(self, widget):
        self.restart()

    def _on_command_error(self, obj):
        self.stage5(errorid=obj.error)

    def _on_command_list(self, obj):
        self.commandlist = obj.commandlist
        if not self.commandlist:
            self.stage4()
        else:
            self.stage2()

    def _on_action_response(self, obj):
        self.stage3_next_form(obj.command)
