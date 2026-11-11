#!/usr/bin/env python3
"""Fail unless the stored contribution data is a complete validated GraphQL snapshot."""
from __future__ import annotations

import sys

try:
    from .render_cards import ContributionError, load_data
except ImportError:  # Direct script execution inside GitHub Actions.
    from render_cards import ContributionError, load_data


def main() -> int:
    try:
        data = load_data(strict=True)
    except ContributionError as error:
        print(f'Invalid contribution snapshot: {error}', file=sys.stderr)
        return 1
    print(f'Validated {len(data["days"])} GitHub contribution days; total={data["total"]}; updated_at={data["updated_at"]}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
