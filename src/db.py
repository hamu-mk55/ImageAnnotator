# -*- coding: utf-8 -*-
import sys
import os
import shutil
import csv
import sqlite3

from PySide6.QtCore import QRectF


class AnnotationDB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute('''CREATE TABLE IF NOT EXISTS annotations (
            filename TEXT,
            x REAL,
            y REAL,
            width REAL,
            height REAL,
            rect_label TEXT,
            img_label TEXT
        )''')
        self.conn.commit()

    def save_annotation(self, img_path, rect, rect_label, label=None):
        _label, filename = self._get_label_and_filename(img_path)

        if label is None:
            label = _label

        self.conn.execute(
            "INSERT INTO annotations (filename, x, y, width, height, rect_label, img_label) VALUES (?, ?, ?, ?, ?, ?,?)",
            (filename, rect.x(), rect.y(), rect.width(), rect.height(), rect_label, label))
        self.conn.commit()

    def load_annotations(self, img_path):
        label, filename = self._get_label_and_filename(img_path)

        cursor = self.conn.execute("SELECT x, y, width, height, rect_label FROM annotations WHERE filename=?",
                                   (filename,))
        return [(QRectF(x, y, w, h), rect_label) for x, y, w, h, rect_label in cursor.fetchall()]

    def delete_annotation(self, img_path, rect, tol=1.0):
        label, filename = self._get_label_and_filename(img_path)

        self.conn.execute(
            '''DELETE FROM annotations WHERE filename=? AND
               ABS(x - ?) < ? AND ABS(y - ?) < ? AND ABS(width - ?) < ? AND ABS(height - ?) < ?''',
            (filename, rect.x(), tol, rect.y(), tol, rect.width(), tol, rect.height(), tol)
        )
        self.conn.commit()

    def update_label(self, img_path):
        label, filename = self._get_label_and_filename(img_path)

        self.conn.execute(
            "UPDATE annotations SET img_label=? WHERE filename=?",
            (label, filename)
        )
        self.conn.commit()

    def delete_all_annotations(self, img_path):
        label, filename = self._get_label_and_filename(img_path)

        self.conn.execute("DELETE FROM annotations WHERE filename=?", (filename,))
        self.conn.commit()

    def export_to_csv(self, csv_path):
        cursor = self.conn.execute("SELECT filename, x, y, width, height, rect_label, img_label FROM annotations")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "img_label", "x", "y", "width", "height", "rect_label"])
            for row in cursor:
                filename, x, y, width, height, rect_label, img_label = row

                writer.writerow([filename, img_label, x, y, width, height, rect_label])

    def import_from_csv(self, path: str):

        with open(path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    filename = row['filename']
                    x = float(row['x'])
                    y = float(row['y'])
                    width = float(row['width'])
                    height = float(row['height'])
                    rect_label = row['rect_label']
                    rect = QRectF(x, y, width, height)
                    label = row['img_label']
                    self.save_annotation(filename, rect, rect_label, label)
                except Exception as e:
                    print(f"[ERROR] Skipping row: {row} → {e}")

    def _get_label_and_filename(self, img_path):
        filename = os.path.basename(img_path)
        label = os.path.basename(os.path.dirname(img_path))

        return label, filename
