#!/usr/bin/env python3
"""Load waypoint_info.txt lines into tours.db descriptions."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("tours.db")
DEFAULT_INFO_PATH = Path("waypoint_info.txt")
POSE_COLUMNS = ("px", "py", "pz", "qx", "qy", "qz", "qw")


def read_waypoint_lines(info_path: Path) -> list[str]:
    return [
        line.strip()
        for line in info_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ensure_tours_table(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS tours "
        "(px, py, pz, qx, qy, qz, qw, description)"
    )

    columns = [row[1] for row in con.execute("PRAGMA table_info(tours)")]
    if "description" not in columns:
        con.execute("ALTER TABLE tours ADD COLUMN description")


def load_descriptions(db_path: Path, info_path: Path) -> tuple[int, int]:
    descriptions = read_waypoint_lines(info_path)

    with sqlite3.connect(db_path) as con:
        ensure_tours_table(con)
        rowids = [
            row[0]
            for row in con.execute("SELECT rowid FROM tours ORDER BY rowid").fetchall()
        ]

        updated = 0
        inserted = 0

        for index, description in enumerate(descriptions):
            if index < len(rowids):
                con.execute(
                    "UPDATE tours SET description = ? WHERE rowid = ?",
                    (description, rowids[index]),
                )
                updated += 1
            else:
                columns = ", ".join((*POSE_COLUMNS, "description"))
                placeholders = ", ".join("?" for _ in range(len(POSE_COLUMNS) + 1))
                values = (*([0.0] * len(POSE_COLUMNS)), description)
                con.execute(
                    f"INSERT INTO tours ({columns}) VALUES ({placeholders})",
                    values,
                )
                inserted += 1

    return updated, inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load waypoint_info.txt into the tours.db description column."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--info", type=Path, default=DEFAULT_INFO_PATH)
    args = parser.parse_args()

    updated, inserted = load_descriptions(args.db, args.info)
    print(
        f"Loaded {updated + inserted} descriptions into {args.db} "
        f"({updated} updated, {inserted} inserted)."
    )


if __name__ == "__main__":
    main()
