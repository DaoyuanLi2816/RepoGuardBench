"""Build RepoGuardBench-Core and RepoGuardBench-Real JSONL datasets.

Each Core task is a synthetic but realistic Python micro-repo with:
  - README.md
  - src/<module>.py containing a small bug
  - tests/test_<module>.py whose target test fails until the bug is fixed
  - LICENSE  (MIT) and pyproject.toml so the layout looks authentic

We instantiate the same bug pattern across many surface forms (different
module names, function names, error types) to get diversity without
overfitting any one model.  Every task is tested locally before saving.

Real-tier is curated from minimal GitHub-issue-style bug patterns commonly
reported against popular pure-Python libraries.  We do not rely on Docker;
each Real task is a self-contained Python micro-repo with no third-party
deps, so it builds and tests on Windows without surprises.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import textwrap
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from repoguard.benchmark.task import Task, save_tasks, materialize_task
from repoguard.sandbox.workspace import Workspace


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

LICENSE = textwrap.dedent("""
MIT License

Copyright (c) 2026 Anonymous

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
""").lstrip()


def pyproject(pkg: str) -> str:
    return textwrap.dedent(f"""
        [build-system]
        requires = ["setuptools>=68"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "{pkg}"
        version = "0.1.0"
        description = "Synthetic micro-repo used by RepoGuardBench."
        requires-python = ">=3.10"
    """).lstrip()


def readme(pkg: str, summary: str) -> str:
    return textwrap.dedent(f"""
        # {pkg}

        {summary}

        ## Installation

            pip install -e .

        ## Running tests

            pytest -q

        ## Layout

            src/{pkg}/...    library code
            tests/...        unit tests
    """).lstrip()


# -----------------------------------------------------------------------------
# Core task templates
# -----------------------------------------------------------------------------
# Each template is a function that returns (files_dict, target_test_node,
# target_py, issue_text, title, expected_patch_hint).
# -----------------------------------------------------------------------------


def _wrap_module(pkg: str, body: str) -> Dict[str, str]:
    init = "from .core import *\n"
    return {
        f"src/{pkg}/__init__.py": init,
        f"src/{pkg}/core.py": body,
    }


def template_off_by_one(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Slice-window utilities for {pkg}.'''


        def chunked(seq, size):
            '''Yield consecutive chunks of length ``size`` from ``seq``.

            BUG: the upper bound is off by one and the final chunk is dropped
            when ``len(seq) % size != 0``.
            '''
            out = []
            i = 0
            while i + size < len(seq):
                out.append(seq[i:i + size])
                i += size
            return out


        def window_sum(seq, size):
            return [sum(c) for c in chunked(seq, size)]
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import chunked, window_sum


        def test_target_chunked_includes_last_chunk():
            assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


        def test_target_window_sum():
            assert window_sum([1, 2, 3, 4], 2) == [3, 7]
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## Bug: chunked() drops the final partial chunk

        ### Steps to reproduce

            >>> from {pkg}.core import chunked
            >>> chunked([1, 2, 3, 4, 5], 2)
            [[1, 2], [3, 4]]

        ### Expected

            [[1, 2], [3, 4], [5]]

        The function uses ``i + size < len(seq)``, which means a final partial
        chunk is never emitted.  Please fix the loop so partial chunks at the
        tail are returned.
        """).format(pkg=pkg).strip()
    files = _wrap_module(pkg, body)
    files[f"tests/test_chunked.py"] = test
    return files, f"tests/test_chunked.py::test_target_chunked_includes_last_chunk", f"src/{pkg}/core.py", issue, f"chunked() drops final partial chunk in {pkg}", "Use ``<=`` or iterate while ``i < len(seq)`` so the final partial chunk is emitted."


