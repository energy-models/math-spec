<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Changelog

Written by [release-please](https://github.com/googleapis/release-please) from
the conventional-commit subjects that land on `main` — see RELEASING.md. Do not
edit it by hand; the next release overwrites what you wrote.

New releases are inserted directly below this paragraph, so nothing may sit
between it and the first `##` heading. The Keep a Changelog skeleton that used
to live here — a hand-maintained `## Unreleased` block, and a comment
documenting the heading format — is what broke 0.0.0-alpha.1: that comment
contained a literal `## [X.Y.Z]` heading, release-please inserts above the first
`##` it finds, and so the entire release landed inside the comment and rendered
nowhere.

## [0.0.0-alpha.6](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.5...v0.0.0-alpha.6) (2026-08-23)


### Documentation

* an Examples section, each model beside the math it prints ([#38](https://github.com/energy-models/math-spec/issues/38)) ([66bfae4](https://github.com/energy-models/math-spec/commit/66bfae482a0ae9b1010b02d26e5316cf72da17dd))

## [0.0.0-alpha.5](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.4...v0.0.0-alpha.5) (2026-08-22)


### Bug Fixes

* to_markdown printed TeX's em-dash ligature, not an em dash ([#34](https://github.com/energy-models/math-spec/issues/34)) ([226407a](https://github.com/energy-models/math-spec/commit/226407a9e0e08575041b32d388288ee456d231d3))

## [0.0.0-alpha.4](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.3...v0.0.0-alpha.4) (2026-08-21)


### Refactoring

* extract the language and typeset from lpspec ([#17](https://github.com/energy-models/math-spec/issues/17)) ([b997193](https://github.com/energy-models/math-spec/commit/b9971930a95a9b6c80938aaff0224d4a0f2e4ff3))

## [0.0.0-alpha.3](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.2...v0.0.0-alpha.3) (2026-08-21)


### Bug Fixes

* stop prettier rewriting what release-please generates ([#27](https://github.com/energy-models/math-spec/issues/27)) ([7486555](https://github.com/energy-models/math-spec/commit/7486555f199f105d1cb6d29a141bbbd3cfedead2))

## [0.0.0-alpha.2](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.1...v0.0.0-alpha.2) (2026-08-21)


### Bug Fixes

* the release notes landed inside an HTML comment ([#25](https://github.com/energy-models/math-spec/issues/25)) ([c33dc24](https://github.com/energy-models/math-spec/commit/c33dc241e12446f2433d600c7afc109063cd3656))

## [0.0.0-alpha.1](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.0...v0.0.0-alpha.1) (2026-08-21)

### Bug Fixes

- stop the release build silently shipping a 0.0.0 wheel ([#23](https://github.com/energy-models/math-spec/issues/23)) ([a801b00](https://github.com/energy-models/math-spec/commit/a801b00061d306661d31b455ed2980fd0dfbeda9))
