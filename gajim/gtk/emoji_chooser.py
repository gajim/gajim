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

import logging
import weakref
from pathlib import Path
from collections import OrderedDict

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GdkPixbuf
from gi.repository import Pango

from gajim.common import app
from gajim.common import helpers
from gajim.common import configpaths

from gajim.gtk.util import get_builder
from gajim.gtk.emoji_data import emoji_data
from gajim.gtk.emoji_data import emoji_pixbufs
from gajim.gtk.emoji_data import Emoji

MODIFIER_MAX_CHILDREN_PER_LINE = 6
MAX_CHILDREN_PER_LINE = 10

log = logging.getLogger('gajim.emoji')


class Section(Gtk.Box):
    def __init__(self, name, search_entry, press_cb, chooser):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self._chooser = chooser
        self._press_cb = press_cb
        self.pixbuf_generator = None
        self.heading = Gtk.Label(label=name)
        self.heading.set_halign(Gtk.Align.START)
        self.heading.get_style_context().add_class('emoji-chooser-heading')
        self.add(self.heading)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.get_style_context().add_class('emoji-chooser-flowbox')
        self.flowbox.set_max_children_per_line(MAX_CHILDREN_PER_LINE)
        self.flowbox.set_filter_func(self._filter_func, search_entry)
        self.flowbox.connect('child-activated', press_cb)

        self.add(self.flowbox)
        self.show_all()

    def _filter_func(self, child, search_entry):
        name = search_entry.get_text()
        if not name:
            self.show()
            return True

        if name in child.desc:
            self.show()
            return True
        return False

    def add_emoji(self, codepoint, attrs):
        # Return always True, this method is used for the emoji factory
        # called by GLib.idle_add()
        pixbuf = self._get_next_pixbuf()

        variations = attrs.get('variations', None)
        if variations is None:
            if pixbuf is None:
                return True
            self.flowbox.add(EmojiChild(codepoint, pixbuf, attrs['desc']))
            if pixbuf != 'font':
                # We save the pixbuf for fast access if we need to
                # replace a codepoint in the textview
                emoji_pixbufs[codepoint] = pixbuf
        else:
            if pixbuf is not None:
                chooser = ModifierChooser()

                # Iterate over the variations and add the codepoints
                for codepoint_ in variations.keys():
                    pixbuf_ = self._get_next_pixbuf()
                    if pixbuf_ is None:
                        continue

                    if pixbuf_ == 'font':
                        if not self._chooser.font_supports_codepoint(
                                codepoint_):
                            continue
                    else:
                        emoji_pixbufs[codepoint_] = pixbuf_

                    # Only codepoints are added which the
                    # font or theme supports
                    chooser.add_emoji(codepoint_, pixbuf_)

                # Check if we successfully added codepoints with modifiers
                if chooser.has_child:
                    # If we have children then add a button
                    # and set the popover
                    child = EmojiModifierChild(
                        codepoint, pixbuf, attrs['desc'])
                    child.button.set_popover(chooser)
                    chooser.flowbox.connect(
                        'child-activated', self._press_cb)
                else:
                    # If no children were added, destroy the chooser
                    # and add a EmojiChild instead of a EmojiModifierChild
                    chooser.destroy()
                    child = EmojiChild(codepoint, pixbuf, attrs['desc'])

                if pixbuf != 'font':
                    emoji_pixbufs[codepoint] = pixbuf

                self.flowbox.add(child)
            else:
                # We don’t have a image for the base codepoint
                # so skip all modifiers of it
                for _entry in variations:
                    pixbuf = self._get_next_pixbuf()
        return True

    def clear_emojis(self):
        def _remove_emoji(emoji):
            self.flowbox.remove(emoji)
            emoji.destroy()
        self.flowbox.foreach(_remove_emoji)

    def _get_next_pixbuf(self):
        if self.pixbuf_generator is None:
            return 'font'
        return next(self.pixbuf_generator, False)


