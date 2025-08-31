from typing import Any
from typing import Literal
from typing import overload

from gi.repository import Adw
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

class ActivityDefaultBuilder(Builder):
    default_page: Gtk.Box

class ActivityGajimUpdateBuilder(Builder):
    gajim_update_page: Gtk.Box
    update_permission_box: Gtk.Box
    update_permission_title_label: Gtk.Label
    update_permission_enable_button: Gtk.Button
    update_gajim_box: Gtk.Box
    update_gajim_title_label: Gtk.Label
    update_gajim_text_label: Gtk.Label
    update_gajim_button: Gtk.Button
    update_plugins_box: Gtk.Box
    update_plugins_title_label: Gtk.Label
    update_plugins_text_label: Gtk.Label
    update_plugins_automatically_checkbox: Gtk.CheckButton
    update_plugins_show_button: Gtk.Button
    update_plugins_button: Gtk.Button
    update_plugins_success_box: Gtk.Box
    update_plugins_success_title_label: Gtk.Label
    update_plugins_success_text_label: Gtk.Label
    update_plugins_success_button: Gtk.Button

class ActivityMucInvitationBuilder(Builder):
    muc_invitation_page: Gtk.Box
    muc_invitation_box: Gtk.Box
    muc_invitation_declined_box: Gtk.Box
    invitation_image: Gtk.Image
    invitation_title_label: Gtk.Label
    invitation_text_label: Gtk.Label

class ActivitySubscriptionBuilder(Builder):
    subscription_page: Gtk.Box
    subscription_image: Gtk.Image
    subscription_title_label: Gtk.Label
    subscription_text_label: Gtk.Label
    subscribe_box: Gtk.Box
    subscribe_deny_button: Gtk.Button
    subscribe_accept_button: Gtk.Button
    subscribe_menu_button: Gtk.MenuButton
    unsubscribed_box: Gtk.Box
    unsubscribed_remove_button: Gtk.Button

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
    jingle_connection_spinner: Adw.Spinner
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
    certificate_scrolled: Gtk.ScrolledWindow
    clipboard_button: Gtk.Button
    account_label_row: Adw.ActionRow
    account_address_row: Adw.ActionRow
    issued_to_common_name_row: Adw.ActionRow
    issued_to_organization_row: Adw.ActionRow
    issued_to_subject_alt_names_row: Adw.ActionRow
    issued_to_serial_number_row: Adw.ActionRow
    issued_by_common_name_row: Adw.ActionRow
    issued_by_organization_row: Adw.ActionRow
    issue_date_row: Adw.ActionRow
    expiry_date_row: Adw.ActionRow
    fingerprint_sha1_row: Adw.ActionRow
    fingerprint_sha256_row: Adw.ActionRow
    algorithm_row: Adw.ActionRow
    key_size_row: Adw.ActionRow

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

class ContactInfoBuilder(Builder):
    groups_model: Gtk.ListStore
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
    contact_settings_box: Adw.PreferencesGroup
    remove_history_button: Gtk.Button
    encryption_scrolled: Gtk.ScrolledWindow
    encryption_box: Adw.Clamp
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
    devices_page: Adw.PreferencesPage

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
    header_box: Gtk.Box
    search_toggle: Gtk.ToggleButton

class ExceptionDialogBuilder(Builder):
    exception_box: Gtk.Box
    infobar: Gtk.Revealer
    exception_view: Gtk.TextView
    user_feedback_box: Gtk.Box
    user_feedback_entry: Gtk.Entry
    close_button: Gtk.Button
    report_spinner: Adw.Spinner
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

class GroupchatBlocksBuilder(Builder):
    main: Gtk.Box
    top_box: Gtk.Box
    search_entry: Gtk.SearchEntry
    remove_button: Gtk.Button
    scrolled_box: Gtk.Box
    scrolled: Gtk.ScrolledWindow
    column_view: Gtk.ColumnView
    nickname_col: Gtk.ColumnViewColumn
    id_col: Gtk.ColumnViewColumn

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
    spinner: Adw.Spinner
    create_button: Gtk.Button

class GroupchatDetailsBuilder(Builder):
    main_stack: Gtk.Stack
    info_container: Gtk.Box
    settings_box: Gtk.Box
    encryption_scrolled: Gtk.ScrolledWindow
    encryption_box: Adw.Clamp
    blocks_box: Gtk.Box
    manage_box: Gtk.Box
    affiliation_box: Gtk.Box
    outcasts_box: Gtk.Box
    configuration_box: Gtk.Box

