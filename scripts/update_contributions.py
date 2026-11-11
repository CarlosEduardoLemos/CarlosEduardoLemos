#!/usr/bin/env python3
"""Refresh the official GitHub contribution snapshot, retaining a valid cache on failure."""
from __future__ import annotations

import sys

try:
    from .render_cards import ContributionError, fetch_contributions, load_data
except ImportError:  # Direct script execution inside GitHub Actions.
    from render_cards import ContributionError, fetch_contributions, load_data


def main() -> int:
    try:
        snapshot = fetch_contributions()
    except ContributionError as error:
        print(f'::warning::{error}', file=sys.stderr)
        try:
            snapshot = load_data(strict=True)
        except ContributionError as cache_error:
            print(f'::error::{cache_error}', file=sys.stderr)
            return 1
        print(f'Using the last valid snapshot from {snapshot["updated_at"]}.')
        return 0
    print(f'Fetched {len(snapshot["days"])} days, total={snapshot["total"]}, updated_at={snapshot["updated_at"]}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
