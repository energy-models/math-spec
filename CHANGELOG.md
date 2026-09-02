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
