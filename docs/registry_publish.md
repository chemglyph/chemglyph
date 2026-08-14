# Publishing ChemGlyph to the official MCP registry

Status: published. `io.github.random-orbit/chemglyph` version `0.1.1` is live
in the official registry (verified via the public v0 API on 2026-08-14).
The registry is in preview; its flow may change.

## What already exists

- `server.json` at the repo root declares the server as a PyPI package
  (`registryType: pypi`, identifier `chemglyph`) with stdio transport.
- The README contains the ownership marker
  `<!-- mcp-name: io.github.random-orbit/chemglyph -->`. The registry checks
  for this string in the published PyPI description, so it must ship in a
  PyPI release.
- Version bumped to `0.1.1` in `pyproject.toml` for that release.

## Steps

1. Create a new PyPI API token (the previous one was revoked), then:

   ```bash
   TWINE_USERNAME='__token__' TWINE_PASSWORD='pypi-...' \
     .venv/bin/python -m build
   TWINE_USERNAME='__token__' TWINE_PASSWORD='pypi-...' \
     .venv/bin/twine upload dist/chemglyph-0.1.1*
   ```

2. Install the publisher CLI (Homebrew or the release binary):

   ```bash
   brew install mcp-publisher
   ```

3. Log in with the GitHub account that owns the repository. This is a
   device-code flow: run the command, open the printed URL in any browser,
   enter the printed code, and authorize.

   ```bash
   mcp-publisher login github
   ```

4. Validate and publish from the repository root:

   ```bash
   mcp-publisher validate
   mcp-publisher publish
   ```

## Notes

- GitHub auth grants the `io.github.random-orbit/*` namespace. Publishing
  under `io.github.chemglyph/*` instead would require the authenticated
  account to be an Owner of the chemglyph GitHub organization.
- If the `validate` step rejects a field, adjust `server.json` against the
  schema URL in it and re-validate.
- Registry entries host metadata only; the actual install stays
  `pip install chemglyph`.
- Authentication was completed with the GitHub account already logged into
  the `gh` CLI (`mcp-publisher login github -token ...`). Run
  `mcp-publisher logout` to clear the saved session.