class EmojiChild(Gtk.FlowBoxChild):
    def __init__(self, codepoint, pixbuf, desc):
        Gtk.FlowBoxChild.__init__(self)
        self.desc = desc
        self.codepoint = codepoint
        self.pixbuf = pixbuf
        if pixbuf == 'font':
            self.add(Gtk.Label(label=codepoint))
        else:
            self.add(Gtk.Image.new_from_pixbuf(pixbuf))
        self.set_tooltip_text(desc)
        self.show_all()

    def get_emoji(self):
        if self.pixbuf != 'font':
            pixbuf = self.get_child().get_pixbuf()
            pixbuf = pixbuf.scale_simple(Emoji.INPUT_SIZE,
                                         Emoji.INPUT_SIZE,
                                         GdkPixbuf.InterpType.HYPER)
            return self.codepoint, pixbuf
        return self.codepoint, None


class EmojiModifierChild(Gtk.FlowBoxChild):
    def __init__(self, codepoint, pixbuf, desc):
        Gtk.FlowBoxChild.__init__(self)
        self.desc = desc
        self.codepoint = codepoint
        self.pixbuf = pixbuf

        self.button = Gtk.MenuButton()
        self.button.set_relief(Gtk.ReliefStyle.NONE)
        self.button.connect('button-press-event', self._button_press)

        if pixbuf == 'font':
            self.button.remove(self.button.get_child())
            label = Gtk.Label(label=codepoint)
            self.button.add(label)
        else:
            self.button.get_child().set_from_pixbuf(pixbuf)

        self.set_tooltip_text(desc)
        self.add(self.button)
        self.show_all()

    def _button_press(self, button, event):
        if event.button == 3:
            button.get_popover().show()
            button.get_popover().get_child().unselect_all()
            return True
        if event.button == 1:
            self.get_parent().emit('child-activated', self)
            return True
        return False

    def get_emoji(self):
        if self.pixbuf != 'font':
            pixbuf = self.button.get_child().get_pixbuf()
            pixbuf = pixbuf.scale_simple(Emoji.INPUT_SIZE,
                                         Emoji.INPUT_SIZE,
                                         GdkPixbuf.InterpType.HYPER)
            return self.codepoint, pixbuf
        return self.codepoint, None


class ModifierChooser(Gtk.Popover):
    def __init__(self):
        Gtk.Popover.__init__(self)
        self.set_name('EmoticonPopover')
        self._has_child = False

        self.flowbox = Gtk.FlowBox()
        self.flowbox.get_style_context().add_class(
            'emoji-modifier-chooser-flowbox')
        self.flowbox.set_size_request(200, -1)
        self.flowbox.set_max_children_per_line(MODIFIER_MAX_CHILDREN_PER_LINE)
        self.flowbox.show()
        self.add(self.flowbox)

    @property
    def has_child(self):
        return self._has_child

    def add_emoji(self, codepoint, pixbuf):
        self.flowbox.add(EmojiChild(codepoint, pixbuf, None))
        self._has_child = True


