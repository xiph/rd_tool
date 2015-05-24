#!/usr/bin/env python2
"""
Information on how to call each encoder
"""

from os import path
import os
from subprocess import check_call, check_output
import subprocess

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
    min_q = None
    max_q = None

    def __init__(self, daala_root):
        self.daala_root = daala_root

    @classmethod
    def name(cls):
        return cls.__name__.lower()

    def encode_and_dump(self, input_y4m, output_y4m, q, extra_options=[]):
        """Encode a raw file and dump the result to a raw file again.
        Returns a tuple with the path to the encoded intermediate file, and the command line used to run the encoder."""
        raise NotImplementedError()

    def get_version(self):
        """Get a version string"""
        raise NotImplementedError()

    def default_qualities(self):
        """List of quality parameters to use by default"""
        raise NotImplementedError()


class Daala(Encoder):
    min_q = 1
    max_q = 511

    def _encoder_path(self):
        """Path to encoder_example binary"""
        return self.daala_root + '/examples/encoder_example'

    def encode_and_dump(self, input_y4m, output_y4m, q, extra_options=[]):
        encoder_example = self._encoder_path()
        output_encoded = output_y4m + '.ogv'
        basename = path.basename(output_y4m)
        env = {
            'OD_LOG_MODULES': 'encoder:10',
            'OD_DUMP_IMAGES_SUFFIX': basename,
        }
        with open(basename + '-enc.out', 'wb') as enc_log:
            encode_cmd = [encoder_example, '--keyframe-rate=256', '--video-quality', str(q), '--output', output_encoded, input_y4m] + extra_options
            check_call(
                encode_cmd,
                env=env,
                stderr=enc_log
            )
        try:
            dumped_file = '00000000out-' + basename + '.y4m'
            os.rename(dumped_file, output_y4m)
        except OSError as e:
            raise RuntimeError("Could not find {0}, is daala configured with --enable-dump-recons?".format(dumped_file), e)
        _remove_file_if_exists(basename + '-enc.out')
        return output_encoded, encode_cmd

    def get_version(self):
        encoder_example = self._encoder_path()
        return check_output([encoder_example, '--version'], stderr=subprocess.STDOUT).decode().strip()

    def default_qualities(self):
        # 256, 128, 64, 32 will probably be hit by the binary search, but start
        # them at once to improve utilization.
        warmup = _predict_binary_search(self.min_q, self.max_q, 4)
        # Add some extremes on each end
        return warmup + [5, 8, 400]


all_encoders = [Daala]

def get_encoder_names():
    return [cls.name() for cls in all_encoders]

def get_encoder(name, daala_root=None):
    """Get encoder by name."""
    if name == 'daala':
        return Daala(daala_root)
    raise ValueError("Unknown encoder name '{}'".format(name))
