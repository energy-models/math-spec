<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Versions

mathspec has two version numbers. This page says how they relate.

- **The package version numbers a release.** The release workflow reads it
  from the
  [git tag](https://github.com/energy-models/mathspec/blob/main/RELEASING.md#the-version),
  so the tag, the changelog heading and the wheel on PyPI carry the same number,
  such as `0.0.0a127`.
- **The language version numbers the file format.** A spec file declares it
  in the top-level [`version:` key](../reference/language/file.md#version). It
  changes only when what the loader accepts changes, and most releases do not
  change that. Version `0` is unstable: any release can change what a
  version-`0` file means.

## How a release relates the two

Each release reads a fixed set of language versions and refuses a file that
declares any other:

```text
version: the spec declares version 1, and mathspec 0.0.0a127 understands [0].
Upgrade mathspec, or write the version this file actually targets.
```

A release that starts or stops reading a language version says so in the
[changelog](../changelog.md).

## What to pin

A spec file declares a language version. A tool built on the Python API, such
as specsolve, pins a package version. On the alpha stream, where any release
can change the API, pin one release.
