
from typing import Literal
from typing import overload

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import GtkSource


class Builder(Gtk.Builder): ...

class AccountPageBuilder(Builder):
    paned: Gtk.Paned
    roster_box: Gtk.Box
    roster_menu_button: Gtk.MenuButton
    roster_search_entry: Gtk.SearchEntry
    account_box: Gtk.Box
    avatar_image: Gtk.Image
    account_label: Gtk.Label
    account_action_box: Gtk.Box
    account_settings: Gtk.Button
    status_message_box: Gtk.Box


class AccountWizardBuilder(Builder):
    account_label_box: Gtk.Box
    account_name_entry: Gtk.Entry
    account_color_button: Gtk.ColorButton
    badge_preview: Gtk.Label
    advanced_grid: Gtk.Grid
    custom_port_entry: Gtk.Entry
    custom_host_entry: Gtk.Entry
    proxies_combobox: Gtk.ComboBox
    manage_proxies_button: Gtk.Button
    con_type_combo: Gtk.ComboBoxText
    entrycompletion1: Gtk.EntryCompletion
    login_box: Gtk.Box
    log_in_address_entry: Gtk.Entry
    log_in_password_entry: Gtk.Entry
    login_advanced_checkbutton: Gtk.CheckButton
    log_in_button: Gtk.Button
    sign_up_button: Gtk.Button
    entrycompletion2: Gtk.EntryCompletion
    redirect_box: Gtk.Box
    instructions: Gtk.Label
    link_button: Gtk.Button
    security_warning_box: Gtk.Box
    error_list: Gtk.ListBox
    view_cert_button: Gtk.Button
    trust_cert_checkbutton: Gtk.CheckButton
    server_recommendations: Gtk.Popover
    visit_server_button: Gtk.Button
    recommendation_link1: Gtk.Label
    recommendation_link2: Gtk.Label
    signup_grid: Gtk.Grid
    server_comboboxtext_sign_up: Gtk.ComboBoxText
    server_comboboxtext_sign_up_entry: Gtk.Entry
    sign_up_anonymously: Gtk.CheckButton
    sign_up_advanced_checkbutton: Gtk.CheckButton


class AddContactBuilder(Builder):
    account_liststore: Gtk.ListStore
    address_box: Gtk.Box
    account_box: Gtk.Box
    account_combo: Gtk.ComboBox
    cellrenderertext3: Gtk.CellRendererText
    address_entry: Gtk.Entry
    contact_grid: Gtk.Grid
    status_switch: Gtk.Switch
    group_combo: Gtk.ComboBoxText
    message_entry: Gtk.Entry
    contact_info_button: Gtk.Button
    gateway_box: Gtk.Box
    gateway_image: Gtk.Image
    gateway_label: Gtk.Label
    register_button: Gtk.Button
    commands_button: Gtk.Button


class AdhocMucBuilder(Builder):
    guests_store: Gtk.ListStore
    server_store: Gtk.ListStore
    adhoc_box: Gtk.Box
    description_label: Gtk.Label
    guests_treeview: Gtk.TreeView
    server_combobox: Gtk.ComboBox
    server_entry: Gtk.Entry
    invite_button: Gtk.Button


class AdvancedConfigurationBuilder(Builder):
    box: Gtk.Box
    search_entry: Gtk.SearchEntry
    advanced_treeview: Gtk.TreeView
    description: Gtk.Label
    reset_button: Gtk.Button


class AppPageBuilder(Builder):
    gajim_update: Gtk.Box
    update_message: Gtk.Label
    gajim_update_check: Gtk.Box
    plugin_updates: Gtk.Box
    auto_update_plugins: Gtk.CheckButton
    plugin_updates_finished: Gtk.Box
    notify_after_plugin_updates: Gtk.CheckButton


class ApplicationMenuBuilder(Builder):
    pass


class AssistantBuilder(Builder):
    main_grid: Gtk.Grid
    content_area: Gtk.Box
    stack: Gtk.Stack
    action_area: Gtk.Box


class BlockingListBuilder(Builder):
    blocking_store: Gtk.ListStore
    blocking_grid: Gtk.Grid
    overlay: Gtk.Overlay
    block_view: Gtk.TreeView
    add_button: Gtk.ToolButton
    remove_button: Gtk.ToolButton
    save_button: Gtk.Button


class BookmarksBuilder(Builder):
    bookmarks_store: Gtk.ListStore
    bookmarks_grid: Gtk.Grid
    bookmarks_view: Gtk.TreeView
    jid: Gtk.CellRendererText
    name: Gtk.CellRendererText
    nick: Gtk.CellRendererText
    password: Gtk.CellRendererText
    autojoin: Gtk.CellRendererToggle


