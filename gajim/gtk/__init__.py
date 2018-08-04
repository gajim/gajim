# Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005      Alex Podaras <bigpod AT gmail.com>
#                         Stéphan Kochen <stephan AT kochen.nl>
#                         Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2005-2008 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006      Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
#                         Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007      James Newton <redshodan AT gmail.com>
#                         Lukas Petrovicky <lukas AT petrovicky.net>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008      Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018      Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InformationDialog
from gajim.gtk.dialogs import ChangeNickDialog
from gajim.gtk.dialogs import FTOverwriteConfirmationDialog
from gajim.gtk.dialogs import InputDialog
from gajim.gtk.dialogs import ConfirmationDialogDoubleRadio
from gajim.gtk.dialogs import InputDialogCheck
from gajim.gtk.dialogs import DoubleInputDialog
from gajim.gtk.dialogs import InputTextDialog
from gajim.gtk.dialogs import PlainConnectionDialog
from gajim.gtk.dialogs import ConfirmationDialogDoubleCheck
from gajim.gtk.dialogs import ConfirmationDialogCheck
from gajim.gtk.dialogs import YesNoDialog
from gajim.gtk.dialogs import WarningDialog
from gajim.gtk.dialogs import NonModalConfirmationDialog
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import AspellDictError
from gajim.gtk.dialogs import HigDialog
from gajim.gtk.dialogs import SSLErrorDialog
from gajim.gtk.dialogs import ChangePasswordDialog

from gajim.gtk.about import AboutDialog
from gajim.gtk.join_groupchat import JoinGroupchatWindow
from gajim.gtk.add_contact import AddNewContactWindow
from gajim.gtk.start_chat import StartChatDialog
from gajim.gtk.xml_console import XMLConsoleWindow
from gajim.gtk.privacy_list import PrivacyListsWindow
from gajim.gtk.single_message import SingleMessageWindow
from gajim.gtk.server_info import ServerInfoDialog
from gajim.gtk.pep_config import ManagePEPServicesWindow
from gajim.gtk.bookmarks import ManageBookmarksWindow
from gajim.gtk.profile import ProfileWindow
from gajim.gtk.features import FeaturesDialog
from gajim.gtk.account_wizard import AccountCreationWizard
from gajim.gtk.service_registration import ServiceRegistration
from gajim.gtk.history import HistoryWindow
