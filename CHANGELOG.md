# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Renamed the package from `qris` to `qriskit`**: `pip install qriskit`, `import qriskit`, and the `qriskit` command. "QRIS" is a registered trademark of Bank Indonesia; the new name makes clear that this is an unofficial toolkit. `qris` was never published to PyPI.

## [0.1.0]

### Added

- `qriskit.parse`, `qriskit.validate`, `qriskit.is_valid` with stable issue codes.
- `QRIS.to_dynamic` (amount, tip or convenience fee, reference), `QRIS.to_static`, `QRIS.with_tag`, `QRIS.without_tag`.
- `qriskit.build` for creating payloads from scratch.
- Acquirer lookup from NNS codes, based on Bank Indonesia's public list.
- `qriskit.anonymize` for sharing payloads safely.
- Optional PNG/SVG rendering via `pip install "qriskit[image]"`.
- `qriskit` command line tool.