class CallWindowBuilder(Builder):
    adjustment1: Gtk.Adjustment
    adjustment2: Gtk.Adjustment
    dtmf_popover: Gtk.Popover
    grid1: Gtk.Grid
    button_1: Gtk.Button
    button_2: Gtk.Button
    button_3: Gtk.Button
    button_4: Gtk.Button
    button_5: Gtk.Button
    button_6: Gtk.Button
    button_7: Gtk.Button
    button_8: Gtk.Button
    button_9: Gtk.Button
    button_star: Gtk.Button
    button_0: Gtk.Button
    button_pound: Gtk.Button
    av_box: Gtk.Box
    video_box: Gtk.Box
    outgoing_viewport: Gtk.Viewport
    incoming_viewport: Gtk.Viewport
    avatar_image: Gtk.Image
    jingle_audio_state: Gtk.Image
    jingle_connection_state: Gtk.Label
    jingle_connection_spinner: Gtk.Spinner
    answer_video_button: Gtk.Button
    av_cam_button: Gtk.Button
    av_cam_image: Gtk.Image
    audio_buttons_box: Gtk.Box
    mic_hscale: Gtk.VolumeButton
    volumebutton_plus_button2: Gtk.Button
    volumebutton_minus_button2: Gtk.Button
    sound_hscale: Gtk.VolumeButton
    volumebutton_plus_button1: Gtk.Button
    volumebutton_minus_button1: Gtk.Button
    dtmf_button: Gtk.MenuButton


class CertificateBuilder(Builder):
    certificate_box: Gtk.Box
    label_cert_for_account: Gtk.Label
    data_it_common_name: Gtk.Label
    data_it_organization: Gtk.Label
    data_it_organizational_unit: Gtk.Label
    data_it_serial_number: Gtk.Label
    data_ib_common_name: Gtk.Label
    data_ib_organization: Gtk.Label
    data_ib_organizational_unit: Gtk.Label
    data_issued_on: Gtk.Label
    data_expires_on: Gtk.Label
    data_sha1: Gtk.Label
    data_sha256: Gtk.Label
    copy_cert_info_button: Gtk.Button
    image1: Gtk.Image


class ChatBannerBuilder(Builder):
    banner_box: Gtk.Box
    avatar_image: Gtk.Image
    name_label: Gtk.Label
    phone_image: Gtk.Image
    toggle_roster_button: Gtk.Button
    toggle_roster_image: Gtk.Image
    account_badge_box: Gtk.Box
    visitor_box: Gtk.Box
    visitor_menu_button: Gtk.MenuButton
    visitor_popover: Gtk.Popover


class ChatControlBuilder(Builder):
    control_box: Gtk.Box
    conv_view_box: Gtk.Box
    conv_view_overlay: Gtk.Overlay


class ChatListRowBuilder(Builder):
    eventbox: Gtk.EventBox
    account_identifier: Gtk.Box
    avatar_image: Gtk.Image
    group_chat_indicator: Gtk.Image
    name_label: Gtk.Label
    chatstate_image: Gtk.Image
    timestamp_label: Gtk.Label
    nick_label: Gtk.Label
    message_icon: Gtk.Image
    message_label: Gtk.Label
    unread_label: Gtk.Label
    revealer: Gtk.Revealer
    close_button: Gtk.Button


class ChatPanedBuilder(Builder):
    paned: Gtk.Paned
    middle_grid: Gtk.Grid
    header_bar: Gtk.Grid
    workspace_label: Gtk.Label
    filter_bar_toggle: Gtk.ToggleButton
    search_entry: Gtk.SearchEntry
    start_chat_button: Gtk.Button
    filter_bar_revealer: Gtk.Revealer
    filter_bar: Gtk.Box
    chat_list_scrolled: Gtk.ScrolledWindow
    right_grid: Gtk.Grid
    right_grid_overlay: Gtk.Overlay


class ContactInfoBuilder(Builder):
    devices_grid: Gtk.Grid
    priority_label: Gtk.Label
    software_label: Gtk.Label
    system_label: Gtk.Label
    time_label: Gtk.Label
    status_value: Gtk.Label
    priority_value: Gtk.Label
    software_value: Gtk.Label
    system_value: Gtk.Label
    time_value: Gtk.Label
    resource_box: Gtk.Box
    resource_label: Gtk.Label
    groups_model: Gtk.ListStore
    main_grid: Gtk.Grid
    header_revealer: Gtk.Revealer
    header_image: Gtk.Image
    name_entry: Gtk.Entry
    edit_name_button: Gtk.ToggleButton
    edit_name_button_image: Gtk.Image
    main_stack: Gtk.Stack
    vcard_scrolled: Gtk.ScrolledWindow
    vcard_box: Gtk.Box
    avatar_image: Gtk.Image
    contact_name_label: Gtk.Label
    contact_jid_label: Gtk.Label
    group_chat_grid: Gtk.Grid
    role_label: Gtk.Label
    affiliation_label: Gtk.Label
    settings_scrolled: Gtk.ScrolledWindow
    settings_box: Gtk.Box
    subscription_listbox: Gtk.ListBox
    from_subscription_switch: Gtk.Switch
    to_subscription_stack: Gtk.Stack
    request_stack: Gtk.Stack
    to_subscription_button: Gtk.Button
    contact_settings_box: Gtk.Box
    remove_history_button: Gtk.Button
    groups_page_box: Gtk.Box
    groups_treeview: Gtk.TreeView
    tree_selection: Gtk.TreeSelection
    toggle_renderer: Gtk.CellRendererToggle
    text_renderer: Gtk.CellRendererText
    group_add_button: Gtk.ToolButton
    group_remove_button: Gtk.ToolButton
    notes_page_box: Gtk.Box
    scrolledwindow_annotation: Gtk.ScrolledWindow
    textview_annotation: Gtk.TextView
    devices_stack: Gtk.Stack
    devices_box: Gtk.Box


