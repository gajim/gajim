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
from types import FunctionType, UnicodeType, TupleType, ListType, BooleanType
from inspect import getargspec
from operator import itemgetter

class InternalError(Exception):
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

    def __init__(self, handler, usage, source, raw, extra, overlap, empty, expand_short):
        self.handler = handler

        self.usage = usage
        self.source = source
        self.raw = raw
        self.extra = extra
        self.overlap = overlap
        self.empty = empty
        self.expand_short = expand_short

    def __call__(self, *args, **kwargs):
        try:
            return self.handler(*args, **kwargs)
        except CommandError, exception:
            # Re-raise an excepttion with a proper command attribute set,
            # unless it is already set by the one who raised an exception.
            if not exception.command and not exception.name:
                raise CommandError(exception.message, self)

            # Do not forget to re-raise an exception just like it was if at
            # least either, command or name attribute is set properly.
            raise

        # This one is a little bit too wide, but as Python does not have
        # anything more constrained - there is no other choice. Take a look here
        # if command complains about invalid arguments while they are ok.
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
        return doc.split('\n', 1)[0] if doc else None

    def extract_arg_spec(self):
        names, var_args, var_kwargs, defaults = getargspec(self.handler)

        # Behavior of this code need to be checked. Might yield incorrect
        # results on some rare occasions.
        spec_args = names[:-len(defaults) if defaults else len(names)]
        spec_kwargs = list(zip(names[-len(defaults):], defaults)) if defaults else {}

        # Removing self from arguments specification. Command handler should
        # normally be an instance method.
        if spec_args.pop(0) != 'self':
            raise InternalError("First argument must be self")

        return spec_args, spec_kwargs, var_args, var_kwargs

    def extract_arg_usage(self, complete=True):
        """
        Extract handler's arguments specification and wrap them in a
        human-readable format. If complete is given - then ARG_USAGE_PATTERN
        will be used to render it completly.
        """
        spec_args, spec_kwargs, var_args, var_kwargs = self.extract_arg_spec()

        # Remove some special positional arguments from the specifiaction, but
        # store their names so they can be used for usage info generation.
        sp_source = spec_args.pop(0) if self.source else None
        sp_extra = spec_args.pop() if self.extra else None

        kwargs = []
        letters = []

        for key, value in spec_kwargs:
            letter = key[0]
            key = key.replace('_', '-')

            if isinstance(value, BooleanType):
                value = str()
            elif isinstance(value, (TupleType, ListType)):
                value = '={%s}' % ', '.join(value)
            else:
                value = '=%s' % value

            if letter not in letters:
                kwargs.append('-(-%s)%s%s' % (letter, key[1:], value))
                letters.append(letter)
            else:
                kwargs.append('--%s%s' % (key, value))

        usage = str()
        args = str()

        if self.raw:
            spec_len = len(spec_args) - 1
            if spec_len:
                args += ('<%s>' % ', '.join(spec_args[:spec_len])) + ' '
            args += ('(|%s|)' if self.empty else '|%s|') % spec_args[-1]
        else:
            if spec_args:
                args += '<%s>' % ', '.join(spec_args)
            if var_args or sp_extra:
                args += (' ' if spec_args else str()) + '<<%s>>' % (var_args or sp_extra)

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

        cls.check_if_conformed(dispatchable, hostable)

        if Dispatcher.is_suitable(cls, dct):
            Dispatcher.register_processor(cls)

        # Sanitize names even if processor is not suitable for registering,
        # because it might be inherited by an another processor.
        Dispatcher.sanitize_names(cls)

        super(Dispatcher, cls).__init__(name, bases, dct)

    @classmethod
    def is_suitable(cls, proc, dct):
        is_not_root = dct.get('__metaclass__') is not cls
        to_be_dispatched = bool(dct.get('DISPATCH'))
        return is_not_root and to_be_dispatched

    @classmethod
    def check_if_dispatchable(cls, bases, dct):
        dispatcher = dct.get('DISPATCHED_BY')
        if not dispatcher:
            return False
        if dispatcher not in bases:
            raise InternalError("Should be dispatched by the same processor it inherits from")
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
                raise InternalError("Should be hosted by the same processors it inherits from")
        return True

    @classmethod
    def check_if_conformed(cls, dispatchable, hostable):
        if dispatchable and hostable:
            raise InternalError("Processor can not be dispatchable and hostable at the same time")

    @classmethod
    def register_processor(cls, proc):
        cls.table[proc] = {}
        inherit = proc.__dict__.get('INHERIT')

        if 'HOSTED_BY' in proc.__dict__:
            cls.register_adhocs(proc)

        commands = cls.traverse_commands(proc, inherit)
        cls.register_commands(proc, commands)

    @classmethod
    def sanitize_names(cls, proc):
        inherit = proc.__dict__.get('INHERIT')
        commands = cls.traverse_commands(proc, inherit)
        for key, command in commands:
            if not proc.SAFE_NAME_SCAN_PATTERN.match(key):
                setattr(proc, proc.SAFE_NAME_SUBS_PATTERN % key, command)
                try:
                    delattr(proc, key)
                except AttributeError:
                    pass

    @classmethod
    def traverse_commands(cls, proc, inherit=True):
        keys = dir(proc) if inherit else proc.__dict__.iterkeys()
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
                    raise InternalError("Command with name %s already exists" % name)
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
                inherit = adhoc.__dict__.get('INHERIT')
                commands.update(dict(cls.traverse_commands(adhoc, inherit)))
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
    DISPATCH = True in order to be included in the dispatching table.

    Every class you will drop the processor in should define DISPATCHED_BY set
    to the same processor you are inheriting from.

    Names of the commands after preparation stuff id done will be sanitized
    (based on SAFE_NAME_SCAN_PATTERN and SAFE_NAME_SUBS_PATTERN) in order not to
    interfere with the methods defined in a class you will drop a processor in.

    If you want to create an adhoc processor (then one that parasites on the
    other one (the host), so it does not have to be included directly into
    whatever includes the host) you need to inherit you processor from the host
    and set HOSTED_BY to that host.

    INHERIT controls whether commands inherited from base classes (which could
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

    COMMAND_PREFIX = '/'
    CASE_SENSITIVE_COMMANDS = False

    ARG_ENCODING = 'utf8'

    def __getattr__(self, name):
        """
        This allows to reach and directly (internally) call commands which are
        defined in (other) adhoc processors.
        """
        command_name = self.SAFE_NAME_SCAN_PATTERN.match(name)
        if command_name:
            command = self.retrieve_command(command_name.group('name'))
            if command:
                return command
        raise AttributeError(name)

    @classmethod
    def prepare_name(cls, name):
        return name if cls.CASE_SENSITIVE_COMMANDS else name.lower()

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
        command arguments and returns them as two lists. First represents
        positional arguments as (argument, position), and second representing
        options as (key, value, position) tuples, where position is a (start,
        end) span tuple of where it was found in the string.

        The format of the input arguments should be:
            <arg1, arg2> <<extra>> [-(-o)ption=value1, -(-a)nother=value2] [[extra_options]]

        Options may be given in --long or -short format. As --option=value or
        --option value or -option value. Keys without values will get True as
        value. Arguments and option values that contain spaces may be given as
        'one two three' or "one two three"; that is between single or double
        quotes.
        """
        args, opts = [], []

        def intersects_opts((given_start, given_end)):
            """
            Check if something intersects with boundaries of any parsed option.
            """
            for key, value, (start, end) in opts:
                if given_start >= start and given_end <= end:
                    return True
            return False

        def intersects_args((given_start, given_end)):
            """
            Check if something intersects with boundaries of any parsed argument.
            """
            for arg, (start, end) in args:
                if given_start >= start and given_end <= end:
                    return True
            return False

        for match in re.finditer(cls.OPT_PATTERN, arguments):
            if match:
                key = match.group('key')
                value = match.group('value') or None
                position = match.span()
                opts.append((key, value, position))

        for match in re.finditer(cls.ARG_PATTERN, arguments):
            if match and not intersects_opts(match.span()):
                body = match.group('body')
                position = match.span()
                args.append((body, position))

        # In rare occasions quoted options are being captured, while they should
        # not be. This fixes the problem by finding options which intersect with
        # arguments and removing them.
        for key, value, position in opts[:]:
            if intersects_args(position):
                opts.remove((key, value, position))

        return args, opts

    @classmethod
    def adapt_command_arguments(cls, command, arguments, args, opts):
        """
        Adapts args and opts got from the parser to a specific handler by means
        of arguments specified on command definition. That is transforms them to
        *args and **kwargs suitable for passing to a command handler.

        Extra arguments which are not considered extra (or optional) - will be
        passed as if they were value for keywords, in the order keywords are
        defined and printed in usage.

        Dashes (-) in the option names will be converted to underscores. So you
        can map --one-more-option to a one_more_option=None.

        If initial value of a keyword argument is a boolean (False in most
        cases) then this option will be treated as a switch, that is an option
        which does not take an argument. Argument preceded by a switch will be
        treated just like a normal positional argument.

        If keyword argument's initial value is a sequence (tuple or a string)
        then possible values of the option will be restricted to one of the
        values given by the sequence.
        """
        spec_args, spec_kwargs, var_args, var_kwargs = command.extract_arg_spec()
        norm_kwargs = dict(spec_kwargs)

        # Quite complex piece of neck-breaking logic to extract raw arguments if
        # there is more, then one positional argument specified by the command.
        # In case if it's just one argument which is the collector this is
        # fairly easy. But when it's more then one argument - the neck-breaking
        # logic of how to retrieve residual arguments as a raw, all in one piece
        # string, kicks on.
        if command.raw:
            if spec_kwargs or var_args or var_kwargs:
                raise InternalError("Raw commands should define only positional arguments")

            if arguments:
                spec_fix = 1 if command.source else 0
                spec_len = len(spec_args) - spec_fix
                arguments_end = len(arguments) - 1

                # If there are any optional arguments given they should be
                # either an unquoted postional argument or part of the raw
                # argument. So we find all optional arguments that can possibly
                # be unquoted argument and append them as is to the args.
                for key, value, (start, end) in opts[:spec_len]:
                    if value:
                        end -= len(value) + 1
                        args.append((arguments[start:end], (start, end)))
                        args.append((value, (end, end + len(value) + 1)))
                    else:
                        args.append((arguments[start:end], (start, end)))

                # We need in-place sort here because after manipulations with
                # options order of arguments might be wrong and we just can't
                # have more complex logic to not let that happen.
                args.sort(key=itemgetter(1))

                if spec_len > 1:
                    try:
                        stopper, (start, end) = args[spec_len - 2]
                    except IndexError:
                        raise CommandError("Missing arguments", command)

                    raw = arguments[end:]
                    raw = raw.strip() or None

                    if not raw and not command.empty:
                        raise CommandError("Missing arguments", command)

                    # Discard residual arguments and all of the options as raw
                    # command does not support options and if an option is given
                    # it is rather a part of a raw argument.
                    args = args[:spec_len - 1]
                    opts = []

                    args.append((raw, (end, arguments_end)))
                elif spec_len == 1:
                    args = [(arguments, (0, arguments_end))]
                    opts = []
                else:
                    raise InternalError("Raw command must define a collector")
            else:
                if command.empty:
                    args.append((None, (0, 0)))
                else:
                    raise CommandError("Missing arguments", command)

        # The first stage of transforming options we have got to a format that
        # can be used to associate them with declared keyword arguments.
        # Substituting dashes (-) in their names with underscores (_).
        for index, (key, value, position) in enumerate(opts):
            if '-' in key:
                opts[index] = (key.replace('-', '_'), value, position)

        # The second stage of transforming options to an associatable state.
        # Expanding short, one-letter options to a verbose ones, if
        # corresponding optin has been given.
        if command.expand_short:
            expanded = []
            for spec_key, spec_value in norm_kwargs.iteritems():
                letter = spec_key[0] if len(spec_key) > 1 else None
                if letter and letter not in expanded:
                    for index, (key, value, position) in enumerate(opts):
                        if key == letter:
                            expanded.append(letter)
                            opts[index] = (spec_key, value, position)
                            break

        # Detect switches and set their values accordingly. If any of them
        # carries a value - append it to args.
        for index, (key, value, position) in enumerate(opts):
            if isinstance(norm_kwargs.get(key), BooleanType):
                opts[index] = (key, True, position)
                if value:
                    args.append((value, position))

        # Sorting arguments and options (just to be sure) in regarding to their
        # positions in the string.
        args.sort(key=itemgetter(1))
        opts.sort(key=itemgetter(2))

        # Stripping down position information supplied with arguments and options as it
        # won't be needed again.
        args = map(lambda (arg, position): arg, args)
        opts = map(lambda (key, value, position): (key, value), opts)

        # If command has extra option enabled - collect all extra arguments and
        # pass them to a last positional argument command defines as a list.
        if command.extra:
            if not var_args:
                spec_fix = 1 if not command.source else 2
                spec_len = len(spec_args) - spec_fix
                extra = args[spec_len:]
                args = args[:spec_len]
                args.append(extra)
            else:
                raise InternalError("Can not have both, extra and *args")

        # Detect if positional arguments overlap keyword arguments. If so and
        # this is allowed by command options - then map them directly to their
        # options, so they can get propert further processings.
        spec_fix = 1 if command.source else 0
        spec_len = len(spec_args) - spec_fix
        if len(args) > spec_len:
            if command.overlap:
                overlapped = args[spec_len:]
                args = args[:spec_len]
                for arg, (spec_key, spec_value) in zip(overlapped, spec_kwargs):
                    opts.append((spec_key, arg))
            else:
                raise CommandError("Excessive arguments", command)

        # Detect every contraint sequences and ensure that if corresponding
        # options are given - they contain proper values, within constraint
        # range.
        for key, value in opts:
            initial = norm_kwargs.get(key)
            if isinstance(initial, (TupleType, ListType)) and value not in initial:
                raise CommandError("Wrong argument", command)

        # Detect every switch and ensure it will not receive any arguments.
        # Normally this does not happen unless overlapping is enabled.
        for key, value in opts:
            initial = norm_kwargs.get(key)
            if isinstance(initial, BooleanType) and not isinstance(value, BooleanType):
                raise CommandError("Switches do not take arguments", command)

        # We need to encode every keyword argument to a simple string, not the
        # unicode one, because ** expansion does not support it.
        for index, (key, value) in enumerate(opts):
            if isinstance(key, UnicodeType):
                opts[index] = (key.encode(cls.ARG_ENCODING), value)

        # Inject the source arguments as a string as a first argument, if
        # command has enabled the corresponding option.
        if command.source:
            args.insert(0, arguments)

        # Return *args and **kwargs in the form suitable for passing to a
        # command handlers and being expanded.
        return tuple(args), dict(opts)

    def process_as_command(self, text):
        """
        Try to process text as a command. Returns True if it is a command and
        False if it is not.
        """
        if not text.startswith(self.COMMAND_PREFIX):
            return False

        body = text[len(self.COMMAND_PREFIX):]
        body = body.strip()

        parts = body.split(' ', 1)
        name, arguments = parts if len(parts) > 1 else (parts[0], None)

        flag = self.looks_like_command(body, name, arguments)
        if flag is not None:
            return flag

        self.execute_command(text, name, arguments)

        return True

    def execute_command(self, text, name, arguments):
        command = self.retrieve_command(name)

        args, opts = self.parse_command_arguments(arguments) if arguments else ([], [])
        args, kwargs = self.adapt_command_arguments(command, arguments, args, opts)

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
    is empty - then the name of the command will be set to native one (extracted
    from the handler name).

    If include_native=True argument is given and names is non-empty - then
    native name will be added as well.

    If usage=True is given - then handler's doc will be appended with an
    auto-generated usage info.

    If source=True is given - then the first positional argument of the command
    handler will receive a string with a raw and unprocessed source arguments.

    If raw=True is given - then command should define only one argument to
    which all raw and unprocessed source arguments will be given.

    If empty=True is given - then when raw=True is set and command receives no
    arguments - an exception will be raised.

    If extra=True is given - then last positional argument will receive every
    extra positional argument that will be given to a command. This is an
    analogue to specifing *args, but the latter one should be used in simplest
    cases only because of some Python limitations on this - arguments can't be
    mapped correctly when there are keyword arguments present.

    If overlap=True is given - then if extra=False and there is extra arguments
    given to the command - they will be mapped as if they were values for the
    keyword arguments, in the order they are defined.

    If expand_short=True is given - then if command receives one-letter
    options (like -v or -f) they will be expanded to a verbose ones (like
    --verbose or --file) if the latter are defined as a command optional
    arguments. Expansion is made on a first-letter comparison basis. If more
    then one long option with the same first letter defined - only first one
    will be used in expansion.
    """
    names = list(names)
    include_native = kwargs.get('include_native', True)

    usage = kwargs.get('usage', True)
    source = kwargs.get('source', False)
    raw = kwargs.get('raw', False)
    extra = kwargs.get('extra', False)
    overlap = kwargs.get('overlap', False)
    empty = kwargs.get('empty', False)
    expand_short = kwargs.get('expand_short', True)

    if extra and overlap:
        raise InternalError("Extra and overlap options can not be used together")

    def decorator(handler):
        command = Command(handler, usage, source, raw, extra, overlap, empty, expand_short)

        # Extract and inject native name while making sure it is going to be the
        # first one in the list.
        if not names or include_native:
            names.insert(0, command.native_name)
        command.names = tuple(names)

        return command

    # Workaround if we are getting called without parameters. Keep in mind that
    # in that case - first item in the names will be the handler.
    if len(names) == 1 and isinstance(names[0], FunctionType):
        return decorator(names.pop())

    return decorator
