from typing import Any
from typing import Literal
from typing import overload

from gi.repository import Gtk
from gi.repository import GtkSource

class GajimBuilder:
    def __init__(
        self,
        filename: str | None = None,
        instance: Any = None,
        widgets: list[str] | None = None,
        domain: str | None = None,
        gettext_: Any | None = None,
    ) -> None: ...

class Builder(Gtk.Builder): ...

class AccountPageBuilder(Builder):
    paned: Gtk.Paned
    roster_box: Gtk.Box
    roster_menu_button: Gtk.MenuButton
    roster_search_entry: Gtk.SearchEntry
    account_box: Gtk.Box
    avatar_image: Gtk.Image
    account_label: Gtk.Label
    our_jid_label: Gtk.Label
    account_settings_button: Gtk.Button
    account_page_menu_button: Gtk.MenuButton
    status_box: Gtk.Box
    notifications_menu_button: Gtk.MenuButton

class AccountWizardBuilder(Builder):
    account_label_box: Gtk.Box
    account_name_entry: Gtk.Entry
    account_color_button: Gtk.ColorDialogButton
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
    sign_up_advanced_checkbutton: Gtk.CheckButton
    sign_up_anonymously: Gtk.CheckButton
    sign_up_info_grid: Gtk.Grid
    server_comboboxtext_sign_up: Gtk.ComboBoxText
    update_provider_list_icon: Gtk.Image

class AddContactBuilder(Builder):
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
    treeview_selection: Gtk.TreeSelection
    description: Gtk.Label
    reset_button: Gtk.Button

class AppPageBuilder(Builder):
    gajim_update: Gtk.Box
    update_message: Gtk.Label
    download_update: Gtk.Button
    dismiss_gajim_update: Gtk.Button
    gajim_update_check: Gtk.Box
    activate_update_check: Gtk.Button
    dismiss_update_check: Gtk.Button
    plugin_updates: Gtk.Box
    auto_update_plugins: Gtk.CheckButton
    update_plugins: Gtk.Button
    open_plugins: Gtk.Button
    dismiss_plugin_updates: Gtk.Button
    plugin_updates_finished: Gtk.Box
    notify_after_plugin_updates: Gtk.CheckButton
    dismiss_update_notification: Gtk.Button

class AssistantBuilder(Builder):
    main_grid: Gtk.Grid
    content_area: Gtk.Box
    stack: Gtk.Stack
    action_area: Gtk.Box

class BlockingListBuilder(Builder):
    blocking_grid: Gtk.Grid
    overlay: Gtk.Overlay
    block_view: Gtk.TreeView
    jid_cell_renderer: Gtk.CellRendererText
    add_button: Gtk.Button
    remove_button: Gtk.Button
    save_button: Gtk.Button

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
    end_call_button: Gtk.Button
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
    copy_button: Gtk.Button
    image1: Gtk.Image
    public_key_algorithm: Gtk.Label
    public_key_size: Gtk.Label

class ChatBannerBuilder(Builder):
    share_popover: Gtk.Popover
    share_instructions: Gtk.Label
    qr_code_image: Gtk.Image
    jid_label: Gtk.Label
    copy_jid_button: Gtk.Button
    banner_box: Gtk.Box
    avatar_image: Gtk.Image
    name_label: Gtk.Label
    phone_image: Gtk.Image
    robot_image: Gtk.Image
    description_label: Gtk.Label
    additional_items_box: Gtk.Box
    share_menu_button: Gtk.MenuButton
    contact_info_button: Gtk.Button
    toggle_roster_button: Gtk.Button
    toggle_roster_image: Gtk.Image
    chat_menu_button: Gtk.MenuButton

class ChatControlBuilder(Builder):
    control_box: Gtk.Box
    conv_view_paned: Gtk.Paned
    conv_view_overlay: Gtk.Overlay

class ChatListRowBuilder(Builder):
    mainbox: Gtk.Box
    account_identifier: Gtk.Box
    avatar_image: Gtk.Image
    connection_icon: Gtk.Image
    group_chat_indicator: Gtk.Image
    name_label: Gtk.Label
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
    controls_box: Gtk.Box
    search_entry: Gtk.SearchEntry
    start_chat_menu_button: Gtk.MenuButton
    section_label_eventbox: Gtk.Box
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
    avatar_image_header: Gtk.Image
    contact_name_header_label: Gtk.Label
    edit_contact_name_header_button: Gtk.Button
    main_stack: Gtk.Stack
    vcard_scrolled: Gtk.ScrolledWindow
    vcard_box: Gtk.Box
    avatar_image: Gtk.Image
    contact_name_controls_box: Gtk.Box
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
    group_add_button: Gtk.Button
    group_remove_button: Gtk.Button
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

