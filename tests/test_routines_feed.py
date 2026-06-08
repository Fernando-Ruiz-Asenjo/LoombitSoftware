"""
Feed de novedades del daemon: descarta los ticks vacíos de vigilancia y marca lo importante.
"""

import json

from loombit_operator.routers.routines import build_feed


def _write(d, name, kind, output, status="pending_approval"):
    (d / f"{name}.json").write_text(
        json.dumps(
            {
                "name": name,
                "output_kind": kind,
                "status": status,
                "fired_at": "2026-06-08T12:00:00+00:00",
                "output": output,
                "error": "",
            }
        ),
        encoding="utf-8",
    )


def test_feed_filters_empty_and_marks_important(tmp_path):
    _write(tmp_path, "watch_empty", "reply_watch", "Sin respuestas nuevas de tus contactos.")
    _write(
        tmp_path, "watch_reply", "reply_watch", "Tienes 1 respuesta(s):\n• David — Borrador: Hola"
    )
    _write(
        tmp_path,
        "watch_imp",
        "reply_watch",
        "Tienes 1 respuesta(s):\n• Banco  ⚠ IMPORTANTE\n  Borrador: [IMPORTANTE] revisa",
    )
    _write(tmp_path, "brief_dia", "brief", "Resumen del día: todo en orden")

    items = build_feed(tmp_path, limit=10)
    names = [i["name"] for i in items]

    assert "watch_empty" not in names  # ruido filtrado
    assert "watch_reply" in names
    assert "brief_dia" in names
    imp = next(i for i in items if i["name"] == "watch_imp")
    assert imp["importante"] is True


def test_feed_empty_dir(tmp_path):
    assert build_feed(tmp_path, 10) == []
