#!/usr/bin/env python3

import rs_rd_tool

get_time = rs_rd_tool.utility.get_time

def rd_print(log, *args, **kwargs):
    print(get_time(), *args, flush=True, **kwargs)
    if log:
        try:
            print(get_time(), file=log, flush=True, *args, **kwargs)
        except:
            pass