class DbMigrationBuilder(Builder):
    box: Gtk.Box
    stack: Gtk.Stack
    status_label: Gtk.Label
    error_label: Gtk.Label
    error_view: Gtk.TextView
    error_copy_button: Gtk.Button
    error_close_button: Gtk.Button
    success_close_button: Gtk.Button

class DebugConsoleBuilder(Builder):
    popover: Gtk.Popover
    stanza_presets_listbox: Gtk.ListBox
    stack: Gtk.Stack
    log_view: GtkSource.View
    paned: Gtk.Paned
    search_revealer: Gtk.Revealer
    search_entry: Gtk.SearchEntry
    search_forward: Gtk.Button
    search_backward: Gtk.Button
    search_results_label: Gtk.Label
    scrolled: Gtk.ScrolledWindow
    protocol_view: GtkSource.View
    jump_to_end_button: Gtk.Button
    scrolled_input: Gtk.ScrolledWindow
    input_entry: GtkSource.View
    actionbox: Gtk.Box
    filter_options_button: Gtk.Button
    clear_button: Gtk.Button
    edit_toggle: Gtk.ToggleButton
    paste: Gtk.Button
    menubutton: Gtk.MenuButton
    account_label: Gtk.Label
    send: Gtk.Button
    headerbar: Gtk.HeaderBar
    search_toggle: Gtk.ToggleButton

class ExceptionDialogBuilder(Builder):
    exception_box: Gtk.Box
    infobar: Gtk.Revealer
    exception_view: Gtk.TextView
    user_feedback_box: Gtk.Box
    user_feedback_entry: Gtk.Entry
    close_button: Gtk.Button
    report_spinner: Gtk.Spinner
    report_button: Gtk.Button

class FileTransferBuilder(Builder):
    transfer_box: Gtk.Box
    transfer_description: Gtk.Label
    file_name: Gtk.Label
    file_size: Gtk.Label
    progress_bar: Gtk.ProgressBar
    transfer_progress: Gtk.Label
    cancel_button: Gtk.Button

class FileTransferJingleBuilder(Builder):
    transfer_box: Gtk.Box
    transfer_action: Gtk.Label
    file_name: Gtk.Label
    file_description: Gtk.Label
    file_size: Gtk.Label
    action_stack: Gtk.Stack
    accept_file_request: Gtk.Button
    reject_file_request: Gtk.Button
    open_folder: Gtk.Button
    open_file: Gtk.Button
    error_show_transfers: Gtk.Button
    error_label: Gtk.Label
    retry_bad_hash: Gtk.Button
    rejected_show_transfers: Gtk.Button
    progress_label: Gtk.Label
    progress_bar: Gtk.ProgressBar
    cancel_transfer: Gtk.Button

class FileTransferSelectorBuilder(Builder):
    file_box: Gtk.Box
    preview_image_box: Gtk.Box
    preview_image: Gtk.Image
    file_name_label: Gtk.Label
    file_size_label: Gtk.Label
    warning_label: Gtk.Label
    remove_file_button: Gtk.Button
    stack: Gtk.Stack
    box: Gtk.Box
    listbox: Gtk.ListBox
    resource_box: Gtk.Box
    resource_instructions: Gtk.Label

class GroupchatAffiliationBuilder(Builder):
    affiliation_store: Gtk.ListStore
    combo_store: Gtk.ListStore
    main_box: Gtk.Box
    affiliation_scrolled: Gtk.ScrolledWindow
    affiliation_treeview: Gtk.TreeView
    affiliation_selection: Gtk.TreeSelection
    address_renderer: Gtk.CellRendererText
    reserved_name_column: Gtk.TreeViewColumn
    reserved_name_renderer: Gtk.CellRendererText
    affiliation_renderer: Gtk.CellRendererCombo
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
    public_radio: Gtk.CheckButton
    private_radio: Gtk.CheckButton
    spinner: Gtk.Spinner
    create_button: Gtk.Button

