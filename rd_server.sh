#!/bin/bash
set -e
cargo build
cp target/debug/librs_rd_tool.so rs_rd_tool.so
./rd_server.py "$@"
