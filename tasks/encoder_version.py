#!/usr/bin/env python2

"""
Get version of encoders and tools
"""

from __future__ import print_function
import argparse
from os import path
import json
import sys

sys.path.append(path.join(path.dirname(sys.argv[0]), '..', 'pylib'))
from encoders import get_encoder, get_all_binaries

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--codec', default='daala')
    for bin_name in get_all_binaries():
        parser.add_argument('--{0}-path'.format(bin_name))
    parser.add_argument('--tools-root', required=True)

    args = parser.parse_args()

    paths = {}
    for bin_name in get_all_binaries():
        bin_path = getattr(args, '{0}_path'.format(bin_name))
        if bin_path:
            paths[bin_name] = bin_path

    encoder = get_encoder(args.codec, paths)

    # Use Daala encoder to name the tools repo version
    tools_daala = get_encoder('daala', {'daala': path.join(args.tools_root, 'examples', 'encoder_example')})

    versions = {
        'tools_version': tools_daala.get_version(),
        encoder.name() + '_version': encoder.get_version(),
    }

    print(json.dumps(versions))

if __name__ == '__main__':
    main()
