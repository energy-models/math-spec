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

## [0.0.0-alpha.23](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.22...v0.0.0-alpha.23) (2026-08-26)


### Bug Fixes

* **docs:** the homepage feature cards render as cards rather than as loose rules and paragraphs ([#145](https://github.com/energy-models/math-spec/issues/145)) ([b88e5dc](https://github.com/energy-models/math-spec/commit/b88e5dc8883f0bc6bc0f5809c688139055715f57))

## [0.0.0-alpha.22](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.21...v0.0.0-alpha.22) (2026-08-26)


### Features

* a piecewise method answers which curvature it is exact for ([#135](https://github.com/energy-models/math-spec/issues/135)) ([6f0fff1](https://github.com/energy-models/math-spec/commit/6f0fff1bc29fe0a958999579b08a5d0ca4a42848))

## [0.0.0-alpha.21](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.20...v0.0.0-alpha.21) (2026-08-26)


### Documentation

* **language:** the absence page is half the length and shows each rule on a model ([#127](https://github.com/energy-models/math-spec/issues/127)) ([147788a](https://github.com/energy-models/math-spec/commit/147788af0d8f912ed3442e56392b3ef3e994a7ed))

## [0.0.0-alpha.20](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.19...v0.0.0-alpha.20) (2026-08-26)


### Documentation

* the language knows nothing about sinks ([#118](https://github.com/energy-models/math-spec/issues/118)) ([886a854](https://github.com/energy-models/math-spec/commit/886a85458a977706ee773f53d8dd75cfbbd7e125))

## [0.0.0-alpha.19](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.18...v0.0.0-alpha.19) (2026-08-26)


### Bug Fixes

* **typeset:** a string value in a where clause prints as a quoted label ([#114](https://github.com/energy-models/math-spec/issues/114)) ([9be22c1](https://github.com/energy-models/math-spec/commit/9be22c1f979c8d887e91cef302b2b63570fcbae0))

## [0.0.0-alpha.18](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.17...v0.0.0-alpha.18) (2026-08-26)


### Refactoring

* **parser:** one number rule, one amount table, and a namespace nothing builds by hand ([#106](https://github.com/energy-models/math-spec/issues/106)) ([f775a07](https://github.com/energy-models/math-spec/commit/f775a07cf8f5159dd8df973f995b8dad87fd01ef))
* **schema:** one wording for an undeclared dimension, and the front door validates once ([#105](https://github.com/energy-models/math-spec/issues/105)) ([69e42db](https://github.com/energy-models/math-spec/commit/69e42db6f453b9caff349ddf109ee77aed3617fa))
* the stack's own additions say less and repeat nothing ([#102](https://github.com/energy-models/math-spec/issues/102)) ([119e588](https://github.com/energy-models/math-spec/commit/119e5884a576264c38c8455c625908ee09d057c9))
* **typeset:** Markdown is LaTeX's math with its own document layer, and a step merges itself ([#107](https://github.com/energy-models/math-spec/issues/107)) ([1ca9178](https://github.com/energy-models/math-spec/commit/1ca9178b82f629bd39170e884b82265c7935b8de))

## [0.0.0-alpha.17](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.16...v0.0.0-alpha.17) (2026-08-25)


### Bug Fixes

* **language:** a link takes any affine expression, an uncalled template hides no typo, and degree is decided at load ([#91](https://github.com/energy-models/math-spec/issues/91)) ([a653056](https://github.com/energy-models/math-spec/commit/a6530562d59b4ac134ef4fd051ae1c9aea5f1b2c))
* **parser:** a negation is over a power, a keyword is given once, and an amount is a number or a name ([#88](https://github.com/energy-models/math-spec/issues/88)) ([4bf994c](https://github.com/energy-models/math-spec/commit/4bf994ce4700b634e970b49e8e10e705c479a65f))
* **schema:** every refusal of a malformed file is a SchemaError, and an empty declared map survives a round trip ([#89](https://github.com/energy-models/math-spec/issues/89)) ([ee07736](https://github.com/energy-models/math-spec/commit/ee07736babd79b2d0f5f99f6c9d7c25a2c98dc9f))
* **schema:** two literal bounds that cross are refused at load ([#97](https://github.com/energy-models/math-spec/issues/97)) ([30589ba](https://github.com/energy-models/math-spec/commit/30589ba4bf61e640c8f3778e34d5bd768e807e2c))
* **typeset:** a sum under its own dimension takes a fresh index, and prose escapes its markup ([#92](https://github.com/energy-models/math-spec/issues/92)) ([20c7076](https://github.com/energy-models/math-spec/commit/20c7076511c5a3ef74dc06fe0d11888f292f1b2d))


### Refactoring

* the tree describes this package, not the project it was cut from ([#94](https://github.com/energy-models/math-spec/issues/94)) ([9673f9a](https://github.com/energy-models/math-spec/commit/9673f9aef6bc7902439d7842c83a3fd95c29895e))

## [0.0.0-alpha.16](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.15...v0.0.0-alpha.16) (2026-08-25)


### Refactoring

* dead branches, an unused depth cap and prose about a parent project are gone ([#86](https://github.com/energy-models/math-spec/issues/86)) ([f31f3b0](https://github.com/energy-models/math-spec/commit/f31f3b00869131f587071a3ede24fa636cf175d7))

## [0.0.0-alpha.15](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.14...v0.0.0-alpha.15) (2026-08-25)


### Documentation

* the title rules are written for the changelog reader ([#79](https://github.com/energy-models/math-spec/issues/79)) ([fdb52e4](https://github.com/energy-models/math-spec/commit/fdb52e49dcd69be775e4be3e1860f4339a6283af))

## [0.0.0-alpha.14](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.13...v0.0.0-alpha.14) (2026-08-25)


### Documentation

* AGENTS.md says what a change here is held to ([#76](https://github.com/energy-models/math-spec/issues/76)) ([5e142f5](https://github.com/energy-models/math-spec/commit/5e142f5c9d41588bac44b9cce769995364f3a94a))

## [0.0.0-alpha.13](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.12...v0.0.0-alpha.13) (2026-08-25)


### Bug Fixes

* refuse a str or bool parameter where arithmetic wants a number ([#71](https://github.com/energy-models/math-spec/issues/71)) ([9b320fd](https://github.com/energy-models/math-spec/commit/9b320fd385d6300df3dadb14be4c9317a9241da0))

## [0.0.0-alpha.12](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.11...v0.0.0-alpha.12) (2026-08-25)


### Documentation

* a named offset needs no edge=, the limitation it named is gone ([#68](https://github.com/energy-models/math-spec/issues/68)) ([d91a0c3](https://github.com/energy-models/math-spec/commit/d91a0c37803906848808c49310356004740b8172)), closes [#64](https://github.com/energy-models/math-spec/issues/64)

## [0.0.0-alpha.11](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.10...v0.0.0-alpha.11) (2026-08-25)


### Bug Fixes

* enforce the two rules a named offset or width was always said to obey ([#61](https://github.com/energy-models/math-spec/issues/61)) ([5bd92dc](https://github.com/energy-models/math-spec/commit/5bd92dc47630d1fb8572d18e80060446c257727c)), closes [#58](https://github.com/energy-models/math-spec/issues/58)
* let sum_back stop at each group's edge, as its checks already assumed ([#65](https://github.com/energy-models/math-spec/issues/65)) ([cb58e88](https://github.com/energy-models/math-spec/commit/cb58e885221484f41804b33d47b1004874565ae4))
* refuse a negated named amount, and one read where there is no coordinate ([#63](https://github.com/energy-models/math-spec/issues/63)) ([15d9c25](https://github.com/energy-models/math-spec/commit/15d9c252e2126278f2547c9df399edf85bd44df3)), closes [#62](https://github.com/energy-models/math-spec/issues/62)

## [0.0.0-alpha.10](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.9...v0.0.0-alpha.10) (2026-08-24)


### Features

* pin the eight names that keep this package and its consumer in step ([#51](https://github.com/energy-models/math-spec/issues/51)) ([15a354b](https://github.com/energy-models/math-spec/commit/15a354b1173f105d85113db6abc2f4e5ac28a6e3))


### Refactoring

* name the groups a pass asks about, and spell each operator once ([#52](https://github.com/energy-models/math-spec/issues/52)) ([e35c46c](https://github.com/energy-models/math-spec/commit/e35c46c128a29a620c9ed562684cf1dd43a08274))
* the package is `typesetting`, the function stays `typeset` ([#54](https://github.com/energy-models/math-spec/issues/54)) ([a1d9599](https://github.com/energy-models/math-spec/commit/a1d95994333b25ac03f75f47eb2b376a03af6593))

## [0.0.0-alpha.9](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.8...v0.0.0-alpha.9) (2026-08-23)


### Features

* position(dim) replaces index(dim, i), converting on the left ([#31](https://github.com/energy-models/math-spec/issues/31)) ([8f78ac5](https://github.com/energy-models/math-spec/commit/8f78ac54f5ff6a790cff4d4b730bb2abd27bef7c))

## [0.0.0-alpha.8](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.7...v0.0.0-alpha.8) (2026-08-23)


### Features

* upright is what the model is given, italic is what the solver chooses ([#44](https://github.com/energy-models/math-spec/issues/44)) ([cbccc68](https://github.com/energy-models/math-spec/commit/cbccc68bef12cb4931f66a9447a71a9cb1174158))

## [0.0.0-alpha.7](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.6...v0.0.0-alpha.7) (2026-08-23)


### Bug Fixes

* the notation page is generated again, and something says so ([#41](https://github.com/energy-models/math-spec/issues/41)) ([3dad75e](https://github.com/energy-models/math-spec/commit/3dad75e136a91025c1d24cf1cdb13c4894c85c15))

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
