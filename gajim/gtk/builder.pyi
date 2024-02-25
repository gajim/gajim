
from typing import Literal
from typing import overload

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import GtkSource

class Builder(Gtk.Builder):
    ...


class AccountPageBuilder(Builder):
    paned: Gtk.Paned
    roster_box: Gtk.Box
    roster_menu_button: Gtk.MenuButton
    roster_search_entry: Gtk.SearchEntry
    account_box: Gtk.Box
    avatar_image: Gtk.Image
    account_label: Gtk.Label
    our_jid_label: Gtk.Label
    account_page_menu_button: Gtk.MenuButton
    status_box: Gtk.Box
    notifications_menu_button: Gtk.MenuButton


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
    data_it_subject_alt_names: Gtk.Label
    data_it_serial_number: Gtk.Label
    data_ib_common_name: Gtk.Label
    data_ib_organization: Gtk.Label
    data_issued_on: Gtk.Label
    data_expires_on: Gtk.Label
    data_sha1: Gtk.Label
    data_sha256: Gtk.Label
    copy_cert_info_button: Gtk.Button
    image1: Gtk.Image
    public_key_algorithm: Gtk.Label
    public_key_size: Gtk.Label


class ChatBannerBuilder(Builder):
    share_popover: Gtk.Popover
    share_instructions: Gtk.Label
    qr_code_image: Gtk.Image
    jid_label: Gtk.Label
    banner_box: Gtk.Box
    avatar_image: Gtk.Image
    chat_menu_button: Gtk.MenuButton
    toggle_roster_button: Gtk.Button
    toggle_roster_image: Gtk.Image
    contact_info_button: Gtk.Button
    share_menu_button: Gtk.MenuButton
    name_label: Gtk.Label
    phone_image: Gtk.Image
    robot_image: Gtk.Image
    description_label: Gtk.Label
    additional_items_box: Gtk.Box
    visitor_box: Gtk.Box
    visitor_menu_button: Gtk.MenuButton
    visitor_popover: Gtk.Popover


class ChatControlBuilder(Builder):
    control_box: Gtk.Box
    conv_view_paned: Gtk.Paned
    conv_view_overlay: Gtk.Overlay


class ChatListRowBuilder(Builder):
    eventbox: Gtk.EventBox
    account_identifier: Gtk.Box
    avatar_image: Gtk.Image
    group_chat_indicator: Gtk.Image
    name_label: Gtk.Label
    connection_icon: Gtk.Image
    chatstate_image: Gtk.Image
    mute_image: Gtk.Image
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
    start_chat_menu_button: Gtk.MenuButton
    filter_bar_toggle: Gtk.ToggleButton
    search_entry: Gtk.SearchEntry
    filter_bar_revealer: Gtk.Revealer
    filter_bar: Gtk.Box
    section_label_eventbox: Gtk.EventBox
    section_label: Gtk.Label
    workspace_settings_button: Gtk.Button
    chat_list_scrolled: Gtk.ScrolledWindow
    right_grid: Gtk.Grid


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
    encryption_scrolled: Gtk.ScrolledWindow
    encryption_box: Gtk.Box
    groups_page_stack: Gtk.Stack
    groups_treeview: Gtk.TreeView
    tree_selection: Gtk.TreeSelection
    toggle_renderer: Gtk.CellRendererToggle
    text_renderer: Gtk.CellRendererText
    group_add_button: Gtk.ToolButton
    group_remove_button: Gtk.ToolButton
    notes_page_stack: Gtk.Stack
    scrolledwindow_annotation: Gtk.ScrolledWindow
    textview_annotation: Gtk.TextView
    devices_stack: Gtk.Stack
    devices_box: Gtk.Box


class ContactTooltipBuilder(Builder):
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


class FileTransferSelectorBuilder(Builder):
    file_box: Gtk.Box
    preview_image_box: Gtk.Box
    preview_image: Gtk.Image
    file_name_label: Gtk.Label
    file_size_label: Gtk.Label
    warning_label: Gtk.Label
    remove_file_button: Gtk.Button
    stack: Gtk.Stack
    listbox: Gtk.ListBox
    resource_box: Gtk.Box
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
    advanced_switch: Gtk.Switch
    advanced_switch_label: Gtk.Label
    error_label: Gtk.Label
    info_label: Gtk.Label
    address_entry_label: Gtk.Label
    address_entry: Gtk.Entry
    public_radio: Gtk.RadioButton
    private_radio: Gtk.RadioButton
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
    encryption_scrolled: Gtk.ScrolledWindow
    encryption_box: Gtk.Box
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
    address_copy_button: Gtk.Button


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
    box: Gtk.Box
    search_entry: Gtk.SearchEntry
    scrolled: Gtk.ScrolledWindow
    roster_treeview: Gtk.TreeView
    contact_column: Gtk.TreeViewColumn
    avatar_renderer: Gtk.CellRendererPixbuf
    text_renderer: Gtk.CellRendererText
    expander: Gtk.TreeViewColumn
    participant_store: Gtk.TreeStore


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
    mam_error_label: Gtk.Label


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
    encryption_details_button: Gtk.Button
    encryption_details_image: Gtk.Image
    encryption_menu_button: Gtk.MenuButton
    encryption_image: Gtk.Image
    sendfile_button: Gtk.Button
    emoticons_button: Gtk.MenuButton
    send_message_button: Gtk.Button
    formattings_button: Gtk.MenuButton
    input_scrolled: Gtk.ScrolledWindow