class EmojiChooserBuilder(Builder):
    box: Gtk.Box
    search: Gtk.SearchEntry
    stack: Gtk.Stack
    section_box: Gtk.Box


class ExceptionDialogBuilder(Builder):
    exception_box: Gtk.Box
    infobar: Gtk.InfoBar
    exception_view: Gtk.TextView
    user_feedback_box: Gtk.Box
    user_feedback_entry: Gtk.Entry
    close_button: Gtk.Button
    report_button: Gtk.Button
    report_spinner: Gtk.Spinner


class FileTransferBuilder(Builder):
    transfer_box: Gtk.Box
    transfer_description: Gtk.Label
    file_name: Gtk.Label
    file_size: Gtk.Label
    progress_bar: Gtk.ProgressBar
    transfer_progress: Gtk.Label


class FileTransferJingleBuilder(Builder):
    transfer_box: Gtk.Box
    transfer_action: Gtk.Label
    file_name: Gtk.Label
    file_description: Gtk.Label
    file_size: Gtk.Label
    action_stack: Gtk.Stack
    error_label: Gtk.Label
    progress_label: Gtk.Label
    progress_bar: Gtk.ProgressBar


class FileTransferSendBuilder(Builder):
    send_stack: Gtk.Stack
    listbox: Gtk.ListBox
    description: Gtk.TextView
    files_send: Gtk.Button
    resource_box: Gtk.Box
    resource_send: Gtk.Button
    resource_instructions: Gtk.Label


class FiletransfersBuilder(Builder):
    accelgroup1: Gtk.AccelGroup
    file_transfers_menu: Gtk.Menu
    remove_menuitem: Gtk.MenuItem
    pause_resume_menuitem: Gtk.MenuItem
    cancel_menuitem: Gtk.MenuItem
    open_folder_menuitem: Gtk.MenuItem
    file_transfers_window: Gtk.Window
    notify_ft_complete: Gtk.Switch
    transfers_scrolledwindow: Gtk.ScrolledWindow
    transfers_list: Gtk.TreeView
    transfers_list_atkobject: Atk.Object
    cleanup_button: Gtk.ToolButton
    pause_resume_button: Gtk.ToolButton
    cancel_button: Gtk.ToolButton
    file_transfers_window_atkobject: Atk.Object


class GroupchatAffiliationBuilder(Builder):
    affiliation_store: Gtk.ListStore
    combo_store: Gtk.ListStore
    main_box: Gtk.Box
    affiliation_scrolled: Gtk.ScrolledWindow
    affiliation_treeview: Gtk.TreeView
    reserved_name_column: Gtk.TreeViewColumn
    button_box: Gtk.Box
    add_remove_button_box: Gtk.Box
    add_button: Gtk.Button
    remove_button: Gtk.Button


class GroupchatConfigBuilder(Builder):
    stack: Gtk.Stack
    loading_box: Gtk.Box
    config_box: Gtk.Box
    error_box: Gtk.Box
    error_image: Gtk.Image
    error_label: Gtk.Label


class GroupchatCreationBuilder(Builder):
    account_liststore: Gtk.ListStore
    stack: Gtk.Stack
    grid: Gtk.Grid
    name_entry: Gtk.Entry
    description_entry: Gtk.Entry
    account_combo: Gtk.ComboBox
    account_label: Gtk.Label
    address_entry: Gtk.Entry
    address_label: Gtk.Label
    private_radio: Gtk.RadioButton
    public_radio: Gtk.RadioButton
    spinner: Gtk.Spinner
    create_button: Gtk.Button


class GroupchatDetailsBuilder(Builder):
    main_grid: Gtk.Grid
    header_revealer: Gtk.Revealer
    header_image: Gtk.Image
    name_entry: Gtk.Entry
    edit_name_button: Gtk.ToggleButton
    edit_name_button_image: Gtk.Image
    main_stack: Gtk.Stack
    info_box: Gtk.Box
    settings_box: Gtk.Box
    manage_box: Gtk.Box
    affiliation_box: Gtk.Box
    outcasts_box: Gtk.Box
    configuration_box: Gtk.Box


class GroupchatInfoScrolledBuilder(Builder):
    info_grid: Gtk.Grid
    address_label: Gtk.Label
    description_label: Gtk.Label
    subject_label: Gtk.Label
    author_label: Gtk.Label
    description: Gtk.Label
    author: Gtk.Label
    users: Gtk.Label
    contact_label: Gtk.Label
    logs_label: Gtk.Label
    lang: Gtk.Label
    logs: Gtk.LinkButton
    users_image: Gtk.Image
    lang_image: Gtk.Image
    contact_box: Gtk.Box
    subject: Gtk.Label
    name: Gtk.Label
    avatar_image: Gtk.Image
    address: Gtk.Label


