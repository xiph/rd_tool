#!/usr/bin/env python2
"""
Utility functions for parsing y4m files
"""

from fractions import Fraction


def read_file(fileobj):
    """Iterate over the parts of a y4m file

    Returns a (header, frame_iterator) tuple, where frame_iterator returns (frame_header, frame_data) tuples
    """
    header = fileobj.readline()
    params = parse_header(header)
    width, height = int(params[b'W']), int(params[b'H'])
    frame_bytes = frame_size(width, height, params[b'C'])
    return (header, _iterate_over_frames(fileobj, frame_bytes))

def read_header(fileobj):
    """Parse the header of a file and return it as a dict"""
    header, _ = read_file(fileobj)
    return parse_header(header)


def _iterate_over_frames(fileobj, frame_bytes):
    """Yield a (header, frame_data) pair for each frame encountered in the file"""
    while True:
        frame_header = fileobj.readline()
        if frame_header == b'':
            return # EOF
        if not frame_header.startswith(b'FRAME'):
            raise ValueError('Expected frame header')
        frame = fileobj.read(frame_bytes)
        if len(frame) < frame_bytes:
            raise ValueError('Read truncated frame')
        yield (frame_header, frame)


def parse_header(header):
    """Parse a y4m header to a dict of parameter values

    >>> sorted(parse_header("YUV4MPEG2 W640 H400 F24:1 Ip A1:1 C420jpeg XYSCSS=420JPEG").items())
    [('A', '1:1'), ('C', '420jpeg'), ('F', '24:1'), ('H', '400'), ('I', 'p'), ('W', '640'), ('X', 'YSCSS=420JPEG')]
    """
    if not header.startswith(b'YUV4MPEG2 '):
        raise ValueError('Not a valid y4m header')
    params = dict((param[:1], param[1:].strip()) for param in header.split(b' ')[1:])
    return params


def frame_size(width, height, subsampling):
    """Get the frame size in bytes from the dimensions and subsampling

    >>> frame_size(640, 400, b'420jpeg')
    384000
    """
    multipliers = {
        b'444': 3,
        b'422': 2,
        b'420': Fraction(3, 2),
        b'420jpeg': Fraction(3, 2),
        b'420paldv': Fraction(3, 2),
    }
    return int(width * height * multipliers[subsampling])
