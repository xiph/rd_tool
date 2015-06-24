#!/usr/bin/env python2

"""
Gather info about a y4m file and print it to standard output in JSON format
Mostly stuff useful for rate calculation.
"""

from __future__ import print_function

from os import path
import json
import sys
from hashlib import md5

sys.path.append(path.join(path.dirname(sys.argv[0]), '..', 'pylib'))
import y4m


def get_y4m_info(filename):
    # Could just as well use CRC32 here, but MD5 is more commonly available as a CLI tool for comparison
    hasher = md5()
    frame_count = 0
    with open(filename, 'rb') as y4m_file:
        header, frames = y4m.read_file(y4m_file)
        hasher.update(header)
        params = y4m.parse_header(header)
        for frame_header, frame_data in frames:
            frame_count += 1
            hasher.update(frame_header)
            hasher.update(frame_data)

    size = path.getsize(filename)
    width, height = int(params[b'W']), int(params[b'H'])
    return {
        'width': width,
        'height': height,
        'bytes': size,
        'frames': frame_count,
        'frame_rate': params[b'F'],
        'subsampling': params[b'C'],
        'md5': hasher.hexdigest(),
        'pixels': width * height * frame_count,
    }


def main(filename):
    print(json.dumps(get_y4m_info(filename)))

if __name__ == '__main__':
    main(sys.argv[1])