class GroupchatInviterBuilder(Builder):
    account_store: Gtk.ListStore
    invite_box: Gtk.Box
    search_entry: Gtk.SearchEntry
    scrolledwindow: Gtk.ScrolledWindow
    contacts_listbox: Gtk.ListBox
    contacts_placeholder: Gtk.Box
    invitees_scrolled: Gtk.ScrolledWindow


class GroupchatManageBuilder(Builder):
    stack: Gtk.Stack
    avatar_button_image: Gtk.Image
    avatar_select_button: Gtk.Button
    muc_description_entry: Gtk.Entry
    muc_name_entry: Gtk.Entry
    manage_save_button: Gtk.Button
    destroy_muc_button: Gtk.Button
    subject_textview: Gtk.TextView
    subject_change_button: Gtk.Button
    avatar_selector_grid: Gtk.Grid
    avatar_update_button: Gtk.Button
    destroy_reason_entry: Gtk.Entry
    destroy_alternate_entry: Gtk.Entry
    destroy_button: Gtk.Button


class GroupchatNickChooserBuilder(Builder):
    button_content: Gtk.Box
    label: Gtk.Label
    popover: Gtk.Popover
    entry: Gtk.Entry
    apply_button: Gtk.Button


class GroupchatOutcastBuilder(Builder):
    info_popover: Gtk.Popover
    outcast_store: Gtk.ListStore
    main_box: Gtk.Box
    outcast_scrolled: Gtk.ScrolledWindow
    outcast_treeview: Gtk.TreeView
    button_box: Gtk.Box
    add_remove_button_box: Gtk.Box
    add_button: Gtk.Button
    remove_button: Gtk.Button
    info_button: Gtk.MenuButton


class GroupchatRosterBuilder(Builder):
    participant_store: Gtk.TreeStore
    scrolled: Gtk.ScrolledWindow
    roster_treeview: Gtk.TreeView
    contact_column: Gtk.TreeViewColumn
    avatar_renderer: Gtk.CellRendererPixbuf
    text_renderer: Gtk.CellRendererText
    expander: Gtk.TreeViewColumn


class GroupchatRosterTooltipBuilder(Builder):
    tooltip_grid: Gtk.Grid
    avatar: Gtk.Image
    jid: Gtk.Label
    nick: Gtk.Label
    fillelement: Gtk.Label
    status: Gtk.Label
    affiliation: Gtk.Label


class GroupchatStateBuilder(Builder):
    groupchat_state: Gtk.Stack


class GroupsPostWindowBuilder(Builder):
    textbuffer1: Gtk.TextBuffer
    groups_post_window: Gtk.Window
    from_entry: Gtk.Entry
    subject_entry: Gtk.Entry
    contents_textview: Gtk.TextView
    send_button: Gtk.Button


class HistoryExportBuilder(Builder):
    account_liststore: Gtk.ListStore
    select_account_box: Gtk.Box
    account_combo: Gtk.ComboBox
    file_chooser_button: Gtk.FileChooserButton


class MainBuilder(Builder):
    main_grid: Gtk.Grid
    left_grid: Gtk.Grid
    workspace_scrolled: Gtk.ScrolledWindow
    app_box: Gtk.Box
    account_box: Gtk.Box
    toggle_chat_list_button: Gtk.Button
    toggle_chat_list_icon: Gtk.Image


class MamPreferencesBuilder(Builder):
    default_store: Gtk.ListStore
    preferences_store: Gtk.ListStore
    mam_box: Gtk.Box
    default_combo: Gtk.ComboBox
    overlay: Gtk.Overlay
    pref_view: Gtk.TreeView
    add: Gtk.ToolButton
    remove: Gtk.ToolButton
    save_button: Gtk.Button


class ManagePepServicesWindowBuilder(Builder):
    manage_pep_services: Gtk.Box
    services_treeview: Gtk.TreeView
    treeview_selection1: Gtk.TreeSelection
    configure_button: Gtk.Button
    image1: Gtk.Image
    delete_button: Gtk.Button


class ManageProxiesBuilder(Builder):
    liststore1: Gtk.ListStore
    box: Gtk.Box
    proxies_treeview: Gtk.TreeView
    treeview_selection1: Gtk.TreeSelection
    add_proxy_button: Gtk.ToolButton
    remove_proxy_button: Gtk.ToolButton
    settings_grid: Gtk.Grid
    proxypass_entry: Gtk.Entry
    proxyuser_entry: Gtk.Entry
    useauth_checkbutton: Gtk.CheckButton
    proxyport_entry: Gtk.Entry
    proxyhost_entry: Gtk.Entry
    proxytype_combobox: Gtk.ComboBox
    proxyname_entry: Gtk.Entry


class ManageSoundsBuilder(Builder):
    liststore1: Gtk.ListStore
    manage_sounds: Gtk.Box
    sounds_treeview: Gtk.TreeView
    filechooser: Gtk.FileChooserButton


class MessageActionsBoxBuilder(Builder):
    box: Gtk.Box
    quick_invite_button: Gtk.Button
    settings_menu: Gtk.MenuButton
    encryption_details_button: Gtk.Button
    encryption_details_image: Gtk.Image
    encryption_menu_button: Gtk.MenuButton
    encryption_image: Gtk.Image
    sendfile_button: Gtk.Button
    emoticons_button: Gtk.MenuButton
    send_message_button: Gtk.Button
    formattings_button: Gtk.MenuButton
    input_scrolled: Gtk.ScrolledWindow


