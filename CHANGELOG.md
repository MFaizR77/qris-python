# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0]

### Added

- `qris.parse`, `qris.validate`, `qris.is_valid` with stable issue codes.
- `QRIS.to_dynamic` (amount, tip or convenience fee, reference), `QRIS.to_static`, `QRIS.with_tag`, `QRIS.without_tag`.
- `qris.build` for creating payloads from scratch.
- Acquirer lookup from NNS codes, based on Bank Indonesia's public list.
- `qris.anonymize` for sharing payloads safely.
- Optional PNG/SVG rendering via `pip install "qris[image]"`.
- `qris` command line tool.
