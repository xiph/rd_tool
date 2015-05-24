#!/usr/bin/env python2
"""
Metric calculations
"""

from os import path
from subprocess import check_output
import subprocess
import re


def parse_total_line(line):
    r"""Parse the total line from the dump tools to a dict with "Total", "Y'", "Cb" and "Cr"

    >>> sorted(parse_total_line("Total: 8.57963   (Y': 8.23833   Cb: 8.90916   Cr: 9.85199 )\n").items())
    [('Cb', 8.90916), ('Cr', 9.85199), ('Total', 8.57963), ("Y'", 8.23833)]
    """
    match = re.match(r"^Total: (?P<Total>[\d\.]*)\s+\(Y': (?P<Y>[\d\.]*)\s+Cb: (?P<Cb>[\d\.]*)\s+Cr: (?P<Cr>[\d\.]*)\s*\)\s*$", line)
    groups = match.groupdict()
    return {
        "total": float(groups['Total']),
        "Y'": float(groups['Y']),
        "Cb": float(groups['Cb']),
        "Cr": float(groups['Cr']),
    }


class ToolMetric(object):
    """Base class for the dump_* tools in the daala repo"""
    def __init__(self, daala_root):
        self.daala_root = daala_root

    @classmethod
    def name(cls):
        return cls.__name__.lower()

    def _get_cmd(self):
        """Get the command to run, """
        tool_name = 'dump_{0}'.format(self.name())
        return [path.join(self.daala_root, 'tools', tool_name), '-s']

    def calculate(self, original_y4m, result_y4m):
        cmd = self._get_cmd() + [original_y4m, result_y4m]
        output = check_output(cmd, stderr=subprocess.STDOUT)
        total_line = next(line for line in output.splitlines() if line.startswith(b'Total:'))
        return parse_total_line(total_line)


class Psnr(ToolMetric):
    pass

class Psnrhvs(ToolMetric):
    pass

class Ssim(ToolMetric):
    pass

class Fastssim(ToolMetric):
    def _get_cmd(self):
        # dump_fastssim requires a '-c' argument to get the same output format as the others
        return super(Fastssim, self)._get_cmd() + ['-c']


all_metrics = [Psnr, Psnrhvs, Ssim, Fastssim]

def get_all_metrics(daala_root):
    return [cls(daala_root) for cls in all_metrics]