class PasswordDialogBuilder(Builder):
    pass_box: Gtk.Box
    header: Gtk.Label
    message_label: Gtk.Label
    pass_entry: Gtk.Entry
    save_pass_checkbutton: Gtk.CheckButton
    cancel_button: Gtk.Button
    ok_button: Gtk.Button
    keyring_hint: Gtk.Label


class PluginsBuilder(Builder):
    liststore: Gtk.ListStore
    plugins_box: Gtk.Box
    plugins_treeview: Gtk.TreeView
    treeview_selection: Gtk.TreeSelection
    enabled_column: Gtk.TreeViewColumn
    enabled_renderer: Gtk.CellRendererToggle
    toolbar: Gtk.Toolbar
    install_from_zip_button: Gtk.ToolButton
    uninstall_plugin_button: Gtk.ToolButton
    download_button: Gtk.ToolButton
    help_button: Gtk.ToolButton
    plugin_name_label: Gtk.Label
    configure_plugin_button: Gtk.Button
    description: Gtk.Label
    plugin_version_label: Gtk.Label
    plugin_authors_label: Gtk.Label
    plugin_homepage_linkbutton: Gtk.Label


class PopupNotificationWindowBuilder(Builder):
    eventbox: Gtk.EventBox
    color_bar: Gtk.Box
    image: Gtk.Image
    event_type_label: Gtk.Label
    close_button: Gtk.Button
    event_description_label: Gtk.Label


class PreferencesBuilder(Builder):
    grid: Gtk.Grid
    stack: Gtk.Stack
    window_behaviour: Gtk.Grid
    plugins: Gtk.Grid
    chats: Gtk.Grid
    group_chats: Gtk.Grid
    file_preview: Gtk.Grid
    visual_notifications: Gtk.Grid
    sounds: Gtk.Grid
    status_message: Gtk.Grid
    automatic_status: Gtk.Grid
    themes: Gtk.Grid
    emoji: Gtk.Grid
    av_info_bar: Gtk.InfoBar
    button1: Gtk.Button
    av_info_bar_label: Gtk.Label
    server: Gtk.Grid
    audio: Gtk.Grid
    video: Gtk.Grid
    miscellaneous: Gtk.Grid
    reset_button: Gtk.Button
    purge_history_button: Gtk.Button
    advanced: Gtk.Grid
    ace_button: Gtk.Button


class PreviewBuilder(Builder):
    preview_box: Gtk.Box
    icon_event_box: Gtk.EventBox
    icon_button: Gtk.Button
    right_box: Gtk.Box
    progress_box: Gtk.Box
    progressbar: Gtk.ProgressBar
    progress_text: Gtk.Label
    cancel_download_button: Gtk.Button
    content_box: Gtk.Box
    image_button: Gtk.Button
    link_button: Gtk.LinkButton
    button_box: Gtk.Box
    download_button: Gtk.Button
    save_as_button: Gtk.Button
    open_folder_button: Gtk.Button
    file_name: Gtk.Label
    file_size: Gtk.Label
    info_message: Gtk.Label


class PreviewContextMenuBuilder(Builder):
    context_menu: Gtk.Menu
    download: Gtk.MenuItem
    open: Gtk.MenuItem
    save_as: Gtk.MenuItem
    open_folder: Gtk.MenuItem
    encryption_separator: Gtk.SeparatorMenuItem
    copy_link_location: Gtk.MenuItem
    open_link_in_browser: Gtk.MenuItem


class ProfileBuilder(Builder):
    privacy_popover: Gtk.Popover
    avatar_nick_access: Gtk.Switch
    vcard_access: Gtk.Switch
    avatar_nick_access_label: Gtk.Label
    vcard_access_label: Gtk.Label
    profile_stack: Gtk.Stack
    spinner: Gtk.Spinner
    scrolled: Gtk.ScrolledWindow
    profile_box: Gtk.Box
    avatar_overlay: Gtk.Overlay
    avatar_image: Gtk.Image
    remove_avatar_button: Gtk.Button
    edit_avatar_button: Gtk.Button
    nickname_entry: Gtk.Entry
    cancel_button: Gtk.Button
    add_entry_button: Gtk.MenuButton
    privacy_button: Gtk.MenuButton
    save_button: Gtk.Button
    edit_button: Gtk.Button
    avatar_selector_box: Gtk.Box
    avatar_update_button: Gtk.Button


class RosterBuilder(Builder):
    contact_store: Gtk.TreeStore
    roster_treeview: Gtk.TreeView
    contact_column: Gtk.TreeViewColumn
    avatar_renderer: Gtk.CellRendererPixbuf
    text_renderer: Gtk.CellRendererText
    expander: Gtk.TreeViewColumn


