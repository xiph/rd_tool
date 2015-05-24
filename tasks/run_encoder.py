#!/usr/bin/env python2
"""
Encode a file at a given quality setting and gather metrics.
The result is printed to standard output in JSON format.
"""

from __future__ import print_function
import argparse
import json
from os import path, chdir
from shutil import rmtree
import sys
from tempfile import mkdtemp
import time

sys.path.append(path.join(path.dirname(sys.argv[0]), '..', 'pylib'))
from encoders import get_encoder
from metrics import get_all_metrics


def gather_metrics_from_encoder(encoder, metrics, input_y4m, q):
    output_y4m = '{0}.{1}.y4m'.format(path.basename(input_y4m), q)
    start_time = time.time()
    encoded_file, cmd = encoder.encode_and_dump(input_y4m, output_y4m, q)
    end_time = time.time()
    encoded_size = path.getsize(encoded_file)

    metrics = calculate_metrics(metrics, input_y4m, output_y4m)

    return {
        'quality': q,
        'bytes': encoded_size,
        'encode_time': int(round(end_time - start_time)),
        'cmd': cmd,
        'metrics': metrics,
    }


def calculate_metrics(metrics, original_y4m, result_y4m):
    results = {"total": {}, "Y'": {}, "Cb": {}, "Cr": {}}
    for metric in metrics:
        values = metric.calculate(original_y4m, result_y4m)
        for plane, value in values.items():
            results[plane][metric.name()] = value
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--codec', default='daala')
    parser.add_argument('--keep-temp-files', action='store_true')
    parser.add_argument('--run-name', default='')
    parser.add_argument('--daala-root', required=True)
    parser.add_argument('q', type=int)
    parser.add_argument('file')

    args = parser.parse_args()

    # Resolve path before we chdir
    file_path = path.abspath(args.file)
    daala_root = path.abspath(args.daala_root)

    # Change to a temporary directory so intermediate files end up there
    temp_dir = mkdtemp(prefix='encode-', suffix=args.run_name)
    chdir(temp_dir)

    encoder = get_encoder(args.codec, daala_root)

    metrics = get_all_metrics(daala_root)

    output = gather_metrics_from_encoder(encoder, metrics, file_path, args.q)

    print(json.dumps(output))

    if not args.keep_temp_files:
        # Remove the temporary directory if everything went well
        rmtree(temp_dir)


if __name__ == '__main__':
    main()
