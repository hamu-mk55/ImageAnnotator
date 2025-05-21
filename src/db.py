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
            image_path TEXT,
            x REAL,
            y REAL,
            width REAL,
            height REAL
        )''')
        self.conn.commit()

    def save_annotation(self, image_path, rect):
        self.conn.execute("INSERT INTO annotations (image_path, x, y, width, height) VALUES (?, ?, ?, ?, ?)",
                          (image_path, rect.x(), rect.y(), rect.width(), rect.height()))
        self.conn.commit()

    def load_annotations(self, image_path):
        cursor = self.conn.execute("SELECT x, y, width, height FROM annotations WHERE image_path=?", (image_path,))
        return [QRectF(x, y, w, h) for x, y, w, h in cursor.fetchall()]

    def delete_annotation(self, image_path, rect, tol=1.0):
        self.conn.execute(
            '''DELETE FROM annotations WHERE image_path=? AND
               ABS(x - ?) < ? AND ABS(y - ?) < ? AND ABS(width - ?) < ? AND ABS(height - ?) < ?''',
            (image_path, rect.x(), tol, rect.y(), tol, rect.width(), tol, rect.height(), tol)
        )
        self.conn.commit()

    def export_to_csv(self, csv_path):
        cursor = self.conn.execute("SELECT image_path, x, y, width, height FROM annotations")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["image_path", "label", "x", "y", "width", "height"])
            for row in cursor:
                image_path, x, y, width, height = row
                base_name = os.path.basename(image_path)
                label = os.path.basename(os.path.dirname(image_path))

                writer.writerow([base_name, label, x, y, width, height])