class RosterItemExchangeBuilder(Builder):
    textbuffer1: Gtk.TextBuffer
    roster_item_exchange: Gtk.Box
    type_label: Gtk.Label
    body_scrolledwindow: Gtk.ScrolledWindow
    body_textview: Gtk.TextView
    items_list_treeview: Gtk.TreeView
    treeview_selection1: Gtk.TreeSelection
    cancel_button: Gtk.Button
    accept_button: Gtk.Button


class RosterTooltipBuilder(Builder):
    tooltip_grid: Gtk.Grid
    jid: Gtk.Label
    tune_label: Gtk.Label
    location_label: Gtk.Label
    tune: Gtk.Label
    location: Gtk.Label
    name: Gtk.Label
    avatar: Gtk.Image
    sub_label: Gtk.Label
    sub: Gtk.Label
    resources_box: Gtk.Box


class SearchViewBuilder(Builder):
    calendar_popover: Gtk.Popover
    calendar: Gtk.Calendar
    search_box: Gtk.Box
    calendar_button: Gtk.MenuButton
    search_entry: Gtk.SearchEntry
    search_checkbutton: Gtk.CheckButton
    date_hint: Gtk.Label
    results_listbox: Gtk.ListBox
    placeholder: Gtk.Box
    header_box: Gtk.Box
    header_name_label: Gtk.Label
    header_date_label: Gtk.Label
    result_row_grid: Gtk.Grid
    row_avatar: Gtk.Image
    row_time_label: Gtk.Label
    row_name_label: Gtk.Label


class ServerInfoBuilder(Builder):
    server_info_notebook: Gtk.Notebook
    server: Gtk.Grid
    server_hostname: Gtk.Label
    server_software: Gtk.Label
    server_uptime: Gtk.Label
    no_addresses_label: Gtk.Label
    connection_type: Gtk.Label
    proxy_type: Gtk.Label
    proxy_host: Gtk.Label
    domain_label: Gtk.Label
    dns_label: Gtk.Label
    ip_port_label: Gtk.Label
    websocket_label: Gtk.Label
    domain: Gtk.Label
    dns: Gtk.Label
    ip_port: Gtk.Label
    websocket: Gtk.Label
    cert_scrolled: Gtk.ScrolledWindow
    features: Gtk.Box
    features_listbox: Gtk.ListBox
    clipboard_button: Gtk.Button


class ServiceDiscoveryWindowBuilder(Builder):
    liststore1: Gtk.ListStore
    service_discovery_window: Gtk.Window
    service_discovery: Gtk.Box
    banner_agent_icon: Gtk.Image
    banner_agent_header: Gtk.Label
    banner_agent_subheader: Gtk.Label
    address_box: Gtk.Box
    address_comboboxtext: Gtk.ComboBoxText
    address_comboboxtext_entry: Gtk.Entry
    browse_button: Gtk.Button
    services_progressbar: Gtk.ProgressBar
    services_scrollwin: Gtk.ScrolledWindow
    services_treeview: Gtk.TreeView
    treeview_selection1: Gtk.TreeSelection
    action_buttonbox: Gtk.Box


class ShortcutsWindowBuilder(Builder):
    shortcuts_window: Gtk.ShortcutsWindow


class SslErrorDialogBuilder(Builder):
    ssl_error_box: Gtk.Box
    intro_text: Gtk.Label
    ssl_error: Gtk.Label
    add_certificate_checkbutton: Gtk.CheckButton
    view_cert_button: Gtk.Button
    connect_button: Gtk.Button


class StartChatDialogBuilder(Builder):
    account_store: Gtk.ListStore
    stack: Gtk.Stack
    infobar: Gtk.InfoBar
    box: Gtk.Box
    search_entry: Gtk.SearchEntry
    filter_bar_toggle: Gtk.ToggleButton
    global_search_toggle: Gtk.ToggleButton
    filter_bar_revealer: Gtk.Revealer
    scrolledwindow: Gtk.ScrolledWindow
    listbox: Gtk.ListBox
    spinner: Gtk.Spinner
    error_label: Gtk.Label
    info_box: Gtk.Box
    join_box: Gtk.Box
    join_button: Gtk.Button
    account_view: Gtk.TreeView
    icon_pixbuf: Gtk.CellRendererPixbuf
    account_text: Gtk.CellRendererText
    placeholder: Gtk.Box


class SynchronizeAccountsBuilder(Builder):
    stack: Gtk.Stack
    sync_accounts_box: Gtk.Box
    accounts_treeview: Gtk.TreeView
    sync_contacts_box: Gtk.Box
    contacts_treeview: Gtk.TreeView


class SystrayContextMenuBuilder(Builder):
    accelgroup1: Gtk.AccelGroup
    systray_context_menu: Gtk.Menu
    status_menu: Gtk.MenuItem
    start_chat_menuitem: Gtk.MenuItem
    sounds_mute_menuitem: Gtk.CheckMenuItem
    toggle_window_menuitem: Gtk.MenuItem
    preferences_menuitem: Gtk.MenuItem
    separator: Gtk.SeparatorMenuItem
    quit_menuitem: Gtk.MenuItem


