# -*- coding: utf-8 -*-
import sys
import os
import shutil
import csv

import cv2

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QListWidget,
    QVBoxLayout, QHBoxLayout, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsTextItem,QSizePolicy, QComboBox, QTreeWidget,
    QTreeWidgetItem, QSplitter, QGridLayout, QInputDialog
)
from PySide6.QtGui import QPixmap, QImage, QPen, QColor, QFont
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent

from src.db import AnnotationDB


class Annotator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ImageAnnotator")
        self.setGeometry(100, 100, 1200, 800)

        self.root_folder = ""
        self.label_list = []
        self.image_dict = {}  # label: [paths]
        self.current_label = None
        self.current_images = []
        self.current_index = 0

        self.db = AnnotationDB("annotations.db")

        self.initUI()

    def initUI(self):
        # left-side: buttons
        self.label_tree = QTreeWidget()
        self.label_tree.setHeaderLabel("Label > Image")
        self.label_tree.itemClicked.connect(self.label_item_selected)

        button_defs = [
            ("Set image folder", self.load_images),
            ("Add Label", self.add_new_label),
            ("Clear Annotations", self.clear_current_annotations),
            ("Export Labels", self.export_labels),
            ("Export Annotations", self.export_annotations),
            ("Import Annotations", self.import_annotations),
        ]

        left_layout = QVBoxLayout()
        for label, handler in button_defs:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            left_layout.addWidget(btn)
        left_layout.insertWidget(1, self.label_tree)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(300)

        # right-side: viewer
        self.image_view = ImageWithControls(self, self.db)
        self.image_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # merge
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.image_view)
        self.setCentralWidget(splitter)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.show_previous_image()
        elif event.key() == Qt.Key_Right:
            self.show_next_image()

    def load_images(self):
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if not folder:
            return

        self.root_folder = folder
        self.image_dict = {}
        self.label_list = [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]

        for label in self.label_list:
            label_path = os.path.join(folder, label)
            self.image_dict[label] = [os.path.join(label_path, f)
                                      for f in os.listdir(label_path)
                                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]

        self.populate_label_tree()

    def populate_label_tree(self):
        self.label_tree.clear()
        self.sort_image_dict()
        for label in self.label_list:
            parent = QTreeWidgetItem(self.label_tree, [label])
            for img_path in self.image_dict[label]:
                QTreeWidgetItem(parent, [os.path.basename(img_path)])

    def sort_image_dict(self):
        for label, file_list in self.image_dict.items():
            self.image_dict[label] = sorted(
                file_list,
                key=lambda path: os.path.basename(path).lower()
            )

    def label_item_selected(self, item, column):
        parent = item.parent()
        if parent:
            label = parent.text(0)
            image_name = item.text(0)
            full_path = os.path.join(self.root_folder, label, image_name)
            self.current_label = label
            self.current_images = self.image_dict[label]
            self.current_index = self.current_images.index(full_path)
        else:
            label = item.text(0)
            self.current_label = label
            self.current_images = self.image_dict[label]
            self.current_index = 0

        self.update_image_display()

    def add_new_label(self):
        text, ok = QInputDialog.getText(self, "New Label", "Label:")
        if ok and text:
            label_path = os.path.join(self.root_folder, text)
            os.makedirs(label_path, exist_ok=True)
            self.label_list.append(text)
            self.image_dict[text] = []
            self.populate_label_tree()

    def show_next_image(self):
        if self.current_index + 1 < len(self.current_images):
            self.current_index += 1
            self.update_image_display()

    def show_previous_image(self):
        if self.current_index - 1 >= 0:
            self.current_index -= 1
            self.update_image_display()

    def update_image_display(self):
        try:
            image_path = self.current_images[self.current_index]
        except IndexError:
            return

        self.image_view.set_image_path(image_path, self.label_list)
        self.image_view.setFocus()

    def move_image_to_label(self, image_path, new_label):
        old_label = os.path.basename(os.path.dirname(image_path))
        if old_label == new_label:
            return image_path

        file_name = os.path.basename(image_path)
        new_dir = os.path.join(self.root_folder, new_label)
        os.makedirs(new_dir, exist_ok=True)
        new_path = os.path.join(new_dir, file_name)
        shutil.move(image_path, new_path)

        self.image_dict[old_label].remove(image_path)
        self.image_dict[new_label].append(new_path)
        self.populate_label_tree()

        self.db.update_label(new_path)

        self.current_images = self.image_dict[old_label]
        self.update_image_display()

        return new_path

    def export_annotations(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV files (*.csv)")
        if path:
            self.db.export_to_csv(path)

    def import_annotations(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV files (*.csv)")
        if path:
            self.db.import_from_csv(path)
            print(f"Imported annotations from: {path}")

    def export_labels(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV files (*.csv)")
        if path:
            with open(path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["file_path", "label"])
                for label, img_paths in self.image_dict.items():
                    for img_path in img_paths:
                        img_path = os.path.basename(img_path)
                        writer.writerow([img_path, label])

    def clear_current_annotations(self):
        self.image_view.clear_annotations()


class ImageWithControls(QWidget):
    def __init__(self, parent_window, db):
        super().__init__()
        self.image_path = None
        self.label_list = []
        self.parent_window = parent_window
        self.db = db

        layout = QVBoxLayout()
        self.setLayout(layout)

        # header: filename, image-label
        header_layout = QHBoxLayout()
        self.label = QLabel("")
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self.on_label_changed)
        self.combo.blockSignals(True)

        header_layout.addWidget(self.label)
        header_layout.addWidget(self.combo)

        layout.addLayout(header_layout)

        # annotation
        anno_layout = QHBoxLayout()
        self.combo_anno = QComboBox()
        anno_layout.addWidget(QLabel("Annotation Label:"))
        anno_layout.addWidget(self.combo_anno)
        layout.addLayout(anno_layout)

        # 画像ビュー（アノテーション付き）
        self.image_view = AnnotatableImageView(parent_window.root_folder, parent_window, db)
        self.image_view.get_current_anno_label = lambda: self.combo_anno.currentText()
        layout.addWidget(self.image_view)

    def set_image_path(self, image_path, label_list):
        self.image_path = image_path
        self.label_list = label_list

        # self.label.setText(os.path.basename(image_path))
        current_label = os.path.basename(os.path.dirname(image_path))

        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo_anno.clear()
        self.combo.addItems(label_list)
        self.combo_anno.addItems(label_list)

        self.combo.setCurrentText(current_label)
        self.combo_anno.setCurrentText(current_label)

        self.combo.blockSignals(False)

        self.label.setText(os.path.basename(image_path))
        self.image_view.set_image(image_path)

    def clear_annotations(self):
        self.image_view.clear_all_annotations()

    def on_label_changed(self, new_label):
        old_label = os.path.basename(os.path.dirname(self.image_path))

        if new_label != old_label and new_label in self.label_list:
            # ラベル変更 → ファイル移動処理
            self.combo.blockSignals(True)
            new_path = self.parent_window.move_image_to_label(self.image_path, new_label)
            # self.set_image_path(new_path, self.label_list)
            self.combo.blockSignals(False)


class AnnotatableImageView(QGraphicsView):
    def __init__(self, root_folder, parent_window, db):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pixmap_item = None
        self.rect_items = []  # [(rect, label)]
        self.start_point = None

        self.get_current_anno_label = None

        self.root_folder = root_folder
        self.parent_window = parent_window
        self.image_path = None
        self.db = db

        self.scale_ratio = 1.0  # 表示サイズと元サイズの比率
        self.orig_width = 1
        self.orig_height = 1

        # zoom
        self.view_scale = 1.0
        self.zoom_scale = 3.0

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def set_image(self, path):
        self.scene.clear()
        self.rect_items.clear()
        self.image_path = path

        image = cv2.imread(path)

        if image is None:
            return

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        self.orig_width = w
        self.orig_height = h

        # 描画用にformat変換
        bytes_per_line = ch * w
        qimage = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(self.viewport().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # スケール比（横方向ベース）
        self.scale_ratio = scaled_pixmap.width() / w

        self.pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(self.scene.itemsBoundingRect())

        self.reset_zoom()

        self.load_annotations()

    def load_annotations(self):
        for rect, label in self.db.load_annotations(self.image_path):
            # 元画像座標 → GUI表示座標
            scaled_rect = QRectF(
                rect.x() * self.scale_ratio,
                rect.y() * self.scale_ratio,
                rect.width() * self.scale_ratio,
                rect.height() * self.scale_ratio
            )

            rect_item = self._get_rect_item(scaled_rect)
            self.scene.addItem(rect_item)

            text_item = self._get_text_item(label, scaled_rect)
            self.scene.addItem(text_item)

            self.rect_items.append((rect_item, text_item))

    def clear_all_annotations(self):
        self.db.delete_all_annotations(self.image_path)
        for rect_item, text_item in self.rect_items:
            self.scene.removeItem(rect_item)
            self.scene.removeItem(text_item)
        self.rect_items.clear()


    def resizeEvent(self, event):
        # 画像を再スケールし直し、ビュー倍率は維持
        if self.pixmap_item and self.image_path:
            # 現在のビュー倍率を保存
            current_view_scale = self.view_scale
            self.set_image(self.image_path)

            self.view_scale = current_view_scale
            self.apply_view_scale()
        super().resizeEvent(event)


    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.position().toPoint())

        # 左クリック：アノテーション追加開始（従来通り）
        if event.button() == Qt.LeftButton:
            self.start_point = scene_pos

        # 右クリック：
        #   - 矩形上なら削除（従来通り）
        #   - それ以外の場所ならズーム操作
        elif event.button() == Qt.RightButton:
            hit_rect = None
            for rect_item, text_item in self.rect_items:
                if rect_item.rect().contains(scene_pos):
                    hit_rect = (rect_item, text_item)
                    break

            if hit_rect:
                # 既存：右クリックで削除
                rect_item, text_item = hit_rect
                gui_rect = rect_item.rect()
                unscaled_rect = QRectF(
                    gui_rect.x() / self.scale_ratio,
                    gui_rect.y() / self.scale_ratio,
                    gui_rect.width() / self.scale_ratio,
                    gui_rect.height() / self.scale_ratio
                )
                rect_label = text_item.text()
                self.db.delete_annotation(self.image_path, unscaled_rect)
                self.scene.removeItem(rect_item)
                self.scene.removeItem(text_item)
                self.rect_items.remove((rect_item, text_item))
            else:
                # 右クリックでズームイン/アウト
                if self.view_scale < self.zoom_scale:
                    self.zoom_in()
                else:
                    self.reset_zoom()

        self.parent_window.image_view.setFocus()

    def mouseMoveEvent(self, event):
        if self.start_point:
            end_point = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_point, end_point).normalized()
            if hasattr(self, 'temp_rect') and self.temp_rect:
                self.scene.removeItem(self.temp_rect)

            self.temp_rect = self._get_rect_item(rect)
            self.scene.addItem(self.temp_rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self, 'temp_rect'):
            end_point = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_point, end_point).normalized()

            unscaled_rect = QRectF(
                rect.x() / self.scale_ratio,
                rect.y() / self.scale_ratio,
                rect.width() / self.scale_ratio,
                rect.height() / self.scale_ratio
            )

            label = self.get_current_anno_label() if self.get_current_anno_label else self.parent_window.current_label
            self.db.save_annotation(self.image_path, unscaled_rect, label)

            # ラベル表示
            text_item = self._get_text_item(label, rect)
            self.scene.addItem(text_item)

            self.rect_items.append((self.temp_rect, text_item))
            self.temp_rect = None
            self.start_point = None
            self.parent_window.image_view.setFocus()

    # ズーム操作（ビュー変換のみを変更し、アノテーション座標はそのまま）
    def apply_view_scale(self):
        self.resetTransform()
        self.scale(self.view_scale, self.view_scale)

    def zoom_in(self):
        self.view_scale = self.zoom_scale
        self.apply_view_scale()

    def reset_zoom(self):
        self.view_scale = 1.0
        self.apply_view_scale()

    def _get_rect_item(self, rect):
        rect_item = QGraphicsRectItem(rect)
        rect_item.setPen(QPen(QColor("red"), 2))

        return rect_item

    def _get_text_item(self, text, rect):
        text_item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPointSize(14)
        text_item.setFont(font)
        text_item.setPos(rect.x(), rect.y() - 25)
        text_item.setBrush(QColor("blue"))

        return text_item




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Annotator()
    window.show()
    sys.exit(app.exec())
