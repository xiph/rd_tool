#!/usr/bin/env python2
"""
Information on how to call each encoder
"""

from os import path
import os
from subprocess import check_call, check_output
import subprocess

import y4m

def _remove_file_if_exists(file_path):
    if path.exists(file_path):
        os.remove(file_path)

def _predict_binary_search(min_q, max_q, steps):
    """Predict the binary search assuming the steps are all downwards

    >>> _predict_binary_search(1, 511, 4)
    [256, 128, 64, 32]
    """
    return [(min_q + max_q) // 2**i for i in range(1, steps + 1)]

class Encoder(object):
    binaries = []
    min_q = None
    max_q = None
    extension = None
    static_args = []

    def __init__(self, paths):
        self._paths = paths

    @classmethod
    def name(cls):
        return cls.__name__.lower()

    def _path_to(self, binary):
        return self._paths[binary]

    def encode_and_dump(self, input_y4m, output_y4m, q, extra_options=[]):
        """Encode a raw file and dump the result to a raw file again.
        Returns a tuple with the path to the encoded intermediate file, and the command line used to run the encoder."""
        encoder = self._path_to(self.binaries[0])
        output_encoded = output_y4m + self.extension

        basename = path.basename(output_y4m)
        logfile = path.basename(output_y4m) + '-enc.out'
        with open(logfile, 'wb') as enc_log:
            encode_cmd = [encoder] + self.static_args + self.get_encoder_args(input_y4m, output_y4m, q, output_encoded) + extra_options
            env = self.get_encoder_env(input_y4m, output_y4m, q)
            check_call(
                encode_cmd,
                env=env,
                stdout=enc_log,
                stderr=subprocess.STDOUT,
            )
        _remove_file_if_exists(logfile)
        return output_encoded, encode_cmd

    def get_encoder_env(self, input_y4m, output_y4m, q):
        return None

    def get_encoder_args(self, input_y4m, output_y4m, q, output_encoded):
        raise NotImplementedError()

    def get_version(self):
        """Get a version string"""
        encoder_binary = self._path_to(self.binaries[0])
        return check_output([encoder_binary, '--version'], stderr=subprocess.STDOUT).decode().strip()

    def default_qualities(self):
        """List of quality parameters to use by default"""
        raise NotImplementedError()


class Daala(Encoder):
    binaries = ['daala']
    min_q = 1
    max_q = 511
    extension = '.ogv'
    static_args = ['--keyframe-rate=256']

    def encode_and_dump(self, input_y4m, output_y4m, q, extra_options=[]):
        output_encoded, encode_cmd = Encoder.encode_and_dump(self, input_y4m, output_y4m, q, extra_options)

        # Move dumped y4m to correct location
        basename = path.basename(output_y4m)
        try:
            dumped_file = '00000000out-' + basename + '.y4m'
            os.rename(dumped_file, output_y4m)
        except OSError as e:
            raise RuntimeError("Could not find {0}, is daala configured with --enable-dump-recons?".format(dumped_file), e)

        return output_encoded, encode_cmd

    def get_encoder_env(self, input_y4m, output_y4m, q):
        basename = path.basename(output_y4m)
        return {
            'OD_LOG_MODULES': 'encoder:10',
            'OD_DUMP_IMAGES_SUFFIX': basename,
        }

    def get_encoder_args(self, input_y4m, output_y4m, q, output_encoded):
        return ['--video-quality', str(q), '--output', output_encoded, input_y4m]

    def default_qualities(self):
        # 256, 128, 64, 32 will probably be hit by the binary search, but start
        # them at once to improve utilization.
        warmup = _predict_binary_search(self.min_q, self.max_q, 4)
        # Add some extremes on each end
        return warmup + [5, 8, 400]


class X264(Encoder):
    binaries = ['x264']
    min_q = 1
    max_q = 51

    extension = '.x264'
    static_args = ['--preset=placebo', '--min-keyint=256', '--keyint=256', '--no-scenecut']

    def encode_and_dump(self, input_y4m, output_y4m, q, extra_options=[]):
        output_encoded, encode_cmd = Encoder.encode_and_dump(self, input_y4m, output_y4m, q, extra_options)

        # Need to convert the yuv dump to a y4m dump
        yuv_tmp_base = self.yuv_tmp_name(output_y4m)
        self.convert_yuv_dump_to_y4m(input_y4m, yuv_tmp_base)
        _remove_file_if_exists(yuv_tmp_base + '.yuv')

        return output_encoded, encode_cmd

    def get_encoder_args(self, input_y4m, output_y4m, q, output_encoded):
        yuv_name = self.yuv_tmp_name(output_y4m) + '.yuv'
        return ['--crf', str(q), '--output', output_encoded, '--dump-yuv', yuv_name, input_y4m]

    def yuv_tmp_name(self, output_y4m):
        yuv_tmp_base, y4m_ext = path.splitext(output_y4m)
        assert y4m_ext == '.y4m', 'yuv2yuv4mpeg only outputs to .y4m'
        return yuv_tmp_base

    def convert_yuv_dump_to_y4m(self, input_y4m, basename):
        """Converts basename.yuv to basename.y4m.
        The original input y4m is used to determine the width and height of the file.
        """
        with open(input_y4m, 'rb') as y4m_file:
            input_header = y4m.read_header(y4m_file)
        width, height = input_header['W'], input_header['H']
        yuv2yuv4mpeg = path.join(self._path_to('tools'), 'tools', 'yuv2yuv4mpeg')
        check_call([yuv2yuv4mpeg, basename, '-w{0}'.format(width), '-h{0}'.format(height), '-an0', '-ad0', '-c420mpeg2'])

    def default_qualities(self):
        return list(range(1,52,5))


class X265(Encoder):
    binaries = ['x265']
    min_q = 5
    max_q = 51
    extension = '.x265'
    static_args = ['--preset=slow', '--frame-threads=1', '--min-keyint=256', '--keyint=256', '--no-scenecut']

    def get_encoder_args(self, input_y4m, output_y4m, q, output_encoded):
        return ['--crf', str(q), '-r', output_y4m, '--output', output_encoded, input_y4m]

    def default_qualities(self):
        return list(range(5,52,5))


class X265Realtime(X265):
    static_args = X265.static_args + ['--tune=zerolatency', '--rc-lookahead=0', '--bframes=0']

    @classmethod
    def name(cls):
        return 'x265-rt'


all_encoders = [Daala, X264, X265, X265Realtime]

def get_encoder_names():
    return [cls.name() for cls in all_encoders]

def get_all_binaries():
    """Get all paths used by encoders, so we can show them as command line options."""
    binaries = []
    for cls in all_encoders:
        for binary in cls.binaries:
            if binary not in binaries:
                binaries.append(binary)
    return binaries

def get_encoder(name, paths={}):
    """Get encoder by name."""
    for cls in all_encoders:
        if cls.name() == name:
            return cls(paths)
    raise ValueError("Unknown encoder name '{}'".format(name))
