#!/usr/bin/env python
##########################
# config
##########################
import re

PORT = 8080
HOST = "0.0.0.0"

##########################
# parsing
##########################
LINE = re.compile(r"^(\w+)=(.*)$")

def parse(text):
    kv = {}
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if m:
            kv[m.group(1)] = m.group(2)
    return kv

##########################
# entry
##########################
def run(path):
    return parse(open(path).read())
