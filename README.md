# PKGBUILDs

My AUR packages, with some scripts to help with updating them.

## Usage

With [direnv](https://direnv.net/) installed and integrated into your shell, the environment activates automatically; otherwise run `devenv shell` first.

Everything goes through one entry point, `tools/cli.py`:

```sh
python tools/cli.py sync                  # rebuild nvchecker.toml from the update.toml files
nvchecker --failures -c nvchecker.toml
nvcmp -j -s none -c nvchecker.toml > /tmp/updates.json
python tools/cli.py apply --input /tmp/updates.json --applied-output /tmp/applied.txt
python tools/cli.py srcinfo --packages-file /tmp/applied.txt
python -m unittest discover -s tests
python tools/cli.py verify
```

`python tools/cli.py --help` lists every command. `publish` pushes updated packages to the AUR and takes `--dry-run`, which is the easiest way to rehearse a release:

```sh
python tools/cli.py publish --packages-file /tmp/applied.txt --work-dir /tmp/aur --dry-run
```

`verify` is the safety net. Per package it checks that the PKGBUILD parses and is `shfmt`-clean, that `pkgname` matches the directory name (the AUR push relies on it), that `.SRCINFO` is regenerated from the PKGBUILD, that `update.toml` is valid for its updater, and that the `source` arrays still match what `update.toml` would generate — so a hand edit cannot be silently reverted by the next run. `--require-makepkg` turns the `.SRCINFO` check from best-effort into mandatory; CI always passes it.

## Adding a package

1. Create the package directory with its `PKGBUILD` and a `.gitignore` matching `tools/templates.py`.
2. Add an `update.toml` beside it: a `[check]` table (passed through to nvchecker) and an `[update]` table selecting one of the updaters in `tools/updaters/`.
3. Run `python tools/cli.py sync` — packages are discovered automatically, nothing else to register.

Checksums are never configured. The declarative updater writes the `source` entries first, asks bash what they expand to, and hashes exactly those URLs, so `sha256sums` always describes what makepkg will download.

## Layout

```
tools/
  cli.py            single entry point; the only sys.path bootstrap in the tree
  packages.py       package discovery and update.toml validation
  commands/         one module per subcommand
  updaters/         one module per updater, plus the registry and the base contract
  common/           PKGBUILD text edits, bash evaluation, downloads, version transforms
  debian/           Debian version comparison, control parsing, repository access
  templates.py      files generated verbatim for every package
```

Adding an updater means writing one module in `tools/updaters/` that parses its own configuration and applies it, then registering it in `tools/updaters/__init__.py`.

## License

[MIT](LICENSE)