class GroupchatDetailsBuilder(Builder):
    main_grid: Gtk.Grid
    header_revealer: Gtk.Revealer
    header_image: Gtk.Image
    contact_name_header_label: Gtk.Label
    edit_name_button: Gtk.Button
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
    avatar_image: Gtk.Image
    address: Gtk.Label
    address_copy_button: Gtk.Button
    name_box: Gtk.Box

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
    avatar_overlay: Gtk.Overlay
    avatar_button_image: Gtk.Image
    remove_avatar_button: Gtk.Button
    muc_description_entry: Gtk.Entry
    muc_name_entry: Gtk.Entry
    destroy_muc_button: Gtk.Button
    manage_save_button: Gtk.Button
    subject_textview: Gtk.TextView
    subject_change_button: Gtk.Button
    avatar_selector_grid: Gtk.Grid
    avatar_cancel_button: Gtk.Button
    avatar_update_button: Gtk.Button
    destroy_reason_entry: Gtk.Entry
    destroy_alternate_entry: Gtk.Entry
    destroy_cancel_button: Gtk.Button
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
    outcast_selection: Gtk.TreeSelection
    address_renderer: Gtk.CellRendererText
    reason_renderer: Gtk.CellRendererText
    button_box: Gtk.Box
    add_remove_button_box: Gtk.Box
    add_button: Gtk.Button
    remove_button: Gtk.Button
    info_button: Gtk.MenuButton

class GroupchatRosterBuilder(Builder):
    box: Gtk.Box
    search_entry: Gtk.SearchEntry
    scrolled: Gtk.ScrolledWindow

class GroupchatRosterTooltipBuilder(Builder):
    tooltip_grid: Gtk.Grid
    avatar: Gtk.Image
    jid: Gtk.Label
    nick: Gtk.Label
    fillelement: Gtk.Label
    status: Gtk.Label
    affiliation: Gtk.Label
    hats_box: Gtk.Box

class GroupchatStateBuilder(Builder):
    groupchat_state: Gtk.Stack
    join_button: Gtk.Button
    joining_spinner: Gtk.Spinner
    abort_join_button: Gtk.Button
    mam_sync_spinner: Gtk.Spinner
    mam_error_label: Gtk.Label
    close_button: Gtk.Button

class HistoryExportBuilder(Builder):
    select_account_box: Gtk.Box
    settings_grid: Gtk.Grid
    account_combo: Gtk.ComboBox

class MainBuilder(Builder):
    main_grid: Gtk.Grid
    left_grid: Gtk.Grid
    workspace_scrolled: Gtk.ScrolledWindow
    app_box: Gtk.Box
    toggle_chat_list_button: Gtk.Button
    toggle_chat_list_icon: Gtk.Image
    account_box: Gtk.Box

class MamPreferencesBuilder(Builder):
    mam_box: Gtk.Box
    default_combo: Gtk.ComboBox
    overlay: Gtk.Overlay
    pref_view: Gtk.TreeView
    jid_cell_renderer: Gtk.CellRendererText
    pref_toggle_cell_renderer: Gtk.CellRendererToggle
    add: Gtk.Button
    remove: Gtk.Button
    save_button: Gtk.Button

class ManageProxiesBuilder(Builder):
    box: Gtk.Box
    proxies_treeview: Gtk.TreeView
    treeview_selection1: Gtk.TreeSelection
    add_proxy_button: Gtk.Button
    remove_proxy_button: Gtk.Button
    settings_grid: Gtk.Grid
    proxypass_entry: Gtk.Entry
    proxyuser_entry: Gtk.Entry
    useauth_checkbutton: Gtk.CheckButton
    proxyport_entry: Gtk.Entry
    proxyhost_entry: Gtk.Entry
    proxytype_combobox: Gtk.ComboBox
    proxyname_entry: Gtk.Entry

class ManageRosterBuilder(Builder):
    main: Gtk.Box
    scrolled_box: Gtk.Box
    scrolled: Gtk.ScrolledWindow
    column_view: Gtk.ColumnView
    jid_col: Gtk.ColumnViewColumn
    name_col: Gtk.ColumnViewColumn
    subscription_col: Gtk.ColumnViewColumn
    ask_col: Gtk.ColumnViewColumn

class ManageSoundsBuilder(Builder):
    manage_sounds: Gtk.Box
    sounds_treeview: Gtk.TreeView
    toggle_cell_renderer: Gtk.CellRendererToggle
    sound_buttons_box: Gtk.Box
    clear_sound_button: Gtk.Button
    play_sound_button: Gtk.Button

