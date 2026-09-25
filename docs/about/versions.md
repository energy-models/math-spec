<!--
SPDX-FileCopyrightText: mathspec contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Versions

This page says what the two version numbers of mathspec mean and how they
relate. Read it before you pin mathspec in a project or write `version:` in a
model file.

|                 | Package version                              | Language version                      |
| --------------- | -------------------------------------------- | ------------------------------------- |
| It numbers      | a release of the Python package              | the format a model file is written in |
| It lives in     | the git tag, PyPI and `mathspec.__version__` | the `version:` key of a model file    |
| It looks like   | `0.0.0a127`                                  | `0`                                   |
| It changes when | a release is cut                             | what the loader accepts changes       |

## The package version

Every release has a package version. The release workflow reads it from the
git tag, so the changelog heading, the tag and the wheel on PyPI carry the same
number
([RELEASING.md](https://github.com/energy-models/mathspec/blob/main/RELEASING.md#the-version)).
It follows PEP 440 (the Python version scheme), so `0.0.0a127` is an alpha
release.

## The language version

A model file declares the language version it is written against, in the
top-level `version:` key ([file shape](../reference/language/file.md#version)).
The key is optional and defaults to `0`.
[`Spec.to_yaml`](../reference/api.md#mathspec.Spec.to_yaml) always writes it.

The language version changes only when the set of files the loader accepts
changes. Most releases fix a bug, add a function or change what the typesetter
prints, and leave the file format as it is. So the language version is not
derived from the package version. If it were, every release would refuse the
files written for the release before it.

**Version `0` is unstable.** Any release can change what a version-`0` file
means or refuses. The package is in the same state: the `0.0.0` alpha releases
make no compatibility promise.

## How a release relates the two

Each release reads a fixed set of language versions. Today every release reads
only version `0`.

- **A release refuses a file whose language version it does not read.** It
  does not try to read the file. The message names the installed release and
  the language versions it reads:

  ```text
  version: model declares version 1, and mathspec 0.0.0a127 understands [0].
  Upgrade mathspec, or write the version this file actually targets.
  ```

- **The changelog says when the set changes.** A release that starts or stops
  reading a language version names it in its notes. The
  [changelog](../changelog.md) is the one table from package version to
  language version.

## What to pin

- **A model file names a language version, never a package version.** A file
  written for language `0` loads in every release that reads `0`, whichever
  package version that is.
- **A tool built on the Python API pins the package version.** An engine such
  as specsolve imports `Spec` and `Program`, so the package version decides
  what it can call. On the alpha stream any release can change that API, so pin
  one release, such as `mathspec==0.0.0a127`. The tool then reads the language
  versions that release reads.
