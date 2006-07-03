NAME = gajim
LANGS   := fr pt el pl es ru bg de nb cs nl pt_BR sv it eu sk no zh_CN br eo
LANGS_PO:=$(foreach LANG, ${LANGS}, ${LANG}.po)
LANGS_MO:=$(foreach LANG, ${LANGS}, ${LANG}.mo)
DATADIR:=$(subst //,/,${DESTDIR}/${PREFIX}/share)

all: $(LANGS_MO)

%.mo: %.po
	msgfmt $< -o $@

gajim.pot: ../src/*py ../src/common/*py \
			../data/glade/account_context_menu.glade.h \
			../data/glade/account_creation_wizard_window.glade.h \
			../data/glade/account_modification_window.glade.h \
			../data/glade/accounts_window.glade.h \
			../data/glade/add_new_contact_window.glade.h \
			../data/glade/advanced_configuration_window.glade.h \
			../data/glade/advanced_menuitem_menu.glade.h \
			../data/glade/change_password_dialog.glade.h \
			../data/glade/change_status_message_dialog.glade.h \
			../data/glade/chat_context_menu.glade.h \
			../data/glade/chat_control_popup_menu.glade.h \
			../data/glade/choose_gpg_key_dialog.glade.h \
			../data/glade/data_form_window.glade.h \
			../data/glade/edit_groups_dialog.glade.h \
			../data/glade/filetransfers.glade.h \
			../data/glade/gajim_themes_window.glade.h \
			../data/glade/gc_control_popup_menu.glade.h \
			../data/glade/gc_occupants_menu.glade.h \
			../data/glade/history_manager.glade.h \
			../data/glade/history_window.glade.h \
			../data/glade/input_dialog.glade.h \
			../data/glade/invitation_received_dialog.glade.h \
			../data/glade/join_groupchat_window.glade.h \
			../data/glade/manage_accounts_window.glade.h \
			../data/glade/manage_bookmarks_window.glade.h \
			../data/glade/manage_proxies_window.glade.h \
			../data/glade/message_window.glade.h \
			../data/glade/passphrase_dialog.glade.h \
			../data/glade/popup_notification_window.glade.h \
			../data/glade/preferences_window.glade.h \
			../data/glade/privacy_list_edit_window.glade.h \
			../data/glade/privacy_lists_first_window.glade.h \
			../data/glade/progress_dialog.glade.h \
			../data/glade/remove_account_window.glade.h \
			../data/glade/roster_contact_context_menu.glade.h \
			../data/glade/roster_window.glade.h \
			../data/glade/service_discovery_window.glade.h \
			../data/glade/service_registration_window.glade.h \
			../data/glade/single_message_window.glade.h \
			../data/glade/subscription_request_window.glade.h \
			../data/glade/systray_context_menu.glade.h \
			../data/glade/vcard_information_window.glade.h \
			../data/glade/xml_console_window.glade.h
	intltool-update --pot --gettext-package=$(NAME)

install:
	for l in ${LANGS}; do\
		dir=${DATADIR}/locale/$${l}/LC_MESSAGES;\
		if test ! -d $${dir}; then\
			install -m 755 -d $${dir};\
		fi;\
		install -m 644 $${l}.mo $${dir}/${NAME}.mo;\
	done

clean:
	rm -f *.mo 
