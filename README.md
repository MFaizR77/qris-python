# qris

[![PyPI](https://img.shields.io/pypi/v/qris)](https://pypi.org/project/qris/)
[![Python](https://img.shields.io/pypi/pyversions/qris)](https://pypi.org/project/qris/)
[![CI](https://github.com/MFaizR77/qris-python/actions/workflows/ci.yml/badge.svg)](https://github.com/MFaizR77/qris-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Parse, validate, build and convert **QRIS** (Quick Response Code Indonesian Standard) payloads in Python.
Zero dependencies, fully typed, Python 3.9+ on every OS.

> **Unofficial.** This project is not affiliated with Bank Indonesia or ASPI.

```python
import qris

q = qris.parse(payload)                    # the text inside a QRIS sticker
q.merchant_name, q.nmid                    # 'TOKO CONTOH', 'ID1020012345678'
q.merchant_accounts[0].acquirer.name       # 'GoPay'

d = q.to_dynamic(25_000, reference="INV-2026-001")
d.dumps()                                  # new payload, CRC recomputed
```

## Install

```bash
pip install qris              # core, no dependencies
pip install "qris[image]"     # + PNG/SVG rendering (segno)
```

## What it does

- **Parse** any QRIS / EMVCo merchant-presented payload into typed, immutable objects.
  `parse(s).dumps() == s` for every valid payload: tag order and unknown tags are preserved.
- **Validate** against QRIS rules and get *all* problems at once, each with a stable code.
- **Convert** static to dynamic (amount, tip or convenience fee, reference number) and back.
- **Build** payloads from scratch for tests and demos.
- **Identify the acquirer** from the NNS code, using Bank Indonesia's public list.
- **Render** PNG/SVG QR codes (optional extra).
- **Anonymize** payloads so they can be shared in bug reports.
- A small **CLI**: `qris decode | validate | dynamic | static | image | anonymize`.

## Usage

### Read

```python
q = qris.parse(payload)          # raises qris.QRISParseError only if the structure is broken
q.point_of_initiation            # 'static' or 'dynamic'
q.amount                         # Decimal('25000') or None
q.tip                            # Tip(kind='fixed', value=Decimal('1000')) or None
q.additional_data.terminal_label # the TID printed on the sticker
q.get("62.05")                   # raw value of any tag or sub-tag
q.to_dict()                      # JSON-friendly summary
```

### Validate

```python
for issue in qris.validate(payload):
    print(issue.severity, issue.code, issue.path, issue.message)
# error crc.mismatch 63 CRC is 0000, expected 3ACC

qris.is_valid(payload)           # True / False, never raises
qris.parse(payload, strict=True) # raises qris.QRISValidationError on any error
```

Errors mean the QRIS will probably fail to pay; warnings are deviations that usually still work.

| Error codes | Warning codes |
|---|---|
| `pfi.invalid`, `crc.missing`, `crc.not_last`, `crc.mismatch`, `tag.required`, `tag.duplicate`, `tag.format`, `tag.length`, `template.malformed`, `poi.invalid`, `merchant_account.missing`, `currency.invalid`, `country.invalid`, `amount.invalid`, `tip.invalid`, `tip.value_missing`, `tip.orphan_value` | `crc.lowercase`, `tag.order`, `postal_code.missing`, `national.missing`, `amount.on_static`, `amount.missing_on_dynamic` |

Codes are part of the public API and will not change in minor releases.

### Convert

```python
from decimal import Decimal
from qris import Tip

q.to_dynamic(25_000)
q.to_dynamic("15000.50", tip=Tip.fixed(1_000))
q.to_dynamic(Decimal("50000"), tip=Tip.percent("2.5"), reference="INV-1")
q.to_dynamic(10_000, tip=Tip.prompt())
d.to_static()

q.with_tag("62.07", "KASIR-01")  # set any tag or sub-tag
q.without_tag("61")
```

Amounts accept `int`, `str` or `Decimal`. Floats are rejected because they are imprecise for money.
Conversion refuses a source whose CRC is missing or wrong, so a corrupted payload is never "repaired" into a valid-looking one.

### Build

```python
from qris import MerchantAccount

q = qris.build(
    merchant_name="TOKO CONTOH",
    merchant_city="JAKARTA",
    postal_code="10110",
    mcc="5812",
    accounts=[
        MerchantAccount.create(tag="26", guid="COM.GO-JEK.WWW", pan="9360091412345678901",
                               merchant_id="G123456789", criteria="UMI"),
        MerchantAccount.national(nmid="ID1020012345678", criteria="UMI"),
    ],
)
```

`build()` is for tests, sandboxes and demos. A payable QRIS needs a merchant registered with an acquirer.

### Images

```python
from qris import image

image.save(q, "qris.png")        # or .svg
png_bytes = image.to_png(q)
```

ASPI requires QR codes of at least 115×115 px; smaller PNGs emit a `qris.QRISWarning`.

### Command line

```bash
qris decode "0002010102..."
qris validate - < payload.txt          # exit code 1 when there are errors
qris dynamic "0002010102..." --amount 25000 --fee 1000 --reference INV-1
qris image "0002010102..." -o qris.png
qris anonymize "0002010102..."         # safe to paste into an issue
```

## FAQ

**How do I get the payload text?** Scan the QRIS image with any plain QR reader (Google Lens, `zbarimg`) and copy the text. Do not use a banking app; it pays instead of showing the text.

**Can a QRIS expire after N minutes?** No. Expiry is not part of the QRIS specification; it is handled by your backend or payment gateway.

**How do I know a QRIS was paid?** That needs your acquirer's API or notifications. This library works offline on the payload only.

**Why does app X reject my converted QRIS?** Acceptance is decided by the paying app. Some issuers reject payloads that were changed from static to dynamic. A reference number you add may also not appear in the merchant's statement, because the acquirer did not issue it.

## Responsible use

A QRIS payload does not prove who owns it. Show the merchant name and NMID to payers, only accept QRIS from trusted sources, and never use this library to impersonate a merchant. There is deliberately no helper for changing the merchant name.

## Contributing test vectors

Real-world payloads make this library better. Anonymize first, then open an issue or pull request with the result:

```bash
qris anonymize "<your QRIS text>"
```

This keeps the structure, NNS, GUIDs and amounts, and replaces names, cities, IDs and NMID.
Vectors live in `tests/vectors/*.json`; adding a file is enough, no code change is needed.

## Development

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest --cov
ruff check src tests && ruff format --check src tests && mypy
```

## License

MIT. Acquirer data comes from Bank Indonesia's public list (see `src/qris/data/nns.json`).
