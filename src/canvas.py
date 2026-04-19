# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from PIL import Image, ImageTk

from .db import AnnotationDB


class ImageWithControls(ttk.Frame):
    """Header (filename, label selectors) + image view."""

    def __init__(self, master, parent_window, db: AnnotationDB) -> None:
        super().__init__(master)

        self.parent_window = parent_window
        self.db = db

        self.image_path: Optional[Path] = None
        self.label_list: List[str] = []

        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        self.filename_label = ttk.Label(header_frame, text="")
        self.filename_label.pack(side=tk.LEFT, padx=5)

        self.combo_label = ttk.Combobox(header_frame, state="readonly")
        self.combo_label.pack(side=tk.LEFT, padx=5)
        self.combo_label.bind("<<ComboboxSelected>>", self._on_label_changed)

        anno_frame = ttk.Frame(self)
        anno_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(anno_frame, text="Annotation Label:").pack(side=tk.LEFT, padx=5)

        self.combo_anno = ttk.Combobox(anno_frame, state="readonly")
        self.combo_anno.pack(side=tk.LEFT, padx=5)

        self.view = AnnotatableCanvas(self, parent_window, db)
        self.view.pack(fill=tk.BOTH, expand=True)
        self.view.get_current_anno_label = lambda: self.combo_anno.get()

    def set_image_path(self, image_path: Path, label_list: List[str]) -> None:
        self.image_path = image_path
        self.label_list = label_list

        current_label = image_path.parent.name

        self.combo_label["values"] = self.label_list
        self.combo_label.set(current_label)

        self.combo_anno["values"] = self.label_list
        self.combo_anno.set(current_label)

        self.filename_label.config(text=image_path.name)
        self.view.set_image(image_path)

    def clear_annotations(self) -> None:
        self.view.clear_all_annotations()

    def _on_label_changed(self, event=None) -> None:
        if not self.image_path:
            return

        new_label = self.combo_label.get()
        old_label = self.image_path.parent.name

        if new_label and new_label != old_label and new_label in self.label_list:
            self.image_path = self.parent_window.move_image_to_label(self.image_path, new_label)