class ThemesWindowBuilder(Builder):
    option_popover: Gtk.Popover
    choose_option_listbox: Gtk.ListBox
    placeholder: Gtk.Box
    theme_store: Gtk.ListStore
    theme_grid: Gtk.Grid
    theme_treeview: Gtk.TreeView
    option_listbox: Gtk.ListBox
    add_option_button: Gtk.MenuButton
    add_theme_button: Gtk.ToolButton
    remove_theme_button: Gtk.ToolButton


class VideoPreviewBuilder(Builder):
    video_preview_box: Gtk.Box
    video_source_label: Gtk.Label
    video_preview_placeholder: Gtk.Box


class WorkspaceDialogBuilder(Builder):
    box: Gtk.Box
    preview: Gtk.Image
    entry: Gtk.Entry
    remove_workspace_button: Gtk.Button
    image_switch: Gtk.Switch
    style_stack: Gtk.Stack
    color_chooser: Gtk.ColorButton
    image_box: Gtk.Box
    save_button: Gtk.Button


class XmlConsoleBuilder(Builder):
    headerbar: Gtk.HeaderBar
    search_toggle: Gtk.ToggleButton
    popover: Gtk.Popover
    box: Gtk.Box
    paned: Gtk.Paned
    search_revealer: Gtk.Revealer
    search_entry: Gtk.SearchEntry
    search_forward: Gtk.ToolButton
    search_backward: Gtk.ToolButton
    scrolled: Gtk.ScrolledWindow
    sourceview: GtkSource.View
    scrolled_input: Gtk.ScrolledWindow
    input_entry: Gtk.TextView
    actionbar: Gtk.ActionBar
    paste: Gtk.Button
    menubutton: Gtk.MenuButton
    send: Gtk.Button


