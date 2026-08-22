# PKGBUILDs

My AUR packages, with some scripts to help with updating them.

## Usage

With [direnv](https://direnv.net/) installed and integrated into your shell, the environment will activates automatically; otherwise run `devenv shell` first.

```sh
python tools/sync_nvchecker.py
nvchecker --failures -c nvchecker.toml
nvcmp -j -s none -c nvchecker.toml > /tmp/updates.json
python tools/apply_updates.py --input /tmp/updates.json --applied-output /tmp/applied.txt
python tools/generate_srcinfo.py --packages-file /tmp/applied.txt
python -m unittest discover -s tests
python tools/verify.py
```

## Adding a package

1. Create the package directory with its `PKGBUILD`.
2. Add an `update.toml` beside it: a `[check]` table (passed through to nvchecker) and an `[update]` table selecting one of the updaters in `tools/updaters/`.
3. Run `python tools/sync_nvchecker.py` — packages are discovered automatically, nothing else to register.

## License

[MIT](LICENSE)
