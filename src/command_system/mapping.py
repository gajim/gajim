# Copyright (C) 2009  Alexander Cherniuk <ts33kr@gmail.com>
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
The module contains routines to parse command arguments and map them to the
command handler's positonal and keyword arguments.

Mapping is done in two stages: 1) parse arguments into positional arguments and
options; 2) adapt them to the specific command handler according to the command
properties.
"""

import re
from types import BooleanType, UnicodeType
from types import TupleType, ListType
from operator import itemgetter

from errors import DefinitionError, CommandError

# Quite complex piece of regular expression logic to parse options and
# arguments. Might need some tweaking along the way.
ARG_PATTERN = re.compile(r'(\'|")?(?P<body>(?(1).+?|\S+))(?(1)\1)')
OPT_PATTERN = re.compile(r'(?<!\w)--?(?P<key>[\w-]+)(?:(?:=|\s)(\'|")?(?P<value>(?(2)[^-]+?|[^-\s]+))(?(2)\2))?')

# Option keys needs to be encoded to a specific encoding as Python does not
# allow to expand dictionary with raw unicode strings as keys from a **kwargs.
KEY_ENCODING = 'UTF-8'

# Defines how complete representation of command usage (generated based on
# command handler argument specification) will be rendered.
USAGE_PATTERN = 'Usage: %s %s'

def parse_arguments(arguments):
    """
    Simple yet effective and sufficient in most cases parser which parses
    command arguments and returns them as two lists.

    First list represents positional arguments as (argument, position), and
    second representing options as (key, value, position) tuples, where position
    is a (start, end) span tuple of where it was found in the string.

    Options may be given in --long or -short format. As --option=value or
    --option value or -option value. Keys without values will get None as value.

    Arguments and option values that contain spaces may be given as 'one two
    three' or "one two three"; that is between single or double quotes.
    """
    args, opts = [], []

    def intersects_opts((given_start, given_end)):
        """
        Check if given span intersects with any of options.
        """
        for key, value, (start, end) in opts:
            if given_start >= start and given_end <= end:
                return True
        return False

    def intersects_args((given_start, given_end)):
        """
        Check if given span intersects with any of arguments.
        """
        for arg, (start, end) in args:
            if given_start >= start and given_end <= end:
                return True
        return False

    for match in re.finditer(OPT_PATTERN, arguments):
        if match:
            key = match.group('key')
            value = match.group('value') or None
            position = match.span()
            opts.append((key, value, position))

    for match in re.finditer(ARG_PATTERN, arguments):
        if match:
            body = match.group('body')
            position = match.span()
            args.append((body, position))

    # Primitive but sufficiently effective way of disposing of conflicted
    # sectors. Remove any arguments that intersect with options.
    for arg, position in args[:]:
        if intersects_opts(position):
            args.remove((arg, position))

    # Primitive but sufficiently effective way of disposing of conflicted
    # sectors. Remove any options that intersect with arguments.
    for key, value, position in opts[:]:
        if intersects_args(position):
            opts.remove((key, value, position))

    return args, opts

def adapt_arguments(command, arguments, args, opts):
    """
    Adapt args and opts got from the parser to a specific handler by means of
    arguments specified on command definition. That is transform them to *args
    and **kwargs suitable for passing to a command handler.

    Dashes (-) in the option names will be converted to underscores. So you can
    map --one-more-option to a one_more_option=None.

    If the initial value of a keyword argument is a boolean (False in most
    cases) - then this option will be treated as a switch, that is an option
    which does not take an argument. If a switch is followed by an argument -
    then this argument will be treated just like a normal positional argument.

    If the initial value of a keyword argument is a sequence, that is a tuple or
    list - then a value of this option will be considered correct only if it is
    present in the sequence.
    """
    spec_args, spec_kwargs, var_args, var_kwargs = command.extract_specification()
    norm_kwargs = dict(spec_kwargs)

    # Quite complex piece of neck-breaking logic to extract raw arguments if
    # there is more, then one positional argument specified by the command.  In
    # case if it's just one argument which is the collector - this is fairly
    # easy. But when it's more then one argument - the neck-breaking logic of
    # how to retrieve residual arguments as a raw, all in one piece string,
    # kicks in.
    if command.raw:
        if arguments:
            spec_fix = 1 if command.source else 0
            spec_len = len(spec_args) - spec_fix
            arguments_end = len(arguments) - 1

            # If there are any optional arguments given they should be either an
            # unquoted postional argument or part of the raw argument. So we
            # find all optional arguments that can possibly be unquoted argument
            # and append them as is to the args.
            for key, value, (start, end) in opts[:spec_len]:
                if value:
                    end -= len(value) + 1
                    args.append((arguments[start:end], (start, end)))
                    args.append((value, (end, end + len(value) + 1)))
                else:
                    args.append((arguments[start:end], (start, end)))

            # We need in-place sort here because after manipulations with
            # options order of arguments might be wrong and we just can't have
            # more complex logic to not let that happen.
            args.sort(key=itemgetter(1))

            if spec_len > 1:
                try:
                    stopper, (start, end) = args[spec_len - 2]
                except IndexError:
                    raise CommandError("Missing arguments", command)

                # The essential point of the whole play. After boundaries are
                # being determined (supposingly correct) we separate raw part
                # from the rest of arguments, which should be normally
                # processed.
                raw = arguments[end:]
                raw = raw.strip() or None

                if not raw and not command.empty:
                    raise CommandError("Missing arguments", command)

                # Discard residual arguments and all of the options as raw
                # command does not support options and if an option is given it
                # is rather a part of a raw argument.
                args = args[:spec_len - 1]
                opts = []

                args.append((raw, (end, arguments_end)))
            else:
                # Substitue all of the arguments with only one, which contain
                # raw and unprocessed arguments as a string. And discard all the
                # options, as raw command does not support them.
                args = [(arguments, (0, arguments_end))]
                opts = []
        else:
            if command.empty:
                args.append((None, (0, 0)))
            else:
                raise CommandError("Missing arguments", command)

    # The first stage of transforming options we have got to a format that can
    # be used to associate them with declared keyword arguments.  Substituting
    # dashes (-) in their names with underscores (_).
    for index, (key, value, position) in enumerate(opts):
        if '-' in key:
            opts[index] = (key.replace('-', '_'), value, position)

    # The second stage of transforming options to an associatable state.
    # Expanding short, one-letter options to a verbose ones, if corresponding
    # optin has been given.
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

    # Detect switches and set their values accordingly. If any of them carries a
    # value - append it to args.
    for index, (key, value, position) in enumerate(opts):
        if isinstance(norm_kwargs.get(key), BooleanType):
            opts[index] = (key, True, position)
            if value:
                args.append((value, position))

    # Sorting arguments and options (just to be sure) in regarding to their
    # positions in the string.
    args.sort(key=itemgetter(1))
    opts.sort(key=itemgetter(2))

    # Stripping down position information supplied with arguments and options as
    # it won't be needed again.
    args = map(lambda (arg, position): arg, args)
    opts = map(lambda (key, value, position): (key, value), opts)

    # If command has extra option enabled - collect all extra arguments and pass
    # them to a last positional argument command defines as a list.
    if command.extra:
        if not var_args:
            spec_fix = 1 if not command.source else 2
            spec_len = len(spec_args) - spec_fix
            extra = args[spec_len:]
            args = args[:spec_len]
            args.append(extra)
        else:
            raise DefinitionError("Can not have both, extra and *args")

    # Detect if positional arguments overlap keyword arguments. If so and this
    # is allowed by command options - then map them directly to their options,
    # so they can get propert further processings.
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

    # Detect every switch and ensure it will not receive any arguments.
    # Normally this does not happen unless overlapping is enabled.
    for key, value in opts:
        initial = norm_kwargs.get(key)
        if isinstance(initial, BooleanType):
            if not isinstance(value, BooleanType):
                raise CommandError("%s: Switch can not take an argument" % key, command)

    # Detect every sequence constraint and ensure that if corresponding options
    # are given - they contain proper values, within the constraint range.
    for key, value in opts:
        initial = norm_kwargs.get(key)
        if isinstance(initial, (TupleType, ListType)):
            if value not in initial:
                raise CommandError("%s: Invalid argument" % key, command)

    # If argument to an option constrained by a sequence was not given - then
    # it's value should be set to None.
    for spec_key, spec_value in spec_kwargs:
        if isinstance(spec_value, (TupleType, ListType)):
            for key, value in opts:
                if spec_key == key:
                    break
            else:
                opts.append((spec_key, None))

    # We need to encode every keyword argument to a simple string, not the
    # unicode one, because ** expansion does not support it.
    for index, (key, value) in enumerate(opts):
        if isinstance(key, UnicodeType):
            opts[index] = (key.encode(KEY_ENCODING), value)

    # Inject the source arguments as a string as a first argument, if command
    # has enabled the corresponding option.
    if command.source:
        args.insert(0, arguments)

    # Return *args and **kwargs in the form suitable for passing to a command
    # handler and being expanded.
    return tuple(args), dict(opts)

def generate_usage(command, complete=True):
    """
    Extract handler's arguments specification and wrap them in a human-readable
    format usage information. If complete is given - then USAGE_PATTERN will be
    used to render the specification completly.
    """
    spec_args, spec_kwargs, var_args, var_kwargs = command.extract_specification()

    # Remove some special positional arguments from the specifiaction, but store
    # their names so they can be used for usage info generation.
    sp_source = spec_args.pop(0) if command.source else None
    sp_extra = spec_args.pop() if command.extra else None

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

    if command.raw:
        spec_len = len(spec_args) - 1
        if spec_len:
            args += ('<%s>' % ', '.join(spec_args[:spec_len])) + ' '
        args += ('(|%s|)' if command.empty else '|%s|') % spec_args[-1]
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

    # Native name will be the first one if it is included. Otherwise, names will
    # be in the order they were specified.
    if len(command.names) > 1:
        names = '%s (%s)' % (command.first_name, ', '.join(command.names[1:]))
    else:
        names = command.first_name

    return USAGE_PATTERN % (names, usage) if complete else usage
