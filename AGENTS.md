# House rules for agents working on ChemGlyph

1. Identity: commit as `random-orbit <305297779+random-orbit@users.noreply.github.com>`.
   Never introduce real names, personal emails, or other PII into files,
   commit messages, or published text. Refer to the redacted mailbox as
   `<redacted-email>`.
2. Commits: subagents write files only. The lead agent reviews, integrates,
   commits, and pushes. Do not run `git commit` or `git push` without the
   lead's approval, and never rewrite history on your own.
3. Writing: anything public (README, docs, launch posts, PR bodies and
   comments, PyPI metadata) must read like a person wrote it. No AI-flavored
   writing: avoid em-dashes and empty superlatives, write plain direct
   sentences, use lists only when they carry information, and proofread
   every outgoing text before publishing.
4. Scope: keep changes minimal and within the assigned task. Add tests for
   behavior changes and keep `ruff check`, `ruff format`, and the test suite
   green.
