// SPDX-FileCopyrightText: mathspec contributors
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

// Instant navigation swaps the document without a reload, so MathJax has to be
// told to run again. `document$` is the builder's own observable, and it emits
// on every swap as well as on the first load. Without this the equations on a
// page reached by a click reach the reader as literal text: they are in the
// DOM as `.arithmatex` spans and MathJax never sees them.
//
// The three resets before the typeset pass are what makes a second visit to a
// page render the same as the first. `typesetClear` drops the nodes MathJax is
// tracking from the outgoing page, `texReset` restarts equation numbering, and
// `clearCache` drops the font metrics measured against it.
document$.subscribe(() => {
  MathJax.startup.output.clearCache();
  MathJax.typesetClear();
  MathJax.texReset();
  MathJax.typesetPromise();
});
