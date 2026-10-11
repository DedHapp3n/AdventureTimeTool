import re


APP_VERSION = "1.3.4"


def parse_version(value):
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",
        str(value).strip(),
    )
    if not match:
        raise ValueError(f"invalid version: {value!r}")
    parts = tuple(int(match.group(i) or 0) for i in (1, 2, 3))
    prerelease = match.group(4)
    identifiers = [] if prerelease is None else prerelease.split(".")
    if any(
        not item or (item.isdigit() and len(item) > 1 and item.startswith("0"))
        for item in identifiers
    ):
        raise ValueError("invalid prerelease")
    return parts, identifiers


def compare_versions(left, right):
    left_parts, left_prerelease = parse_version(left)
    right_parts, right_prerelease = parse_version(right)
    if left_parts != right_parts:
        return (left_parts > right_parts) - (left_parts < right_parts)
    if not left_prerelease or not right_prerelease:
        return (not left_prerelease) - (not right_prerelease)
    for left_item, right_item in zip(left_prerelease, right_prerelease):
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            difference = (int(left_item) > int(right_item)) - (int(left_item) < int(right_item))
        elif left_numeric != right_numeric:
            difference = -1 if left_numeric else 1
        else:
            difference = (left_item > right_item) - (left_item < right_item)
        if difference:
            return difference
    return (len(left_prerelease) > len(right_prerelease)) - (
        len(left_prerelease) < len(right_prerelease)
    )