class MessageActionsBoxBuilder(Builder):
    box: Gtk.Box
    chat_state_box: Gtk.Box
    reply_box: Gtk.Box
    state_box: Gtk.Box
    state_box_image: Gtk.Image
    state_box_label: Gtk.Label
    visitor_menu_button: Gtk.MenuButton
    edit_box: Gtk.Box
    edit_box_image: Gtk.Image
    cancel_correction_button: Gtk.Button
    action_box: Gtk.Box
    emoticons_button: Gtk.MenuButton
    formattings_button: Gtk.MenuButton
    input_wrapper: Gtk.Overlay
    input_scrolled: Gtk.ScrolledWindow
    input_overlay: Gtk.Box
    input_overlay_label: Gtk.Label
    send_message_button: Gtk.Button
    sendfile_button: Gtk.Button
    encryption_menu_button: Gtk.MenuButton
    encryption_image: Gtk.Image
    encryption_details_button: Gtk.Button
    encryption_details_image: Gtk.Image
    visitor_popover: Gtk.Popover
    request_voice_button: Gtk.Button

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
    pass_entry: Gtk.PasswordEntry
    save_pass_checkbutton: Gtk.CheckButton
    keyring_hint: Gtk.Label
    cancel_button: Gtk.Button
    ok_button: Gtk.Button

class PepConfigBuilder(Builder):
    stack: Gtk.Stack
    overview_box: Gtk.Box
    services_treeview: Gtk.TreeView
    delete_button: Gtk.Button
    configure_button: Gtk.Button
    show_content_button: Gtk.Button
    items_box: Gtk.Box
    items_label: Gtk.Label
    items_view: GtkSource.View
    items_back_button: Gtk.Button
    config_box: Gtk.Box
    form_label: Gtk.Label
    form_box: Gtk.Box
    config_back_button: Gtk.Button
    save_button: Gtk.Button

class PluginsBuilder(Builder):
    liststore: Gtk.ListStore
    plugins_box: Gtk.Box
    plugins_treeview: Gtk.TreeView
    treeview_selection: Gtk.TreeSelection
    enabled_column: Gtk.TreeViewColumn
    enabled_renderer: Gtk.CellRendererToggle
    toolbar: Gtk.Box
    download_button: Gtk.Button
    uninstall_plugin_button: Gtk.Button
    help_button: Gtk.Button
    plugin_name_label: Gtk.Label
    configure_plugin_button: Gtk.Button
    description: Gtk.Label
    plugin_version_label: Gtk.Label
    plugin_authors_label: Gtk.Label
    plugin_homepage_linkbutton: Gtk.Label

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
    av_info_bar: Gtk.Revealer
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
    icon_event_box: Gtk.Box
    icon_button: Gtk.Button
    right_box: Gtk.Box
    progress_box: Gtk.Box
    progressbar: Gtk.ProgressBar
    progress_text: Gtk.Label
    cancel_download_button: Gtk.Button
    content_box: Gtk.Box
    content_overlay: Gtk.Overlay
    image_button: Gtk.Button
    link_button: Gtk.LinkButton
    button_box: Gtk.Box
    file_name: Gtk.Label
    file_size: Gtk.Label
    info_message: Gtk.Label
    open_folder_button: Gtk.Button
    save_as_button: Gtk.Button
    download_button: Gtk.Button

class PreviewAudioBuilder(Builder):
    seek_bar_adj: Gtk.Adjustment
    speed_bar_adj: Gtk.Adjustment
    preview_box: Gtk.Box
    drawing_box: Gtk.Box
    seek_bar_box: Gtk.Box
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
    nickname_entry: Gtk.Entry
    cancel_button: Gtk.Button
    add_entry_button: Gtk.MenuButton
    privacy_button: Gtk.MenuButton
    save_button: Gtk.Button
    edit_button: Gtk.Button
    avatar_selector_box: Gtk.Box
    avatar_cancel: Gtk.Button
    avatar_update_button: Gtk.Button
    error_label: Gtk.Label
    error_title_label: Gtk.Label
    back_button: Gtk.Button

class QuitDialogBuilder(Builder):
    box: Gtk.Box
    remember_checkbutton: Gtk.CheckButton
    hide_button: Gtk.Button
    minimize_button: Gtk.Button
    quit_button: Gtk.Button

class RosterBuilder(Builder):
    roster_treeview: Gtk.TreeView
    contact_column: Gtk.TreeViewColumn
    avatar_renderer: Gtk.CellRendererPixbuf
    text_renderer: Gtk.CellRendererText
    expander: Gtk.TreeViewColumn

