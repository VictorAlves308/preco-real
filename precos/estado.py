"""Memória local (SQLite): o que já foi avisado e o menor preço já visto por item."""
from __future__ import annotations

import sqlite3
from pathlib import Path

QUEDA_MIN = 0.98  # só avisa de novo se cair pelo menos 2%


class Estado:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS avisos (item TEXT, offer_id TEXT, total REAL,
                                               PRIMARY KEY (item, offer_id));
            CREATE TABLE IF NOT EXISTS menores (item TEXT PRIMARY KEY, total REAL);
            """
        )

    def ja_avisado(self, item: str, offer_id: str, total: float) -> bool:
        row = self.db.execute(
            "SELECT total FROM avisos WHERE item=? AND offer_id=?", (item, offer_id)
        ).fetchone()
        return row is not None and total > row[0] * QUEDA_MIN

    def registrar_aviso(self, item: str, offer_id: str, total: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO avisos VALUES (?,?,?)", (item, offer_id, total)
            )

    def menor_visto(self, item: str) -> float | None:
        row = self.db.execute("SELECT total FROM menores WHERE item=?", (item,)).fetchone()
        return row[0] if row else None

    def registrar_preco(self, item: str, total: float) -> None:
        atual = self.menor_visto(item)
        if atual is None or total < atual:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO menores VALUES (?,?)", (item, total))
