#!/usr/bin/env python3
import sys
import re


def parse_tap(lines):
    total = 0
    passed = 0
    failed = 0
    details = []

    for line in lines:
        line = line.strip()
        # Match a passing test line
        if re.match(r"^ok\b", line):
            passed += 1
            total += 1
            details.append(f"- ✅ {line}")
        # Match a failing test line
        elif re.match(r"^not ok\b", line):
            failed += 1
            total += 1
            details.append(f"- ❌ {line}")
    return total, passed, failed, details


def main():
    if len(sys.argv) < 2:
        print("Usage: tap2md.py <tap_output_file>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        lines = f.readlines()

    total, passed, failed, details = parse_tap(lines)

    md = []
    md.append("# Test Results")
    md.append("")
    md.append(f"**Total tests:** {total}")
    md.append(f"**Passed:** {passed}")
    md.append(f"**Failed:** {failed}")
    md.append("")
    md.append("## Test Details")
    md.append("")
    md.extend(details)

    print("\n".join(md))


if __name__ == '__main__':
    main()
