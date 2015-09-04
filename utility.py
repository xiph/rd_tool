#!/usr/bin/env python3

from datetime import datetime

#our timestamping function, accurate to milliseconds
#(remove [:-3] to display microseconds)
def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
