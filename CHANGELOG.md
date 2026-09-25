<!--
SPDX-FileCopyrightText: math-spec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Changelog

Written by [release-please](https://github.com/googleapis/release-please) from
the conventional-commit subjects that land on `main` — see RELEASING.md. Do not
write an entry by hand; the next release lands above whatever you put at the
top. A released entry is never rewritten, so one that is wrong is corrected in
place.

New releases are inserted directly below this paragraph, so nothing may sit
between it and the first `##` heading. The Keep a Changelog skeleton that used
to live here — a hand-maintained `## Unreleased` block, and a comment
documenting the heading format — is what broke 0.0.0-alpha.1: that comment
contained a literal `## [X.Y.Z]` heading, release-please inserts above the first
`##` it finds, and so the entire release landed inside the comment and rendered
nowhere.

## [0.0.0-alpha.126](https://github.com/energy-models/mathspec/compare/v0.0.0-alpha.125...v0.0.0-alpha.126) (2026-09-25)


### Documentation

* the site is built by zensical, and its API reference is the public surface rather than every module ([#568](https://github.com/energy-models/mathspec/issues/568)) ([64eb268](https://github.com/energy-models/mathspec/commit/64eb26894dcd5444f1cd65c7035abe4f5ccec252))

## [0.0.0-alpha.125](https://github.com/energy-models/mathspec/compare/v0.0.0-alpha.124...v0.0.0-alpha.125) (2026-09-25)


### Bug Fixes

* **language:** an unknown operator's refusal points at the limits page instead of an escape key that does not exist ([#676](https://github.com/energy-models/mathspec/issues/676)) ([5e4ef2b](https://github.com/energy-models/mathspec/commit/5e4ef2b8e6f397f71f9b09ab55685d6c02fe3a83))
* **language:** messages and docs say data is attached rather than bound, so a bound is only a variable's limit ([#694](https://github.com/energy-models/mathspec/issues/694)) ([cc8ba08](https://github.com/energy-models/mathspec/commit/cc8ba089ed50f746aae39d914ba3b7a8e700a267))


### Documentation

* a development section holds the PyPSA parity pages and the contributing guide ([#678](https://github.com/energy-models/mathspec/issues/678)) ([a399bdd](https://github.com/energy-models/mathspec/commit/a399bdd045500bf2cca5c5c386653188ef640361))
* a first tutorial writes the dispatch model one block at a time, checks it and prints it ([#680](https://github.com/energy-models/mathspec/issues/680)) ([48b60e8](https://github.com/energy-models/mathspec/commit/48b60e8507cbfd598471109a2813c48c2654cba5))
* a glossary defines each word the docs use in a fixed sense ([#675](https://github.com/energy-models/mathspec/issues/675)) ([2561ad8](https://github.com/energy-models/mathspec/commit/2561ad874cdf5d5300c1fb95bf520b09b59aa1b8))
* each page keeps only what its reader needs, and a fact stated twice keeps one home ([#686](https://github.com/energy-models/mathspec/issues/686)) ([ef8dcb9](https://github.com/energy-models/mathspec/commit/ef8dcb9c71845a1a64c471406bd3a47ec8bc45af))
* engine authors get a program api page rendered from math_spec.program, and the per-module pages and the file-and-program page are gone ([#697](https://github.com/energy-models/mathspec/issues/697)) ([784867a](https://github.com/energy-models/mathspec/commit/784867a5db6df556001d58559b46cb5acf916055))
* one Python API page documents every public name, including the typesetting functions ([#679](https://github.com/energy-models/mathspec/issues/679)) ([ee5ffdf](https://github.com/energy-models/mathspec/commit/ee5ffdf58ade9d803aedb48cdfbc5c47f5dd625c))
* the nav keeps tutorials, how-to guides, reference and about for model writers, and puts the rest under development ([#683](https://github.com/energy-models/mathspec/issues/683)) ([341ad2a](https://github.com/energy-models/mathspec/commit/341ad2a768aea4808d579627d39ab9321f05bd78))
* the notation page heads each section with the construct it shows ([#682](https://github.com/energy-models/mathspec/issues/682)) ([66faa7b](https://github.com/energy-models/mathspec/commit/66faa7b24863eae2d170355a70bc6f1216dbaaa0))
* the readme and home page lead with what a user gets, and name specsolve and linopy as engines ([#698](https://github.com/energy-models/mathspec/issues/698)) ([9fda1bc](https://github.com/energy-models/mathspec/commit/9fda1bc9f967246db2e7f27a9e6c6432b7ffd686))
* the readme drops the internals diagram and the repeated formats, and is a third shorter ([#699](https://github.com/energy-models/mathspec/issues/699)) ([234245b](https://github.com/energy-models/mathspec/commit/234245b82427d046eb79e15955dc6ad34e578114))
* what spec.expand() returns is documented on the model writer's python api page, and reading.md keeps only which program an engine reads ([#696](https://github.com/energy-models/mathspec/issues/696)) ([a9caeae](https://github.com/energy-models/mathspec/commit/a9caeae7cbc07e18cdf5685e2234f31980afd746))
* what spec.expand() returns is stated once, as a different model that binds the same data ([#677](https://github.com/energy-models/mathspec/issues/677)) ([413550e](https://github.com/energy-models/mathspec/commit/413550e884fc1a31639c5518bf3f869edee18548))

## [0.0.0-alpha.124](https://github.com/energy-models/mathspec/compare/v0.0.0-alpha.123...v0.0.0-alpha.124) (2026-09-24)


### Features

* **language:** a bound is null where it is open, never infinite, in the file and in the program ([#689](https://github.com/energy-models/mathspec/issues/689)) ([8df92d0](https://github.com/energy-models/mathspec/commit/8df92d08422bfbb973f604306419da05dd34e550))

## [0.0.0-alpha.123](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.122...v0.0.0-alpha.123) (2026-09-24)


### Documentation

* the engine these pages point at is called specsolve ([#673](https://github.com/energy-models/math-spec/issues/673)) ([647e351](https://github.com/energy-models/math-spec/commit/647e351066dc63750a63e43c0e15469daaf1f81a))

## [0.0.0-alpha.122](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.121...v0.0.0-alpha.122) (2026-09-24)


### Refactoring

* **program:** the program no longer exports fan_in, FanIn, quotients or divisor_parameters ([#633](https://github.com/energy-models/math-spec/issues/633)) ([352431b](https://github.com/energy-models/math-spec/commit/352431b121d5e517e3e1ed08c0553b3c33489ab7))

## [0.0.0-alpha.121](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.120...v0.0.0-alpha.121) (2026-09-24)


### Features

* **language:** a model's program is an attribute of the model, and the one door to both states is to_spec ([#656](https://github.com/energy-models/math-spec/issues/656)) ([91f0640](https://github.com/energy-models/math-spec/commit/91f064019c580fa1342ee1c4f2307829b32db3c5))
* **language:** nothing writes a formulation out unasked ([#661](https://github.com/energy-models/math-spec/issues/661)) ([b5241fd](https://github.com/energy-models/math-spec/commit/b5241fde3b04727f689e4b36142be5192462703f))


### Bug Fixes

* **language:** a name a curve writes is refused at load whatever declares it, and advice reads a named coefficient's sign ([#666](https://github.com/energy-models/math-spec/issues/666)) ([c1574ab](https://github.com/energy-models/math-spec/commit/c1574ab811e50bebcc6f69ae5d27a5a28828621d))


### Refactoring

* **language:** a model loads without writing its curves out, and the program owns the vocabulary the file declares in ([#653](https://github.com/energy-models/math-spec/issues/653)) ([7e93ecb](https://github.com/energy-models/math-spec/commit/7e93ecbafce83bcce9144877f306fafc566a3f28))
* **language:** every rule that reads across declarations runs in lowering, before any expression is read ([#651](https://github.com/energy-models/math-spec/issues/651)) ([6c1fb6b](https://github.com/energy-models/math-spec/commit/6c1fb6b68dedfba64db5154283d35e20f4b0b350))
* **language:** the top-level surface is the two states, the door, the errors, the advice and the typesetter ([#660](https://github.com/energy-models/math-spec/issues/660)) ([5c4f8be](https://github.com/energy-models/math-spec/commit/5c4f8be36044255518ee71105234546786aee111))
* **program:** a program carries the trees the typesetter prints, and every curve is written out before a model becomes one ([#649](https://github.com/energy-models/math-spec/issues/649)) ([762394d](https://github.com/energy-models/math-spec/commit/762394d01521323de919b8ae7cbc3598a28ea875))
* **program:** a program mirrors the file, descriptions and curves included, and the typesetter reads it alone ([#650](https://github.com/energy-models/math-spec/issues/650)) ([bfd628e](https://github.com/energy-models/math-spec/commit/bfd628e88e132639ce6569d5e0c9e3c8f0a05793))


### Documentation

* a page explains why a loaded model is a spec and a program, and which tool reads which ([#668](https://github.com/energy-models/math-spec/issues/668)) ([dc0d731](https://github.com/energy-models/math-spec/commit/dc0d731569355b823067bd58335449f081b017b8))

## [0.0.0-alpha.120](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.119...v0.0.0-alpha.120) (2026-09-23)


### Features

* **language:** a sos block says along, not over, for the dimension its set runs along ([#646](https://github.com/energy-models/math-spec/issues/646)) ([57062de](https://github.com/energy-models/math-spec/commit/57062de713c31faa42aaceb101f1ad3a2df37a1a))

## [0.0.0-alpha.119](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.118...v0.0.0-alpha.119) (2026-09-23)


### Bug Fixes

* **language:** a long chain of named expressions loads, a typo beside a formal is refused, and a fault in an entry hides no other ([#643](https://github.com/energy-models/math-spec/issues/643)) ([1e010ca](https://github.com/energy-models/math-spec/commit/1e010ca0f29994bd4b31099885d2696e3f7e979f))
* **language:** a macro template nothing calls is held to every rule a call site is ([#628](https://github.com/energy-models/math-spec/issues/628)) ([ffab0ff](https://github.com/energy-models/math-spec/commit/ffab0ffe2dbc1cf9a4711954c6ae3c5372f4b8b8))


### Refactoring

* **language:** an expression resolves straight into the program's own nodes ([#638](https://github.com/energy-models/math-spec/issues/638)) ([b3cee88](https://github.com/energy-models/math-spec/commit/b3cee8879dd38306fa86f0db93211ea88b437477))
* **language:** each named expression is resolved once, and every use reads that node ([#632](https://github.com/energy-models/math-spec/issues/632)) ([ceecf69](https://github.com/energy-models/math-spec/commit/ceecf694316a3af17cbb570b28c5c40585b6cc25))
* **program:** a comparison of expressions is one node before and after lowering ([#631](https://github.com/energy-models/math-spec/issues/631)) ([f723602](https://github.com/energy-models/math-spec/commit/f7236025a70ce0958512b326e3ae789b56eed986))

## [0.0.0-alpha.118](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.117...v0.0.0-alpha.118) (2026-09-23)


### Features

* **language:** a where may read a predicate through a relation with at() ([#634](https://github.com/energy-models/math-spec/issues/634)) ([6190cf4](https://github.com/energy-models/math-spec/commit/6190cf4e3dae0f07455cb5a7f10c9bdb572f1b9b))

## [0.0.0-alpha.117](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.116...v0.0.0-alpha.117) (2026-09-22)


### Documentation

* **limits:** a where cannot test a relation against its target dimension, and composition is a limit on the file ([#624](https://github.com/energy-models/math-spec/issues/624)) ([216208b](https://github.com/energy-models/math-spec/commit/216208b7dd548c99309ae409e34d264eb1b70421))

## [0.0.0-alpha.116](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.115...v0.0.0-alpha.116) (2026-09-22)


### Features

* **lowering:** a program is lowered from the model as it arrived, and a curve left as written is refused ([#618](https://github.com/energy-models/math-spec/issues/618)) ([b15c78a](https://github.com/energy-models/math-spec/commit/b15c78a4b8ef3614f46f3ea67c55080b71054716))

## [0.0.0-alpha.115](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.114...v0.0.0-alpha.115) (2026-09-22)


### Bug Fixes

* **typeset:** a set prints under the name its sos: block declares ([#615](https://github.com/energy-models/math-spec/issues/615)) ([f2c91e8](https://github.com/energy-models/math-spec/commit/f2c91e80f8de9df641ebe32ae6ac7c2982e75e5b))

## [0.0.0-alpha.114](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.113...v0.0.0-alpha.114) (2026-09-22)


### Documentation

* **expand:** every formulation expands to a hand-written file the suite compares whole ([#611](https://github.com/energy-models/math-spec/issues/611)) ([d7069b2](https://github.com/energy-models/math-spec/commit/d7069b2fcf3ce2ab9d44ffefed4e2e4e18865cd7))

## [0.0.0-alpha.113](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.112...v0.0.0-alpha.113) (2026-09-22)


### Bug Fixes

* **language:** a gap in points: is explained by the rows its method writes ([#612](https://github.com/energy-models/math-spec/issues/612)) ([e903272](https://github.com/energy-models/math-spec/commit/e903272606f6741050b319477ea85db76c6f0540))

## [0.0.0-alpha.112](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.111...v0.0.0-alpha.112) (2026-09-22)


### Bug Fixes

* **language:** an expanded curve declares only the parameters the file declared ([#609](https://github.com/energy-models/math-spec/issues/609)) ([423468e](https://github.com/energy-models/math-spec/commit/423468e2033e870343546a5c42994f6265efa362))

## [0.0.0-alpha.111](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.110...v0.0.0-alpha.111) (2026-09-22)


### Features

* **language:** a model declares what it assumes of its data ([#589](https://github.com/energy-models/math-spec/issues/589)) ([e1454cf](https://github.com/energy-models/math-spec/commit/e1454cf6fac8ef1b05b80532fcc0fe6a8a4e5372))
* **language:** a model writes its formulations out on request, and states what each assumes of its data ([#602](https://github.com/energy-models/math-spec/issues/602)) ([1e00c23](https://github.com/energy-models/math-spec/commit/1e00c23e227489d14790d85de5337b8edd584b10))
* **language:** a where counts the coordinates a predicate admits ([#592](https://github.com/energy-models/math-spec/issues/592)) ([5cc55d3](https://github.com/energy-models/math-spec/commit/5cc55d3c145a9139672029aa257ed4935da0d79f))
* **language:** a where may compare arithmetic over parameters ([#566](https://github.com/energy-models/math-spec/issues/566)) ([e9793bd](https://github.com/energy-models/math-spec/commit/e9793bde6e903b5783e517aeeaa1e29150d0c37c))

## [0.0.0-alpha.110](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.109...v0.0.0-alpha.110) (2026-09-21)


### Documentation

* **language:** the relations page states what decides a sum from a read ([#597](https://github.com/energy-models/math-spec/issues/597)) ([3f6b632](https://github.com/energy-models/math-spec/commit/3f6b6325ee6a89dbaec55482a6f0e126cadb664c))

## [0.0.0-alpha.109](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.108...v0.0.0-alpha.109) (2026-09-21)


### Bug Fixes

* **language:** a read that lands outside the key is refused ([#598](https://github.com/energy-models/math-spec/issues/598)) ([ce6359c](https://github.com/energy-models/math-spec/commit/ce6359cd7a5fbc66738cd746f704ab96a77f3d36))

## [0.0.0-alpha.108](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.107...v0.0.0-alpha.108) (2026-09-20)


### Refactoring

* **program:** a program names its nodes by the naming rule and its groups as the file does ([#585](https://github.com/energy-models/math-spec/issues/585)) ([3848821](https://github.com/energy-models/math-spec/commit/38488217d8f1fc23990c9bb4d933ccec1b1e0a42))

## [0.0.0-alpha.107](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.106...v0.0.0-alpha.107) (2026-09-20)


### Bug Fixes

* **language:** at refuses a read that consumes a column over the dimension it joins on, as sum does ([#562](https://github.com/energy-models/math-spec/issues/562)) ([c10c181](https://github.com/energy-models/math-spec/commit/c10c18164526efb774a881a5411a4df24f83ae7e))


### Refactoring

* **language:** a partition is its own class rather than a direction with nothing consumed or produced ([#559](https://github.com/energy-models/math-spec/issues/559)) ([6af0075](https://github.com/energy-models/math-spec/commit/6af0075729eb5132eb54234444572bb9df89c2c5))
* **language:** a relation is read in a direction rather than walked ([#494](https://github.com/energy-models/math-spec/issues/494)) ([bbc4344](https://github.com/energy-models/math-spec/commit/bbc43447bd4bf0f20978dbdd9fd212f26d5e866a))

## [0.0.0-alpha.106](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.105...v0.0.0-alpha.106) (2026-09-19)


### Refactoring

* no signature says Any, and a symbol table section that is not a mapping is refused ([#572](https://github.com/energy-models/math-spec/issues/572)) ([394599b](https://github.com/energy-models/math-spec/commit/394599b9e44adf0ee851074f59f498014b2b7d19))

## [0.0.0-alpha.105](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.104...v0.0.0-alpha.105) (2026-09-18)


### Documentation

* the README's folded document renders as math rather than as TeX ([#563](https://github.com/energy-models/math-spec/issues/563)) ([8c1d9ba](https://github.com/energy-models/math-spec/commit/8c1d9ba923eaa97352d6239703f09b0427ae6165))

## [0.0.0-alpha.104](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.103...v0.0.0-alpha.104) (2026-09-18)


### Bug Fixes

* **language:** a sum refused for walking to the key names an at() the language accepts ([#558](https://github.com/energy-models/math-spec/issues/558)) ([352fc7e](https://github.com/energy-models/math-spec/commit/352fc7e28cb15d17b30865fc1535d56b9a1cefbb))

## [0.0.0-alpha.103](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.102...v0.0.0-alpha.103) (2026-09-18)


### Documentation

* the contributing page points at the generated-pages table rather than a stale count ([#555](https://github.com/energy-models/math-spec/issues/555)) ([796ca8a](https://github.com/energy-models/math-spec/commit/796ca8af49b9808d8cd8c3f838daab37692b2c16))

## [0.0.0-alpha.102](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.101...v0.0.0-alpha.102) (2026-09-18)


### Documentation

* a rule states what is accepted and stops, rather than naming what it is not ([#552](https://github.com/energy-models/math-spec/issues/552)) ([1019b57](https://github.com/energy-models/math-spec/commit/1019b572a7be7695587b0a1a20bb32b1dbdc3781))
* every page says what a model author needs and drops rationale, history and internals ([#551](https://github.com/energy-models/math-spec/issues/551)) ([ba6ad9a](https://github.com/energy-models/math-spec/commit/ba6ad9a8815d65da909dea3021162c17802ab9c5))

## [0.0.0-alpha.101](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.100...v0.0.0-alpha.101) (2026-09-18)


### Documentation

* **language:** deciding what a column of data is declared as is a how-to, and the dimensions page keeps the axis ([#544](https://github.com/energy-models/math-spec/issues/544)) ([3540c5c](https://github.com/energy-models/math-spec/commit/3540c5c468f9421206aaea587e7b3daa41bacf48))
* **language:** named expressions, cases and macros get a page, and the reported page folds into it ([#545](https://github.com/energy-models/math-spec/issues/545)) ([4e49fc7](https://github.com/energy-models/math-spec/commit/4e49fc7ca33e7c6ff703a5dc0ec054e5ec0b7ecb))
* **language:** relations get a page of their own, and the operators page stops restating how a call reads one ([#543](https://github.com/energy-models/math-spec/issues/543)) ([7e9a572](https://github.com/energy-models/math-spec/commit/7e9a572798f73359be7731e84585fb9d90ea7c74))
* **language:** the reference pages state their rules and stop arguing for them ([#546](https://github.com/energy-models/math-spec/issues/546)) ([efc9404](https://github.com/energy-models/math-spec/commit/efc9404e40d45db4b022ffd316486b073e2b3dff))
* **language:** the relations page says what a relation is, how it is spelled, what its data owes, and how it is read, in that order ([#549](https://github.com/energy-models/math-spec/issues/549)) ([6f9e1a4](https://github.com/energy-models/math-spec/commit/6f9e1a45713578dc6d257ab30acb3b083db8aed3))
* **language:** the six rules every walk through a relation keeps ([#539](https://github.com/energy-models/math-spec/issues/539)) ([6e93995](https://github.com/energy-models/math-spec/commit/6e93995363dd59e9525018a4b9162d5c05f3fe9a))
* pinning a variable and writing a curve out by hand are how-tos ([#547](https://github.com/energy-models/math-spec/issues/547)) ([0bf0924](https://github.com/energy-models/math-spec/commit/0bf09243c822f7331faa238bdac7c8239d1a5d05))
* reading a loaded model sits beside the Python API rather than among the language pages ([#548](https://github.com/energy-models/math-spec/issues/548)) ([17d1e96](https://github.com/energy-models/math-spec/commit/17d1e96feaa4e5fde5ac9953e28e6e480ae8dc80))

## [0.0.0-alpha.100](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.99...v0.0.0-alpha.100) (2026-09-18)


### Features

* **language:** a partition names the value columns it groups by, so a relation may gain one without changing the call ([#540](https://github.com/energy-models/math-spec/issues/540)) ([0da7f50](https://github.com/energy-models/math-spec/commit/0da7f502732618f3e4766afc712ad8306e8f0f70)), closes [#538](https://github.com/energy-models/math-spec/issues/538)

## [0.0.0-alpha.99](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.98...v0.0.0-alpha.99) (2026-09-18)


### Features

* **language:** a call walks one relation, so by= names one rather than a list ([#533](https://github.com/energy-models/math-spec/issues/533)) ([b78135d](https://github.com/energy-models/math-spec/commit/b78135d7f55e8e5d5dad6eba1a37228283c4c635))
* **language:** a relation names the columns its key determines under values: ([#504](https://github.com/energy-models/math-spec/issues/504)) ([d9b0371](https://github.com/energy-models/math-spec/commit/d9b03712a58e0eda8d78fabf79ddce9eb81d4ece))
* **language:** a walk through a relation names both of its ends, and lands only on dimensions it brings ([#532](https://github.com/energy-models/math-spec/issues/532)) ([26f29b0](https://github.com/energy-models/math-spec/commit/26f29b00df45d6e18d4da4240af736d6a9c97999))

## [0.0.0-alpha.98](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.97...v0.0.0-alpha.98) (2026-09-18)


### Documentation

* **program:** linking rows and columns say when they are the whole border ([#527](https://github.com/energy-models/math-spec/issues/527)) ([7972ad0](https://github.com/energy-models/math-spec/commit/7972ad06ca68049b31faaf52480f0de4e92d7886))

## [0.0.0-alpha.97](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.96...v0.0.0-alpha.97) (2026-09-18)


### Features

* **program:** a walk that says which regions each node stands under ([#482](https://github.com/energy-models/math-spec/issues/482)) ([3f37cbe](https://github.com/energy-models/math-spec/commit/3f37cbeff7122733d3e5ff77d82bc980f4025c0d)), closes [#473](https://github.com/energy-models/math-spec/issues/473)
* **program:** every axis names its linking rows and linking columns ([#525](https://github.com/energy-models/math-spec/issues/525)) ([588142f](https://github.com/energy-models/math-spec/commit/588142f2dd5ef196078c83cf94ad07818409ff08))


### Bug Fixes

* **typesetting:** a grouped sum's domain carries every column its walk fixes ([#513](https://github.com/energy-models/math-spec/issues/513)) ([cd78ca5](https://github.com/energy-models/math-spec/commit/cd78ca5ab53d3c06ee66bb8f7d439ded10c69a4a))

## [0.0.0-alpha.96](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.95...v0.0.0-alpha.96) (2026-09-17)


### Bug Fixes

* **language:** an unknown keyword in an uncalled macro is refused by its signature ([#462](https://github.com/energy-models/math-spec/issues/462)) ([a1659da](https://github.com/energy-models/math-spec/commit/a1659daf8a6f2a9137dd9110f9d49d2003f2bd9f))
* **language:** an unknown keyword on an operator is refused once, by its signature ([#458](https://github.com/energy-models/math-spec/issues/458)) ([aa3e052](https://github.com/energy-models/math-spec/commit/aa3e05254844dc03bc8b655489ff371a18b1dfff))

## [0.0.0-alpha.95](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.94...v0.0.0-alpha.95) (2026-09-16)


### Features

* **language:** a relation declares key columns and value columns ([#501](https://github.com/energy-models/math-spec/issues/501)) ([4069792](https://github.com/energy-models/math-spec/commit/4069792247b9410aad02502b71bf0548c2679be2))

## [0.0.0-alpha.94](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.93...v0.0.0-alpha.94) (2026-09-16)


### Documentation

* **operators:** every relational call form prints beside its YAML, the ones that name their columns included ([#496](https://github.com/energy-models/math-spec/issues/496)) ([602c29e](https://github.com/energy-models/math-spec/commit/602c29e5feba2a4ad5baa4701544560b7aab67b9))

## [0.0.0-alpha.93](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.92...v0.0.0-alpha.93) (2026-09-16)


### Documentation

* **language:** a walk through a relation is stated once, in the three verbs the loader uses ([#490](https://github.com/energy-models/math-spec/issues/490)) ([ebc9b16](https://github.com/energy-models/math-spec/commit/ebc9b16b607d75dd40e72d62fdd9bf8487055fc7))

## [0.0.0-alpha.92](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.91...v0.0.0-alpha.92) (2026-09-16)


### Features

* **program:** a grouped sum and a pullback say which dimensions their walks join on ([#488](https://github.com/energy-models/math-spec/issues/488)) ([dd05088](https://github.com/energy-models/math-spec/commit/dd050883cd4aa79701bef1b175210526fd15b0ca))

## [0.0.0-alpha.91](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.90...v0.0.0-alpha.91) (2026-09-15)

Corrected: this release carries no change. [#474](https://github.com/energy-models/math-spec/pull/474)
was merged and then reverted by [#481](https://github.com/energy-models/math-spec/pull/481), both
before the tag was cut, and `revert` had no section in `changelog-sections`, so release-please kept
the feature and dropped the revert. The line it published was:

> * **program:** a walk that says which regions each node stands under ([#474](https://github.com/energy-models/math-spec/issues/474)) ([3986c6b](https://github.com/energy-models/math-spec/commit/3986c6bbe25261ec3720fbadf0005a6990fa5c16))

## [0.0.0-alpha.90](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.89...v0.0.0-alpha.90) (2026-09-15)


### Documentation

* the README shows the math a model prints, in all three formats ([#449](https://github.com/energy-models/math-spec/issues/449)) ([aad56d9](https://github.com/energy-models/math-spec/commit/aad56d9e4a6e8eade148cfadb74b5d9d0a3bfeb9))

## [0.0.0-alpha.89](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.88...v0.0.0-alpha.89) (2026-09-15)


### Features

* **language:** a relation between dimensions, walked in the direction each call names ([#437](https://github.com/energy-models/math-spec/issues/437)) ([3284926](https://github.com/energy-models/math-spec/commit/3284926ebe0d82da28cfd533448c68bbc2ba8fe4))

## [0.0.0-alpha.88](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.87...v0.0.0-alpha.88) (2026-09-15)


### Documentation

* **limits:** a whole-table operator is priced at a barrier rather than refused ([#468](https://github.com/energy-models/math-spec/issues/468)) ([835e4a4](https://github.com/energy-models/math-spec/commit/835e4a430a79a71ca0ee7f74e3c5fe5626719521))

## [0.0.0-alpha.87](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.86...v0.0.0-alpha.87) (2026-09-14)


### Features

* **language:** a variable, a constraint and a cased expression declare their shape as dims, as a parameter does ([#429](https://github.com/energy-models/math-spec/issues/429)) ([d8dfdb0](https://github.com/energy-models/math-spec/commit/d8dfdb01fcffdf2190a73875f73ed266635dc15a))

## [0.0.0-alpha.86](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.85...v0.0.0-alpha.86) (2026-09-11)


### Bug Fixes

* **language:** a where that mistypes a lookup name lists the lookups ([#455](https://github.com/energy-models/math-spec/issues/455)) ([46c48b2](https://github.com/energy-models/math-spec/commit/46c48b27241dc2569fed30911ab5b636e124becd))

## [0.0.0-alpha.85](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.84...v0.0.0-alpha.85) (2026-09-10)


### Documentation

* the pages read in plain English, arranged by what each is for ([#442](https://github.com/energy-models/math-spec/issues/442)) ([8dc4b60](https://github.com/energy-models/math-spec/commit/8dc4b602edaff106aa671f11346f8a07c813d3ce))

## [0.0.0-alpha.84](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.83...v0.0.0-alpha.84) (2026-09-10)


### Bug Fixes

* **typesetting:** Markdown math renders on GitHub as the file's own math ([#446](https://github.com/energy-models/math-spec/issues/446)) ([31ff1c3](https://github.com/energy-models/math-spec/commit/31ff1c375c5c8dd29f830d2c344ce3037463e1aa))

## [0.0.0-alpha.83](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.82...v0.0.0-alpha.83) (2026-09-09)


### Features

* **language:** a lookup always maps into a declared dimension ([#422](https://github.com/energy-models/math-spec/issues/422)) ([533665c](https://github.com/energy-models/math-spec/commit/533665cb15e5f03f37f261f276b1a2e920db5de7))


### Refactoring

* **program:** a variable's domain is called domain in the program, as the file calls it ([#427](https://github.com/energy-models/math-spec/issues/427)) ([62564a2](https://github.com/energy-models/math-spec/commit/62564a26e48ebba5a0fa34d0f2e889481db90b4c))

## [0.0.0-alpha.82](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.81...v0.0.0-alpha.82) (2026-09-09)


### Features

* **program:** a where predicate's operands are walked with where_children, as an expression's are with children ([#416](https://github.com/energy-models/math-spec/issues/416)) ([b653537](https://github.com/energy-models/math-spec/commit/b653537970f33ca01bcc56b524dc7cf8e3e70d4c))
* **typesetting:** a backticked name in a description sets in monospace in every format ([#421](https://github.com/energy-models/math-spec/issues/421)) ([a2dcee7](https://github.com/energy-models/math-spec/commit/a2dcee759adc5cbe7db884a09cfca45849325400))


### Bug Fixes

* **typesetting:** a Markdown description sets as text rather than as markup ([#420](https://github.com/energy-models/math-spec/issues/420)) ([a793961](https://github.com/energy-models/math-spec/commit/a7939613393aa4dbd2df926d934a99786562e7ce))


### Performance

* **validation:** a model's expressions and where strings are resolved once per load rather than once per reader ([#415](https://github.com/energy-models/math-spec/issues/415)) ([bd86867](https://github.com/energy-models/math-spec/commit/bd86867fef29b233dcf9016b1d22077152935907))

## [0.0.0-alpha.81](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.80...v0.0.0-alpha.81) (2026-09-09)


### Documentation

* the reading page says what a spec writes back out ([#414](https://github.com/energy-models/math-spec/issues/414)) ([3f4e5e0](https://github.com/energy-models/math-spec/commit/3f4e5e05a4f965d407e390d69667c073cf1d780d))

## [0.0.0-alpha.80](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.79...v0.0.0-alpha.80) (2026-09-09)


### Documentation

* the editor recipe and the naming rules live with the language ([#412](https://github.com/energy-models/math-spec/issues/412)) ([dac95bd](https://github.com/energy-models/math-spec/commit/dac95bdd3c8e6634592087c0571f1eeb4f8040a1))

## [0.0.0-alpha.79](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.78...v0.0.0-alpha.79) (2026-09-09)


### Bug Fixes

* **program:** two groups of a program merge with | as they did before the seal ([#410](https://github.com/energy-models/math-spec/issues/410)) ([e053e00](https://github.com/energy-models/math-spec/commit/e053e00dda028f3c5a957b5fe73c42b9feb782ff))

## [0.0.0-alpha.78](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.77...v0.0.0-alpha.78) (2026-09-09)


### Bug Fixes

* **program:** a lowered program pickles, and the model it came from with it ([#407](https://github.com/energy-models/math-spec/issues/407)) ([cd41ae4](https://github.com/energy-models/math-spec/commit/cd41ae4fb00839d3b553a994c987e3cc2c42e4cd))

## [0.0.0-alpha.77](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.76...v0.0.0-alpha.77) (2026-09-09)


### Features

* a model loads from its YAML text as well as from a file ([#406](https://github.com/energy-models/math-spec/issues/406)) ([e88a0ef](https://github.com/energy-models/math-spec/commit/e88a0ef7037375ef3da0351f5d156986b89a190f))

## [0.0.0-alpha.76](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.75...v0.0.0-alpha.76) (2026-09-08)


### Bug Fixes

* **program:** a parameter under a power is seen by every walk, so a divisor written as a power is named ([#404](https://github.com/energy-models/math-spec/issues/404)) ([1689a7a](https://github.com/energy-models/math-spec/commit/1689a7a38274a69e8cc0e67fe1e5889b2355fc63)), closes [#403](https://github.com/energy-models/math-spec/issues/403)

## [0.0.0-alpha.75](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.74...v0.0.0-alpha.75) (2026-09-08)


### Features

* **language:** an expression the math never reads may be nonlinear and may call dual() ([#395](https://github.com/energy-models/math-spec/issues/395)) ([18020f4](https://github.com/energy-models/math-spec/commit/18020f44b6b7095cac41ff2486cd05be959b409b))

## [0.0.0-alpha.74](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.73...v0.0.0-alpha.74) (2026-09-08)


### Features

* **typeset:** a named expression prints as a definition, and one declaration prints on its own by name ([#385](https://github.com/energy-models/math-spec/issues/385)) ([f66925e](https://github.com/energy-models/math-spec/commit/f66925e5565d21aee9023093bf315b38cfce7613))

## [0.0.0-alpha.73](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.72...v0.0.0-alpha.73) (2026-09-02)


### Documentation

* **about:** the test a function has to pass to be part of this package's surface ([#246](https://github.com/energy-models/math-spec/issues/246)) ([cc1414a](https://github.com/energy-models/math-spec/commit/cc1414a6d2df94d8b97d8ef5382ab48862671204))

## [0.0.0-alpha.72](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.71...v0.0.0-alpha.72) (2026-09-02)


### Features

* **program:** a model says whether an axis may be built a window at a time, and what each coordinate needs from its neighbours ([#374](https://github.com/energy-models/math-spec/issues/374)) ([1e029b4](https://github.com/energy-models/math-spec/commit/1e029b4637637e12a1dad12b7d5b6b127695cdc9))

## [0.0.0-alpha.71](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.70...v0.0.0-alpha.71) (2026-09-02)


### Bug Fixes

* an expression too deep to walk is refused rather than crashing ([#359](https://github.com/energy-models/math-spec/issues/359)) ([d6cee25](https://github.com/energy-models/math-spec/commit/d6cee25b37294993a6733723f256d28a140f63f2))

## [0.0.0-alpha.70](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.69...v0.0.0-alpha.70) (2026-09-02)


### Documentation

* **language:** only a dimension some declaration reaches needs a source ([#378](https://github.com/energy-models/math-spec/issues/378)) ([b3b9549](https://github.com/energy-models/math-spec/commit/b3b9549582a9976dafabd25ef203bc4353f4791c))

## [0.0.0-alpha.69](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.68...v0.0.0-alpha.69) (2026-09-02)


### Bug Fixes

* the docstrings no longer point a consumer at the package-private expression tree ([#351](https://github.com/energy-models/math-spec/issues/351)) ([15b1985](https://github.com/energy-models/math-spec/commit/15b1985e7660eadec0d5d6bfe1850fbb7b20733e))


### Refactoring

* the expression parser is package-private, and the parsed tree is named apart from the program's ([#342](https://github.com/energy-models/math-spec/issues/342)) ([55ff525](https://github.com/energy-models/math-spec/commit/55ff525f1dfacd7e93d6448adb0b377d09fa3e85))

## [0.0.0-alpha.68](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.67...v0.0.0-alpha.68) (2026-09-02)


### Documentation

* **language:** the rules binding obeys belong to the language, not to whichever engine reads the data ([#242](https://github.com/energy-models/math-spec/issues/242)) ([c05da6a](https://github.com/energy-models/math-spec/commit/c05da6a69d46ca0f595cfab4bd9e8eec827dfeb0))

## [0.0.0-alpha.67](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.66...v0.0.0-alpha.67) (2026-09-02)


### Refactoring

* a built-in's one positional argument is stated once, and a degree question names the tree it walks ([#364](https://github.com/energy-models/math-spec/issues/364)) ([556af30](https://github.com/energy-models/math-spec/commit/556af3053e0bb32ca8bf60e656b9455b98068981))
* every rule two passes shared has one home, and a docstring says what a caller needs rather than why ([#363](https://github.com/energy-models/math-spec/issues/363)) ([f24ddd3](https://github.com/energy-models/math-spec/commit/f24ddd3089da12aa75715560992822a5a3ee818b))
* **model:** each cross-declaration rule is one method, so a refusal names the rule that raised it ([#369](https://github.com/energy-models/math-spec/issues/369)) ([b25a602](https://github.com/energy-models/math-spec/commit/b25a602d21a6bb91d597f663f8bcf0b97f95aed8))
* **piecewise:** one block expands itself, holding its names, frame and mask once ([#367](https://github.com/energy-models/math-spec/issues/367)) ([537eadf](https://github.com/energy-models/math-spec/commit/537eadf76f52615c83235e0dfbbdd2af5fa70588))
* resolution is one method per node kind, and each operator's dim rule is one function ([#368](https://github.com/energy-models/math-spec/issues/368)) ([c7c2833](https://github.com/energy-models/math-spec/commit/c7c283347869fbd45e0ff851d0112bfcbc09f98c))
* **typesetting:** the legend reads what the equations returned rather than state left on the walk ([#366](https://github.com/energy-models/math-spec/issues/366)) ([db96a54](https://github.com/energy-models/math-spec/commit/db96a54d55996a9e4cc89a3f837303149475211b))

## [0.0.0-alpha.66](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.65...v0.0.0-alpha.66) (2026-09-01)


### Performance

* a model loads, lowers and typesets three to eight times faster ([#357](https://github.com/energy-models/math-spec/issues/357)) ([ea6fe79](https://github.com/energy-models/math-spec/commit/ea6fe798c85118750294b642463b16aa0935065f))

## [0.0.0-alpha.65](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.64...v0.0.0-alpha.65) (2026-09-01)


### Refactoring

* **language:** a translation policy and a bound's side name the values they can be, rather than being a string ([#354](https://github.com/energy-models/math-spec/issues/354)) ([d212157](https://github.com/energy-models/math-spec/commit/d2121572496bf7e624cfa5e38c348cfbed4b71ad))
* **typesetting:** a format spells the operators the language names, rather than any string a walk happens to ask for ([#352](https://github.com/energy-models/math-spec/issues/352)) ([12b4041](https://github.com/energy-models/math-spec/commit/12b404126dbe00e28ad16b4736dbe90dfda833d0))

## [0.0.0-alpha.64](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.63...v0.0.0-alpha.64) (2026-09-01)


### Features

* **parser:** a refused where string names the rewrite for pandas and C connective habits ([#346](https://github.com/energy-models/math-spec/issues/346)) ([3dbd9b2](https://github.com/energy-models/math-spec/commit/3dbd9b261dd82fc5cd52924ecdd03b18ddd88c14))

## [0.0.0-alpha.63](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.62...v0.0.0-alpha.63) (2026-09-01)


### Refactoring

* **language:** an operator, a declaration kind and a notation name the values they can be, rather than being a string ([#345](https://github.com/energy-models/math-spec/issues/345)) ([3f3f858](https://github.com/energy-models/math-spec/commit/3f3f8581baabc51882ad4e1d97fb774ae1944dc3))

## [0.0.0-alpha.62](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.61...v0.0.0-alpha.62) (2026-09-01)


### Bug Fixes

* **language:** a declaration named what no expression could write is refused, rather than loading unreferenceable ([#340](https://github.com/energy-models/math-spec/issues/340)) ([b865bc1](https://github.com/energy-models/math-spec/commit/b865bc15fde7e5a7714cdf809f5f0b9e6e6f44e5))

## [0.0.0-alpha.61](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.60...v0.0.0-alpha.61) (2026-09-01)


### Performance

* **program:** a mask walks its leaves once and every question reads that walk ([#338](https://github.com/energy-models/math-spec/issues/338)) ([337d169](https://github.com/energy-models/math-spec/commit/337d1697724980356c8d911bf21242a19a6f517a))

## [0.0.0-alpha.60](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.59...v0.0.0-alpha.60) (2026-09-01)


### Bug Fixes

* **language:** the language reference states which case arms are refused, and the refusal says what actually breaks ([#336](https://github.com/energy-models/math-spec/issues/336)) ([01920d1](https://github.com/energy-models/math-spec/commit/01920d1be4f6dbd6965f6f0e7e683543384cc744))

## [0.0.0-alpha.59](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.58...v0.0.0-alpha.59) (2026-09-01)


### Bug Fixes

* **parser:** a parsed expression cannot be rewritten under another pass ([#329](https://github.com/energy-models/math-spec/issues/329)) ([fcfb7b8](https://github.com/energy-models/math-spec/commit/fcfb7b8a3e2c66cd03da316994154b9c2dd493d0))

## [0.0.0-alpha.58](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.57...v0.0.0-alpha.58) (2026-09-01)


### Features

* **program:** a resolved where is a first-class Mask whose leaves carry their dims, and the where grammar is package-private ([#327](https://github.com/energy-models/math-spec/issues/327)) ([53cc352](https://github.com/energy-models/math-spec/commit/53cc3522e917a5849ce3150585c2c9e05a8ea162))

## [0.0.0-alpha.57](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.56...v0.0.0-alpha.57) (2026-09-01)


### Bug Fixes

* **program:** a program describes a mathematical program rather than being one, and claims neither linearity nor a storage format ([#315](https://github.com/energy-models/math-spec/issues/315)) ([5dfa6be](https://github.com/energy-models/math-spec/commit/5dfa6be817fb49999571b2fdc8b8b820371f80d0))

## [0.0.0-alpha.56](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.55...v0.0.0-alpha.56) (2026-09-01)


### Features

* **program:** the conjuncts of a where mask are the program's to give, not each consumer's to re-derive ([#313](https://github.com/energy-models/math-spec/issues/313)) ([db63d3c](https://github.com/energy-models/math-spec/commit/db63d3ca90079e4031a9339ea7749c0567b31be9))

## [0.0.0-alpha.55](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.54...v0.0.0-alpha.55) (2026-08-31)


### Documentation

* **ceiling:** load-time unit checking has its own refusal, where the data-prep row used to answer for it ([#272](https://github.com/energy-models/math-spec/issues/272)) ([8dfd17d](https://github.com/energy-models/math-spec/commit/8dfd17df17993f1209fe479734c3dee756fcc384))

## [0.0.0-alpha.54](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.53...v0.0.0-alpha.54) (2026-08-31)


### Documentation

* drop the effects row from the PyPSA-1.3.0 parity table, a feature that release does not have ([#305](https://github.com/energy-models/math-spec/issues/305)) ([92e5ed8](https://github.com/energy-models/math-spec/commit/92e5ed84c14c59e8068a7814722950f936e2925a))

## [0.0.0-alpha.53](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.52...v0.0.0-alpha.53) (2026-08-31)


### Documentation

* a link's delivery lags its flow, wrapping or losing what is in transit at the horizon's edge ([#300](https://github.com/energy-models/math-spec/issues/300)) ([1d4f10f](https://github.com/energy-models/math-spec/commit/1d4f10fce6ef9889400caddd0cf0436ab2b07c53))

## [0.0.0-alpha.52](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.51...v0.0.0-alpha.52) (2026-08-31)


### Documentation

* **examples:** the PyPSA file states a constraint once where PyPSA builds one row set, rather than a block per regime ([#257](https://github.com/energy-models/math-spec/issues/257)) ([#292](https://github.com/energy-models/math-spec/issues/292)) ([c35e637](https://github.com/energy-models/math-spec/commit/c35e637c8632e361d1d9565824e0497d3199bc16))

## [0.0.0-alpha.51](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.50...v0.0.0-alpha.51) (2026-08-31)


### Features

* a named expression may give a value per region, and no two regions may claim one coordinate ([#168](https://github.com/energy-models/math-spec/issues/168)) ([e12e7da](https://github.com/energy-models/math-spec/commit/e12e7da502e959191066ab220097edbb2ae566ee))

## [0.0.0-alpha.50](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.49...v0.0.0-alpha.50) (2026-08-31)


### Documentation

* **language:** a label space may group a position, though not a reduction or a walk ([#281](https://github.com/energy-models/math-spec/issues/281)) ([00be0cb](https://github.com/energy-models/math-spec/commit/00be0cb9bca7bc3f73860a50fe703d6eefff3be6))

## [0.0.0-alpha.49](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.48...v0.0.0-alpha.49) (2026-08-31)


### Features

* **examples:** a link delivers to as many buses as its data declares, not two ([#273](https://github.com/energy-models/math-spec/issues/273)) ([0ece0d8](https://github.com/energy-models/math-spec/commit/0ece0d86794a86664e2596428df25e319eb6b56e))


### Bug Fixes

* **examples:** a committable modular unit that is not extendable gets the rows PyPSA builds for it ([#271](https://github.com/energy-models/math-spec/issues/271)) ([5af0ac8](https://github.com/energy-models/math-spec/commit/5af0ac8cb15271c4b6982e4397604fe3dfb5cb10))

## [0.0.0-alpha.48](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.47...v0.0.0-alpha.48) (2026-08-31)


### Features

* **language:** which dims a mask reads is the language's answer, so two consumers cannot restrict one model differently ([#269](https://github.com/energy-models/math-spec/issues/269)) ([350b1ed](https://github.com/energy-models/math-spec/commit/350b1ed5b572146f8168297e6ded1a234c6fc619))

## [0.0.0-alpha.47](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.46...v0.0.0-alpha.47) (2026-08-28)


### Documentation

* the README's example of reading a loaded model runs as written ([#240](https://github.com/energy-models/math-spec/issues/240)) ([304a233](https://github.com/energy-models/math-spec/commit/304a233d408979aa54b7fa2b0a6b5f12469e8afd))

## [0.0.0-alpha.46](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.45...v0.0.0-alpha.46) (2026-08-28)


### Features

* **program:** a piecewise assumption names the data it is about, and a derived parameter says how it is filled ([#237](https://github.com/energy-models/math-spec/issues/237)) ([48431b1](https://github.com/energy-models/math-spec/commit/48431b1a72197570ab291103267212d269141936))

## [0.0.0-alpha.45](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.44...v0.0.0-alpha.45) (2026-08-28)


### Bug Fixes

* **language:** a negative edge fill prints, the sign of a literal amount being folded once at resolution ([#234](https://github.com/energy-models/math-spec/issues/234)) ([d9303db](https://github.com/energy-models/math-spec/commit/d9303dbd1e824f674331b7e9403dd5799444dd15))

## [0.0.0-alpha.44](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.43...v0.0.0-alpha.44) (2026-08-28)


### Bug Fixes

* **language:** a where mask is folded at resolution, so a typeset page and a program agree about it ([#232](https://github.com/energy-models/math-spec/issues/232)) ([553bda0](https://github.com/energy-models/math-spec/commit/553bda0239932b8a1225a6df0f9d008dff5e285d))

## [0.0.0-alpha.43](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.42...v0.0.0-alpha.43) (2026-08-28)


### Features

* **program:** a parameter says which piecewise block derived it, and a label space keeps its dtype ([#227](https://github.com/energy-models/math-spec/issues/227)) ([515dbd5](https://github.com/energy-models/math-spec/commit/515dbd5054dae8ae61fd8818be4d204e1d98950b))
* **program:** a piecewise block is kept as facts — its breakpoints, its mask, and what it assumes of the data ([#228](https://github.com/energy-models/math-spec/issues/228)) ([2fdbd6f](https://github.com/energy-models/math-spec/commit/2fdbd6f5760975132f0dc9db605b11f4d2cc7103))

## [0.0.0-alpha.42](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.41...v0.0.0-alpha.42) (2026-08-28)


### Bug Fixes

* **language:** a negative sum_back width is refused at load rather than asserting in lowering ([#223](https://github.com/energy-models/math-spec/issues/223)) ([62e52eb](https://github.com/energy-models/math-spec/commit/62e52eb6c7071f16e360055c5d11870e8a2ba1a0)), closes [#222](https://github.com/energy-models/math-spec/issues/222)

## [0.0.0-alpha.41](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.40...v0.0.0-alpha.41) (2026-08-28)


### Bug Fixes

* **language:** a boolean literal in a where is decided at load wherever it stands ([#216](https://github.com/energy-models/math-spec/issues/216)) ([fab308f](https://github.com/energy-models/math-spec/commit/fab308f61fddfad230fe8fb9d11e3961faa0a704)), closes [#214](https://github.com/energy-models/math-spec/issues/214)

## [0.0.0-alpha.40](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.39...v0.0.0-alpha.40) (2026-08-28)


### Refactoring

* **program:** the declaration vocabularies have one home, so a program cannot spell one differently from the file ([#219](https://github.com/energy-models/math-spec/issues/219)) ([f7596d7](https://github.com/energy-models/math-spec/commit/f7596d7bcf7ff61aff5a94807b34bf5516b29085)), closes [#209](https://github.com/energy-models/math-spec/issues/209)

## [0.0.0-alpha.39](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.38...v0.0.0-alpha.39) (2026-08-28)


### Bug Fixes

* **advice:** a model handed over as a program is advised of everything a file is ([#217](https://github.com/energy-models/math-spec/issues/217)) ([4fc50e6](https://github.com/energy-models/math-spec/commit/4fc50e60b7387c657a7571650a151054f564308b)), closes [#210](https://github.com/energy-models/math-spec/issues/210)

## [0.0.0-alpha.38](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.37...v0.0.0-alpha.38) (2026-08-28)


### Features

* **program:** a program says which of the language's constructs it uses ([#207](https://github.com/energy-models/math-spec/issues/207)) ([4e55a15](https://github.com/energy-models/math-spec/commit/4e55a15df57bef28364049ff16d449312d06aebd))


### Bug Fixes

* a file the language accepts is one every consumer can build, the edge rules being decided at load ([#211](https://github.com/energy-models/math-spec/issues/211)) ([a362ff0](https://github.com/energy-models/math-spec/commit/a362ff0e9bb582ffa11edadec69daf700f7cea3f))
* **program:** a where mask cannot be rewritten under another consumer ([#197](https://github.com/energy-models/math-spec/issues/197)) ([ce406b0](https://github.com/energy-models/math-spec/commit/ce406b045567ff82732f818e2a905bf7d302852b))
* **program:** an unknown dimension is refused rather than answered empty ([#199](https://github.com/energy-models/math-spec/issues/199)) ([96fdccf](https://github.com/energy-models/math-spec/commit/96fdccf105bf2ffc37d8cda078f3560e56bff9ec))
* **program:** every expression node answers fan_in ([#202](https://github.com/energy-models/math-spec/issues/202)) ([f5cc67d](https://github.com/energy-models/math-spec/commit/f5cc67d9320ab254771e2d5527bf41641a6ca648))


### Refactoring

* **program:** a program is built by keyword, so a new field cannot reorder an old call ([#203](https://github.com/energy-models/math-spec/issues/203)) ([214394a](https://github.com/energy-models/math-spec/commit/214394a0dc2499b5af8c8300b2306631e9592f98))
* **program:** a program's declarations are keyed by the name the file wrote ([#205](https://github.com/energy-models/math-spec/issues/205)) ([579264a](https://github.com/energy-models/math-spec/commit/579264a6b69557ab840edf38dace462e10b6715e))
* **program:** drop the two pieces of the program API nothing reaches ([#204](https://github.com/energy-models/math-spec/issues/204)) ([ca25fa5](https://github.com/energy-models/math-spec/commit/ca25fa5433540d45b73bc9fe307eeca78bc47376))
* **program:** expressions are the ones a row is built from, and the declared ones say so ([#206](https://github.com/energy-models/math-spec/issues/206)) ([81aaddd](https://github.com/energy-models/math-spec/commit/81aaddd655a8db6676f4f87c073908f6c0340a16))
* **program:** the program module says what it promises, rather than offering its whole namespace ([#208](https://github.com/energy-models/math-spec/issues/208)) ([08d2f64](https://github.com/energy-models/math-spec/commit/08d2f644f1975aca0a3eb4927e034c402e6d46eb))

## [0.0.0-alpha.37](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.36...v0.0.0-alpha.37) (2026-08-28)


### Features

* a model is checked from the shell, advice included, with no consumer installed ([#192](https://github.com/energy-models/math-spec/issues/192)) ([941126c](https://github.com/energy-models/math-spec/commit/941126cd95af7decb0d37538e93c4f7c4ad54935))
* advice carries which pass said it and which declaration it is about, so a consumer can filter rather than parse ([#195](https://github.com/energy-models/math-spec/issues/195)) ([89408f6](https://github.com/energy-models/math-spec/commit/89408f6fae500df661bda66cc2f0ef100b691636))


### Refactoring

* one call returns every note the language can give without data ([#191](https://github.com/energy-models/math-spec/issues/191)) ([2face7a](https://github.com/energy-models/math-spec/commit/2face7a39092e5f2fc1ddb705efee8a7d34dd343))

## [0.0.0-alpha.36](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.35...v0.0.0-alpha.36) (2026-08-28)


### Refactoring

* a program is trusted by construction, so the language's rules are checked once, on the spec ([#189](https://github.com/energy-models/math-spec/issues/189)) ([45931b1](https://github.com/energy-models/math-spec/commit/45931b1a975d80faa45ad47303fdbb30b1f12855))

## [0.0.0-alpha.35](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.34...v0.0.0-alpha.35) (2026-08-28)


### Documentation

* the style guide's front-door example is the function it quotes ([#187](https://github.com/energy-models/math-spec/issues/187)) ([5dbed70](https://github.com/energy-models/math-spec/commit/5dbed70024c1e59633ffcee0f4f6295abc69fd8c))

## [0.0.0-alpha.34](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.33...v0.0.0-alpha.34) (2026-08-28)


### Refactoring

* two public states and a conversion to each, where the surface was seventy-seven names ([#180](https://github.com/energy-models/math-spec/issues/180)) ([718e2de](https://github.com/energy-models/math-spec/commit/718e2dea7c6e05933c4880196279ae9fe015dd09))

## [0.0.0-alpha.33](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.32...v0.0.0-alpha.33) (2026-08-28)


### Features

* the notes a check prints are reachable, so a consumer surfaces them rather than re-deriving them ([#184](https://github.com/energy-models/math-spec/issues/184)) ([19ef814](https://github.com/energy-models/math-spec/commit/19ef81411b619ae187f7763338202e1e06401cf0))

## [0.0.0-alpha.32](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.31...v0.0.0-alpha.32) (2026-08-28)


### Features

* a program is the second public state, and one call reaches it ([#177](https://github.com/energy-models/math-spec/issues/177)) ([c9ee1ab](https://github.com/energy-models/math-spec/commit/c9ee1ab2607fce5618a4b3df56082d9ec1b2b3a5))

## [0.0.0-alpha.31](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.30...v0.0.0-alpha.31) (2026-08-28)


### Documentation

* **agents:** the cheap gates run here, and CI is reported rather than watched ([#175](https://github.com/energy-models/math-spec/issues/175)) ([78e3d80](https://github.com/energy-models/math-spec/commit/78e3d80e0705238296a90e9eed3ecf182f737e2c))

## [0.0.0-alpha.30](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.29...v0.0.0-alpha.30) (2026-08-28)


### Documentation

* the absence rules cover every operator, not the three they named ([#173](https://github.com/energy-models/math-spec/issues/173)) ([3266a5b](https://github.com/energy-models/math-spec/commit/3266a5bbfb5df657f4a1a417f8ce5206ee986227))

## [0.0.0-alpha.29](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.28...v0.0.0-alpha.29) (2026-08-27)


### Features

* **language:** dimension members and lookup maps come from the data, rather than from the file ([#169](https://github.com/energy-models/math-spec/issues/169)) ([f3c4e5f](https://github.com/energy-models/math-spec/commit/f3c4e5fa492ece1ae0af1ac27e7b0a36266a287a))

## [0.0.0-alpha.28](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.27...v0.0.0-alpha.28) (2026-08-27)


### Bug Fixes

* the ac-dc-meshed rung states its network, so the reference run needs no download ([#166](https://github.com/energy-models/math-spec/issues/166)) ([abf734c](https://github.com/energy-models/math-spec/commit/abf734c8cd294935907455048a39da585cca56e1))

## [0.0.0-alpha.27](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.26...v0.0.0-alpha.27) (2026-08-27)


### Bug Fixes

* the linearized rung states its three caps as rows and starts one unit cold, so every block it declares is built ([#162](https://github.com/energy-models/math-spec/issues/162)) ([cb4863f](https://github.com/energy-models/math-spec/commit/cb4863f35f71a97c44703390335121200273a4f6))

## [0.0.0-alpha.26](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.25...v0.0.0-alpha.26) (2026-08-27)


### Features

* a snapshot is a timestamp, in the file and in every rung's network ([#159](https://github.com/energy-models/math-spec/issues/159)) ([dd5122e](https://github.com/energy-models/math-spec/commit/dd5122ec2184bdaf3145e56949e42a6fa0612948))

## [0.0.0-alpha.25](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.24...v0.0.0-alpha.25) (2026-08-27)


### Features

* rung 11 — PyPSA's ac-dc-meshed example, whole ([#151](https://github.com/energy-models/math-spec/issues/151)) ([a133044](https://github.com/energy-models/math-spec/commit/a1330441ba7926aeedc086afa48f2efa8971fa10))
* rung 12 — linearized unit commitment, a file of its own ([#152](https://github.com/energy-models/math-spec/issues/152)) ([69b926e](https://github.com/energy-models/math-spec/commit/69b926e64b2431ad723b92e614b4c43523525253))
* rung 13 — transmission losses in tangent form, a file of its own ([#153](https://github.com/energy-models/math-spec/issues/153)) ([379ce23](https://github.com/energy-models/math-spec/commit/379ce2316b2146ca064bcc3bac0d3ea0bd995011))
* rung 14 — two-stage stochastic with CVaR, a file of its own ([#154](https://github.com/energy-models/math-spec/issues/154)) ([41b427d](https://github.com/energy-models/math-spec/commit/41b427daa7525f7fd6368488e005e0a42983f3fd))
* rung 15 — investment periods with a growth limit, a file of its own ([#155](https://github.com/energy-models/math-spec/issues/155)) ([285aac3](https://github.com/energy-models/math-spec/commit/285aac35bda2ee69a2872a6b20618f5827c3d19f))

## [0.0.0-alpha.24](https://github.com/energy-models/math-spec/compare/v0.0.0-alpha.23...v0.0.0-alpha.24) (2026-08-26)


### Features

* PyPSA in one file — every rung stated, shown beside its data, and solved to the same objective on both lanes ([#122](https://github.com/energy-models/math-spec/issues/122)) ([46544e3](https://github.com/energy-models/math-spec/commit/46544e3d405d8ed1f982053934c3d033e2ccbe19))

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
