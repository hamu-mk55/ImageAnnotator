# -*- coding: utf-8 -*-
"""Tkinter canvas widgets for displaying images and editing annotations."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .db import AnnotationDB


class ImageWithControls(ttk.Frame):
    """Composite widget containing image controls and the annotation canvas."""

    def __init__(self, master, parent_window, db: AnnotationDB) -> None:
        """Create filename display, label selectors, and the image canvas."""
        super().__init__(master)

        self.parent_window = parent_window
        self.db = db

        self.image_path: Optional[Path] = None
        self.label_list: List[str] = []
        self.current_annotation_label: str = ""

        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(header_frame, text="Filename:", width=16, anchor=tk.W).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.filename_label = ttk.Label(header_frame, text="")
        self.filename_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(header_frame, text="Change Label:", width=16, anchor=tk.W).grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.label_button_frame = ttk.Frame(header_frame)
        self.label_button_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(header_frame, text="Annotation Label:", width=16, anchor=tk.W).grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )

        self.annotation_button_frame = ttk.Frame(header_frame)
        self.annotation_button_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        self.view = AnnotatableCanvas(self, parent_window, db)
        self.view.pack(fill=tk.BOTH, expand=True)
        self.view.get_current_anno_label = lambda: self.current_annotation_label

    def set_image_path(self, image_path: Path, label_list: List[str]) -> None:
        """Set the active image and refresh label selectors for it."""
        self.image_path = image_path
        self.label_list = label_list

        current_label = image_path.parent.name

        self.current_annotation_label = current_label

        self.filename_label.config(text=image_path.name)
        self._render_label_buttons(current_label)
        self._render_annotation_buttons()
        self.view.set_image(image_path)

    def clear_annotations(self) -> None:
        """Clear all annotations for the currently displayed image."""
        self.view.clear_all_annotations()

    def clear_label_buttons(self) -> None:
        """Clear label and annotation selection buttons."""
        self._clear_buttons(self.label_button_frame)
        self._clear_buttons(self.annotation_button_frame)
        self.current_annotation_label = ""

    def _render_label_buttons(self, current_label: str) -> None:
        """Render image label change buttons."""
        self._clear_buttons(self.label_button_frame)
        for index, label in enumerate(self.label_list):
            button = ttk.Button(
                self.label_button_frame,
                text=label,
                command=lambda selected=label: self._on_label_selected(selected),
            )
            if label == current_label:
                button.state(["disabled"])
            self._grid_label_button(button, index)

    def _render_annotation_buttons(self) -> None:
        """Render annotation label selection buttons."""
        self._clear_buttons(self.annotation_button_frame)
        for index, label in enumerate(self.label_list):
            button = ttk.Button(
                self.annotation_button_frame,
                text=label,
                command=lambda selected=label: self._on_annotation_label_selected(
                    selected
                ),
            )
            if label == self.current_annotation_label:
                button.state(["disabled"])
            self._grid_label_button(button, index)

    def _grid_label_button(self, button: ttk.Button, index: int) -> None:
        """Place label buttons in one row, wrapping to two rows when needed."""
        if len(self.label_list) > 6:
            columns = max(1, (len(self.label_list) + 1) // 2)
        else:
            columns = max(1, len(self.label_list))

        row = index // columns
        column = index % columns
        button.grid(row=row, column=column, sticky=tk.W, padx=(0, 5), pady=2)

    def _clear_buttons(self, frame: ttk.Frame) -> None:
        """Remove all buttons from a selector frame."""
        for child in frame.winfo_children():
            child.destroy()

    def _on_label_selected(self, new_label: str) -> None:
        """Move the current image when an image label button is selected."""
        if not self.image_path:
            return

        old_label = self.image_path.parent.name

        if new_label and new_label != old_label and new_label in self.label_list:
            new_path = self.parent_window.move_image_to_label(self.image_path, new_label)
            if new_path == self.image_path:
                self._render_label_buttons(old_label)
            else:
                self.image_path = new_path

    def _on_annotation_label_selected(self, new_label: str) -> None:
        """Set the label used for newly drawn annotations."""
        self.current_annotation_label = new_label
        self._render_annotation_buttons()


class AnnotatableCanvas(tk.Frame):
    """Canvas-based image viewer with rectangle annotations."""

    def __init__(self, master, parent_window, db: AnnotationDB) -> None:
        """Initialize canvas state and bind mouse and resize events."""
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

        self.rect_items: List[
            Tuple[int, int, Tuple[float, float, float, float], str]
        ] = []
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
        """Load an image, fit it to the canvas, and draw saved annotations."""
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
        """Draw the current image scaled to fit within the canvas."""
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

        self.canvas_image_id = self.canvas.create_image(
            offset_x, offset_y, anchor="nw", image=self.tk_image
        )

    def _redraw_all(self) -> None:
        """Redraw the image and all visible rectangles after a canvas change."""
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
        """Redraw the image and annotations when the canvas is resized."""
        if self.pil_image is not None:
            self._redraw_all()

    # ------------------------------------------------------------------
    # Annotation load / clear
    # ------------------------------------------------------------------
    def _load_annotations(self) -> None:
        """Load saved annotations for the current image and draw them."""
        if not self.image_path:
            return

        for rect, label in self.db.load_annotations(str(self.image_path)):
            x, y, w, h = rect
            unscaled = (x, y, x + w, y + h)
            self._draw_saved_rect(unscaled, label)

    def clear_all_annotations(self) -> None:
        """Delete all saved and visible annotations for the current image."""
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
        """Return the top-left canvas offset of the fitted image."""
        canvas_w = max(self.canvas.winfo_width(), 1)
        canvas_h = max(self.canvas.winfo_height(), 1)
        draw_w = self.orig_width * self.scale_ratio
        draw_h = self.orig_height * self.scale_ratio
        offset_x = (canvas_w - draw_w) / 2
        offset_y = (canvas_h - draw_h) / 2
        return offset_x, offset_y

    def _canvas_to_image(self, x: float, y: float) -> Tuple[float, float]:
        """Convert canvas coordinates to original image coordinates."""
        ox, oy = self._image_offset()
        ix = (x - ox) / self.scale_ratio
        iy = (y - oy) / self.scale_ratio
        return ix, iy

    def _image_to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """Convert original image coordinates to canvas coordinates."""
        ox, oy = self._image_offset()
        cx = ox + x * self.scale_ratio
        cy = oy + y * self.scale_ratio
        return cx, cy

    def _draw_saved_rect(
        self, unscaled_rect: Tuple[float, float, float, float], label: str
    ) -> None:
        """Draw a saved rectangle and label using original image coordinates."""
        x1, y1 = self._image_to_canvas(unscaled_rect[0], unscaled_rect[1])
        x2, y2 = self._image_to_canvas(unscaled_rect[2], unscaled_rect[3])

        rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)
        text_id = self.canvas.create_text(
            x1, y1 - 15, text=label, fill="blue", anchor="nw"
        )
        self.rect_items.append((rect_id, text_id, unscaled_rect, label))

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------
    def _on_left_down(self, event) -> None:
        """Start drawing a temporary rectangle at the mouse position."""
        self.temp_start = (event.x, event.y)
        self.temp_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2
        )

    def _on_left_drag(self, event) -> None:
        """Resize the temporary rectangle while the mouse is dragged."""
        if self.temp_rect_id is None or self.temp_start is None:
            return

        x0, y0 = self.temp_start
        self.canvas.coords(self.temp_rect_id, x0, y0, event.x, event.y)

    def _on_left_up(self, event) -> None:
        """Finalize a drawn rectangle, save it, and attach its label."""
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
            str(self.image_path), (ix1, iy1, ix2 - ix1, iy2 - iy1), label
        )

        text_id = self.canvas.create_text(
            cx1, cy1 - 15, text=label, fill="blue", anchor="nw"
        )
        self.rect_items.append(
            (self.temp_rect_id, text_id, (ix1, iy1, ix2, iy2), label)
        )

        self.temp_rect_id = None
        self.temp_start = None

    def _on_right_click(self, event) -> None:
        """Delete the rectangle under the mouse cursor, if any."""
        hit = self._hit_test(event.x, event.y)
        if hit is not None:
            self._delete_rect(hit)
            return

    def _hit_test(self, x: float, y: float) -> Optional[int]:
        """Return the index of the rectangle containing a canvas point."""
        for i, (rect_id, text_id, _, _) in enumerate(self.rect_items):
            coords = self.canvas.coords(rect_id)
            if len(coords) == 4:
                x1, y1, x2, y2 = coords
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return i
        return None

    def _delete_rect(self, index: int) -> None:
        """Delete one rectangle annotation by index from the database and canvas."""
        if not self.image_path:
            return

        rect_id, text_id, unscaled_rect, _ = self.rect_items[index]
        x1, y1, x2, y2 = unscaled_rect

        self.db.delete_annotation(str(self.image_path), (x1, y1, x2 - x1, y2 - y1))

        self.canvas.delete(rect_id)
        self.canvas.delete(text_id)
        del self.rect_items[index]
