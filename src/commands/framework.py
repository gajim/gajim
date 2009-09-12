# Copyright (C) 2009  red-agent <hell.director@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Provides a tiny framework with simple, yet powerful and extensible architecture
to implement commands in a streight and flexible, declarative way.
"""

import re
from types import FunctionType, UnicodeType, TupleType, ListType
from inspect import getargspec

class CommandInternalError(Exception):
    pass

class CommandError(Exception):
    def __init__(self, message=None, command=None, name=None):
        self.command = command
        self.name = name

        if command:
            self.name = command.first_name

        if message:
            super(CommandError, self).__init__(message)
        else:
            super(CommandError, self).__init__()

class Command(object):

    DOC_STRIP_PATTERN = re.compile(r'(?:^[ \t]+|\A\n)', re.MULTILINE)
    DOC_FORMAT_PATTERN = re.compile(r'(?<!\n)\n(?!\n)', re.MULTILINE)

    ARG_USAGE_PATTERN = 'Usage: %s %s'

    def __init__(self, handler, is_instance, usage, raw, dashes, optional, empty):
        self.handler = handler

        self.is_instance = is_instance
        self.usage = usage
        self.raw = raw
        self.dashes = dashes
        self.optional = optional
        self.empty = empty

    def __call__(self, *args, **kwargs):
        try:
            return self.handler(*args, **kwargs)
        except CommandError, exception:
            if not exception.command and not exception.name:
                raise CommandError(exception.message, self)
        except TypeError:
            raise CommandError("Command received invalid arguments", self)

    def __repr__(self):
        return "<Command %s>" % ', '.join(self.names)

    def __cmp__(self, other):
        """
        Comparison is implemented based on a first name.
        """
        return cmp(self.first_name, other.first_name)

    @property
    def first_name(self):
        return self.names[0]

    @property
    def native_name(self):
        return self.handler.__name__

    def extract_doc(self):
        """
        Extract handler's doc-string and transform it to a usable format.
        """
        doc = self.handler.__doc__ or None

        if not doc:
            return

        doc = re.sub(self.DOC_STRIP_PATTERN, str(), doc)
        doc = re.sub(self.DOC_FORMAT_PATTERN, ' ', doc)

        return doc

    def extract_description(self):
        """
        Extract handler's description (which is a first line of the doc). Try to
        keep them simple yet meaningful.
        """
        doc = self.extract_doc()
        if doc:
            return doc.split('\n', 1)[0]

    def extract_arg_spec(self):
        names, var_args, var_kwargs, defaults = getargspec(self.handler)

        # Behavior of this code need to be checked. Might yield incorrect
        # results on some rare occasions.
        spec_args = names[:-len(defaults) if defaults else len(names)]
        spec_kwargs = dict(zip(names[-len(defaults):], defaults)) if defaults else {}

        # Removing self from arguments specification in case if command handler
        # is an instance method.
        if self.is_instance and spec_args.pop(0) != 'self':
            raise CommandInternalError("Invalid arguments specification")

        return spec_args, spec_kwargs, var_args, var_kwargs

    def extract_arg_usage(self, complete=True):
        """
        Extract handler's arguments specification and wrap them in a
        human-readable format. If complete is given - then ARG_USAGE_PATTERN
        will be used to render it completly.
        """
        names, _var_args, _var_kwargs, defaults = getargspec(self.handler)
        spec_args, spec_kwargs, var_args, var_kwargs = self.extract_arg_spec()

        '__arguments__' not in spec_args or spec_args.remove('__arguments__')

        optional = '__optional__' in spec_args
        if optional:
            spec_args.remove('__optional__')

        kwargs = []
        letters = []

        # The reason we don't iterate here through spec_kwargs, like we would
        # normally do is that it does not retains order of items. We need to be
        # sure that arguments will be printed in the order they were specified.
        for key in (names[-len(defaults):] if defaults else ()):
            value = spec_kwargs[key]
            letter = key[0]

            if self.dashes:
                key = key.replace('_', '-')

            if letter not in letters:
                kwargs.append('-(-%s)%s=%s' % (letter, key[1:], value))
                letters.append(letter)
            else:
                kwargs.append('--%s=%s' % (key, value))

        usage = str()
        args = str()

        if len(spec_args) == 1 and self.raw:
            args += ('(|%s|)' if self.empty else '|%s|') % spec_args[0]
        elif spec_args or var_args or optional:
            if spec_args:
                args += '<%s>' % ', '.join(spec_args)
            if var_args or optional:
                args += (' ' if spec_args else str()) + '<<%s>>' % (var_args or self.optional)

        usage += args

        if kwargs or var_kwargs:
            if kwargs:
                usage += (' ' if args else str()) + '[%s]' % ', '.join(kwargs)
            if var_kwargs:
                usage += (' ' if args else str()) + '[[%s]]' % var_kwargs

        # Native name will be the first one if it is included. Otherwise, names
        # will be in the order they were specified.
        if len(self.names) > 1:
            names = '%s (%s)' % (self.first_name, ', '.join(self.names[1:]))
        else:
            names = self.first_name

        return usage if not complete else self.ARG_USAGE_PATTERN % (names, usage)

class Dispatcher(type):
    table = {}
    hosted = {}

    def __init__(cls, name, bases, dct):
        dispatchable = Dispatcher.check_if_dispatchable(bases, dct)
        hostable = Dispatcher.check_if_hostable(bases, dct)

        if Dispatcher.is_suitable(cls, dct):
            Dispatcher.register_processor(cls)

        # Sanitize names even if processor is not suitable for registering,
        # because it might be inherited by an another processor.
        Dispatcher.sanitize_names(cls)

        super(Dispatcher, cls).__init__(name, bases, dct)

    @classmethod
    def is_suitable(cls, proc, dct):
        is_not_root = dct.get('__metaclass__') is not cls
        is_processor = bool(dct.get('IS_COMMAND_PROCESSOR'))
        return is_not_root and is_processor

    @classmethod
    def check_if_dispatchable(cls, bases, dct):
        dispatcher = dct.get('DISPATCHED_BY')
        if not dispatcher:
            return False
        if dispatcher not in bases:
            raise CommandInternalError("Should be dispatched by the same processor it inherits from")
        return True

    @classmethod
    def check_if_hostable(cls, bases, dct):
        hosters = dct.get('HOSTED_BY')
        if not hosters:
            return False
        if not isinstance(hosters, (TupleType, ListType)):
            hosters = (hosters,)
        for hoster in hosters:
            if hoster not in bases:
                raise CommandInternalError("Should be hosted by the same processors it inherits from")
        return True

    @classmethod
    def check_if_conformed(cls, dispatchable, hostable):
        if dispatchable and hostable:
            raise CommandInternalError("Processor can not be dispatchable and hostable at the same time")

    @classmethod
    def register_processor(cls, proc):
        cls.table[proc] = {}
        inherited = proc.__dict__.get('INHERITED')

        if 'HOSTED_BY' in proc.__dict__:
            cls.register_adhocs(proc)

        commands = cls.traverse_commands(proc, inherited)
        cls.register_commands(proc, commands)

    @classmethod
    def sanitize_names(cls, proc):
        inherited = proc.__dict__.get('INHERITED')
        commands = cls.traverse_commands(proc, inherited)
        for key, command in commands:
            if not proc.SAFE_NAME_SCAN_PATTERN.match(key):
                setattr(proc, proc.SAFE_NAME_SUBS_PATTERN % key, command)
                try:
                    delattr(proc, key)
                except AttributeError:
                    pass

    @classmethod
    def traverse_commands(cls, proc, inherited=True):
        keys = dir(proc) if inherited else proc.__dict__.iterkeys()
        for key in keys:
            value = getattr(proc, key)
            if isinstance(value, Command):
                yield key, value

    @classmethod
    def register_commands(cls, proc, commands):
        for key, command in commands:
            for name in command.names:
                name = proc.prepare_name(name)
                if name not in cls.table[proc]:
                    cls.table[proc][name] = command
                else:
                    raise CommandInternalError("Command with name %s already exists" % name)
    @classmethod
    def register_adhocs(cls, proc):
        hosters = proc.HOSTED_BY
        if not isinstance(hosters, (TupleType, ListType)):
            hosters = (hosters,)
        for hoster in hosters:
            if hoster in cls.hosted:
                cls.hosted[hoster].append(proc)
            else:
                cls.hosted[hoster] = [proc]

    @classmethod
    def retrieve_command(cls, proc, name):
        command = cls.table[proc.DISPATCHED_BY].get(name)
        if command:
            return command
        if proc.DISPATCHED_BY in cls.hosted:
            for adhoc in cls.hosted[proc.DISPATCHED_BY]:
                command = cls.table[adhoc].get(name)
                if command:
                    return command

    @classmethod
    def list_commands(cls, proc):
        commands = dict(cls.traverse_commands(proc.DISPATCHED_BY))
        if proc.DISPATCHED_BY in cls.hosted:
            for adhoc in cls.hosted[proc.DISPATCHED_BY]:
                inherited = adhoc.__dict__.get('INHERITED')
                commands.update(dict(cls.traverse_commands(adhoc, inherited)))
        return commands.values()

class CommandProcessor(object):
    """
    A base class for a drop-in command processor which you can drop (make your
    class to inherit from it) in any of your classes to support commands. In
    order to get it done you need to make your own processor, inheriter from
    CommandProcessor and then drop it in. Don't forget about few important steps
    described below.

    Every command in the processor (normally) will gain full access through self
    to an object you are adding commands to.

    Your subclass, which will contain commands should define in its body
    IS_COMMAND_PROCESSOR = True in order to be included in the dispatching
    table.

    Every class you will drop the processor in should define DISPATCHED_BY set
    to the same processor you are inheriting from.

    Names of the commands after preparation stuff id done will be sanitized
    (based on SAFE_NAME_SCAN_PATTERN and SAFE_NAME_SUBS_PATTERN) in order not to
    interfere with the methods defined in a class you will drop a processor in.

    If you want to create an adhoc processor (then one that parasites on the
    other one (the host), so it does not have to be included directly into
    whatever includes the host) you need to inherit you processor from the host
    and set HOSTED_BY to that host.

    INHERITED controls whether commands inherited from base classes (which could
    include other processors) will be registered or not. This is disabled
    by-default because it leads to unpredictable consequences when used in adhoc
    processors which inherit from more then one processor or has such processors
    in its inheritance tree. In that case - encapsulation is being broken and
    some (all) commands are shared between non-related processors.
    """
    __metaclass__ = Dispatcher

    SAFE_NAME_SCAN_PATTERN = re.compile(r'_(?P<name>\w+)_')
    SAFE_NAME_SUBS_PATTERN = '_%s_'

    # Quite complex piece of regular expression logic.
    ARG_PATTERN = re.compile(r'(\'|")?(?P<body>(?(1).+?|\S+))(?(1)\1)')
    OPT_PATTERN = re.compile(r'(?<!\w)--?(?P<key>[\w-]+)(?:(?:=|\s)(\'|")?(?P<value>(?(2)[^-]+?|[^-\s]+))(?(2)\2))?')

    EXPAND_SHORT_OPTIONS = True

    COMMAND_PREFIX = '/'
    CASE_SENVITIVE_COMMANDS = False

    ARG_ENCODING = 'utf8'

    def __getattr__(self, name):
        """
        This allows to reach and directly (internally) call commands which are
        defined in (other) adhoc processors.
        """
        command_name = self.SAFE_NAME_SCAN_PATTERN.match(name)
        if command_name:
            command = Dispatcher.retrieve_command(self, command_name.group('name'))
            if command:
                return command
            raise AttributeError(name)
        return super(CommandProcessor, self).__getattr__(name)

    @classmethod
    def prepare_name(cls, name):
        return name if cls.CASE_SENVITIVE_COMMANDS else name.lower()

    @classmethod
    def retrieve_command(cls, name):
        name = cls.prepare_name(name)
        command = Dispatcher.retrieve_command(cls, name)
        if not command:
            raise CommandError("Command does not exist", name=name)
        return command

    @classmethod
    def list_commands(cls):
        commands = Dispatcher.list_commands(cls)
        return sorted(set(commands))

    @classmethod
    def parse_command_arguments(cls, arguments):
        """
        Simple yet effective and sufficient in most cases parser which parses
        command arguments and maps them to *args and **kwargs, which we all use
        extensivly in daily Python coding.

        The format of the input arguments should be:
            <arg1, arg2> <<optional>> [-(-o)ption=value1, -(-a)nother=value2] [[extra_options]]

        Options may be given in --long or -short format. As --option=value or
        --option value or -option value. Keys without values will get True as
        value. Arguments and option values that contain spaces may be given as
        'one two three' or "one two three"; that is between single or double
        quotes.
        """
        args, kwargs = [], {}

        # Need to store every option we have parsed in order to get arguments
        # to be parsed correct later.
        options = []

        def intersects((given_start, given_end)):
            """
            Check if something intersects with boundaries of any parsed options.
            """
            for start, end in options:
                if given_start == start or given_end == end:
                    return True
            return False

        for match in re.finditer(cls.OPT_PATTERN, arguments):
            if match:
                options.append(match.span())
                kwargs[match.group('key')] = match.group('value') or True

        for match in re.finditer(cls.ARG_PATTERN, arguments):
            if match and not intersects(match.span()):
                args.append(match.group('body'))

        return args, kwargs

    @classmethod
    def adapt_command_arguments(cls, command, arguments, args, kwargs):
        """
        Adapts *args and **kwargs got from a parser to a specific handler by
        means of arguments specified on command definition.

        When EXPAND_SHORT_OPTIONS is set then if command receives one-latter
        options (like -v or -f) they will be expanded to a verbose ones (like
        --verbose or --file) if the latter are defined as a command optional
        argumens. Expansion is made on a first-latter comparison basis. If more
        then one long option with the same first letter defined - only first one
        will be used in expanding.

        If command defines __arguments__ as a first argument - then this
        argument will receive raw and unprocessed arguments. Also, if nothing
        except __arguments__ (including *args, *kwargs splatting) is defined -
        then all parsed arguments will be discarded. It will be discarded in the
        argument usage information.

        If command defines __optional__ - that is an analogue for *args, to
        collect extra arguments. This is a preffered way over *args. Because of
        some Python limitations, *args could not be mapped to as expected. And
        it is hardly advised to define it after all hard arguments.

        Extra arguments which are not considered extra (or optional) - will be
        passed as if they were value for keywords, in the order keywords are
        defined and printed in usage.
        """
        spec_args, spec_kwargs, var_args, var_kwargs = command.extract_arg_spec()

        if command.raw:
            if len(spec_args) == 1:
                if arguments or command.empty:
                    return (arguments,), {}
                raise CommandError("Can not be used without arguments", command)
            raise CommandInternalError("Raw command must define no more then one argument")

        if '__optional__' in spec_args:
            if not var_args:
                hard_len = len(spec_args) - 1
                optional = args[hard_len:]
                args = args[:hard_len]
                args.insert(spec_args.index('__optional__'), optional)
            raise CommandInternalError("Cant have both, __optional__ and *args")

        if command.dashes:
            for key, value in kwargs.items():
                if '-' in key:
                    del kwargs[key]
                    kwargs[key.replace('-', '_')] = value

        if cls.EXPAND_SHORT_OPTIONS:
            expanded = []
            for key, value in spec_kwargs.iteritems():
                letter = key[0] if len(key) > 1 else None
                if letter and letter in kwargs and letter not in expanded:
                    expanded.append(letter)
                    kwargs[key] = kwargs[letter]
                    del kwargs[letter]

        # We need to encode every keyword argument to a simple string, not the
        # unicode one, because ** expanding does not support it. The nasty issue
        # here to consider is that if dict key was initially set as u'test',
        # then resetting it to just 'test' leaves u'test' as it was...
        for key, value in kwargs.items():
            if isinstance(key, UnicodeType):
                del kwargs[key]
                kwargs[key.encode(cls.ARG_ENCODING)] = value

        if '__arguments__' in spec_args:
            if len(spec_args) == 1 and not spec_kwargs and not var_args and not var_kwargs:
                return (arguments,), {}
            args.insert(spec_args.index('__arguments__'), arguments)

        return args, kwargs

    def process_as_command(self, text):
        """
        Try to process text as a command. Returns True if it is a command and
        False if it is not.
        """
        if not text.startswith(self.COMMAND_PREFIX):
            return False

        text = text[len(self.COMMAND_PREFIX):]
        text = text.strip()

        parts = text.split(' ', 1)

        if len(parts) > 1:
            name, arguments = parts
        else:
            name, arguments = parts[0], None

        flag = self.looks_like_command(text, name, arguments)
        if flag is not None:
            return flag

        self.execute_command(name, arguments)

        return True

    def execute_command(self, name, arguments):
        command = self.retrieve_command(name)

        args, kwargs = self.parse_command_arguments(arguments) if arguments else ([], {})
        args, kwargs = self.adapt_command_arguments(command, arguments, args, kwargs)

        if self.command_preprocessor(name, command, arguments, args, kwargs):
            return
        value = command(self, *args, **kwargs)
        self.command_postprocessor(name, command, arguments, args, kwargs, value)

    def command_preprocessor(self, name, command, arguments, args, kwargs):
        """
        Redefine this method in the subclass to execute custom code before
        command gets executed. If returns True then command execution will be
        interrupted and command will not be executed.
        """
        pass

    def command_postprocessor(self, name, command, arguments, args, kwargs, output):
        """
        Redefine this method in the subclass to execute custom code after
        command gets executed.
        """
        pass

    def looks_like_command(self, text, name, arguments):
        """
        This hook is being called before any processing, but after it was
        determined that text looks like a command. If returns non None value
        - then further processing will be interrupted and that value will be
        used to return from process_as_command.
        """
        pass

def command(*names, **kwargs):
    """
    A decorator which provides a declarative way of defining commands.

    You can specify a set of names by which you can call the command. If names
    are empty - then the name of the command will be set to native (extracted
    from the handler name). If no_native=True argument is given and names is
    non-empty - then native name will not be added.

    If command handler is not an instance method then is_instance=False should
    be given. Though mentioned case is not covered by defined behaviour, and
    should not be used, unless you know what you are doing.

    If usage=True is given - then handler's doc will be appended with an
    auto-gereated usage info.

    If raw=True is given then command should define only one argument to
    which all raw, unprocessed command arguments will be given.

    If dashes=True is given, then dashes (-) in the option
    names will be converted to underscores. So you can map --one-more-option to
    a one_more_option=None.

    If optional is set to a string then if __optional__ specified - its name
    ('optional' by-default) in the usage info will be substitued by whatever is
    given.

    If empty=True is given - then if raw is enabled it will allow to pass empty
    (None) raw arguments to a command.
    """
    names = list(names)

    no_native = kwargs.get('no_native', False)
    is_instance = kwargs.get('is_instance', True)
    usage = kwargs.get('usage', True)
    raw = kwargs.get('raw', False)
    dashes = kwargs.get('dashes', True)
    optional = kwargs.get('optional', 'optional')
    empty = kwargs.get('empty', False)

    def decorator(handler):
        command = Command(handler, is_instance, usage, raw, dashes, optional, empty)

        # Extract and inject native name while making sure it is going to be the
        # first one in the list.
        if not names or names and not no_native:
            names.insert(0, command.native_name)
        command.names = tuple(names)

        return command

    # Workaround if we are getting called without parameters.
    if len(names) == 1 and isinstance(names[0], FunctionType):
        return decorator(names.pop())

    return decorator
