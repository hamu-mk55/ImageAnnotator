# -*- coding: utf-8 -*-
import sys
import os
import shutil
import csv

import cv2

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QListWidget,
    QVBoxLayout, QHBoxLayout, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QSizePolicy, QComboBox, QTreeWidget,
    QTreeWidgetItem, QSplitter, QGridLayout, QInputDialog
)
from PySide6.QtGui import QPixmap, QImage, QPen, QColor
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
        self.image_count = 1  # 1 or 4

        self.db = AnnotationDB("annotations.db")

        self.initUI()

    def initUI(self):
        self.label_tree = QTreeWidget()
        self.label_tree.setHeaderLabel("Label > Image")
        self.label_tree.itemClicked.connect(self.label_item_selected)

        self.add_label_button = QPushButton("Add Label")
        self.add_label_button.clicked.connect(self.add_new_label)

        self.toggle_button = QPushButton("Display 1/4 images")
        self.toggle_button.clicked.connect(self.toggle_display_mode)

        left_layout = QVBoxLayout()
        self.load_button = QPushButton("Set image folder")
        self.load_button.clicked.connect(self.load_images)

        self.export_button_anno = QPushButton("Export Annotations")
        self.export_button_anno.clicked.connect(self.export_annotations)

        self.export_button_label = QPushButton("Export Labels")
        self.export_button_label.clicked.connect(self.export_labels)

        self.clear_button = QPushButton("Clear Annotations")
        self.clear_button.clicked.connect(self.clear_current_annotations)

        left_layout.addWidget(self.load_button)
        left_layout.addWidget(self.label_tree)
        left_layout.addWidget(self.add_label_button)
        left_layout.addWidget(self.toggle_button)
        left_layout.addWidget(self.clear_button)
        left_layout.addWidget(self.export_button_label)
        left_layout.addWidget(self.export_button_anno)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(300)

        self.image_view = GridView()
        self.image_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.image_view)
        self.setCentralWidget(splitter)

    def export_annotations(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV files (*.csv)")
        if path:
            self.db.export_to_csv(path)

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
        self.image_view.clear_all_annotations()

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
        for label in self.label_list:
            parent = QTreeWidgetItem(self.label_tree, [label])
            for img_path in self.image_dict[label]:
                QTreeWidgetItem(parent, [os.path.basename(img_path)])

    def label_item_selected(self, item, column):
        parent = item.parent()
        if parent:
            label = parent.text(0)
            image_name = item.text(0)
            full_path = os.path.join(self.root_folder, label, image_name)
            self.current_label = label
            self.current_images = self.image_dict[label]
            self.current_index = self.current_images.index(full_path)
            self.update_image_display()
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

    def toggle_display_mode(self):
        self.image_count = 4 if self.image_count == 1 else 1
        self.update_image_display()

    def show_next_image(self):
        if self.current_index + self.image_count < len(self.current_images):
            self.current_index += self.image_count
            self.update_image_display()

    def show_previous_image(self):
        if self.current_index - self.image_count >= 0:
            self.current_index -= self.image_count
            self.update_image_display()

    def update_image_display(self):
        images_to_show = self.current_images[self.current_index:self.current_index + self.image_count]
        self.image_view.set_images(images_to_show, self.root_folder, self, self.db)

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

        self.current_images = self.image_dict[old_label]
        self.update_image_display()

        return new_path


class GridView(QWidget):
    def __init__(self):
        super().__init__()
        self.grid_layout = QGridLayout()
        self.setLayout(self.grid_layout)
        self.image_views = []

    def set_images(self, image_paths, root_folder, parent, db):
        for view in self.image_views:
            self.grid_layout.removeWidget(view)
            view.deleteLater()
        self.image_views = []

        for i, path in enumerate(image_paths):
            view = ImageWithControls(path, parent.label_list, parent, db)
            self.grid_layout.addWidget(view, i // 2, i % 2)
            self.image_views.append(view)

    def clear_all_annotations(self):
        for view in self.image_views:
            view.clear_annotations()


class ImageWithControls(QWidget):
    def __init__(self, image_path, label_list, parent_window, db):
        super().__init__()
        self.image_path = image_path
        self.label_list = label_list
        self.parent_window = parent_window

        layout = QVBoxLayout()
        self.setLayout(layout)

        # header: filename, image-label
        header_layout = QHBoxLayout()
        file_name = os.path.basename(image_path)
        self.label = QLabel(file_name)

        self.combo = QComboBox()
        self.combo.addItems(label_list)

        current_label = os.path.basename(os.path.dirname(image_path))
        self.combo.setCurrentText(current_label)
        self.combo.currentTextChanged.connect(self.on_label_changed)

        header_layout.addWidget(self.label)
        header_layout.addWidget(self.combo)

        layout.addLayout(header_layout)

        # annotation
        anno_layout = QHBoxLayout()
        self.combo_anno = QComboBox()
        self.combo_anno.addItems(label_list)

        anno_layout.addWidget(QLabel("Annotation Label:"))
        anno_layout.addWidget(self.combo_anno)

        layout.addLayout(anno_layout)

        # 画像ビュー（アノテーション付き）
        self.image_view = AnnotatableImageView(parent_window.root_folder, parent_window, db)
        self.image_view.set_image(image_path)

        self.image_view.get_current_anno_label = lambda: self.combo_anno.currentText()

        layout.addWidget(self.image_view)

    def clear_annotations(self):
        self.image_view.clear_all_annotations()

    def on_label_changed(self, new_label):
        # ラベル変更 → ファイル移動処理
        new_path = self.parent_window.move_image_to_label(self.image_path, new_label)
        self.image_path = new_path
        self.image_view.set_image(new_path)

        # アノテーションラベルの初期値も画像ラベルに合わせて切り替え
        self.combo_anno.setCurrentText(new_label)


class AnnotatableImageView(QGraphicsView):
    def __init__(self, root_folder, parent_window, db):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pixmap_item = None
        self.rect_items = []
        self.start_point = None
        self.setMouseTracking(True)

        self.get_current_anno_label = None

        self.root_folder = root_folder
        self.parent_window = parent_window
        self.image_path = None
        self.db = db

        self.scale_ratio = 1.0
        self.orig_width = 1
        self.orig_height = 1

    def set_image(self, path):
        self.scene.clear()
        self.rect_items = []
        self.image_path = path

        image = cv2.imread(path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        self.orig_width = w
        self.orig_height = h

        bytes_per_line = ch * w
        qimage = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(self.viewport().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # スケール比（横方向ベース）
        self.scale_ratio = scaled_pixmap.width() / w

        self.pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(self.scene.itemsBoundingRect())

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
            rect_item = QGraphicsRectItem(scaled_rect)
            rect_item.setPen(QPen(QColor("red"), 2))
            self.scene.addItem(rect_item)

            text_item = QGraphicsSimpleTextItem(label)
            text_item.setPos(scaled_rect.x(), scaled_rect.y() - 15)
            text_item.setBrush(QColor("blue"))
            self.scene.addItem(text_item)

            self.rect_items.append((rect_item, text_item))

    def clear_all_annotations(self):
        self.db.delete_all_annotations(self.image_path)
        for rect_item, text_item in self.rect_items:
            self.scene.removeItem(rect_item)
            self.scene.removeItem(text_item)
        self.rect_items.clear()

    def resizeEvent(self, event):
        if self.pixmap_item and self.image_path:
            self.set_image(self.image_path)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = self.mapToScene(event.position().toPoint())
        elif event.button() == Qt.RightButton:
            pos = self.mapToScene(event.position().toPoint())
            for rect_item, text_item in self.rect_items:
                if rect_item.rect().contains(pos):
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

                    break

        self.parent_window.image_view.setFocus()

    def mouseMoveEvent(self, event):
        if self.start_point:
            end_point = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_point, end_point).normalized()
            if hasattr(self, 'temp_rect') and self.temp_rect:
                self.scene.removeItem(self.temp_rect)
            self.temp_rect = QGraphicsRectItem(rect)
            self.temp_rect.setPen(QPen(QColor("red"), 2))
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
            text_item = QGraphicsSimpleTextItem(label)
            text_item.setPos(rect.x(), rect.y() - 15)
            text_item.setBrush(QColor("blue"))
            self.scene.addItem(text_item)

            self.rect_items.append((self.temp_rect, text_item))
            self.temp_rect = None
            self.start_point = None
            self.parent_window.image_view.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Annotator()
    window.show()
    sys.exit(app.exec())
