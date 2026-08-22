# PKGBUILDs

My AUR packages, with some scripts to help with updating them.

## Packages

- [deepin-wine10-stable](deepin-wine10-stable)
- [hfd-git](hfd-git)
- [serenity-bin](serenity-bin)
- [spark-store-console-bin](spark-store-console-bin)
- [xwayclip](xwayclip)
- [xwayclip-bin](xwayclip-bin)
- [xwayclip-git](xwayclip-git)

## Usage

With [direnv](https://direnv.net/) installed and integrated into your shell, the environment will activates automatically; otherwise run `devenv shell` first.

```sh
nvchecker --failures -c nvchecker.toml
nvcmp -j -s none -c nvchecker.toml > /tmp/updates.json
python tools/apply_updates.py --input /tmp/updates.json --applied-output /tmp/applied.txt
python tools/generate_srcinfo.py --packages-file /tmp/applied.txt
python -m unittest discover -s tests
python tools/verify.py
```

## License

[MIT](LICENSE)