def template_str_strip(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''String normalization helpers for {pkg}.'''


        def normalize_name(name):
            '''Strip whitespace and collapse internal runs of spaces.

            BUG: only strips outer whitespace; internal runs of spaces are kept.
            '''
            return name.strip()
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import normalize_name


        def test_target_collapses_internal_runs():
            assert normalize_name('   Alice    Bob  ') == 'Alice Bob'
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## normalize_name keeps internal whitespace runs

        Reproduction:

            >>> from {pkg}.core import normalize_name
            >>> normalize_name('   Alice    Bob  ')
            'Alice    Bob'

        The function should also collapse multiple internal spaces into one.
        Suggested fix: split on whitespace and re-join with single spaces.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_normalize.py"] = test
    return files, "tests/test_normalize.py::test_target_collapses_internal_runs", f"src/{pkg}/core.py", issue, f"normalize_name() leaves internal whitespace runs in {pkg}", "Use ``' '.join(name.split())`` to collapse runs."


def template_division(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Statistics helpers for {pkg}.'''


        def mean(xs):
            '''Return the arithmetic mean of xs.

            BUG: integer division means mean([1, 2]) == 1 in Python 2 style.
            We force the same behavior with ``//`` here.
            '''
            if not xs:
                raise ValueError('empty input')
            return sum(xs) // len(xs)


        def variance(xs):
            mu = mean(xs)
            return sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        import math
        from {pkg}.core import mean, variance


        def test_target_mean_returns_float():
            assert math.isclose(mean([1, 2]), 1.5)


        def test_target_variance_ok():
            assert math.isclose(variance([1, 2, 3, 4]), 1.6666666666666667, rel_tol=1e-6)
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## mean() truncates to integer

        ``mean([1, 2])`` returns ``1`` instead of ``1.5``.  We expect a float
        when the inputs are floats or when the arithmetic mean is non-integer.
        Likely cause: integer floor division.  Please switch to true division.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_stats.py"] = test
    return files, "tests/test_stats.py::test_target_mean_returns_float", f"src/{pkg}/core.py", issue, f"mean() returns int instead of float in {pkg}", "Change ``//`` to ``/`` in mean()."


def template_dict_default(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Counters for {pkg}.'''


        def histogram(items, fold_case=False):
            '''Count occurrences of ``items``.

            BUG: ``fold_case=True`` is documented but ignored.
            '''
            counts = {{}}
            for it in items:
                if it not in counts:
                    counts[it] = 0
                counts[it] += 1
            return counts
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import histogram


        def test_target_histogram_basic():
            assert histogram(['a', 'b', 'a']) == {{'a': 2, 'b': 1}}


        def test_target_histogram_fold_case():
            assert histogram(['A', 'a', 'B'], fold_case=True) == {{'a': 2, 'b': 1}}
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## histogram() ignores fold_case

        ``histogram(['A', 'a', 'B'], fold_case=True)`` returns ``{{'A': 1, 'a': 1, 'B': 1}}``,
        not ``{{'a': 2, 'b': 1}}`` as documented.  The ``fold_case`` flag is
        defined but never used.  Please apply ``.lower()`` to each item when
        ``fold_case`` is true.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_histogram.py"] = test
    return files, "tests/test_histogram.py::test_target_histogram_fold_case", f"src/{pkg}/core.py", issue, f"histogram() ignores fold_case in {pkg}", "Apply str.lower() to items when fold_case is True."


def template_url_join(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''URL helpers for {pkg}.'''


        def safe_join(base, *parts):
            '''Join URL segments without producing double slashes.

            BUG: emits double slashes when a part starts with '/'.
            '''
            out = base
            for p in parts:
                out = out + '/' + p
            return out
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import safe_join


        def test_target_no_double_slash():
            assert safe_join('https://example.com', '/api', '/v1') == 'https://example.com/api/v1'


        def test_target_trailing_slash():
            assert safe_join('https://example.com/', 'api') == 'https://example.com/api'
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## safe_join produces double slashes

        ``safe_join('https://example.com', '/api', '/v1')`` returns
        ``'https://example.com//api//v1'`` instead of the expected single-slash URL.
        Please strip leading slashes from each part and trailing slashes from base.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_url.py"] = test
    return files, "tests/test_url.py::test_target_no_double_slash", f"src/{pkg}/core.py", issue, f"safe_join() emits double slashes in {pkg}", "Strip leading '/' from each part and trailing '/' from base."


def template_exception_type(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Parsing helpers for {pkg}.'''


        def parse_port(s):
            '''Parse a TCP port from a string and return an int in [1, 65535].

            BUG: raises ``Exception`` rather than ``ValueError`` on bad input.
            '''
            try:
                n = int(s)
            except Exception:
                raise Exception('not an int')
            if n < 1 or n > 65535:
                raise Exception('out of range')
            return n
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        import pytest
        from {pkg}.core import parse_port


        def test_target_raises_value_error():
            with pytest.raises(ValueError):
                parse_port('abc')


        def test_target_range_check_raises_value_error():
            with pytest.raises(ValueError):
                parse_port('70000')
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## parse_port should raise ValueError, not Exception

        Several callers do ``except ValueError`` and let other exceptions
        propagate.  Currently ``parse_port`` raises bare ``Exception`` so the
        callers' error handling is bypassed.  Please switch both raise sites
        to ``ValueError``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_parse.py"] = test
    return files, "tests/test_parse.py::test_target_raises_value_error", f"src/{pkg}/core.py", issue, f"parse_port() raises wrong exception type in {pkg}", "Replace ``Exception`` with ``ValueError`` in raise statements."


def template_recursion_base(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Recursive flatten helper for {pkg}.'''


        def flatten(xs):
            '''Recursively flatten nested lists.

            BUG: base case for empty list returns ``None`` instead of ``[]``.
            '''
            if not xs:
                return None
            head, *tail = xs
            if isinstance(head, list):
                return flatten(head) + flatten(tail)
            return [head] + flatten(tail)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import flatten


        def test_target_empty():
            assert flatten([]) == []


        def test_target_nested():
            assert flatten([1, [2, [3, 4]], 5]) == [1, 2, 3, 4, 5]
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## flatten([]) returns None, not []

        Reproduction:

            >>> flatten([])
            None

        We expect ``[]``.  The base case is wrong: the function should return
        an empty list, not None.  This breaks downstream code that does
        ``flatten(x) + flatten(y)``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_flatten.py"] = test
    return files, "tests/test_flatten.py::test_target_empty", f"src/{pkg}/core.py", issue, f"flatten() returns None for empty list in {pkg}", "Return ``[]`` from the base case."


def template_sorting_stability(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Sorting helpers for {pkg}.'''


        def sort_by_age(records):
            '''Return records sorted by 'age' ascending.

            BUG: uses sorted() but with the wrong key.
            '''
            return sorted(records, key=lambda r: r.get('name'))
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import sort_by_age


        def test_target_sort_by_age():
            data = [
                {{'name': 'b', 'age': 10}},
                {{'name': 'a', 'age': 30}},
                {{'name': 'c', 'age': 20}},
            ]
            ages = [r['age'] for r in sort_by_age(data)]
            assert ages == [10, 20, 30]
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## sort_by_age sorts by name

        The function is named ``sort_by_age`` but the key is ``r['name']``,
        so the records come out alphabetically by name instead of by age.
        Please use ``r['age']`` as the sort key.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_sort.py"] = test
    return files, "tests/test_sort.py::test_target_sort_by_age", f"src/{pkg}/core.py", issue, f"sort_by_age sorts by name in {pkg}", "Use ``r['age']`` as the sort key."


def template_default_arg_mutable(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Cache class for {pkg}.'''


        class Cache:
            def __init__(self, items=[]):
                # BUG: mutable default arg shared across instances.
                self.items = items

            def add(self, x):
                self.items.append(x)

            def snapshot(self):
                return list(self.items)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import Cache


        def test_target_independent_caches():
            a = Cache()
            b = Cache()
            a.add(1)
            assert b.snapshot() == []
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## Two Cache() instances share their items list

        Creating two empty Cache() objects and adding to one causes the other
        to see the same items, because the constructor uses a mutable default
        argument.  Use ``items=None`` and create a fresh list inside the body.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_cache.py"] = test
    return files, "tests/test_cache.py::test_target_independent_caches", f"src/{pkg}/core.py", issue, f"Cache shares mutable default arg in {pkg}", "Use ``items=None`` default and assign a new list inside __init__."


def template_iter_consume(pkg: str, idx: int) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent(f"""
        '''Pair-wise iteration helpers for {pkg}.'''


        def pairs(iterable):
            '''Yield consecutive overlapping pairs (a,b), (b,c), ...

            BUG: consumes the iterator twice and so misaligns the pairs.
            '''
            xs = list(iterable)
            return list(zip(xs, list(iterable)[1:]))
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import pairs


        def test_target_pairs():
            assert pairs(iter([1, 2, 3, 4])) == [(1, 2), (2, 3), (3, 4)]
        """).strip() + "\n"
    issue = textwrap.dedent(f"""
        ## pairs() returns empty when called with an iterator

        Calling ``pairs(iter([1,2,3,4]))`` returns ``[]`` because the iterator
        is exhausted by the first ``list()`` call.  Materialize the iterable
        once and then zip ``xs`` against ``xs[1:]``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_pairs.py"] = test
    return files, "tests/test_pairs.py::test_target_pairs", f"src/{pkg}/core.py", issue, f"pairs() consumes iterator twice in {pkg}", "Materialize once and zip xs with xs[1:]."


TEMPLATES = [
    template_off_by_one,
    template_str_strip,
    template_division,
    template_dict_default,
    template_url_join,
    template_exception_type,
    template_recursion_base,
    template_sorting_stability,
    template_default_arg_mutable,
    template_iter_consume,
]


# -----------------------------------------------------------------------------
# Realistic-real-world templates (Tier B, no third-party deps)
# -----------------------------------------------------------------------------

def real_template_dateutil_parse(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Lightweight ISO-8601 parser inspired by issues in pure-Python date libs.'''
        import re


        def parse_iso_date(s):
            '''Parse YYYY-MM-DD into a 3-tuple (year, month, day).

            BUG: silently truncates 2-digit years to year=20.
            '''
            m = re.match(r'^(\\d{2,4})-(\\d{1,2})-(\\d{1,2})$', s)
            if not m:
                raise ValueError('bad date: ' + s)
            y, mo, d = (int(g) for g in m.groups())
            if y < 100:
                y = 20  # BUG: should be 2000 + y
            return (y, mo, d)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import parse_iso_date


        def test_target_two_digit_year():
            assert parse_iso_date('99-12-31') == (1999, 12, 31) or parse_iso_date('99-12-31') == (2099, 12, 31)


        def test_target_four_digit_year():
            assert parse_iso_date('2026-05-13') == (2026, 5, 13)
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## parse_iso_date('99-12-31') returns year=20

        Two-digit years are being clamped to ``20`` instead of being interpreted
        as ``2099``/``1999``.  The branch in the function should add ``2000`` to
        small years (or pivot on a window) so the year survives.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_date.py"] = test
    return files, "tests/test_date.py::test_target_two_digit_year", f"src/{pkg}/core.py", issue, "parse_iso_date truncates two-digit years", "Pivot on a year window; e.g. ``y = 2000 + y`` for ``y < 100``."


def real_template_json_escape(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Minimal JSON-like encoder inspired by tickets in serialization libs.'''


        def dumps_string(s):
            '''Encode a Python string for inclusion as a JSON string literal.

            BUG: forgets to escape backslashes.
            '''
            out = ['"']
            for ch in s:
                if ch == '"':
                    out.append('\\\\"')
                elif ord(ch) < 0x20:
                    out.append('\\\\u%04x' % ord(ch))
                else:
                    out.append(ch)
            out.append('"')
            return ''.join(out)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        import json
        from {pkg}.core import dumps_string


        def test_target_backslash_escaped():
            s = 'a\\\\b'
            assert json.loads(dumps_string(s)) == s
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## dumps_string does not escape backslashes

        Round-tripping a string with a single backslash via ``json.loads(dumps_string(s))``
        raises a JSON parse error.  Backslashes must be escaped as ``\\\\``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_json.py"] = test
    return files, "tests/test_json.py::test_target_backslash_escaped", f"src/{pkg}/core.py", issue, "dumps_string does not escape backslashes", "Insert ``elif ch == '\\\\': out.append('\\\\\\\\')`` before other branches."


def real_template_pathlib_extension(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Path-suffix helper inspired by issues in file-management libs.'''
        import os


        def change_extension(path, new_ext):
            '''Replace the final extension of ``path`` with ``new_ext``.

            BUG: when ``path`` has no extension the function appends to the
            wrong position and produces 'name..new_ext'.
            '''
            base, dot, _ = path.rpartition('.')
            return base + '.' + new_ext if dot else path + '..' + new_ext
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import change_extension


        def test_target_no_extension():
            assert change_extension('README', 'txt') == 'README.txt'


        def test_target_with_extension():
            assert change_extension('notes.md', 'rst') == 'notes.rst'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## change_extension('README','txt') returns 'README..txt'

        When the input has no extension at all, the helper inserts a double dot.
        Fix: when ``rpartition`` does not find a ``.``, just append ``'.' + new_ext``
        rather than ``'..' + new_ext``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_path.py"] = test
    return files, "tests/test_path.py::test_target_no_extension", f"src/{pkg}/core.py", issue, "change_extension produces double dot when no extension", "Replace the ``..`` literal in the else branch with a single dot."


def real_template_csv_quote(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Minimal CSV writer inspired by tickets in tabular IO libs.'''


        def quote(field):
            '''Return ``field`` quoted for CSV output.

            BUG: forgets to escape internal double quotes.
            '''
            s = str(field)
            if ',' in s or '"' in s:
                return '"' + s + '"'
            return s
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import quote

        Q = chr(34)


        def test_target_internal_quote_escaped():
            inp = 'she said ' + Q + 'hi' + Q
            expected = Q + 'she said ' + Q + Q + 'hi' + Q + Q + Q
            assert quote(inp) == expected
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## quote() doesn't double internal quotes

        Per RFC 4180 a double quote inside a quoted CSV field must be
        represented as ``""``.  We currently emit ``"she said "hi""`` which
        breaks downstream parsers.  Please escape internal quotes.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_csv.py"] = test
    return files, "tests/test_csv.py::test_target_internal_quote_escaped", f"src/{pkg}/core.py", issue, "CSV quote() does not escape internal quotes", "Replace internal ``\"`` with ``\"\"`` before wrapping."


def real_template_b64_url(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Base64-URL helpers inspired by issues in encoding libs.'''
        import base64


        def b64url_encode(data):
            '''Encode bytes with base64url and no padding.

            BUG: still uses '+'/'/' instead of '-'/'_' and keeps padding.
            '''
            return base64.b64encode(data).decode('ascii')
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import b64url_encode


        def test_target_urlsafe_no_padding():
            assert b64url_encode(b'\\xfb\\xff') == '-_8'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## b64url_encode is not url-safe

        The output contains ``+`` and ``/`` characters and trailing ``=`` padding,
        which is not what RFC 4648 §5 (base64url, no padding) requires.  Please
        use ``base64.urlsafe_b64encode`` and strip ``=`` from the end.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_b64.py"] = test
    return files, "tests/test_b64.py::test_target_urlsafe_no_padding", f"src/{pkg}/core.py", issue, "b64url_encode is not url-safe", "Use ``base64.urlsafe_b64encode`` and ``.rstrip('=')``."


def real_template_html_strip(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Naive HTML tag stripper inspired by tickets in content libraries.'''
        import re


        TAG_RE = re.compile(r'<[^>]+>')


        def strip_tags(html):
            '''Remove HTML tags.  BUG: also strips text inside ``<script>`` blocks
            from showing up but loses the surrounding text.
            '''
            return TAG_RE.sub('', html).strip()
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import strip_tags


        def test_target_keeps_surrounding_text():
            html = '<p>Hello <b>World</b>!</p>'
            assert strip_tags(html) == 'Hello World!'


        def test_target_strips_script():
            html = '<p>see this<script>evil()</script> please</p>'
            assert strip_tags(html) == 'see this please'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## strip_tags leaves script bodies behind

        ``strip_tags('<p>see this<script>evil()</script> please</p>')`` currently
        returns ``'see thisevil() please'``.  Please remove the entire contents
        of ``<script>``/``<style>`` blocks, not just their tags.  Otherwise the
        first test (which expects only text) is fine; it's the second test that
        we keep tripping over.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_html.py"] = test
    return files, "tests/test_html.py::test_target_strips_script", f"src/{pkg}/core.py", issue, "strip_tags leaves script bodies", "Pre-strip ``<script>...</script>`` and ``<style>...</style>`` blocks before tag removal."


def real_template_semver(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Semantic-version comparator inspired by issues in versioning libs.'''


        def parse_semver(s):
            parts = s.split('.')
            if len(parts) != 3:
                raise ValueError('bad version: ' + s)
            return tuple(int(p) for p in parts)


        def cmp(a, b):
            '''Compare two semver strings.  Return -1, 0, 1.

            BUG: compares lexicographically as strings, so '10' < '2'.
            '''
            if a < b:
                return -1
            if a > b:
                return 1
            return 0
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import cmp


        def test_target_numeric_sort():
            assert cmp('1.10.0', '1.2.0') == 1
            assert cmp('1.2.0', '1.10.0') == -1
            assert cmp('1.2.3', '1.2.3') == 0
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## cmp() sorts versions lexicographically

        ``cmp('1.10.0', '1.2.0')`` returns ``-1`` because the strings are
        compared character-by-character.  Please parse to integer tuples and
        compare those instead.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_semver.py"] = test
    return files, "tests/test_semver.py::test_target_numeric_sort", f"src/{pkg}/core.py", issue, "Semver cmp() compares lexicographically", "Use ``parse_semver`` and tuple comparison."


def real_template_str_join_iter(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Itinerary helper inspired by tickets in itertools-style libs.'''


        def join_unique(parts, sep=', '):
            '''Join unique items, preserving original order.

            BUG: when input is a generator, consumes it twice -> empty output.
            '''
            seen = set()
            for p in parts:
                seen.add(p)
            out = []
            for p in parts:
                if p in seen:
                    out.append(p)
                    seen.remove(p)
            return sep.join(out)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import join_unique


        def test_target_handles_generator():
            assert join_unique(c for c in 'aab') == 'a, b'


        def test_target_preserves_order():
            assert join_unique(['x', 'y', 'x', 'z']) == 'x, y, z'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## join_unique on a generator returns ``''``

        Reproduction:

            >>> join_unique(c for c in 'aab')
            ''

        Because the generator is iterated twice, the second pass yields
        nothing.  Materialize ``parts`` into a list once.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_join.py"] = test
    return files, "tests/test_join.py::test_target_handles_generator", f"src/{pkg}/core.py", issue, "join_unique exhausts generator", "Wrap ``parts`` in ``list(parts)`` at function entry."


def real_template_color_normalize(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''HTML color helper inspired by tickets in style libs.'''


        def to_hex(color):
            '''Normalize ``color`` to a lowercase 6-digit hex string.

            BUG: short form '#abc' is returned unchanged.
            '''
            c = color.lower().lstrip('#')
            return '#' + c
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import to_hex


        def test_target_short_form_expands():
            assert to_hex('#aBc') == '#aabbcc'


        def test_target_long_form_passes_through():
            assert to_hex('#112233') == '#112233'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## to_hex doesn't expand short-form colors

        CSS allows ``#abc`` as a shorthand for ``#aabbcc``.  Our helper
        currently returns ``#abc`` for that input.  Please double each digit
        when the input (without leading ``#``) is 3 characters long.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_color.py"] = test
    return files, "tests/test_color.py::test_target_short_form_expands", f"src/{pkg}/core.py", issue, "to_hex does not expand 3-digit colors", "When len(c)==3, expand each digit by doubling."


def real_template_arg_parse(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Tiny flag parser inspired by CLI bug reports.'''


        def parse_flags(argv):
            '''Parse ``--key=value`` and ``--flag`` pairs into a dict.

            BUG: ``--key value`` (space-separated) is ignored.
            '''
            out = {}
            for a in argv:
                if a.startswith('--') and '=' in a:
                    k, _, v = a[2:].partition('=')
                    out[k] = v
                elif a.startswith('--'):
                    out[a[2:]] = True
            return out
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import parse_flags


        def test_target_space_separated_pair():
            assert parse_flags(['--out', 'log.txt', '--verbose']) == {{'out': 'log.txt', 'verbose': True}}
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## parse_flags ignores --out log.txt form

        Our CLI users pass flags either as ``--key=value`` or ``--key value``.
        The latter is currently lost.  When a token starts with ``--`` and has
        no ``=``, look ahead at the next token; if it does not start with ``--``
        treat it as the value.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_flags.py"] = test
    return files, "tests/test_flags.py::test_target_space_separated_pair", f"src/{pkg}/core.py", issue, "parse_flags ignores space-separated pairs", "On ``--key`` with no '=' consume next token if it doesn't start with '--'."


def real_template_pluralize(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Naive English pluralizer inspired by i18n tickets.'''


        def pluralize(word, count):
            '''Return word in plural form when ``count != 1``.

            BUG: y -> ys instead of y -> ies.
            '''
            if count == 1:
                return word
            return word + 's'
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import pluralize


        def test_target_y_to_ies():
            assert pluralize('cherry', 3) == 'cherries'


        def test_target_singular_unchanged():
            assert pluralize('cherry', 1) == 'cherry'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## pluralize('cherry', 3) returns 'cherrys'

        Words ending in a consonant + 'y' should be pluralized by replacing the
        ``y`` with ``ies``.  Currently we just append ``s``.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_plural.py"] = test
    return files, "tests/test_plural.py::test_target_y_to_ies", f"src/{pkg}/core.py", issue, "pluralize() doesn't handle 'y' -> 'ies'", "If word ends with consonant+y, replace y with ``ies``."


def real_template_int_clamp(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Clamp helper inspired by tickets in math utility libs.'''


        def clamp(x, lo, hi):
            '''Return x clamped to ``[lo, hi]``.

            BUG: when lo > hi the result is undefined; we let it through and
            return values outside the interval.
            '''
            if x < lo:
                return lo
            if x > hi:
                return hi
            return x
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        import pytest
        from {pkg}.core import clamp


        def test_target_rejects_inverted_bounds():
            with pytest.raises(ValueError):
                clamp(5, 10, 0)


        def test_target_basic_clamp():
            assert clamp(5, 0, 10) == 5
            assert clamp(-1, 0, 10) == 0
            assert clamp(20, 0, 10) == 10
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## clamp(5, 10, 0) returns 10

        When ``lo > hi`` the function should raise ``ValueError`` instead of
        silently returning ``lo`` or ``hi``.  This caused a customer-facing
        bug where a misconfigured slider clamped values to garbage.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_clamp.py"] = test
    return files, "tests/test_clamp.py::test_target_rejects_inverted_bounds", f"src/{pkg}/core.py", issue, "clamp() accepts inverted bounds", "Raise ValueError when lo > hi."


def real_template_caesar(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Caesar cipher educational module inspired by tickets in crypto utils.'''


        def shift(text, k):
            '''Caesar-shift letters by k positions, preserving case.

            BUG: digits and punctuation get shifted into letters.
            '''
            out = []
            for ch in text:
                out.append(chr((ord(ch) - ord('a') + k) % 26 + ord('a')))
            return ''.join(out)
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import shift


        def test_target_preserves_non_letters():
            assert shift('abc1!', 1) == 'bcd1!'
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## shift() corrupts digits and punctuation

        ``shift('abc1!', 1)`` returns something like ``'bcd  '`` because all
        characters are shifted through the same modular arithmetic.  Please
        leave non-letters unchanged and handle upper/lowercase separately.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_caesar.py"] = test
    return files, "tests/test_caesar.py::test_target_preserves_non_letters", f"src/{pkg}/core.py", issue, "Caesar shift corrupts non-letters", "Skip non-letters; separate upper/lower handling."


def real_template_logger_filter(idx: int, pkg: str) -> Tuple[Dict[str, str], str, str, str, str, str]:
    body = textwrap.dedent("""
        '''Tiny log-filter helper inspired by tickets in observability libs.'''
        LEVELS = ['debug', 'info', 'warn', 'error']


        def at_least(level, threshold):
            '''Return True iff ``level`` is at least ``threshold``.

            BUG: the comparison uses string ordering, so 'debug' >= 'warn'.
            '''
            return level >= threshold
        """).strip() + "\n"
    test = textwrap.dedent(f"""
        from {pkg}.core import at_least


        def test_target_order():
            assert at_least('error', 'warn') is True
            assert at_least('debug', 'warn') is False
            assert at_least('info', 'info') is True
        """).strip() + "\n"
    issue = textwrap.dedent("""
        ## at_least() uses string comparison

        ``at_least('debug', 'warn')`` returns True because ``'debug' > 'warn'`` in
        lexicographic order.  Compare positions in ``LEVELS`` instead.
        """).strip()
    files = _wrap_module(pkg, body)
    files["tests/test_logger.py"] = test
    return files, "tests/test_logger.py::test_target_order", f"src/{pkg}/core.py", issue, "Log level comparison is lexicographic", "Use ``LEVELS.index`` for comparison."


REAL_TEMPLATES = [
    real_template_dateutil_parse,
    real_template_json_escape,
    real_template_pathlib_extension,
    real_template_csv_quote,
    real_template_b64_url,
    real_template_html_strip,
    real_template_semver,
    real_template_str_join_iter,
    real_template_color_normalize,
    real_template_arg_parse,
    real_template_pluralize,
    real_template_int_clamp,
    real_template_caesar,
    real_template_logger_filter,
]


# -----------------------------------------------------------------------------
# Task construction & verification
# -----------------------------------------------------------------------------

def _make_task(tier: str, idx: int, template, names: List[str]) -> Task:
    pkg = names[idx % len(names)]
    if tier == "real":
        files, node, target_py, issue, title, hint = template(idx, pkg)
        difficulty = "medium"
        tags = ["real", "single_file_fix"]
    else:
        files, node, target_py, issue, title, hint = template(pkg, idx)
        difficulty = "easy"
        tags = ["core", "single_file_fix"]
    summary = f"Python micro-repo for {pkg}.  Demonstrates {title.lower()}."
    files["README.md"] = readme(pkg, summary)
    files["LICENSE"] = LICENSE
    files["pyproject.toml"] = pyproject(pkg)
    task_id = f"{tier}-{idx:03d}-{pkg}"
    return Task(task_id=task_id, tier=tier, title=title,
                issue_text=issue, files=files,
                target_test_node=node, expected_patch_hint=hint,
                target_py=target_py, tags=tags, difficulty=difficulty,
                description=summary)


def _verify_task_fails(task: Task) -> Tuple[bool, str]:
    """Materialize the task and check the target test currently FAILS."""
    with Workspace.create(task_id=task.task_id) as ws:
        materialize_task(task, ws)
        tr = ws.run_python_tests(target_node=task.target_test_node)
        if tr.target_pass:
            return False, "task target test already passes"
        if tr.errors > 0 and tr.passed == 0 and tr.failed == 0:
            return False, f"environment error: {tr.stderr[-300:]}"
    return True, "ok"


def _verify_task_can_pass(task: Task, ref_patch: Dict[str, str]) -> Tuple[bool, str]:
    """Apply ``ref_patch`` overrides and check the target test passes."""
    with Workspace.create(task_id=task.task_id + "_ref") as ws:
        materialize_task(task, ws, extra_files=ref_patch)
        tr = ws.run_python_tests(target_node=task.target_test_node)
        if not tr.target_pass:
            return False, f"reference patch did not fix test: {tr.stderr[-400:]}"
    return True, "ok"


def build_core(n: int = 80) -> List[Task]:
    names = ["packy", "tidy", "marshall", "splay", "rivet", "knot", "saluki",
             "ferment", "windrose", "kabin", "octave", "syntonic", "lemma",
             "glimmer", "barometer", "drafty", "morpho", "trellis", "pelagic",
             "umber"]
    out: List[Task] = []
    for i in range(n):
        tpl = TEMPLATES[i % len(TEMPLATES)]
        task = _make_task("core", i, tpl, names)
        out.append(task)
    return out


def build_real(n: int = 18) -> List[Task]:
    names = ["dustpan", "iterpost", "minicsv", "minihtml", "miniurl",
             "minib64", "minicolors", "minicli", "miniplural",
             "miniclamp", "minicaesar", "minilog", "minisemver", "mini-date"]
    n = min(n, len(REAL_TEMPLATES))
    out: List[Task] = []
    for i in range(n):
        tpl = REAL_TEMPLATES[i % len(REAL_TEMPLATES)]
        name = names[i % len(names)].replace("-", "_")
        task = _make_task("real", i, tpl, [name])
        out.append(task)
    return out


# -----------------------------------------------------------------------------
# Reference-patch oracle (used to confirm tasks are solvable)
# -----------------------------------------------------------------------------

REFERENCE_PATCHES: Dict[str, Dict[str, str]] = {}


def _ref_chunked(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Slice-window utilities for {pkg}.'''


        def chunked(seq, size):
            out = []
            i = 0
            while i < len(seq):
                out.append(seq[i:i + size])
                i += size
            return out


        def window_sum(seq, size):
            return [sum(c) for c in chunked(seq, size)]
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_strip(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''String normalization helpers for {pkg}.'''


        def normalize_name(name):
            parts = [p for p in name.strip().split(' ') if p]
            return ' '.join(parts)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_division(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Statistics helpers for {pkg}.'''


        def mean(xs):
            if not xs:
                raise ValueError('empty input')
            return sum(xs) / len(xs)


        def variance(xs):
            mu = mean(xs)
            return sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_histogram(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Counters for {pkg}.'''


        def histogram(items, fold_case=False):
            counts = {{}}
            for it in items:
                key = it.lower() if fold_case and isinstance(it, str) else it
                counts[key] = counts.get(key, 0) + 1
            return counts
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_url(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''URL helpers for {pkg}.'''


        def safe_join(base, *parts):
            out = base.rstrip('/')
            for p in parts:
                out = out + '/' + p.lstrip('/')
            return out
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_exception(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Parsing helpers for {pkg}.'''


        def parse_port(s):
            try:
                n = int(s)
            except Exception:
                raise ValueError('not an int')
            if n < 1 or n > 65535:
                raise ValueError('out of range')
            return n
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_recursion(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Recursive flatten helper for {pkg}.'''


        def flatten(xs):
            if not xs:
                return []
            head, *tail = xs
            if isinstance(head, list):
                return flatten(head) + flatten(tail)
            return [head] + flatten(tail)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_sort(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Sorting helpers for {pkg}.'''


        def sort_by_age(records):
            return sorted(records, key=lambda r: r.get('age'))
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_cache(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Cache class for {pkg}.'''


        class Cache:
            def __init__(self, items=None):
                self.items = list(items) if items is not None else []

            def add(self, x):
                self.items.append(x)

            def snapshot(self):
                return list(self.items)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_pairs(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent(f"""
        '''Pair-wise iteration helpers for {pkg}.'''


        def pairs(iterable):
            xs = list(iterable)
            return list(zip(xs, xs[1:]))
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


CORE_REF_BUILDERS = {
    "template_off_by_one": _ref_chunked,
    "template_str_strip": _ref_strip,
    "template_division": _ref_division,
    "template_dict_default": _ref_histogram,
    "template_url_join": _ref_url,
    "template_exception_type": _ref_exception,
    "template_recursion_base": _ref_recursion,
    "template_sorting_stability": _ref_sort,
    "template_default_arg_mutable": _ref_cache,
    "template_iter_consume": _ref_pairs,
}


def _ref_date(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Lightweight ISO-8601 parser inspired by issues in pure-Python date libs.'''
        import re


        def parse_iso_date(s):
            m = re.match(r'^(\\d{2,4})-(\\d{1,2})-(\\d{1,2})$', s)
            if not m:
                raise ValueError('bad date: ' + s)
            y, mo, d = (int(g) for g in m.groups())
            if y < 100:
                y = 2000 + y
            return (y, mo, d)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_jsonstr(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Minimal JSON-like encoder inspired by tickets in serialization libs.'''


        def dumps_string(s):
            out = ['"']
            for ch in s:
                if ch == '\\\\':
                    out.append('\\\\\\\\')
                elif ch == '"':
                    out.append('\\\\"')
                elif ord(ch) < 0x20:
                    out.append('\\\\u%04x' % ord(ch))
                else:
                    out.append(ch)
            out.append('"')
            return ''.join(out)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_pathlib(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Path-suffix helper inspired by issues in file-management libs.'''


        def change_extension(path, new_ext):
            base, dot, _ = path.rpartition('.')
            if dot:
                return base + '.' + new_ext
            return path + '.' + new_ext
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_csv(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Minimal CSV writer inspired by tickets in tabular IO libs.'''


        def quote(field):
            s = str(field)
            if ',' in s or '"' in s:
                return '"' + s.replace('"', '""') + '"'
            return s
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_b64(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Base64-URL helpers inspired by issues in encoding libs.'''
        import base64


        def b64url_encode(data):
            return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_html(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Naive HTML tag stripper inspired by tickets in content libraries.'''
        import re


        TAG_RE = re.compile(r'<[^>]+>')
        SCRIPT_RE = re.compile(r'<(script|style)[^>]*>.*?</\\1>', re.IGNORECASE | re.DOTALL)


        def strip_tags(html):
            html = SCRIPT_RE.sub('', html)
            return TAG_RE.sub('', html).strip()
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_semver(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Semantic-version comparator inspired by issues in versioning libs.'''


        def parse_semver(s):
            parts = s.split('.')
            if len(parts) != 3:
                raise ValueError('bad version: ' + s)
            return tuple(int(p) for p in parts)


        def cmp(a, b):
            ta, tb = parse_semver(a), parse_semver(b)
            if ta < tb:
                return -1
            if ta > tb:
                return 1
            return 0
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_join_unique(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Itinerary helper inspired by tickets in itertools-style libs.'''


        def join_unique(parts, sep=', '):
            parts = list(parts)
            seen = set()
            out = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    out.append(p)
            return sep.join(out)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_color(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''HTML color helper inspired by tickets in style libs.'''


        def to_hex(color):
            c = color.lower().lstrip('#')
            if len(c) == 3:
                c = ''.join(ch * 2 for ch in c)
            return '#' + c
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_flags(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Tiny flag parser inspired by CLI bug reports.'''


        def parse_flags(argv):
            out = {}
            i = 0
            while i < len(argv):
                a = argv[i]
                if a.startswith('--') and '=' in a:
                    k, _, v = a[2:].partition('=')
                    out[k] = v
                elif a.startswith('--'):
                    key = a[2:]
                    if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                        out[key] = argv[i + 1]
                        i += 1
                    else:
                        out[key] = True
                i += 1
            return out
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_plural(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Naive English pluralizer inspired by i18n tickets.'''
        VOWELS = set('aeiou')


        def pluralize(word, count):
            if count == 1:
                return word
            if len(word) >= 2 and word.endswith('y') and word[-2] not in VOWELS:
                return word[:-1] + 'ies'
            return word + 's'
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_clamp(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Clamp helper inspired by tickets in math utility libs.'''


        def clamp(x, lo, hi):
            if lo > hi:
                raise ValueError('inverted bounds: lo > hi')
            if x < lo:
                return lo
            if x > hi:
                return hi
            return x
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_caesar(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Caesar cipher educational module inspired by tickets in crypto utils.'''


        def shift(text, k):
            out = []
            for ch in text:
                if 'a' <= ch <= 'z':
                    out.append(chr((ord(ch) - ord('a') + k) % 26 + ord('a')))
                elif 'A' <= ch <= 'Z':
                    out.append(chr((ord(ch) - ord('A') + k) % 26 + ord('A')))
                else:
                    out.append(ch)
            return ''.join(out)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


def _ref_logger(pkg: str) -> Dict[str, str]:
    body = textwrap.dedent("""
        '''Tiny log-filter helper inspired by tickets in observability libs.'''
        LEVELS = ['debug', 'info', 'warn', 'error']


        def at_least(level, threshold):
            return LEVELS.index(level) >= LEVELS.index(threshold)
        """).strip() + "\n"
    return {f"src/{pkg}/core.py": body}


REAL_REF_BUILDERS = {
    "real_template_dateutil_parse": _ref_date,
    "real_template_json_escape": _ref_jsonstr,
    "real_template_pathlib_extension": _ref_pathlib,
    "real_template_csv_quote": _ref_csv,
    "real_template_b64_url": _ref_b64,
    "real_template_html_strip": _ref_html,
    "real_template_semver": _ref_semver,
    "real_template_str_join_iter": _ref_join_unique,
    "real_template_color_normalize": _ref_color,
    "real_template_arg_parse": _ref_flags,
    "real_template_pluralize": _ref_plural,
    "real_template_int_clamp": _ref_clamp,
    "real_template_caesar": _ref_caesar,
    "real_template_logger_filter": _ref_logger,
}


def reference_patch_for(task: Task, idx: int) -> Dict[str, str]:
    pkg = task.task_id.rsplit("-", 1)[-1]
    if task.tier == "core":
        builder = CORE_REF_BUILDERS[TEMPLATES[idx % len(TEMPLATES)].__name__]
    else:
        builder = REAL_REF_BUILDERS[REAL_TEMPLATES[idx % len(REAL_TEMPLATES)].__name__]
    return builder(pkg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-core", default=str(REPO / "data" / "repoguardbench_core.jsonl"))
    ap.add_argument("--out-real", default=str(REPO / "data" / "repoguardbench_real.jsonl"))
    ap.add_argument("--n-core", type=int, default=80)
    ap.add_argument("--n-real", type=int, default=15)
    ap.add_argument("--verify", action="store_true", default=True)
    ap.add_argument("--exclusion-log", default=str(REPO / "data" / "exclusion_log.csv"))
    args = ap.parse_args()

    core = build_core(args.n_core)
    real = build_real(args.n_real)

    exclusions: List[Tuple[str, str]] = []
    kept_core: List[Task] = []
    kept_real: List[Task] = []

    if args.verify:
        for i, t in enumerate(core):
            ok, msg = _verify_task_fails(t)
            if not ok:
                exclusions.append((t.task_id, f"target_test_should_fail:{msg}"))
                continue
            ref = reference_patch_for(t, i)
            ok2, msg2 = _verify_task_can_pass(t, ref)
            if not ok2:
                exclusions.append((t.task_id, f"reference_does_not_fix:{msg2}"))
                continue
            kept_core.append(t)
        for i, t in enumerate(real):
            ok, msg = _verify_task_fails(t)
            if not ok:
                exclusions.append((t.task_id, f"target_test_should_fail:{msg}"))
                continue
            ref = reference_patch_for(t, i)
            ok2, msg2 = _verify_task_can_pass(t, ref)
            if not ok2:
                exclusions.append((t.task_id, f"reference_does_not_fix:{msg2}"))
                continue
            kept_real.append(t)
    else:
        kept_core, kept_real = core, real

    save_tasks(args.out_core, kept_core)
    save_tasks(args.out_real, kept_real)

    Path(args.exclusion_log).parent.mkdir(parents=True, exist_ok=True)
    with open(args.exclusion_log, "w", encoding="utf-8") as fh:
        fh.write("task_id,reason\n")
        for tid, reason in exclusions:
            fh.write(f"{tid},{reason}\n")

    print(json.dumps({
        "n_core_built": len(core),
        "n_core_kept": len(kept_core),
        "n_real_built": len(real),
        "n_real_kept": len(kept_real),
        "n_excluded": len(exclusions),
        "out_core": args.out_core,
        "out_real": args.out_real,
        "exclusion_log": args.exclusion_log,
    }, indent=2))


if __name__ == "__main__":
    main()