class RosterItemExchangeBuilder(Builder):
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
    first_day_button: Gtk.Button
    previous_day_button: Gtk.Button
    next_day_button: Gtk.Button
    last_day_button: Gtk.Button
    search_box: Gtk.Box
    close_button: Gtk.Button
    calendar_button: Gtk.MenuButton
    search_entry: Gtk.SearchEntry
    search_checkbutton: Gtk.CheckButton
    search_filters_box: Gtk.Box
    results_scrolled: Gtk.ScrolledWindow
    results_listbox: Gtk.ListBox
    placeholder: Gtk.Box
    placeholder_image: Gtk.Image
    placeholder_label: Gtk.Label
    filter_date_before_popover: Gtk.Popover
    filter_date_before_calendar: Gtk.Calendar
    filter_date_before_reset_button: Gtk.Button
    filter_date_after_popover: Gtk.Popover
    filter_date_after_calendar: Gtk.Calendar
    filter_date_after_reset_button: Gtk.Button
    search_filters_grid: Gtk.Grid
    filter_from_desc_label: Gtk.Label
    filter_from_entry: Gtk.Entry
    filter_before_button: Gtk.MenuButton
    filter_after_button: Gtk.MenuButton
    filter_before_label: Gtk.Label
    filter_after_label: Gtk.Label
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
    no_certificate_label: Gtk.Label
    features: Gtk.Box
    features_listbox: Gtk.ListBox
    clipboard_button: Gtk.Button

class ServiceDiscoveryWindowBuilder(Builder):
    service_discovery: Gtk.Box
    banner_agent_icon: Gtk.Image
    banner_agent_header: Gtk.Label
    banner_agent_subheader: Gtk.Label
    address_box: Gtk.Box
    address_comboboxtext: Gtk.ComboBoxText
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
    stack: Gtk.Stack
    infobar: Gtk.Revealer
    infobar_close_button: Gtk.Button
    box: Gtk.Box
    controls_box: Gtk.Box
    search_entry: Gtk.SearchEntry
    global_search_toggle: Gtk.ToggleButton
    search_error_box: Gtk.Box
    search_error_label: Gtk.Label
    list_stack: Gtk.Stack
    contact_scrolled: Gtk.ScrolledWindow
    no_contacts_placeholder: Gtk.Box
    global_scrolled: Gtk.ScrolledWindow
    global_search_placeholder_stack: Gtk.Stack
    global_search_placeholder_hints: Gtk.Box
    global_search_results_label: Gtk.Label
    spinner: Gtk.Spinner
    error_label: Gtk.Label
    error_back_button: Gtk.Button
    info_box: Gtk.Box
    info_back_button: Gtk.Button
    join_box: Gtk.Box
    join_button: Gtk.Button
    account_view: Gtk.TreeView
    icon_pixbuf: Gtk.CellRendererPixbuf
    account_text: Gtk.CellRendererText
    account_back_button: Gtk.Button
    account_select_button: Gtk.Button

class SynchronizeAccountsBuilder(Builder):
    stack: Gtk.Stack
    sync_accounts_box: Gtk.Box
    accounts_treeview: Gtk.TreeView
    select_contacts_button: Gtk.Button
    connection_warning_label: Gtk.Label
    sync_contacts_box: Gtk.Box
    contacts_treeview: Gtk.TreeView
    synchronize_button: Gtk.Button
    back_button: Gtk.Button

class ThemesWindowBuilder(Builder):
    option_popover: Gtk.Popover
    choose_option_listbox: Gtk.ListBox
    placeholder: Gtk.Box
    theme_store: Gtk.ListStore
    theme_grid: Gtk.Grid
    theme_treeview: Gtk.TreeView
    theme_treeview_selection: Gtk.TreeSelection
    theme_name_cell_renderer: Gtk.CellRendererText
    option_listbox: Gtk.ListBox
    add_option_button: Gtk.MenuButton
    add_theme_button: Gtk.Button
    remove_theme_button: Gtk.Button

class VideoPreviewBuilder(Builder):
    video_preview_box: Gtk.Box
    video_source_label: Gtk.Label
    video_preview_placeholder: Gtk.Box

class VoiceMessageRecorderBuilder(Builder):
    popover: Gtk.Popover
    box: Gtk.Box
    error_label: Gtk.Label
    progression_box: Gtk.Box
    time_label: Gtk.Label
    visualization_box: Gtk.Box
    audio_player_box: Gtk.Box
    record_control_box: Gtk.Box
    cancel_button: Gtk.Button
    record_toggle_button: Gtk.Button
    record_toggle_button_image: Gtk.Image
    send_button: Gtk.Button

