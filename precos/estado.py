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
            CREATE TABLE IF NOT EXISTS ia_cache (chave TEXT PRIMARY KEY, valor TEXT);
            CREATE TABLE IF NOT EXISTS gastos (mes TEXT PRIMARY KEY, usd REAL);
            CREATE TABLE IF NOT EXISTS observacoes (chave TEXT, dia TEXT, preco REAL,
                                                    PRIMARY KEY (chave, dia));
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

    def cache_ler(self, chave: str) -> str | None:
        row = self.db.execute("SELECT valor FROM ia_cache WHERE chave=?", (chave,)).fetchone()
        return row[0] if row else None

    def cache_gravar(self, chave: str, valor: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO ia_cache VALUES (?,?)", (chave, valor))

    def gasto(self, mes: str) -> float:
        row = self.db.execute("SELECT usd FROM gastos WHERE mes=?", (mes,)).fetchone()
        return row[0] if row else 0.0

    def somar_gasto(self, mes: str, usd: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO gastos VALUES (?,?) ON CONFLICT(mes) DO UPDATE SET usd = usd + excluded.usd",
                (mes, usd),
            )

    # ---- histórico próprio: menor preço à vista de cada modelo por dia
    def registrar_observacao(self, chave: str, dia, preco: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO observacoes VALUES (?,?,?) ON CONFLICT(chave, dia) "
                "DO UPDATE SET preco = MIN(preco, excluded.preco)",
                (chave, dia.isoformat(), preco),
            )

    def historico_proprio(self, chave: str):
        from datetime import date

        rows = self.db.execute("SELECT dia, preco FROM observacoes WHERE chave=? ORDER BY dia", (chave,)).fetchall()
        return [(date.fromisoformat(d), p) for d, p in rows]
