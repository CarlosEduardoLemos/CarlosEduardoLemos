#!/usr/bin/env python3
"""Validate generated profile SVGs for GitHub's <img> rendering model."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'
FORBIDDEN = {'script', 'foreignObject', 'animate', 'animateTransform', 'animateMotion', 'set'}


def validate_svg(path: Path) -> None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValueError(f'{path.name}: invalid XML/SVG: {error}') from error
    if root.tag != f'{{{SVG_NS}}}svg':
        raise ValueError(f'{path.name}: root element is not SVG.')
    if not root.get('viewBox') or root.get('role') != 'img' or not root.get('aria-label'):
        raise ValueError(f'{path.name}: missing viewBox or accessible image label.')
    if root.find(f'{{{SVG_NS}}}title') is None:
        raise ValueError(f'{path.name}: missing SVG title.')

    text = path.read_text(encoding='utf-8')
    if 'data:font/woff;base64,' not in text:
        raise ValueError(f'{path.name}: embedded Inter WOFF font is missing.')
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1]
        if tag in FORBIDDEN:
            raise ValueError(f'{path.name}: unsupported or executable SVG element <{tag}>.')
        for key in ('href', '{http://www.w3.org/1999/xlink}href', 'src'):
            target = element.get(key)
            if target and not target.startswith('data:'):
                raise ValueError(f'{path.name}: external resource reference is not allowed.')
    if re.search(r'url\(\s*(?!data:)', text, flags=re.IGNORECASE):
        raise ValueError(f'{path.name}: CSS must not load external resources.')
    if '@keyframes' in text and 'prefers-reduced-motion:reduce' not in text:
        raise ValueError(f'{path.name}: animated SVG is missing prefers-reduced-motion.')


def validate_directory(directory: Path) -> list[Path]:
    files = sorted(directory.glob('*.svg'))
    if not files:
        raise ValueError(f'No SVG files found in {directory}.')
    for path in files:
        validate_svg(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'cards')
    args = parser.parse_args()
    try:
        files = validate_directory(args.directory)
    except ValueError as error:
        print(f'SVG validation failed: {error}', file=sys.stderr)
        return 1
    print(f'Validated {len(files)} self-contained SVG cards in {args.directory}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
