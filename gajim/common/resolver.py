# Copyright (C) 2006 Dimitur Kirov <dkirov@gmail.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

import logging
import functools

from gi.repository import Gio, GLib

log = logging.getLogger('gajim.c.resolver')


def get_resolver():
    return GioResolver()


class CommonResolver():
    def __init__(self):
        # dict {"host+type" : list of records}
        self.resolved_hosts = {}
        # dict {"host+type" : list of callbacks}
        self.handlers = {}

    def resolve(self, host, on_ready, type_='srv'):
        host = host.lower()
        log.debug('resolve %s type=%s', host, type_)
        assert(type_ in ['srv', 'txt'])
        if not host:
            # empty host, return empty list of srv records
            on_ready([])
            return
        if host + type_ in self.resolved_hosts:
            # host is already resolved, return cached values
            log.debug('%s already resolved: %s',
                      host, self.resolved_hosts[host + type_])
            on_ready(host, self.resolved_hosts[host + type_])
            return
        if host + type_ in self.handlers:
            # host is about to be resolved by another connection,
            # attach our callback
            log.debug('already resolving %s', host)
            self.handlers[host + type_].append(on_ready)
        else:
            # host has never been resolved, start now
            log.debug('Starting to resolve %s using %s', host, self)
            self.handlers[host + type_] = [on_ready]
            self.start_resolve(host, type_)

    def _on_ready(self, host, type_, result_list):
        # practically it is impossible to be the opposite, but who knows :)
        host = host.lower()
        log.debug('Resolving result for %s: %s', host, result_list)
        if host + type_ not in self.resolved_hosts:
            self.resolved_hosts[host + type_] = result_list
        if host + type_ in self.handlers:
            for callback in self.handlers[host + type_]:
                callback(host, result_list)
            del(self.handlers[host + type_])

    def start_resolve(self, host, type_):
        pass


class GioResolver(CommonResolver):
    """
    Asynchronous resolver using GIO. process() method has to be
    called in order to proceed the pending requests.
    """

    def __init__(self):
        super().__init__()
        self.gio_resolver = Gio.Resolver.get_default()

    def start_resolve(self, host, type_):
        if type_ == 'txt':
            callback = functools.partial(self._on_ready_txt, host)
            type_ = Gio.ResolverRecordType.TXT
        else:
            callback = functools.partial(self._on_ready_srv, host)
            type_ = Gio.ResolverRecordType.SRV

        self.gio_resolver.lookup_records_async(host, type_, None, callback)

    def _on_ready_srv(self, host, source_object, result):
        try:
            variant_results = source_object.lookup_records_finish(result)
        except GLib.Error as e:
            if e.domain == 'g-resolver-error-quark':
                result_list = []
                log.info("Could not resolve host: %s", e.message)
            else:
                raise
        else:
            result_list = [
                {
                    'weight': weight,
                    'prio': prio,
                    'port': port,
                    'host': host,
                }
                for prio, weight, port, host
                in variant_results
            ]
        super()._on_ready(host, 'srv', result_list)

    def _on_ready_txt(self, host, source_object, result):
        try:
            variant_results = source_object.lookup_records_finish(result)
        except GLib.Error as e:
            if e.domain == 'g-resolver-error-quark':
                result_list = []
                log.warning("Could not resolve host: %s", e.message)
            else:
                raise
        else:
            result_list = [res[0][0] for res in variant_results]
        super()._on_ready(host, 'txt', result_list)


# below lines is on how to use API and assist in testing
if __name__ == '__main__':
    from gi.repository import Gtk
    resolver = get_resolver()

    def clicked(widget):
        global resolver
        host = text_view.get_text()
        def on_result(host, result_array):
            print('Result:\n' + repr(result_array))
        resolver.resolve(host, on_result)
    win = Gtk.Window()
    win.set_border_width(6)
    win.connect('remove', Gtk.main_quit)
    text_view = Gtk.Entry()
    text_view.set_text('_xmpp-client._tcp.jabber.org')
    hbox = Gtk.HBox()
    hbox.set_spacing(3)
    but = Gtk.Button(' Lookup SRV ')
    hbox.pack_start(text_view, 5, True, 0)
    hbox.pack_start(but, 0, True, 0)
    but.connect('clicked', clicked)
    win.add(hbox)
    win.show_all()
    Gtk.main()
