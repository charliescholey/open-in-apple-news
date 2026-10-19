"""Talk to the installed helper exactly the way Chrome does (framed JSON over stdio).
Usage: ask_helper.py '{"action": "open", "url": "https://..."}'
       ask_helper.py --urls urls.txt      # one URL per line, prints one JSON result per line
"""
import json
import os
import struct
import subprocess
import sys

HOST = os.path.expanduser("~/Library/Application Support/OpenInAppleNews/host")


def ask(message):
    data = json.dumps(message).encode("utf-8")
    out = subprocess.run([HOST], input=struct.pack("<I", len(data)) + data,
                         capture_output=True, timeout=60).stdout
    (length,) = struct.unpack("<I", out[:4])
    return json.loads(out[4:4 + length])


if __name__ == "__main__":
    if sys.argv[1] == "--urls":
        with open(sys.argv[2]) as f:
            for url in filter(None, (line.strip() for line in f)):
                print(json.dumps({"url": url, **ask({"action": "open", "url": url})}), flush=True)
    else:
        print(json.dumps(ask(json.loads(sys.argv[1])), indent=1))
