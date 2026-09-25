# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Hooks to run when building documentation."""

import re
from pathlib import Path

import mkdocs.plugins
from mkdocs.structure.files import File


@mkdocs.plugins.event_priority(50)
def on_files(files: list, config: dict, **kwargs) -> list:
    """Link the top-level files the site shows, such as the changelog, into the docs.

    Args:
        files (list): mkdocs file list.
        config (dict): mkdocs config dictionary.
        **kwargs: Automatic MKDocs hook inputs.

    Returns:
        list: Updated mkdocs file list.
    """
    for file in Path('./resources').glob('**/*.*'):
        files.append(_new_file(file, config))
    files.append(_new_file(Path('./CHANGELOG.md'), config))
    return files


def _new_file(path: Path, config: dict, src_dir: str = '.') -> File:
    """Link a file out in the wilderness to a filename in the documentation directory hierarchy.

    Args:
        path (Path):
            Path (relative to "src_dir") to file that you want to bring into the documentation directory.
            In the documentation directory, this same path with apply (e.g., `[src_dir]/path/to/file.md` will become `[docs_dir]/path/to/file.md`)
        config (dict): mkdocs config dictionary.
        src_dir (str, optional):
            Path in which to find the file you want to bring into the docs directory. Defaults to ".".

    Returns:
        File: mkdocs object that links your file to the docs directory, ready to be added to the mkdocs file list.
    """
    return File(
        path=str(path),
        src_dir=src_dir,
        dest_dir=config['site_dir'],
        use_directory_urls=config['use_directory_urls'],
    )


#: A fenced block, indented or not — its contents are nobody's to rewrite, and
#: a ```math one is the superfences entry's in `mkdocs.yml`.
FENCED_BLOCK = re.compile(r'^[ \t]*```.*?^[ \t]*```$', re.DOTALL | re.MULTILINE)

#: GitHub's verbatim inline math, `$`…`$` — the pair the typesetter prints so
#: that GitHub's escape pass cannot reach into the span. A backtick on either
#: outer edge means a code span quoting the syntax rather than math using it,
#: which is how this page's own prose spells it.
GITHUB_INLINE_MATH = re.compile(r'(?<!`)\$`(?P<math>[^`\n]+)`\$(?!`)')


def on_page_markdown(markdown: str, **kwargs) -> str:
    """Rewrite GitHub's verbatim inline math into the `$…$` arithmatex reads.

    `math_spec.to_markdown` prints GitHub-flavoured Markdown, where inline math
    is delimited `$`…`$` so that GitHub hands the span to MathJax untouched.
    Arithmatex has no syntax for it: python-markdown's own inline code
    processor claims the backtick span first. Nothing is escaped away on the
    way in, so `$…$` carries the same math the generated page was written with.

    A fenced block is left exactly as it is — the YAML a gallery page shows
    beside each equation is not math, and a ```math one is handled by the
    superfences entry in `mkdocs.yml`, which reads it where it is indented
    inside a tab as well.

    Args:
        markdown (str): Page source, as the file holds it.
        **kwargs: Automatic MKDocs hook inputs.

    Returns:
        str: The same page with inline math arithmatex can find.
    """
    spans: list[str] = []
    kept = FENCED_BLOCK.sub(lambda m: spans.append(m[0]) or f'\x00{len(spans) - 1}\x00', markdown)
    rewritten = GITHUB_INLINE_MATH.sub(lambda m: f'${m["math"]}$', kept)
    return re.sub(r'\x00(\d+)\x00', lambda m: spans[int(m[1])], rewritten)
