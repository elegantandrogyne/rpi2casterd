"""Converter and parser functions for rpi2caster driver"""

from collections import deque, OrderedDict

COLUMNS = tuple('ABCDEFGHIJKLMNO')
ROWS = tuple(str(x) for x in range(16, 0, -1))
JUSTIFICATION = ('0005', '0075', 'S')
# the signals in a sequence for parsing
PARSED_SIGNALS = tuple(['0005', '0075', *(str(x) for x in range(16, 0, -1)),
                        *'ABCDEFGHIJKLMNOS'])
# the signals in a sequence for encoding
ORDERED_SIGNALS = tuple(['0075', 'S', '0005', *'ABCDEFGHIJKLMN',
                         *(str(x) for x in range(1, 15)), 'O15'])
# all Monotype signals
SIGNALS = [*COLUMNS[:-1], *(str(x) for x in range(15)), 'O15', *JUSTIFICATION]


def signals(input_string):
    """Convert 'a,b,c,d,e' -> ['A', 'B', 'C', 'D', 'E']."""
    raw = [x.strip().upper() for x in input_string.split(',')]
    return [x for x in raw if x in SIGNALS]


def integers(input_string):
    """Convert '1,2,3,4,5' -> [1, 2, 3, 4, 5]"""
    return [int(x.strip()) for x in input_string.split(',')]


def lcstring(input_string):
    """Return a lowercase string stripped of all whitespace"""
    return input_string.strip().lower()


def millis(input_string):
    """Get milliseconds from a fractional value in seconds"""
    seconds = float(lcstring(input_string))
    return int(seconds * 1000)


def anyint(input_string):
    """Convert a decimal, octal, binary or hexadecimal string to integer"""
    return int(lcstring(input_string), 0)


def command(input_string):
    """Operating system command: string -> accepted by subprocess.run"""
    chunks = input_string.split(' ')
    return [x.strip() for x in chunks]


def get(parameter, source, convert):
    """Gets a value from a specified source for a given parameter,
    converts it to a desired data type"""
    return convert(source[parameter])


def parse_configuration(source):
    """Get the interface parameters from a config parser section"""
    try:
        config = OrderedDict()
        # supported operation and row 16 addressing modes
        modes = get('supported_modes', source, integers)
        row16_modes = get('supported_row16_modes', source, integers)
        config['supported_modes'] = modes
        config['mode'] = modes[0]
        config['supported_row16_modes'] = row16_modes
        config['row16_mode'] = row16_modes[0]

        # determine the sensor and output drivers
        config['sensor_driver'] = get('sensor_driver', source, lcstring)
        config['output_driver'] = get('output_driver', source, lcstring)

        # get timings
        config['startup_timeout'] = get('startup_timeout', source, float)
        config['sensor_timeout'] = get('sensor_timeout', source, float)
        config['pump_stop_timeout'] = get('pump_stop_timeout', source, float)
        config['punching_on_time'] = get('punching_on_time', source, float)
        config['punching_off_time'] = get('punching_off_time', source, float)

        # interface settings: input
        config['sensor_gpio'] = get('sensor_gpio', source, int)
        config['input_bounce_time'] = get('input_bounce_time', source, float)

        # interface settings: output
        config['i2c_bus'] = get('i2c_bus', source, anyint)
        config['mcp0_address'] = get('mcp0_address', source, anyint)
        config['mcp1_address'] = get('mcp1_address', source, anyint)
        config['signal_mappings'] = dict(valve1=get('valve1', source, signals),
                                         valve2=get('valve2', source, signals),
                                         valve3=get('valve3', source, signals),
                                         valve4=get('valve4', source, signals))

        # configuration ready to ship
        return config

    except KeyError as exc:
        return dict(error='configuration_error: {}'.format(exc))


