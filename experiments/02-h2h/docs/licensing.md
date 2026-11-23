# Licensing: H2H

How H2H stays safe to adopt for a company that audits the copyright and licences of what it runs.

This is a working policy based on common practice. It is not legal advice, and a company's own legal team has the final say for its use.

## Goal

A company should be able to run a licence audit on H2H and its dependencies and find nothing that stops it from using H2H internally or shipping it inside its own workflow. Two rules serve that:

- **No copied code.** H2H is a clean-room build; see [prior-art.md](prior-art.md).
- **Only permissively licensed dependencies,** as set out below.

## Dependencies

| Licence | Use in H2H | Why |
|---|---|---|
| MIT, BSD 2-Clause, BSD 3-Clause, ISC, Apache-2.0 | Allowed | Permissive. They ask for attribution and, for Apache-2.0, a notice file. Accepted by almost every corporate policy |
| Unlicense, CC0, 0BSD | Allowed | Public-domain style. Some policies ask for review, so prefer an alternative under the licences above when one exists |
| MPL-2.0 | Avoid. Allowed only when no permissive alternative exists, recorded with the reason | Weak copyleft at file level. Usually acceptable, but it adds a condition an auditor has to assess |
| LGPL | Not allowed | Go links statically, which makes the LGPL's relinking terms hard to meet |
| GPL, AGPL | Not allowed | Copyleft that can extend to the whole binary. Many companies ban AGPL outright |
| SSPL, BUSL, Elastic, Commons Clause and other source-available licences | Not allowed | Not open source, with limits on commercial use |
| No licence, or a custom or unclear one | Not allowed | With no licence there is no permission to use the code at all |

Further rules:

- **Fewer dependencies.** The Go standard library is the first choice. A dependency is added only for something that would be costly or risky to write, such as a pseudo-terminal or a database library.
- **Transitive dependencies count.** A library is judged by everything it pulls in.
- **Embedded files count.** Web UI assets, fonts and icons built into the binary follow the same rules.
- **Maintained and widely used.** A dependency should have an active maintainer and real adoption, so a licence change or abandonment is less likely to strand H2H.
- **Recorded.** Each dependency is listed with its version, licence and the reason it is needed.

## Enforcement

A rule that is not checked drifts. From the first build:

- **A licence check in the build.** It fails when a dependency, direct or transitive, has a licence outside the allowed list.
- **A notices file in every release,** listing each dependency with its licence text, as the permissive licences require.
- **A software bill of materials** per release, so a company's audit can start from a list instead of the source.
- **Review on change.** Adding or upgrading a dependency shows its licence in the change, because a new version can change licence.

The tools for these checks are not chosen yet. They must meet the same licence rules.

## Contributions and generated code

- **Contributions** come under H2H's own licence, with the contributor confirming they have the right to submit the code.
- **Code written by harnesses** during development follows the clean-room rule like any other: it must not reproduce another project's code. Suggestions that look like a copy of an existing project are rejected.

## Open questions

- **H2H's own licence.** H2H will be released under an open-source licence that companies accept. Apache-2.0 is proposed: it is permissive, widely approved by corporate policies, and includes a patent grant, which MIT does not. Not final until a `LICENSE` file is added.
- **Harnesses are not dependencies.** Claude Code, Copilot and Codex are separate products the user installs and licenses. H2H starts them and does not ship them. Whether an audit still wants them listed is unknown.
- **Runtime protocols.** Using a published protocol such as MCP or A2A is use of a specification, not of code. Any library used to speak it falls under the dependency rules.