class EmojiChooser(Gtk.Popover):

    _section_names = [
        'Smileys & People',
        'Animals & Nature',
        'Food & Drink',
        'Travel & Places',
        'Activities',
        'Objects',
        'Symbols',
        'Flags'
    ]

    def __init__(self):
        super().__init__()
        self.set_name('EmoticonPopover')
        self._text_widget = None
        self._load_source_id = None
        self._pango_layout = Pango.Layout(self.get_pango_context())

        self._builder = get_builder('emoji_chooser.ui')
        self._search = self._builder.get_object('search')
        self._stack = self._builder.get_object('stack')

        self._sections = OrderedDict()
        for name in self._section_names:
            self._sections[name] = Section(
                name, self._search, self._on_emoticon_press, self)

        section_box = self._builder.get_object('section_box')
        for section in self._sections.values():
            section_box.add(section)

        self.add(self._builder.get_object('box'))

        self.connect('key-press-event', self._key_press)
        self._builder.connect_signals(self)
        self.show_all()

    @property
    def text_widget(self):
        return self._text_widget

    @text_widget.setter
    def text_widget(self, value):
        # Hold only a weak reference so if we can destroy
        # the ChatControl
        self._text_widget = weakref.ref(value)

    def _key_press(self, _widget, event):
        return self._search.handle_event(event)

    def _search_changed(self, _entry):
        for section in self._sections.values():
            section.hide()
            section.flowbox.invalidate_filter()
        self._switch_stack()

    def _clear_sections(self):
        for section in self._sections.values():
            section.clear_emojis()

    def _switch_stack(self):
        for section in self._sections.values():
            if section.is_visible():
                self._stack.set_visible_child_name('list')
                return
        self._stack.set_visible_child_name('not-found')

    @staticmethod
    def _get_current_theme():
        theme = app.settings.get('emoticons_theme')
        themes = helpers.get_available_emoticon_themes()
        if theme not in themes:
            app.settings.set('emoticons_theme', 'noto')
            theme = 'noto'
        return theme

    @staticmethod
    def _get_emoji_theme_path(theme):
        if theme == 'font':
            return 'font'

        base_path = Path(configpaths.get('EMOTICONS'))
        emoticons_data_path = base_path / theme / f'{theme}.png'
        if emoticons_data_path.exists():
            return emoticons_data_path

        emoticons_user_path = Path(configpaths.get('MY_EMOTS')) / f'{theme}.png'
        if emoticons_user_path.exists():
            return emoticons_user_path

        log.warning('Could not find emoji theme: %s', theme)
        return None

    def load(self):
        theme = self._get_current_theme()
        path = self._get_emoji_theme_path(theme)
        if not theme or path is None:
            self._clear_sections()
            emoji_pixbufs.clear()
            return

        # Attach pixbuf generator
        pixbuf_generator = None
        if theme != 'font':
            pixbuf_generator = self._get_next_pixbuf(path)
        for section in self._sections.values():
            section.pixbuf_generator = pixbuf_generator

        if self._load_source_id is not None:
            GLib.source_remove(self._load_source_id)

        # When we change emoji theme
        self._clear_sections()
        emoji_pixbufs.clear()

        factory = self._emoji_factory(theme == 'font')
        self._load_source_id = GLib.idle_add(lambda: next(factory, False),
                                             priority=GLib.PRIORITY_LOW)

    def _emoji_factory(self, font):
        for codepoint, attrs in emoji_data.items():
            if not attrs['fully-qualified']:
                # We don’t add these to the UI
                continue

            if font and not self.font_supports_codepoint(codepoint):
                continue

            section = self._sections[attrs['group']]
            yield section.add_emoji(codepoint, attrs)
        self._load_source_id = None
        emoji_pixbufs.complete = True

    def font_supports_codepoint(self, codepoint):
        self._pango_layout.set_text(codepoint, -1)
        if self._pango_layout.get_unknown_glyphs_count():
            return False
        if len(codepoint) > 1:
            # The font supports each of the codepoints
            # Check if the rendered glyph is more than one char
            if self._pango_layout.get_size()[0] > 19000:
                return False
        return True

    @staticmethod
    def _get_next_pixbuf(path):
        src_x = src_y = cur_column = 0
        atlas = GdkPixbuf.Pixbuf.new_from_file(str(path))

        while True:
            src_x = cur_column * Emoji.PARSE_WIDTH
            subpixbuf = atlas.new_subpixbuf(src_x, src_y,
                                            Emoji.PARSE_WIDTH,
                                            Emoji.PARSE_HEIGHT)

            if list(subpixbuf.get_pixels())[0:4] == [0, 0, 0, 255]:
                # top left corner is a black pixel means image is missing
                subpixbuf = None

            if cur_column == Emoji.PARSE_COLUMNS - 1:
                src_y += Emoji.PARSE_WIDTH
                cur_column = 0
            else:
                cur_column += 1

            yield subpixbuf

    def _on_emoticon_press(self, flowbox, child):
        GLib.timeout_add(100, flowbox.unselect_child, child)
        codepoint, pixbuf = child.get_emoji()
        self._text_widget().insert_emoji(codepoint, pixbuf)

    def do_destroy(self):
        # Remove the references we hold to other objects
        self._text_widget = None
        # Never destroy, creating a new EmoticonPopover is expensive
        return True


emoji_chooser = EmojiChooser()