def parse_signals(source):
    """Parse the incoming signals iterable into useful signals"""
    def find(value):
        """Detect and dispatch known signals in source string"""
        nonlocal _source
        string = str(value)
        if string in _source:
            _source = _source.replace(string, '')
            return True
        else:
            return False

    # make sure it's an uppercase string
    try:
        _source = source.upper()
    except AttributeError:
        _source = ''.join(str(x).upper() for x in source)
    # read the signals to know what's inside
    return {s for s in PARSED_SIGNALS if find(s)}


def ordered_signals(source):
    """Returns a list of arranged signals ready for display"""
    arranged = deque(s for s in ORDERED_SIGNALS if s in source)
    # put NI, NL, NK, NJ, NKJ etc. at the front
    if 'N' in arranged:
        for other in 'JKLI':
            if other in source:
                arranged.remove('N')
                arranged.appendleft(other)
                arranged.appendleft('N')
    return list(arranged)


def signals_set(source):
    """Convert an iterable of signals to a set"""
    return {str(s).upper() for s in source}


def convert_hmn(source):
    """HMN addressing mode - developed by Monotype, based on KMN.
    Uncommon."""
    # NI, NL, M -> add H -> HNI, HNL, HM
    # H -> add N -> HN
    # N -> add M -> MN
    # O -> add HMN
    # {ABCDEFGIJKL} -> add HM -> HM{ABCDEFGIJKL}

    # earlier rows than 16 won't trigger the attachment -> early return
    sigset = signals_set(source)
    for i in range(1, 16):
        if str(i) in sigset:
            return sigset

    columns = 'NI', 'NL', 'H', 'M', 'N', 'O'
    extras = 'H', 'H', 'N', 'H', 'M', 'HMN'
    if '16' in sigset:
        for column, extra in zip(columns, extras):
            if sigset.issuperset(column):
                sigset.discard('16')
                sigset.update(extra)
                break
    return sigset


def convert_kmn(source):
    """KMN addressing mode - invented by a British printshop.
    Very uncommon."""
    # NI, NL, M -> add K -> KNI, KNL, KM
    # K -> add N -> KN
    # N -> add M -> MN
    # O -> add KMN
    # {ABCDEFGHIJL} -> add KM -> KM{ABCDEFGHIJL}

    # earlier rows than 16 won't trigger the attachment -> early return
    sigset = signals_set(source)
    for i in range(1, 16):
        if str(i) in sigset:
            return sigset

    columns = 'NI', 'NL', 'K', 'M', 'N', 'O'
    extras = 'K', 'K', 'N', 'K', 'M', 'HMN'
    if '16' in sigset:
        for column, extra in zip(columns, extras):
            if sigset.issuperset(column):
                sigset.update(extra)
                sigset.discard('16')
                break
    return sigset


def convert_unitshift(source):
    """Unit-shift addressing mode - rather common,
    designed by Monotype and introduced in 1963"""
    sigset = signals_set(source)
    if 'D' in sigset:
        # when the attachment is on, the D signal is routed
        # to unit-shift activation piston instead of column D air pin
        # this pin is activated by EF combination instead
        sigset.discard('D')
        sigset.update('EF')
    if '16' in sigset:
        # use unit shift if the row signal is 16
        # make it possible to shift the diecase on earlier rows
        sigset.update('D')
        sigset.discard('16')
    return sigset


def strip_16(source):
    """Get rid of the "16" signal and replace it with "15"."""
    sigset = signals_set(source)
    if '16' in sigset:
        sigset.discard('16')
        sigset.add('15')
    return sigset


def convert_o15(source):
    """Change O and 15 to a combined O+15 signal"""
    source_signals = set(source)
    for signal in ('O', '15'):
        if signal in source_signals:
            source_signals.discard(signal)
            source_signals.update('O15')
    return source_signals


def strip_o15(source):
    """For casting, don't use O+15"""
    source_signals = set(source)
    source_signals.discard('O15')
    return source_signals


def add_missing_o15(source):
    """If length of signals is less than 2, add an O+15 so that when punching,
    the ribbon will be advanced properly."""
    source_signals = set(source)
    if len(source_signals) < 2:
        source_signals.update('O15')
    return source_signals