class GroupchatInfoScrolledBuilder(Builder):
    info_clamp: Adw.Clamp
    avatar_image: Gtk.Image
    name_box: Gtk.Box
    info_listbox: Gtk.ListBox
    address_row: Adw.ActionRow
    address_copy_button: Gtk.Button
    description_row: Adw.ActionRow
    subject_row: Adw.ActionRow
    author_row: Adw.ActionRow
    users_row: Adw.ActionRow
    contact_row: Adw.ActionRow
    contact_box: Gtk.Box
    logs_row: Adw.ActionRow
    logs: Gtk.LinkButton
    lang_row: Adw.ActionRow
    features_listbox: Gtk.ListBox

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
    manage_save_button: Gtk.Button
    contact_addresses_listbox: Gtk.ListBox
    muc_name_entry_row: Adw.EntryRow
    muc_description_entry_row: Adw.EntryRow
    destroy_muc_button: Gtk.Button
    subject_change_button: Gtk.Button
    subject_textview: Gtk.TextView
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
    participants_count_label: Gtk.Label
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
    joining_spinner: Adw.Spinner
    abort_join_button: Gtk.Button
    mam_sync_spinner: Adw.Spinner
    mam_error_label: Gtk.Label
    close_button: Gtk.Button

class HistoryExportBuilder(Builder):
    select_account_box: Gtk.Box
    settings_grid: Gtk.Grid

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
    top_box: Gtk.Box
    search_entry: Gtk.SearchEntry
    import_button: Gtk.MenuButton
    export_button: Gtk.Button
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
    our_fingerprint_row: Adw.ActionRow
    copy_button: Gtk.Button
    qr_menu_button: Gtk.MenuButton
    manage_trust_button: Gtk.Button
    list_heading: Gtk.Label
    list_heading_box: Gtk.Box
    show_inactive_switch: Gtk.Switch
    search_button: Gtk.MenuButton
    clear_devices_button: Gtk.Button
    list: Gtk.ListBox

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
    spinner: Adw.Spinner
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
    search_entry: Gtk.SearchEntry
    calendar_button: Gtk.MenuButton
    close_button: Gtk.Button
    search_checkbutton: Gtk.CheckButton
    search_filters_box: Gtk.Box
    results_scrolled: Gtk.ScrolledWindow
    results_listbox: Gtk.ListBox
    status_page: Adw.StatusPage
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
    box: Gtk.Box
    server_info_stack: Adw.ViewStack
    server_hostname_row: Adw.ActionRow
    server_software_row: Adw.ActionRow
    server_uptime_row: Adw.ActionRow
    contact_addresses_listbox: Gtk.ListBox
    domain_row: Adw.ActionRow
    dns_row: Adw.ActionRow
    ip_port_row: Adw.ActionRow
    websocket_row: Adw.ActionRow
    connection_type_row: Adw.ActionRow
    tls_version_row: Adw.ActionRow
    cipher_suite_row: Adw.ActionRow
    proxy_type_row: Adw.ActionRow
    proxy_host_row: Adw.ActionRow
    cert_box: Gtk.Box
    no_certificate_label: Gtk.Label
    features_group: Adw.PreferencesGroup
    clipboard_button: Gtk.Button
    features_listbox: Gtk.ListBox

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
    settings_menu: Gtk.MenuButton
    search_error_box: Gtk.Box
    search_error_label: Gtk.Label
    list_stack: Gtk.Stack
    contact_scrolled: Gtk.ScrolledWindow
    no_contacts_placeholder: Gtk.Box
    global_scrolled: Gtk.ScrolledWindow
    global_search_placeholder_stack: Gtk.Stack
    global_search_placeholder_hints: Gtk.Box
    global_search_results_label: Gtk.Label
    spinner: Adw.Spinner
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
    file_name: Literal["account_wizard.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> AccountWizardBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["activity_default.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ActivityDefaultBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["activity_gajim_update.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ActivityGajimUpdateBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["activity_muc_invitation.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ActivityMucInvitationBuilder: ...  # noqa
@overload
def get_builder(
    file_name: Literal["activity_subscription.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> ActivitySubscriptionBuilder: ...  # noqa
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
    file_name: Literal["groupchat_blocks.ui"],
    instance: Any = None,
    widgets: list[str] = ...,
) -> GroupchatBlocksBuilder: ...  # noqa
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
