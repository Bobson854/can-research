"""Serialize internal DBC models to DBC text."""

from __future__ import annotations

from pathlib import Path

from canresearch.core.dbc_model import DbcDatabase


def _format_number(value: float) -> str:
    text = f"{value:g}"
    if "e" in text or "E" in text:
        return text
    if "." in text:
        return text.rstrip("0").rstrip(".") or "0"
    return text


def render_dbc(database: DbcDatabase) -> str:
    """Render a DBC database to deterministic text."""
    lines = [
        f'VERSION "{database.version}"',
        "",
        "NS_ :",
        "    NS_DESC_",
        "    CM_",
        "    BA_DEF_",
        "    BA_",
        "    VAL_",
        "    CAT_DEF_",
        "    CAT_",
        "    FILTER",
        "    BA_DEF_DEF_",
        "    EV_DATA_",
        "    ENVVAR_DATA_",
        "    SGTYPE_",
        "    SGTYPE_VAL_",
        "    BA_DEF_SGTYPE_",
        "    BA_SGTYPE_",
        "    SIG_TYPE_REF_",
        "    VAL_TABLE_",
        "    SIG_GROUP_",
        "    SIG_VALTYPE_",
        "    SIGTYPE_VALTYPE_",
        "    BO_TX_BU_",
        "    BA_DEF_REL_",
        "    BA_REL_",
        "    BA_DEF_DEF_REL_",
        "    BU_SG_REL_",
        "    BU_EV_REL_",
        "    BU_BO_REL_",
        "    SG_MUL_VAL_",
        "",
        "BS_:",
        "",
        "BU_: " + " ".join(database.nodes),
        "",
    ]

    for message in database.messages:
        lines.append(
            f"BO_ {message.dbc_frame_id} {message.name}: {message.dlc} {message.transmitter}"
        )
        for signal in message.signals:
            sign = "-" if signal.signed else "+"
            lines.append(
                f' SG_ {signal.name} : {signal.start_bit}|{signal.bit_length}'
                f"@{signal.byte_order}{sign} "
                f"({_format_number(signal.factor)},{_format_number(signal.offset)}) "
                f"[{_format_number(signal.minimum)}|{_format_number(signal.maximum)}] "
                f'"{signal.unit}" Vector__XXX'
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_dbc(database: DbcDatabase, output_path: Path) -> None:
    """Write a DBC file to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_dbc(database), encoding="ascii", errors="replace")