class WorkspaceDialogBuilder(Builder):
    box: Gtk.Box
    preview: Gtk.Image
    entry: Gtk.Entry
    remove_workspace_button: Gtk.Button
    image_switch: Gtk.Switch
    style_stack: Gtk.Stack
    color_dialog_button: Gtk.ColorDialogButton
    image_box: Gtk.Box
    cancel_button: Gtk.Button
    save_button: Gtk.Button

@overload
def get_builder(
    file_name: Literal["account_page.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> AccountPageBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["account_wizard.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> AccountWizardBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["add_contact.ui"], instance: Any = None, widgets: list[str] = ...
) -> AddContactBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["advanced_configuration.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> AdvancedConfigurationBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["app_page.ui"], instance: Any = None, widgets: list[str] = ...
) -> AppPageBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["assistant.ui"], instance: Any = None, widgets: list[str] = ...
) -> AssistantBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["blocking_list.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> BlockingListBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["call_window.ui"], instance: Any = None, widgets: list[str] = ...
) -> CallWindowBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["certificate.ui"], instance: Any = None, widgets: list[str] = ...
) -> CertificateBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["chat_banner.ui"], instance: Any = None, widgets: list[str] = ...
) -> ChatBannerBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["chat_control.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ChatControlBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["chat_list_row.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ChatListRowBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["chat_paned.ui"], instance: Any = None, widgets: list[str] = ...
) -> ChatPanedBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["contact_info.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ContactInfoBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["contact_tooltip.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ContactTooltipBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["db_migration.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> DbMigrationBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["debug_console.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> DebugConsoleBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["exception_dialog.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ExceptionDialogBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["file_transfer.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> FileTransferBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["file_transfer_jingle.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> FileTransferJingleBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["file_transfer_selector.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> FileTransferSelectorBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_affiliation.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatAffiliationBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_config.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatConfigBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_creation.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatCreationBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_details.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatDetailsBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_info_scrolled.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatInfoScrolledBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_inviter.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatInviterBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_manage.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatManageBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_nick_chooser.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatNickChooserBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_outcast.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatOutcastBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_roster.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatRosterBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_roster_tooltip.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatRosterTooltipBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["groupchat_state.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatStateBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["history_export.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> HistoryExportBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["main.ui"], instance: Any = None, widgets: list[str] = ...
) -> MainBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["mam_preferences.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> MamPreferencesBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["manage_proxies.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ManageProxiesBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["manage_roster.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ManageRosterBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["manage_sounds.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ManageSoundsBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["message_actions_box.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> MessageActionsBoxBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["omemo_trust_manager.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> OmemoTrustManagerBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["password_dialog.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> PasswordDialogBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["pep_config.ui"], instance: Any = None, widgets: list[str] = ...
) -> PepConfigBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["plugins.ui"], instance: Any = None, widgets: list[str] = ...
) -> PluginsBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["preferences.ui"], instance: Any = None, widgets: list[str] = ...
) -> PreferencesBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["preview.ui"], instance: Any = None, widgets: list[str] = ...
) -> PreviewBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["preview_audio.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> PreviewAudioBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["profile.ui"], instance: Any = None, widgets: list[str] = ...
) -> ProfileBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["quit_dialog.ui"], instance: Any = None, widgets: list[str] = ...
) -> QuitDialogBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["roster.ui"], instance: Any = None, widgets: list[str] = ...
) -> RosterBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["roster_item_exchange.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> RosterItemExchangeBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["search_view.ui"], instance: Any = None, widgets: list[str] = ...
) -> SearchViewBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["server_info.ui"], instance: Any = None, widgets: list[str] = ...
) -> ServerInfoBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["service_discovery_window.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ServiceDiscoveryWindowBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["shortcuts_window.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ShortcutsWindowBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["ssl_error_dialog.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> SslErrorDialogBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["start_chat_dialog.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> StartChatDialogBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["synchronize_accounts.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> SynchronizeAccountsBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["themes_window.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ThemesWindowBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["video_preview.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> VideoPreviewBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["voice_message_recorder.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> VoiceMessageRecorderBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["workspace_dialog.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> WorkspaceDialogBuilder: ...  # noqa
def get_builder(
    file_name: str, instance: Any = None, widgets: list[str] = ...
) -> Builder: ...
