// SPDX-FileCopyrightText: math-spec contributors
//
// SPDX-License-Identifier: MIT

// `pymdownx.arithmatex` in `generic: true` mode rewrites `$...$` / `$$...$$`
// into `\(...\)` / `\[...\]` before MathJax ever sees the page, so the escaped
// delimiters are the ones that matter. The dollar forms are enabled too: the
// typeset output this site quotes is written with them, and a block pasted out
// of `to_markdown` should render the same here as it does on GitHub.
//
// There is deliberately no `ignoreHtmlClass`. MathJax's default `skipHtmlTags`
// already covers `pre` and `code`, so a `$` inside a fenced block or an inline
// span is never scanned and the delimiters only ever meet prose — which is
// what a class guard would have been protecting, at the cost of subtrees it
// then refuses to descend into.
window.MathJax = {
  tex: {
    inlineMath: [
      ["\\(", "\\)"],
      ["$", "$"],
    ],
    displayMath: [
      ["\\[", "\\]"],
      ["$$", "$$"],
    ],
    processEscapes: true,
    processEnvironments: true,
  },
};
