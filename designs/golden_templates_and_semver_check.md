Title: Golden Templates and Semver Check
========================================

What is the problem?
--------------------

SAM CLI processes user templates and writes the result to disk for
CloudFormation to consume. The output template is the contract with users
and their tooling — yet the existing test suite has no review surface for
that output's *shape*. Unit tests verify individual functions in
isolation; integration tests assert exit codes and a few narrow
properties (`Resources.X.Type == ...`); neither puts the rendered
template in front of a human reviewer.

This shows up most painfully in feature PRs that introduce new
output-shaping behavior. The reviewer can read the code and run the
tests, but cannot easily see *what the feature produces for representative
inputs* — the diff in the PR is `samcli/lib/...` Python code, not the
YAML that customers will deploy. Subtle interactions between pipeline
stages — LE expansion vs. SAM transform vs. global-transform export
vs. artifact-path merge — are invisible at review time.

PR #8637 (sam-cli 1.160.0, in-tree CFN Language Extensions support) is
exhibit A. It introduced large new output-shaping behavior across the
build and package paths. Within weeks of release four bugs surfaced,
each a behavior shift visible in the post-build or post-package
template that no automated test caught before release:

- #9004 — `Fn::FindInMap` / `Join` / `Select` / `Base64` raised on
  unresolved parameter `Ref`s in PARTIAL mode (fixed in #9010).
- #9005 — `PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES` had drifted from
  canonical resource lists; `AWS::Serverless::Application` and seven
  sibling types failed packaging (fixed in #9009).
- #9027 — `AWS::Include` buried inside `Fn::ToJsonString` was invisible
  to the global-transform walker because LE expansion ran first (fixed
  in #9030).
- #9029 — LE-aware build merge overwrote `Code: { ZipFile: !Sub ... }`
  with the LE-resolved value, baking pseudo-param defaults into the
  built template (fixed in #9031).

PR #9033 made local LE processing opt-in to give customers a clean
migration path.

These bugs didn't slip past #8637 because the test suite was small —
the LE module shipped with comprehensive unit tests and integration
tests. They slipped past because nobody was asked, at PR-review time,
to look at the actual templates `sam build` and `sam package` produce
for templates exercising each new LE intrinsic. Each bug is a YAML-shape
diff that a reviewer would have caught on sight — if the diff had been
visible.

The right moment for that review surface is the feature PR itself.
#8637 should have shipped with one pinned input/output pair per LE
intrinsic plus the cross-cutting interactions (LE × nested stacks, LE
× AWS::Include, LE × Globals). Each iteration on the PR would have
produced output diffs alongside code diffs; the four bugs would have
appeared as visible shape changes during development, before the PR
merged. That same pattern then carries forward: every future feature
PR pins what it produces, every patch release is auditable for
behavior changes.

A pinned-output corpus solves only half the problem, though. Behavior
changes — intentional or not — must also be visible to *consumers* of
SAM CLI, not just to reviewers. The most impactful changes don't just
alter output shape: they cause `sam build` or `sam package` to fail
outright, breaking customer CI/CD pipelines on what was assumed to be
a routine upgrade. #9004 is the canonical example — `sam build`
started raising `InvalidTemplateException` on any template that used
`!FindInMap` over a parameter without a `Default`, blocking every CI
that consumed such a template until the customer either pinned to
1.159.x or upgraded past the fix. The 1.159 → 1.160 bump was minor
per semver, signalling "additive, backwards-compatible" — but local
LE processing turning on by default broke working pipelines, which
is the definition of a backwards-incompatible change. The version
number didn't tell consumers to audit their pipelines, so they
didn't.

This design proposes:

1. **A golden-template corpus** under `tests/golden/templates/`.
   For each representative input, pin the post-build and post-package
   YAML byte-for-byte. The pins live in the repo; PR diffs include
   both the code change and the resulting output change. Reviewers see
   what users will see.

2. **A CI semver gate** that requires a major-version bump in
   `samcli/__init__.py` whenever an existing pinned output is modified
   or deleted. New pins (corpus growth) are ungated. The gate makes
   user-visible behavior changes explicit at version-number granularity
   so downstream tooling can react deliberately.

The two compose: goldens make output changes *visible* to reviewers;
the semver check makes them *commitments* to consumers.

What will be changed?
---------------------

Add a new `tests/golden/` corpus and harness (per-PR unit tier), a daily
subprocess-driven tier under `tests/integration/golden_templates/`, and a
tiny standalone GitHub workflow that enforces the semver rule. The corpus
covers both LE and non-LE templates across four axes: SAM resources,
packageable CFN resources, LE intrinsics, and cross-cutting features.

The two tiers share `tests/golden/templates/` as their single corpus
source — the integration tier reads case directories straight from the
unit tier so authoring a new case lands in both places at once.

Success criteria for the change
-------------------------------

1. Every PR runs the corpus through an in-process build + package pipeline
   and fails on any byte-exact diff against pinned `expected.{build,package}.yaml`.
2. The daily integration-tests workflow runs the same corpus through real
   `sam` subprocess invocations and structurally compares the output.
3. Modifying or deleting an existing pin in a PR fails CI unless the same PR
   bumps the major version in `samcli/__init__.py`. Adding new pins is
   ungated.
4. A single regeneration script (`update_goldens.py`) is the canonical way
   to re-pin; the regenerator and the verifier share the harness so they
   cannot diverge.
5. The corpus is built incrementally as a series of independently-reviewable
   PRs, each ≤1000 LOC.

Out-of-Scope
------------

- No deploy step. The integration tier stops at packaged-template output
  — no CloudFormation, no real Lambdas.
- No CFN compatibility check (e.g. `cfn-lint`, `ValidateTemplate`) at this
  stage. The corpus pins what *SAM-CLI* produces; CFN-side parity is a
  separate exercise.
- No coverage of `sam local` runtime invocation paths. The bugs we're
  guarding against are template-shape bugs, not runtime bugs.
- No reorganization of existing
  `tests/integration/testdata/buildcmd/language-extensions-*` /
  `tests/integration/testdata/package/language-extensions-*` directories.
  The new corpus lives separately.

User Experience Walkthrough
---------------------------

A SAM-CLI contributor authoring a behavior-affecting change runs the existing
test suite and discovers one or more golden mismatches:

```
$ make test-all
...
tests/golden/test_corpus.py::test_build_output_matches_golden[language_extensions/foreach_static] FAILED

Golden mismatch in language_extensions/foreach_static.
To inspect:   python tests/golden/update_goldens.py --diff --filter 'language_extensions/foreach_static'
To re-pin:    python tests/golden/update_goldens.py --filter 'language_extensions/foreach_static'
If intentional:
  - new case (added expected.*.yaml)         -> no version bump at PR time
  - modified/deleted existing expected.*     -> bump major in samcli/__init__.py
```

The contributor inspects the diff:

```
$ python tests/golden/update_goldens.py --diff --filter 'language_extensions/foreach_static'
--- a/language_extensions/foreach_static/expected.build.yaml
+++ b/language_extensions/foreach_static/expected.build.yaml
@@ -...
-    Code: <<BUILT_ARTIFACT>>
+    Code:
+      ZipFile: ...
```

If the diff is intentional, the contributor re-pins, bumps the major version,
and ships. If unintentional, they fix their code and the test passes again.

Authoring a new case follows the same flow with `--new`:

```
$ python tests/golden/update_goldens.py --new --filter 'sam_resources/<new-case>'
```

Implementation
==============

CLI Changes
-----------

No `sam` CLI changes. New developer-facing CLIs:

- `python tests/golden/update_goldens.py [--filter GLOB] [--check | --diff | --new]`
- `python tests/golden/check_semver_bump.py --base REF --head REF`

### Breaking Change

None.

Design
------

### Repository layout

```
tests/golden/                                   # NEW
├── conftest.py                                 # parametrize over corpus dir
├── harness.py                                  # in-process build + package + diff
├── normalize.py                                # deterministic YAML rendering
├── update_goldens.py                           # regeneration CLI
├── check_semver_bump.py                        # semver gate
├── README.md                                   # author workflow
└── templates/
    ├── sam_resources/<case>/...                # SAM resource axis
    ├── packageable_resources/<case>/...        # CFN resource axis
    ├── language_extensions/<case>/...          # LE axis
    └── cross_cutting/<case>/...                # nested stacks, AWS::Include, etc.

tests/integration/golden_templates/              # NEW
├── test_golden_subprocess.py                   # imports tests/golden/templates as data
└── structural_compare.py                       # looser comparator for real-CLI output
```

The `tests/golden/templates/` directory is the single source of truth for
the corpus. Both the unit tier (`tests/golden/`) and the integration tier
(`tests/integration/golden_templates/`) read from it; nothing is duplicated.

The integration tier sits alongside the existing
`tests/integration/buildcmd/`, `tests/integration/package/`, and
`tests/integration/deploy/` suites. ``tests/regression/`` is reserved for
``sam`` vs ``aws cloudformation`` parity tests — a different semantic
that compares SAM CLI output against the AWS CLI's current output —
which is not what the golden corpus asserts. Goldens compare SAM CLI
against its own pinned past behavior, so they belong under
``tests/integration/``.

### Per-case directory layout

```
templates/<axis>/<case>/
├── template.yaml                               # input
├── metadata.yaml                               # language_extensions, description, issue_refs
├── expected.build.yaml                         # pinned post-build template
├── expected.package.yaml                       # pinned post-package template
├── README.md                                   # what this case covers and why
└── src/                                        # any source files referenced by CodeUri etc.
```

### The harness

Three functions, used by both pytest and `update_goldens.py`:

**`run_build_pipeline(template_path, language_extensions: bool) -> dict`**
mirrors `sam build`:

1. Read `template.yaml`.
2. Call `expand_language_extensions(template, enabled=language_extensions)`
   (the function PR #9033 made explicit).
3. Run the SAM transform.
4. Walk artifact properties using the JMESPath-aware machinery from PR #9009
   and replace any local artifact path with `<<BUILT_ARTIFACT>>`.
5. Apply the LE-aware merge with a stub artifact-set that mirrors what
   `ApplicationBuilder` would have produced (the three sites fixed in #9031).

**`run_package_pipeline(template_path, build_output) -> dict`**
mirrors `sam package`:

1. Run `_export_global_artifacts_pass` on the original template (the pre-LE
   AWS::Include pass added in PR #9030).
2. Walk packageable artifact properties and replace each local path with
   `s3://golden-bucket/<sha256-of-content>` — deterministic, content-addressed.
3. Re-run `_export_global_artifacts_pass` to catch AWS::Include nested in
   the LE-expanded template.

S3 is mocked via a thin `GoldenS3Uploader` class — no `moto`, no network,
no `boto3` stubbing.

**`normalize(template) -> str`** renders deterministic YAML:

- Sort `Resources` and `Mappings` keys alphabetically.
- Drop volatile `Metadata.SamTransformMetrics`.
- `yaml.safe_dump(..., sort_keys=True, default_flow_style=False)`.
- Single trailing newline.

The harness invokes the same high-level functions the CLI invokes; it does
not re-implement the pipeline. The integration tier verifies that contract
holds.

### Pytest collection

A single parametrize collects every case directory:

```python
def pytest_generate_tests(metafunc):
    if "golden_case" in metafunc.fixturenames:
        cases = sorted(p.parent for p in TEMPLATES_ROOT.rglob("template.yaml"))
        metafunc.parametrize(
            "golden_case",
            cases,
            ids=lambda p: str(p.relative_to(TEMPLATES_ROOT)),
        )
```

Each case becomes one parametrized test ID like
`language_extensions/foreach_static`, so `pytest -k foreach_static` works.

Two tests per case, one for build output and one for package output. Both
diff against the pinned file and emit the actionable hint shown in the UX
walkthrough on mismatch.

### Per-case `metadata.yaml`

Optional, defaults applied if absent:

```yaml
language_extensions: true
description: "Repro for #9027 — AWS::Include inside Fn::ToJsonString"
issue_refs: [9027]
```

Default for `language_extensions`: `true` for cases under
`templates/language_extensions/`, `false` elsewhere — matching the
post-#9033 opt-in default.

### The regeneration script

Single CLI, thin wrapper around the same harness functions the tests use:

- *(default, no args)* — regenerate every case.
- `--filter <glob>` — regenerate only matching cases.
- `--check` — dry-run; exit non-zero if anything would change. CI mode.
- `--diff` — like `--check`, also print unified diff of each would-be
  change.
- `--new` — for cases with `template.yaml` but no `expected.*` yet,
  generate both pinned outputs from scratch.

By construction the regenerator and the verifier share the harness, so they
can never diverge.

### The semver gate

Tiny standalone GitHub workflow at
`.github/workflows/golden-semver-gate.yml`. Runs on every PR; the script
itself returns exit 0 when no corpus pins changed, so it's cheap to run
unconditionally and posts a definitive status on every PR (which lets
branch protection mark it as a required check without blocking
unrelated PRs):

```yaml
on:
  pull_request:
    branches: [develop, "feat/*", "feat-*"]
```

The workflow does *not* use `on.pull_request.paths:` filtering. Path
filtering at the trigger level skips the workflow entirely on PRs that
touch no matching path — no status posts, and a required check that
never reports gets treated by branch protection as missing/pending.
Self-gating in the script (return 0 when there are no relevant changes)
is the simpler fix and keeps the check eligible to be required.

`check_semver_bump.py` rules:

1. Diff merge base vs HEAD; collect changes to
   `tests/golden/templates/**/expected.*.yaml`.
2. Classify each:
   - **Added** — no version requirement at PR time.
   - **Modified** or **Deleted** — requires major bump in this same PR.
3. Read `__version__` from `samcli/__init__.py` on base and head.
4. If any modification or deletion exists, require `head.major > base.major`.
5. On failure, print the changed goldens, current vs. required version, and
   the suggested new version string.

A rename (delete-old + add-new) is treated as one deletion + one addition →
requires a major bump. Conservative on purpose: a rename usually means
reorganization but could mask a content edit, so we make the human
acknowledge it.

#### Why additions don't require a per-PR minor bump

The project's existing release process bumps the version in a dedicated
release PR (e.g. #9051 `chore: bump version to 1.161.1`). Forcing a minor
bump on every corpus-addition PR would either churn that release process
or require funnelling the corpus rollout through a single feature branch.
Neither is worth the friction. The gate enforces the only invariant that
actually matters at PR time: *a behavior change to an existing pin must
ship as a major version*. New cases simply broaden coverage and have no
backwards-compatibility implication.

### Per-PR CI wiring

`make pr` already invokes `pytest tests/unit/...`. We extend the `test` and
`test-all` Makefile targets to include `tests/golden/` as a separate pytest
invocation (so it doesn't enter the 94% coverage calculation against
`samcli/`). The harness is in-process, deterministic, and offline —
estimated <30s for ~50 cases. The existing Windows `TEMP=D:\Temp` shim
already handles temp-dir contention. No new workflow file (the semver gate
above is its own workflow, but the corpus tests ride on `build.yml`).

### Integration tier

Daily run on the existing `integration-tests.yml` workflow's matrix
(one new entry: `golden-templates`). The suite sits alongside the
existing `tests/integration/buildcmd/`, `tests/integration/package/`,
and `tests/integration/deploy/` directories — all subprocess-driven
``sam`` invocations against real AWS resources.

We deliberately do **not** put this under ``tests/regression/``. The
existing ``tests/regression/`` suites are ``sam`` vs
``aws cloudformation`` parity tests — they assert SAM CLI's output
matches AWS CLI's *current* output. Goldens assert the opposite: SAM
CLI's output matches its own *pinned past* output. Different semantics;
sharing a directory would invite future contributors to confuse the
two.

Per case:

1. Copy case dir to a temp working dir; copy `src/`.
2. `sam build [--language-extensions]` subprocess; assert exit 0; read
   `.aws-sam/build/template.yaml`.
3. `sam package --s3-bucket <test-bucket> --output-template-file packaged.yaml`
   subprocess; assert exit 0; read `packaged.yaml`.
4. Structurally compare against the pinned `expected.{build,package}.yaml`:
   - Same set of resource logical IDs.
   - Same `Type` per ID.
   - Same set of property keys at each path.
   - Same `Outputs` and `Mappings` keys.
   - For LE-relevant artifact properties (`Code`, `CodeUri`, `ContentUri`,
     `DefinitionUri`, `Location`, `Command.ScriptLocation`, etc.) flag
     dict-vs-string differences (the #9029 bug class).

The comparator lives in
`tests/integration/golden_templates/structural_compare.py` and is reused
for both build and package outputs.

#### Why structural, not byte-exact

Real `sam build` writes timestamps, real S3 URIs, real artifact hashes.
Byte-exact pinning at this tier would either require the same normalization
the in-process tier uses (defeats the purpose — we want to see the real
output) or constant churn from environmental noise. Structural comparison
answers "did the user-visible output shape change?" — which is what catches
the four bugs we just fixed.

If the unit tier passes but the integration tier fails for a case, the
in-process harness has drifted from the CLI surface — investigation, not
a re-pin.

### Wave plan

Each PR is independently reviewable; LOC estimates are upper-bound net diff.

- **PR 0** (this design doc).
- **PR 1** — Harness skeleton, three sentinel cases, semver gate workflow.
- **PR 2** — Integration-tier subprocess runner under
  `tests/integration/golden_templates/`. Adds a new `golden-templates`
  entry to the existing `integration-tests.yml` matrix.
- **PR 3** — SAM resources axis: Function variants (~10 cases).
- **PR 4** — SAM resources axis: Api / HttpApi / StateMachine / others
  (~10 cases).
- **PR 5** — Packageable CFN resources axis (~12 cases). One per entry in
  `RESOURCES_WITH_LOCAL_PATHS` + `RESOURCES_WITH_IMAGE_COMPONENT` not
  already covered. Catches #9009-class drift; locks every dotted artifact
  path.
- **PR 6** — LE intrinsics: `Fn::ForEach` (~10 cases).
- **PR 7** — LE intrinsics: non-ForEach + bug repros (~10 cases). Each
  metadata.yaml carries the issue ref.
- **PR 8** — Cross-cutting: nested stacks, Globals, Mappings, Conditions
  (~10 cases).
- **PR 9** — Cross-cutting: AWS::Include, SAR Metadata, Unicode (~7 cases).
  Final corpus README listing the full coverage matrix.

#### Wave invariants

- PRs 2–9 are additions only under `tests/golden/templates/`, so the
  semver gate passes without any version bump.
- Every case carries `metadata.yaml` with `description` and `issue_refs`.
- No PR after PR 1 modifies harness behavior unless a wave reveals a
  missing capability; if so, the harness change is its own follow-up PR.

`samconfig.toml` Changes
----------------

None.

Security Considerations
-----------------------

The harness intentionally invokes only in-process SAM-CLI code; no
network calls, no credentials, no AWS API access. The integration tier
uses the existing integration-tests workflow's IAM role and S3 bucket;
no new permissions required.

Documentation Changes
---------------------

`tests/golden/README.md` — authoring guide for contributors adding new
cases or re-pinning existing ones.

Alternatives considered
=======================

Subprocess-only harness (no in-process)
---------------------------------------

Every golden runs the real `sam` CLI as a subprocess. Rejected: process
startup × N templates is too slow for a per-PR gate; flakier on Windows;
deterministic package output without `moto` is hard. Subprocess invocation
is kept, but only at the daily integration tier where speed and
determinism matter less.

Snapshot plugin (`syrupy`, `pytest-snapshot`)
---------------------------------------------

Less harness code to write. Rejected: opaque snapshot format hurts
code-review readability; update flow is plugin-specific; corpus growth
across many PRs is harder when snapshots are plugin-managed rather than
plain YAML files in the case directory.

CFN-side validation (`cfn-lint` or `ValidateTemplate`)
------------------------------------------------------

Would catch SAM-CLI vs CFN divergence. Rejected for now: out of scope for
this design; can be added as a separate compatibility tier later. The
current bugs are SAM-CLI's own output-shape bugs, not CFN-divergence bugs.

Per-PR minor bump on every corpus-addition PR
---------------------------------------------

Initially considered. Rejected: would either churn the existing
release-PR process (e.g. #9051) or require funnelling the corpus rollout
through a single feature branch. The gate's only PR-time invariant is
that *behavior changes* require major bumps; coverage growth is
backwards-compatible by definition.