class OmemoTrustManagerBuilder(Builder):
    search_popover: Gtk.Popover
    search: Gtk.SearchEntry
    qr_code_popover: Gtk.Popover
    comparing_instructions: Gtk.Label
    our_fingerprint_2: Gtk.Label
    qr_code_image: Gtk.Image
    stack: Gtk.Stack
    our_fingerprint_1: Gtk.Label
    qr_menu_button: Gtk.MenuButton
    manage_trust_button: Gtk.Button
    list_heading: Gtk.Label
    list_heading_box: Gtk.Box
    show_inactive_switch: Gtk.Switch
    search_button: Gtk.MenuButton
    list: Gtk.ListBox
    clear_devices_button: Gtk.Button


class PasswordDialogBuilder(Builder):
    pass_box: Gtk.Box
    header: Gtk.Label
    message_label: Gtk.Label
    pass_entry: Gtk.Entry
    save_pass_checkbutton: Gtk.CheckButton
    cancel_button: Gtk.Button
    ok_button: Gtk.Button
    keyring_hint: Gtk.Label


class PepConfigBuilder(Builder):
    stack: Gtk.Stack
    overview_box: Gtk.Box
    services_treeview: Gtk.TreeView
    show_content_button: Gtk.Button
    delete_button: Gtk.Button
    configure_button: Gtk.Button
    items_box: Gtk.Box
    items_label: Gtk.Label
    items_view: GtkSource.View
    config_box: Gtk.Box
    form_label: Gtk.Label
    form_box: Gtk.Box


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
    general: Gtk.Grid
    chats: Gtk.Grid
    group_chats: Gtk.Grid
    file_preview: Gtk.Grid
    visual_notifications: Gtk.Grid
    sounds: Gtk.Grid
    status_message: Gtk.Grid
    automatic_status: Gtk.Grid
    themes: Gtk.Grid
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
    preview_stack: Gtk.Stack
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


class PreviewAudioBuilder(Builder):
    seek_bar_adj: Gtk.Adjustment
    speed_bar_adj: Gtk.Adjustment
    preview_box: Gtk.Box
    drawing_box: Gtk.Box
    seek_bar: Gtk.Scale
    progress_label: Gtk.Label
    control_box: Gtk.Box
    rewind_button: Gtk.Button
    play_pause_button: Gtk.Button
    play_icon: Gtk.Image
    forward_button: Gtk.Button
    speed_dec_button: Gtk.Button
    speed_menubutton: Gtk.MenuButton
    speed_label: Gtk.Label
    speed_inc_button: Gtk.Button
    speed_popover: Gtk.Popover
    speed_bar: Gtk.Scale


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
    error_label: Gtk.Label
    error_title_label: Gtk.Label
    back_button: Gtk.Button


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


class SearchViewBuilder(Builder):
    calendar_popover: Gtk.Popover
    calendar: Gtk.Calendar
    search_box: Gtk.Box
    calendar_button: Gtk.MenuButton
    search_entry: Gtk.SearchEntry
    search_checkbutton: Gtk.CheckButton
    date_hint: Gtk.Label
    results_scrolled: Gtk.ScrolledWindow
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
    tls_version: Gtk.Label
    cipher_suite: Gtk.Label
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
    select_contacts_button: Gtk.Button
    connection_warning_label: Gtk.Label
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
    popover: Gtk.Popover
    stack: Gtk.Stack
    paned: Gtk.Paned
    search_revealer: Gtk.Revealer
    search_entry: Gtk.SearchEntry
    search_forward: Gtk.ToolButton
    search_backward: Gtk.ToolButton
    scrolled: Gtk.ScrolledWindow
    protocol_view: GtkSource.View
    scrolled_input: Gtk.ScrolledWindow
    input_entry: GtkSource.View
    actionbox: Gtk.Box
    send: Gtk.Button
    account_label: Gtk.Label
    paste: Gtk.Button
    menubutton: Gtk.MenuButton
    log_view: GtkSource.View
    headerbar: Gtk.HeaderBar
    search_toggle: Gtk.ToggleButton


