"""Command line interface: ``qris <command> ...`` or ``python -m qris <command> ...``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import TextIO

from . import __version__
from .anonymize import anonymize
from .errors import QRISError
from .model import QRIS, Tip
from .validate import parse, validate

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code."""
    args = _parser().parse_args(argv)
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        # Merchant names may contain characters the console encoding cannot show.
        out.reconfigure(errors="replace")
    try:
        code: int = args.handler(args, out)
    except (QRISError, ValueError, TypeError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    return code


def _read(payload: str) -> QRIS:
    return parse(sys.stdin.read() if payload == "-" else payload)


def _decode(args: argparse.Namespace, out: TextIO) -> int:
    qris = _read(args.payload)
    if args.json:
        print(json.dumps(qris.to_dict(), indent=2, ensure_ascii=False), file=out)
    else:
        print(format_summary(qris), file=out)
    return EXIT_OK


def _validate(args: argparse.Namespace, out: TextIO) -> int:
    issues = validate(_read(args.payload))
    if args.json:
        rows = [
            {"code": i.code, "severity": i.severity, "path": i.path, "message": i.message}
            for i in issues
        ]
        print(json.dumps(rows, indent=2), file=out)
    elif issues:
        for issue in issues:
            print(issue, file=out)
    else:
        print("OK: no issues found", file=out)
    return EXIT_INVALID if any(i.severity == "error" for i in issues) else EXIT_OK


def _dynamic(args: argparse.Namespace, out: TextIO) -> int:
    tip: Tip | None = None
    if args.tip:
        tip = Tip.prompt()
    elif args.fee is not None:
        tip = Tip.fixed(args.fee)
    elif args.fee_percent is not None:
        tip = Tip.percent(args.fee_percent)
    result = _read(args.payload).to_dynamic(args.amount, tip=tip, reference=args.reference)
    print(result.dumps(), file=out)
    return EXIT_OK


def _static(args: argparse.Namespace, out: TextIO) -> int:
    print(_read(args.payload).to_static().dumps(), file=out)
    return EXIT_OK


def _image(args: argparse.Namespace, out: TextIO) -> int:
    from .image import save

    save(_read(args.payload), args.output, scale=args.scale)
    print(f"Saved {args.output}", file=out)
    return EXIT_OK


def _anonymize(args: argparse.Namespace, out: TextIO) -> int:
    print(anonymize(_read(args.payload), seed=args.seed).dumps(), file=out)
    return EXIT_OK


def format_summary(qris: QRIS) -> str:
    """Human-readable table used by ``qris decode``."""
    place = " ".join(p for p in (qris.merchant_city, qris.postal_code) if p)
    rows = [("Merchant", (qris.merchant_name or "-") + (f" ({place})" if place else ""))]
    rows.append(("NMID", qris.nmid or "-"))
    if qris.additional_data.terminal_label:
        rows.append(("TID", qris.additional_data.terminal_label))
    rows.append(("Type", qris.point_of_initiation or "unknown"))
    rows.append(("Currency", "IDR (360)" if qris.currency == "360" else qris.currency or "-"))
    if qris.amount is not None:
        rows.append(("Amount", str(qris.amount)))
    tip = qris.tip
    if tip is not None:
        rows.append(("Tip", tip.kind + ("" if tip.value is None else f" {tip.value}")))
    if qris.additional_data.reference_label:
        rows.append(("Reference", qris.additional_data.reference_label))
    for index, account in enumerate(qris.merchant_accounts):
        if account.is_national:
            detail = f"NMID {account.merchant_id or '-'}"
        elif account.nns:
            acquirer = account.acquirer
            detail = f"NNS {account.nns}" + (f" ({acquirer})" if acquirer else "")
        else:
            detail = ""
        line = f"{account.tag}  {account.guid or '-':<22} {detail}".rstrip()
        rows.append(("Accounts" if index == 0 else "", line))
    expected = qris.dumps()[-4:]
    if qris.crc is None:
        crc = "missing"
    elif qris.crc.upper() == expected:
        crc = f"{qris.crc} OK"
    else:
        crc = f"{qris.crc} MISMATCH (expected {expected})"
    rows.append(("CRC", crc))
    return "\n".join(f"{label:<13} {value}" for label, value in rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qris", description="Inspect, validate and convert QRIS payloads."
    )
    parser.add_argument("--version", action="version", version=f"qris {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    help_payload = "QRIS payload text, or - to read it from stdin"

    decode = commands.add_parser("decode", help="show what a QRIS contains")
    decode.add_argument("payload", help=help_payload)
    decode.add_argument("--json", action="store_true", help="print JSON")
    decode.set_defaults(handler=_decode)

    check = commands.add_parser("validate", help="list rule violations (exit 1 on errors)")
    check.add_argument("payload", help=help_payload)
    check.add_argument("--json", action="store_true", help="print JSON")
    check.set_defaults(handler=_validate)

    dynamic = commands.add_parser("dynamic", help="print a dynamic QRIS with an amount")
    dynamic.add_argument("payload", help=help_payload)
    dynamic.add_argument("--amount", required=True, help="e.g. 25000 or 15000.50")
    fee = dynamic.add_mutually_exclusive_group()
    fee.add_argument("--tip", action="store_true", help="ask the payer for a tip")
    fee.add_argument("--fee", help="fixed convenience fee")
    fee.add_argument("--fee-percent", help="percentage convenience fee (0.01-99.99)")
    dynamic.add_argument("--reference", help="invoice/order number (tag 62.05, max 25 chars)")
    dynamic.set_defaults(handler=_dynamic)

    static = commands.add_parser("static", help="print a static QRIS without amount")
    static.add_argument("payload", help=help_payload)
    static.set_defaults(handler=_static)

    image = commands.add_parser("image", help='save a PNG or SVG (needs "qris[image]")')
    image.add_argument("payload", help=help_payload)
    image.add_argument("-o", "--output", required=True, help="file ending in .png or .svg")
    image.add_argument("--scale", type=int, default=10, help="pixels per module (default 10)")
    image.set_defaults(handler=_image)

    anon = commands.add_parser("anonymize", help="replace merchant data for safe sharing")
    anon.add_argument("payload", help=help_payload)
    anon.add_argument("--seed", type=int, default=0, help="same seed, same output")
    anon.set_defaults(handler=_anonymize)
    return parser