class AnnotatableCanvas(tk.Frame):
    """Canvas-based image viewer with rectangle annotations."""

    def __init__(self, master, parent_window, db: AnnotationDB) -> None:
        super().__init__(master)

        self.parent_window = parent_window
        self.db = db

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.image_path: Optional[Path] = None
        self.pil_image: Optional[Image.Image] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None
        self.canvas_image_id: Optional[int] = None

        self.scale_ratio: float = 1.0
        self.orig_width: int = 1
        self.orig_height: int = 1

        self.rect_items: List[Tuple[int, int, Tuple[float, float, float, float], str]] = []
        self.temp_rect_id: Optional[int] = None
        self.temp_start: Optional[Tuple[float, float]] = None

        self.view_scale: float = 1.0
        self.zoom_scale: float = 3.0

        self.get_current_anno_label = lambda: ""

        self.canvas.bind("<Button-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------
    def set_image(self, path: Path) -> None:
        self.image_path = path
        self.canvas.delete("all")
        self.rect_items.clear()
        self.temp_rect_id = None
        self.temp_start = None

        try:
            self.pil_image = Image.open(path).convert("RGB")
        except Exception:
            self.pil_image = None
            return

        self.orig_width, self.orig_height = self.pil_image.size
        self._draw_image_fit()
        self._load_annotations()

    def _draw_image_fit(self) -> None:
        if self.pil_image is None:
            return

        canvas_w = max(self.canvas.winfo_width(), 1)
        canvas_h = max(self.canvas.winfo_height(), 1)

        img = self.pil_image.copy()

        ratio_w = canvas_w / self.orig_width
        ratio_h = canvas_h / self.orig_height
        self.scale_ratio = min(ratio_w, ratio_h)

        new_w = max(1, int(self.orig_width * self.scale_ratio))
        new_h = max(1, int(self.orig_height * self.scale_ratio))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        offset_x = (canvas_w - new_w) // 2
        offset_y = (canvas_h - new_h) // 2

        self.canvas_image_id = self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.tk_image)

    def _redraw_all(self) -> None:
        if self.image_path is None:
            return

        old_rects = []
        for rect_id, text_id, unscaled_rect, label in self.rect_items:
            old_rects.append((unscaled_rect, label))

        self.canvas.delete("all")
        self.rect_items.clear()
        self._draw_image_fit()

        for rect, label in old_rects:
            self._draw_saved_rect(rect, label)

    def _on_resize(self, event=None) -> None:
        if self.pil_image is not None:
            self._redraw_all()

    # ------------------------------------------------------------------
    # Annotation load / clear
    # ------------------------------------------------------------------
    def _load_annotations(self) -> None:
        if not self.image_path:
            return

        for rect, label in self.db.load_annotations(str(self.image_path)):
            x, y, w, h = rect
            unscaled = (x, y, x + w, y + h)
            self._draw_saved_rect(unscaled, label)

    def clear_all_annotations(self) -> None:
        if not self.image_path:
            return

        self.db.delete_all_annotations(str(self.image_path))
        for rect_id, text_id, _, _ in self.rect_items:
            self.canvas.delete(rect_id)
            self.canvas.delete(text_id)
        self.rect_items.clear()
        self.temp_rect_id = None

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _image_offset(self) -> Tuple[float, float]:
        canvas_w = max(self.canvas.winfo_width(), 1)
        canvas_h = max(self.canvas.winfo_height(), 1)
        draw_w = self.orig_width * self.scale_ratio
        draw_h = self.orig_height * self.scale_ratio
        offset_x = (canvas_w - draw_w) / 2
        offset_y = (canvas_h - draw_h) / 2
        return offset_x, offset_y

    def _canvas_to_image(self, x: float, y: float) -> Tuple[float, float]:
        ox, oy = self._image_offset()
        ix = (x - ox) / self.scale_ratio
        iy = (y - oy) / self.scale_ratio
        return ix, iy

    def _image_to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        ox, oy = self._image_offset()
        cx = ox + x * self.scale_ratio
        cy = oy + y * self.scale_ratio
        return cx, cy

    def _draw_saved_rect(self, unscaled_rect: Tuple[float, float, float, float], label: str) -> None:
        x1, y1 = self._image_to_canvas(unscaled_rect[0], unscaled_rect[1])
        x2, y2 = self._image_to_canvas(unscaled_rect[2], unscaled_rect[3])

        rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)
        text_id = self.canvas.create_text(x1, y1 - 15, text=label, fill="blue", anchor="nw")
        self.rect_items.append((rect_id, text_id, unscaled_rect, label))

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------
    def _on_left_down(self, event) -> None:
        self.temp_start = (event.x, event.y)
        self.temp_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2
        )

    def _on_left_drag(self, event) -> None:
        if self.temp_rect_id is None or self.temp_start is None:
            return

        x0, y0 = self.temp_start
        self.canvas.coords(self.temp_rect_id, x0, y0, event.x, event.y)

    def _on_left_up(self, event) -> None:
        if self.temp_rect_id is None or self.temp_start is None or not self.image_path:
            return

        x0, y0 = self.temp_start
        x1, y1 = event.x, event.y

        cx1, cy1 = min(x0, x1), min(y0, y1)
        cx2, cy2 = max(x0, x1), max(y0, y1)

        ix1, iy1 = self._canvas_to_image(cx1, cy1)
        ix2, iy2 = self._canvas_to_image(cx2, cy2)

        ix1 = max(0, min(ix1, self.orig_width))
        iy1 = max(0, min(iy1, self.orig_height))
        ix2 = max(0, min(ix2, self.orig_width))
        iy2 = max(0, min(iy2, self.orig_height))

        if abs(ix2 - ix1) < 1 or abs(iy2 - iy1) < 1:
            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None
            self.temp_start = None
            return

        label = self.get_current_anno_label() or self.image_path.parent.name

        self.db.save_annotation(
            str(self.image_path),
            (ix1, iy1, ix2 - ix1, iy2 - iy1),
            label
        )

        text_id = self.canvas.create_text(cx1, cy1 - 15, text=label, fill="blue", anchor="nw")
        self.rect_items.append((self.temp_rect_id, text_id, (ix1, iy1, ix2, iy2), label))

        self.temp_rect_id = None
        self.temp_start = None

    def _on_right_click(self, event) -> None:
        hit = self._hit_test(event.x, event.y)
        if hit is not None:
            self._delete_rect(hit)
            return

    def _hit_test(self, x: float, y: float) -> Optional[int]:
        for i, (rect_id, text_id, _, _) in enumerate(self.rect_items):
            coords = self.canvas.coords(rect_id)
            if len(coords) == 4:
                x1, y1, x2, y2 = coords
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return i
        return None

    def _delete_rect(self, index: int) -> None:
        if not self.image_path:
            return

        rect_id, text_id, unscaled_rect, _ = self.rect_items[index]
        x1, y1, x2, y2 = unscaled_rect

        self.db.delete_annotation(
            str(self.image_path),
            (x1, y1, x2 - x1, y2 - y1)
        )

        self.canvas.delete(rect_id)
        self.canvas.delete(text_id)
        del self.rect_items[index]

