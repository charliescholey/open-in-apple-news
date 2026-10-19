"""Print the Chrome extension ID derived from the "key" in manifest.json.

Chrome's ID is the first 32 hex digits of SHA-256(public key DER), with
digits 0-f mapped to letters a-p.
Usage: extension_id.py path/to/manifest.json
"""
import base64
import hashlib
import json
import sys


def extension_id(public_key_b64):
    digest = hashlib.sha256(base64.b64decode(public_key_b64)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        print(extension_id(json.load(f)["key"]))
