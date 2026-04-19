# -*- coding: utf-8 -*-
"""SQLite persistence helpers for image labels and rectangle annotations."""

import csv
import os
import sqlite3
from typing import Any, List, Tuple

RectWH = Tuple[float, float, float, float]  # (x, y, width, height)


class AnnotationDB:
    """SQLite-backed storage for rectangle annotations and image labels."""

    def __init__(self, db_path: str):
        """Open the SQLite database and ensure the annotations table exists."""
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self) -> None:
        """Create the annotations table when it does not already exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS annotations (
                filename TEXT,
                x REAL,
                y REAL,
                width REAL,
                height REAL,
                rect_label TEXT,
                img_label TEXT
            )
            """
        )
        self.conn.commit()

    def save_annotation(
        self, img_path: str, rect: Any, rect_label: str, label: str = None
    ) -> None:
        """
        Save one rectangle annotation for an image.

        Args:
            img_path: Path or filename of the annotated image.
            rect: Rectangle coordinates in a supported format.
            rect_label: Label assigned to the rectangle.
            label: Optional image label. Defaults to the parent folder name.
        """
        _label, filename = self._get_label_and_filename(img_path)

        if label is None:
            label = _label

        x, y, width, height = self._normalize_rect(rect)

        self.conn.execute(
            """
            INSERT INTO annotations (filename, x, y, width, height, rect_label, img_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, x, y, width, height, rect_label, label),
        )
        self.conn.commit()

    def load_annotations(self, img_path: str) -> List[Tuple[RectWH, str]]:
        """Load all rectangle annotations saved for the given image."""
        _, filename = self._get_label_and_filename(img_path)

        cursor = self.conn.execute(
            """
            SELECT x, y, width, height, rect_label
            FROM annotations
            WHERE filename=?
            """,
            (filename,),
        )
        return [
            ((x, y, w, h), rect_label) for x, y, w, h, rect_label in cursor.fetchall()
        ]

    def delete_annotation(self, img_path: str, rect: Any, tol: float = 1.0) -> None:
        """
        Delete annotations matching an image and rectangle within a tolerance.

        Args:
            img_path: Path or filename of the annotated image.
            rect: Rectangle coordinates in a supported format.
            tol: Maximum absolute coordinate difference to treat as a match.
        """
        _, filename = self._get_label_and_filename(img_path)
        x, y, width, height = self._normalize_rect(rect)

        self.conn.execute(
            """
            DELETE FROM annotations
            WHERE filename=?
              AND ABS(x - ?) < ?
              AND ABS(y - ?) < ?
              AND ABS(width - ?) < ?
              AND ABS(height - ?) < ?
            """,
            (filename, x, tol, y, tol, width, tol, height, tol),
        )
        self.conn.commit()

    def update_label(self, img_path: str) -> None:
        """Update the stored image label to match the image path's parent folder."""
        label, filename = self._get_label_and_filename(img_path)

        self.conn.execute(
            "UPDATE annotations SET img_label=? WHERE filename=?", (label, filename)
        )
        self.conn.commit()

    def delete_all_annotations(self, img_path: str) -> None:
        """Delete all rectangle annotations saved for the given image."""
        _, filename = self._get_label_and_filename(img_path)

        self.conn.execute("DELETE FROM annotations WHERE filename=?", (filename,))
        self.conn.commit()

    def export_to_csv(self, csv_path: str) -> None:
        """Export all saved annotations to a CSV file."""
        cursor = self.conn.execute(
            """
            SELECT filename, x, y, width, height, rect_label, img_label
            FROM annotations
            """
        )

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["filename", "img_label", "x", "y", "width", "height", "rect_label"]
            )

            for row in cursor:
                filename, x, y, width, height, rect_label, img_label = row
                writer.writerow([filename, img_label, x, y, width, height, rect_label])

    def import_from_csv(self, path: str) -> None:
        """
        Import annotations from a CSV file, replacing rows for matching filenames.

        Invalid rows are skipped and reported to stdout.
        """
        imported_rows = []
        filenames = set()

        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    filename = row["filename"]
                    x = float(row["x"])
                    y = float(row["y"])
                    width = float(row["width"])
                    height = float(row["height"])
                    rect_label = row["rect_label"]
                    label = row["img_label"]

                    rect = (x, y, width, height)
                    imported_rows.append((filename, rect, rect_label, label))
                    filenames.add(filename)

                except Exception as e:
                    print(f"[ERROR] Skipping row: {row} -> {e}")

        for filename in filenames:
            self.conn.execute("DELETE FROM annotations WHERE filename=?", (filename,))
        self.conn.commit()

        for filename, rect, rect_label, label in imported_rows:
            self.save_annotation(filename, rect, rect_label, label)

    def close(self) -> None:
        """Close the SQLite connection if it is open."""
        if self.conn:
            self.conn.close()

    def _get_label_and_filename(self, img_path: str) -> Tuple[str, str]:
        """Return the parent-folder label and basename for an image path."""
        filename = os.path.basename(img_path)
        _dirname = os.path.dirname(img_path)
        label = os.path.basename(_dirname) if _dirname else ""
        return label, filename

    def _normalize_rect(self, rect: Any) -> RectWH:
        """
        Convert a supported rectangle object to (x, y, width, height).

        Supported formats:
        - tuple/list: (x, y, width, height)
        - dict: {"x":..., "y":..., "width":..., "height":...}
        - QRectF-like object: x(), y(), width(), height()
        """
        if isinstance(rect, (tuple, list)) and len(rect) == 4:
            x, y, width, height = rect
            return float(x), float(y), float(width), float(height)

        if isinstance(rect, dict):
            return (
                float(rect["x"]),
                float(rect["y"]),
                float(rect["width"]),
                float(rect["height"]),
            )

        if all(hasattr(rect, name) for name in ("x", "y", "width", "height")):
            x_attr = getattr(rect, "x")
            y_attr = getattr(rect, "y")
            w_attr = getattr(rect, "width")
            h_attr = getattr(rect, "height")

            x = x_attr() if callable(x_attr) else x_attr
            y = y_attr() if callable(y_attr) else y_attr
            width = w_attr() if callable(w_attr) else w_attr
            height = h_attr() if callable(h_attr) else h_attr

            return float(x), float(y), float(width), float(height)

        raise TypeError(f"Unsupported rect format: {type(rect)} / {rect}")
