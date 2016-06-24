rd_tool
=======

rd_tool.py is a script for running Daala RD collection across a series of either local or Amazon AWS nodes.

Using AWS nodes
===============

You will need a ~/.aws configuration for boto with your AWS information and credentials.

Specify the autoscaling groukp to use with -awsgroup.

Using local nodes
=================

You can specify all of the machines you want to use in a JSON file:

```json
[
  {
    "host": "localhost",
    "user": "thomas",
    "cores": 4
  },
  {
    ...
  }
]
    
```

Specify this configuration on the command line with --machineconf.

Dependencies
============

You will need Python 3.4 or later, as well as [boto3](https://github.com/boto/boto3).
