# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-24

### Added

- `qriskit.scan` and `qriskit.scan_all` read QRIS from photos and screenshots (`pip install "qriskit[scan]"`), with `qriskit.QRISScanError` reasons `no_qr`, `no_qris`, `multiple_qris`, `unreadable_image` and `image_too_large`.
- `qriskit scan` command, which can be piped into the other commands.

### Fixed

- Payloads containing characters that cannot be encoded as UTF-8 now raise `QRISParseError` instead of crashing `validate()` and `is_valid()`.

## [0.1.0] - 2026-09-24

### Added

- `qriskit.parse`, `qriskit.validate`, `qriskit.is_valid` with stable issue codes.
- `QRIS.to_dynamic` (amount, tip or convenience fee, reference), `QRIS.to_static`, `QRIS.with_tag`, `QRIS.without_tag`.
- `qriskit.build` for creating payloads from scratch.
- Acquirer lookup from NNS codes, based on Bank Indonesia's public list.
- `qriskit.anonymize` for sharing payloads safely.
- Optional PNG/SVG rendering via `pip install "qriskit[image]"`.
- `qriskit` command line tool.

[Unreleased]: https://github.com/MFaizR77/qris-python/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/MFaizR77/qris-python/releases/tag/v0.2.0