@overload
def get_builder(file_name: Literal['account_page.ui'], widgets: list[str] = ...) -> AccountPageBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['account_wizard.ui'], widgets: list[str] = ...) -> AccountWizardBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['add_contact.ui'], widgets: list[str] = ...) -> AddContactBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['advanced_configuration.ui'], widgets: list[str] = ...) -> AdvancedConfigurationBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['app_page.ui'], widgets: list[str] = ...) -> AppPageBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['application_menu.ui'], widgets: list[str] = ...) -> ApplicationMenuBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['assistant.ui'], widgets: list[str] = ...) -> AssistantBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['blocking_list.ui'], widgets: list[str] = ...) -> BlockingListBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['bookmarks.ui'], widgets: list[str] = ...) -> BookmarksBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['call_window.ui'], widgets: list[str] = ...) -> CallWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['certificate.ui'], widgets: list[str] = ...) -> CertificateBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['chat_banner.ui'], widgets: list[str] = ...) -> ChatBannerBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['chat_control.ui'], widgets: list[str] = ...) -> ChatControlBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['chat_list_row.ui'], widgets: list[str] = ...) -> ChatListRowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['chat_paned.ui'], widgets: list[str] = ...) -> ChatPanedBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['contact_info.ui'], widgets: list[str] = ...) -> ContactInfoBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['contact_tooltip.ui'], widgets: list[str] = ...) -> ContactTooltipBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['emoji_chooser.ui'], widgets: list[str] = ...) -> EmojiChooserBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['exception_dialog.ui'], widgets: list[str] = ...) -> ExceptionDialogBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['file_transfer.ui'], widgets: list[str] = ...) -> FileTransferBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['file_transfer_jingle.ui'], widgets: list[str] = ...) -> FileTransferJingleBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['file_transfer_selector.ui'], widgets: list[str] = ...) -> FileTransferSelectorBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['filetransfers.ui'], widgets: list[str] = ...) -> FiletransfersBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_affiliation.ui'], widgets: list[str] = ...) -> GroupchatAffiliationBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_config.ui'], widgets: list[str] = ...) -> GroupchatConfigBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_creation.ui'], widgets: list[str] = ...) -> GroupchatCreationBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_details.ui'], widgets: list[str] = ...) -> GroupchatDetailsBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_info_scrolled.ui'], widgets: list[str] = ...) -> GroupchatInfoScrolledBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_inviter.ui'], widgets: list[str] = ...) -> GroupchatInviterBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_manage.ui'], widgets: list[str] = ...) -> GroupchatManageBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_nick_chooser.ui'], widgets: list[str] = ...) -> GroupchatNickChooserBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_outcast.ui'], widgets: list[str] = ...) -> GroupchatOutcastBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_roster.ui'], widgets: list[str] = ...) -> GroupchatRosterBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_roster_tooltip.ui'], widgets: list[str] = ...) -> GroupchatRosterTooltipBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groupchat_state.ui'], widgets: list[str] = ...) -> GroupchatStateBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['groups_post_window.ui'], widgets: list[str] = ...) -> GroupsPostWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['history_export.ui'], widgets: list[str] = ...) -> HistoryExportBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['main.ui'], widgets: list[str] = ...) -> MainBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['mam_preferences.ui'], widgets: list[str] = ...) -> MamPreferencesBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['manage_proxies.ui'], widgets: list[str] = ...) -> ManageProxiesBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['manage_sounds.ui'], widgets: list[str] = ...) -> ManageSoundsBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['message_actions_box.ui'], widgets: list[str] = ...) -> MessageActionsBoxBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['omemo_trust_manager.ui'], widgets: list[str] = ...) -> OmemoTrustManagerBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['password_dialog.ui'], widgets: list[str] = ...) -> PasswordDialogBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['pep_config.ui'], widgets: list[str] = ...) -> PepConfigBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['plugins.ui'], widgets: list[str] = ...) -> PluginsBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['popup_notification_window.ui'], widgets: list[str] = ...) -> PopupNotificationWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['preferences.ui'], widgets: list[str] = ...) -> PreferencesBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['preview.ui'], widgets: list[str] = ...) -> PreviewBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['preview_audio.ui'], widgets: list[str] = ...) -> PreviewAudioBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['profile.ui'], widgets: list[str] = ...) -> ProfileBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['roster.ui'], widgets: list[str] = ...) -> RosterBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['roster_item_exchange.ui'], widgets: list[str] = ...) -> RosterItemExchangeBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['search_view.ui'], widgets: list[str] = ...) -> SearchViewBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['server_info.ui'], widgets: list[str] = ...) -> ServerInfoBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['service_discovery_window.ui'], widgets: list[str] = ...) -> ServiceDiscoveryWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['shortcuts_window.ui'], widgets: list[str] = ...) -> ShortcutsWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['ssl_error_dialog.ui'], widgets: list[str] = ...) -> SslErrorDialogBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['start_chat_dialog.ui'], widgets: list[str] = ...) -> StartChatDialogBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['synchronize_accounts.ui'], widgets: list[str] = ...) -> SynchronizeAccountsBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['systray_context_menu.ui'], widgets: list[str] = ...) -> SystrayContextMenuBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['themes_window.ui'], widgets: list[str] = ...) -> ThemesWindowBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['video_preview.ui'], widgets: list[str] = ...) -> VideoPreviewBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['workspace_dialog.ui'], widgets: list[str] = ...) -> WorkspaceDialogBuilder: ...  # noqa
@overload
def get_builder(file_name: Literal['xml_console.ui'], widgets: list[str] = ...) -> XmlConsoleBuilder: ...  # noqa


def get_builder(file_name: str, widgets: list[str] = ...) -> Builder: ...
