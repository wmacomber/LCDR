#!/usr/bin/env python3
"""
wordcounter.py — simple demo tool for command steps.

Usage:
  python wordcounter.py "some text here"
"""

import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python wordcounter.py \"some text here\"", file=sys.stderr)
        sys.exit(1)

    text = sys.argv[1].strip()
    if not text:
        print("0")
        return

    # Basic whitespace split
    count = len(text.split())
    print(count)

if __name__ == "__main__":
    main()
