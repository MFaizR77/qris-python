"""Parsing entry points and QRIS rule checks. Issue codes are listed in ``Referensi/Kode Issue``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from . import spec, tlv
from ._money import MAX_PERCENT, parse_decimal
from .crc import crc16
from .errors import Issue, QRISParseError, QRISValidationError
from .model import QRIS, children_of, parse_payload
from .tlv import Node


def parse(payload: str, *, strict: bool = False) -> QRIS:
    """Read a QRIS payload.

    Only broken tag-length-value structure raises :class:`QRISParseError`. Rule
    violations are reported by :func:`validate`; with ``strict=True`` any error
    raises :class:`QRISValidationError` instead.
    """
    qris = parse_payload(payload)
    if strict:
        issues = validate(qris)
        if any(issue.severity == "error" for issue in issues):
            raise QRISValidationError(issues)
    return qris


def validate(payload: str | QRIS) -> list[Issue]:
    """Return every rule violation, errors and warnings, in a stable order."""
    qris = payload if isinstance(payload, QRIS) else parse_payload(payload)
    nodes = qris.nodes
    issues: list[Issue] = []
    _check_format_indicator(nodes, issues)
    issues.extend(crc_issues(qris))
    _check_structure(nodes, issues)
    _check_required(nodes, issues)
    _check_values(qris, issues)
    return issues


def is_valid(payload: str | QRIS) -> bool:
    """True if the payload parses and has no error-level issues. Never raises."""
    try:
        return not any(issue.severity == "error" for issue in validate(payload))
    except (QRISParseError, TypeError):
        return False


def _error(code: str, path: str | None, message: str) -> Issue:
    return Issue(code, "error", path, message)


def _warning(code: str, path: str | None, message: str) -> Issue:
    return Issue(code, "warning", path, message)


def crc_issues(qris: QRIS) -> list[Issue]:
    """CRC checks only: missing, not last, mismatch, lowercase."""
    nodes = qris.nodes
    index = next((i for i, node in enumerate(nodes) if node.tag == spec.TAG_CRC), None)
    if index is None:
        return [_error("crc.missing", spec.TAG_CRC, "CRC (tag 63) is missing")]
    issues: list[Issue] = []
    if index != len(nodes) - 1:
        issues.append(_error("crc.not_last", spec.TAG_CRC, "CRC (tag 63) must be the last element"))
    actual = nodes[index].value
    expected = crc16(tlv.encode(nodes[:index]) + spec.TAG_CRC + "04")
    if len(actual) != 4 or not all(c in "0123456789abcdefABCDEF" for c in actual):
        issues.append(
            _error("crc.mismatch", spec.TAG_CRC, f"CRC {actual!r} is not 4 hexadecimal characters")
        )
    elif actual.upper() != expected:
        issues.append(_error("crc.mismatch", spec.TAG_CRC, f"CRC is {actual}, expected {expected}"))
    elif actual != expected:
        issues.append(_warning("crc.lowercase", spec.TAG_CRC, f"CRC {actual} should be uppercase"))
    return issues


def _check_format_indicator(nodes: Sequence[Node], issues: list[Issue]) -> None:
    tags = [node.tag for node in nodes]
    if spec.TAG_PFI not in tags:
        message = "Payload Format Indicator (tag 00) is missing"
    elif tags[0] != spec.TAG_PFI:
        message = "Payload Format Indicator (tag 00) must be the first element"
    elif nodes[0].value != "01":
        message = f"Payload Format Indicator must be '01', got {nodes[0].value!r}"
    else:
        return
    issues.append(_error("pfi.invalid", spec.TAG_PFI, message))


def _check_rule(path: str, value: str, rule: spec.TagRule, issues: list[Issue]) -> None:
    if len(value) > rule.max_len:
        issues.append(
            _error(
                "tag.length",
                path,
                f"{rule.name} is {len(value)} characters; the maximum is {rule.max_len}",
            )
        )
    elif value == "":
        issues.append(_error("tag.format", path, f"{rule.name} must not be empty"))
    elif rule.exact and len(value) != rule.max_len:
        issues.append(
            _error("tag.format", path, f"{rule.name} must be exactly {rule.max_len} characters")
        )
    elif rule.numeric and not (value.isascii() and value.isdigit()):
        issues.append(_error("tag.format", path, f"{rule.name} must contain only digits"))


def _check_duplicates(nodes: Sequence[Node], prefix: str, issues: list[Issue]) -> None:
    counts = Counter(node.tag for node in nodes)
    for tag, count in counts.items():
        if count > 1:
            path = f"{prefix}{tag}"
            issues.append(_error("tag.duplicate", path, f"Tag {path} appears {count} times"))


def _check_structure(nodes: Sequence[Node], issues: list[Issue]) -> None:
    _check_duplicates(nodes, "", issues)
    for node in nodes:
        if spec.is_template(node.tag):
            children = children_of(node.value)
            if children is None:
                issues.append(
                    _error(
                        "template.malformed",
                        node.tag,
                        f"Template {node.tag} does not contain valid tag-length-value data",
                    )
                )
                continue
            _check_duplicates(children, f"{node.tag}.", issues)
            rules = spec.child_rules(node.tag)
            for child in children:
                rule = rules.get(child.tag)
                if rule is not None:
                    _check_rule(f"{node.tag}.{child.tag}", child.value, rule, issues)
        elif node.tag in spec.GENERIC_ROOT_TAGS:
            _check_rule(node.tag, node.value, spec.ROOT_RULES[node.tag], issues)
    middle = [node.tag for node in nodes if node.tag not in (spec.TAG_PFI, spec.TAG_CRC)]
    if middle != sorted(middle):
        issues.append(_warning("tag.order", None, "Tags are not in ascending order"))


def _check_required(nodes: Sequence[Node], issues: list[Issue]) -> None:
    present = {node.tag for node in nodes}
    for tag in spec.REQUIRED_ROOT_TAGS:
        if tag not in present:
            name = spec.ROOT_RULES[tag].name
            issues.append(_error("tag.required", tag, f"{name} (tag {tag}) is missing"))
    if not any(spec.is_merchant_account(tag) for tag in present):
        issues.append(
            _error(
                "merchant_account.missing",
                None,
                "No merchant account information (tags 02-51) found",
            )
        )


def _check_values(qris: QRIS, issues: list[Issue]) -> None:
    poi = qris.get(spec.TAG_POI)
    if poi is not None and poi not in (spec.POI_STATIC, spec.POI_DYNAMIC):
        issues.append(
            _error(
                "poi.invalid", spec.TAG_POI, f"Point of Initiation must be 11 or 12, got {poi!r}"
            )
        )

    currency = qris.get(spec.TAG_CURRENCY)
    if currency is not None and currency != spec.CURRENCY_IDR:
        issues.append(
            _error(
                "currency.invalid",
                spec.TAG_CURRENCY,
                f"Currency must be '360' (IDR), got {currency!r}",
            )
        )

    country = qris.get(spec.TAG_COUNTRY)
    if country is not None and country != spec.COUNTRY_ID:
        issues.append(
            _error("country.invalid", spec.TAG_COUNTRY, f"Country must be 'ID', got {country!r}")
        )

    amount = qris.get(spec.TAG_AMOUNT)
    if amount is not None and (parse_decimal(amount) is None or len(amount) > 13):
        issues.append(
            _error(
                "amount.invalid",
                spec.TAG_AMOUNT,
                f"Amount {amount!r} must be a positive number with at most 2 decimals "
                "and at most 13 characters",
            )
        )
    if poi == spec.POI_STATIC and amount is not None:
        issues.append(
            _warning(
                "amount.on_static", spec.TAG_AMOUNT, "Static QRIS should not contain an amount"
            )
        )
    if poi == spec.POI_DYNAMIC and amount is None:
        issues.append(
            _warning("amount.missing_on_dynamic", spec.TAG_AMOUNT, "Dynamic QRIS has no amount")
        )

    _check_tip(qris, issues)

    if not any(
        a.is_national and a.guid == spec.NATIONAL_GUID and a.merchant_id
        for a in qris.merchant_accounts
    ):
        issues.append(
            _warning(
                "national.missing",
                spec.TAG_NATIONAL,
                "No national repository account (tag 51, ID.CO.QRIS.WWW) with NMID",
            )
        )
    if qris.get(spec.TAG_POSTAL) is None:
        issues.append(
            _warning("postal_code.missing", spec.TAG_POSTAL, "Postal code (tag 61) is missing")
        )


def _check_tip(qris: QRIS, issues: list[Issue]) -> None:
    indicator = qris.get(spec.TAG_TIP)
    fixed = qris.get(spec.TAG_FEE_FIXED)
    percent = qris.get(spec.TAG_FEE_PERCENT)

    if indicator is not None and indicator not in (
        spec.TIP_PROMPT,
        spec.TIP_FIXED,
        spec.TIP_PERCENT,
    ):
        issues.append(
            _error(
                "tip.invalid",
                spec.TAG_TIP,
                f"Tip indicator must be 01, 02 or 03, got {indicator!r}",
            )
        )
    if indicator == spec.TIP_FIXED:
        if fixed is None:
            issues.append(
                _error("tip.value_missing", spec.TAG_FEE_FIXED, "Fixed fee (tag 56) is missing")
            )
        elif parse_decimal(fixed) is None or len(fixed) > 13:
            issues.append(
                _error("tip.invalid", spec.TAG_FEE_FIXED, f"Fixed fee {fixed!r} is not valid")
            )
    if indicator == spec.TIP_PERCENT:
        rate = parse_decimal(percent)
        if percent is None:
            issues.append(
                _error(
                    "tip.value_missing",
                    spec.TAG_FEE_PERCENT,
                    "Percentage fee (tag 57) is missing",
                )
            )
        elif rate is None or rate > MAX_PERCENT or len(percent) > 5:
            issues.append(
                _error(
                    "tip.invalid",
                    spec.TAG_FEE_PERCENT,
                    f"Percentage fee {percent!r} must be between 0.01 and 99.99",
                )
            )
    if fixed is not None and indicator != spec.TIP_FIXED:
        issues.append(
            _error("tip.orphan_value", spec.TAG_FEE_FIXED, "Tag 56 needs tip indicator 02")
        )
    if percent is not None and indicator != spec.TIP_PERCENT:
        issues.append(
            _error("tip.orphan_value", spec.TAG_FEE_PERCENT, "Tag 57 needs tip indicator 03")
        )