@overload
def get_builder(file_name: Literal['account_page.ui'], widgets: list[str] = ...) -> AccountPageBuilder: ...
@overload
def get_builder(file_name: Literal['account_wizard.ui'], widgets: list[str] = ...) -> AccountWizardBuilder: ...
@overload
def get_builder(file_name: Literal['add_contact.ui'], widgets: list[str] = ...) -> AddContactBuilder: ...
@overload
def get_builder(file_name: Literal['adhoc_muc.ui'], widgets: list[str] = ...) -> AdhocMucBuilder: ...
@overload
def get_builder(file_name: Literal['advanced_configuration.ui'], widgets: list[str] = ...) -> AdvancedConfigurationBuilder: ...
@overload
def get_builder(file_name: Literal['app_page.ui'], widgets: list[str] = ...) -> AppPageBuilder: ...
@overload
def get_builder(file_name: Literal['application_menu.ui'], widgets: list[str] = ...) -> ApplicationMenuBuilder: ...
@overload
def get_builder(file_name: Literal['assistant.ui'], widgets: list[str] = ...) -> AssistantBuilder: ...
@overload
def get_builder(file_name: Literal['blocking_list.ui'], widgets: list[str] = ...) -> BlockingListBuilder: ...
@overload
def get_builder(file_name: Literal['bookmarks.ui'], widgets: list[str] = ...) -> BookmarksBuilder: ...
@overload
def get_builder(file_name: Literal['call_window.ui'], widgets: list[str] = ...) -> CallWindowBuilder: ...
@overload
def get_builder(file_name: Literal['certificate.ui'], widgets: list[str] = ...) -> CertificateBuilder: ...
@overload
def get_builder(file_name: Literal['chat_banner.ui'], widgets: list[str] = ...) -> ChatBannerBuilder: ...
@overload
def get_builder(file_name: Literal['chat_control.ui'], widgets: list[str] = ...) -> ChatControlBuilder: ...
@overload
def get_builder(file_name: Literal['chat_list_row.ui'], widgets: list[str] = ...) -> ChatListRowBuilder: ...
@overload
def get_builder(file_name: Literal['chat_paned.ui'], widgets: list[str] = ...) -> ChatPanedBuilder: ...
@overload
def get_builder(file_name: Literal['contact_info.ui'], widgets: list[str] = ...) -> ContactInfoBuilder: ...
@overload
def get_builder(file_name: Literal['emoji_chooser.ui'], widgets: list[str] = ...) -> EmojiChooserBuilder: ...
@overload
def get_builder(file_name: Literal['exception_dialog.ui'], widgets: list[str] = ...) -> ExceptionDialogBuilder: ...
@overload
def get_builder(file_name: Literal['file_transfer.ui'], widgets: list[str] = ...) -> FileTransferBuilder: ...
@overload
def get_builder(file_name: Literal['file_transfer_jingle.ui'], widgets: list[str] = ...) -> FileTransferJingleBuilder: ...
@overload
def get_builder(file_name: Literal['file_transfer_send.ui'], widgets: list[str] = ...) -> FileTransferSendBuilder: ...
@overload
def get_builder(file_name: Literal['filetransfers.ui'], widgets: list[str] = ...) -> FiletransfersBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_affiliation.ui'], widgets: list[str] = ...) -> GroupchatAffiliationBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_config.ui'], widgets: list[str] = ...) -> GroupchatConfigBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_creation.ui'], widgets: list[str] = ...) -> GroupchatCreationBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_details.ui'], widgets: list[str] = ...) -> GroupchatDetailsBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_info_scrolled.ui'], widgets: list[str] = ...) -> GroupchatInfoScrolledBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_inviter.ui'], widgets: list[str] = ...) -> GroupchatInviterBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_manage.ui'], widgets: list[str] = ...) -> GroupchatManageBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_nick_chooser.ui'], widgets: list[str] = ...) -> GroupchatNickChooserBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_outcast.ui'], widgets: list[str] = ...) -> GroupchatOutcastBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_roster.ui'], widgets: list[str] = ...) -> GroupchatRosterBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_roster_tooltip.ui'], widgets: list[str] = ...) -> GroupchatRosterTooltipBuilder: ...
@overload
def get_builder(file_name: Literal['groupchat_state.ui'], widgets: list[str] = ...) -> GroupchatStateBuilder: ...
@overload
def get_builder(file_name: Literal['groups_post_window.ui'], widgets: list[str] = ...) -> GroupsPostWindowBuilder: ...
@overload
def get_builder(file_name: Literal['history_export.ui'], widgets: list[str] = ...) -> HistoryExportBuilder: ...
@overload
def get_builder(file_name: Literal['main.ui'], widgets: list[str] = ...) -> MainBuilder: ...
@overload
def get_builder(file_name: Literal['mam_preferences.ui'], widgets: list[str] = ...) -> MamPreferencesBuilder: ...
@overload
def get_builder(file_name: Literal['manage_pep_services_window.ui'], widgets: list[str] = ...) -> ManagePepServicesWindowBuilder: ...
@overload
def get_builder(file_name: Literal['manage_proxies.ui'], widgets: list[str] = ...) -> ManageProxiesBuilder: ...
@overload
def get_builder(file_name: Literal['manage_sounds.ui'], widgets: list[str] = ...) -> ManageSoundsBuilder: ...
@overload
def get_builder(file_name: Literal['message_actions_box.ui'], widgets: list[str] = ...) -> MessageActionsBoxBuilder: ...
@overload
def get_builder(file_name: Literal['password_dialog.ui'], widgets: list[str] = ...) -> PasswordDialogBuilder: ...
@overload
def get_builder(file_name: Literal['plugins.ui'], widgets: list[str] = ...) -> PluginsBuilder: ...
@overload
def get_builder(file_name: Literal['popup_notification_window.ui'], widgets: list[str] = ...) -> PopupNotificationWindowBuilder: ...
@overload
def get_builder(file_name: Literal['preferences.ui'], widgets: list[str] = ...) -> PreferencesBuilder: ...
@overload
def get_builder(file_name: Literal['preview.ui'], widgets: list[str] = ...) -> PreviewBuilder: ...
@overload
def get_builder(file_name: Literal['preview_context_menu.ui'], widgets: list[str] = ...) -> PreviewContextMenuBuilder: ...
@overload
def get_builder(file_name: Literal['profile.ui'], widgets: list[str] = ...) -> ProfileBuilder: ...
@overload
def get_builder(file_name: Literal['roster.ui'], widgets: list[str] = ...) -> RosterBuilder: ...
@overload
def get_builder(file_name: Literal['roster_item_exchange.ui'], widgets: list[str] = ...) -> RosterItemExchangeBuilder: ...
@overload
def get_builder(file_name: Literal['roster_tooltip.ui'], widgets: list[str] = ...) -> RosterTooltipBuilder: ...
@overload
def get_builder(file_name: Literal['search_view.ui'], widgets: list[str] = ...) -> SearchViewBuilder: ...
@overload
def get_builder(file_name: Literal['server_info.ui'], widgets: list[str] = ...) -> ServerInfoBuilder: ...
@overload
def get_builder(file_name: Literal['service_discovery_window.ui'], widgets: list[str] = ...) -> ServiceDiscoveryWindowBuilder: ...
@overload
def get_builder(file_name: Literal['shortcuts_window.ui'], widgets: list[str] = ...) -> ShortcutsWindowBuilder: ...
@overload
def get_builder(file_name: Literal['ssl_error_dialog.ui'], widgets: list[str] = ...) -> SslErrorDialogBuilder: ...
@overload
def get_builder(file_name: Literal['start_chat_dialog.ui'], widgets: list[str] = ...) -> StartChatDialogBuilder: ...
@overload
def get_builder(file_name: Literal['synchronize_accounts.ui'], widgets: list[str] = ...) -> SynchronizeAccountsBuilder: ...
@overload
def get_builder(file_name: Literal['systray_context_menu.ui'], widgets: list[str] = ...) -> SystrayContextMenuBuilder: ...
@overload
def get_builder(file_name: Literal['themes_window.ui'], widgets: list[str] = ...) -> ThemesWindowBuilder: ...
@overload
def get_builder(file_name: Literal['video_preview.ui'], widgets: list[str] = ...) -> VideoPreviewBuilder: ...
@overload
def get_builder(file_name: Literal['workspace_dialog.ui'], widgets: list[str] = ...) -> WorkspaceDialogBuilder: ...
@overload
def get_builder(file_name: Literal['xml_console.ui'], widgets: list[str] = ...) -> XmlConsoleBuilder: ...
def get_builder(file_name: str, widgets: list[str] = ...) -> Builder: ...
