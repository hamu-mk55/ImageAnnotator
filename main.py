# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from src.canvas import ImageWithControls
from src.db import AnnotationDB


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def is_image(path: Path) -> bool:
    """Return True if the path has a supported image file extension."""
    return path.suffix.lower() in IMAGE_EXTS


class Annotator(tk.Tk):
    """Main application window coordinating folders, labels, and the image view."""

    def __init__(self) -> None:
        """Initialize application state, database access, UI, and key bindings."""
        super().__init__()

        self.title("ImageAnnotator")
        self.geometry("1200x800")

        self.root_folder: Path = Path()
        self.image_dict: Dict[str, List[Path]] = {}

        self.current_label: Optional[str] = None
        self.current_images: List[Path] = []
        self.current_index: int = 0

        self.db = AnnotationDB("annotations.db")

        self._init_ui()
        self.bind("<Left>", lambda e: self._show_prev_image())
        self.bind("<Right>", lambda e: self._show_next_image())

    def _init_ui(self) -> None:
        """Create the folder controls, label tree, and image display area."""
        main_pane = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # ---------------- Left panel ----------------
        left_frame = ttk.Frame(main_pane, width=300)
        main_pane.add(left_frame, weight=0)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        buttons = [
            ("Set image folder", self._choose_image_folder),
            ("Add Label", self._add_label),
            ("Clear Annotations", self._clear_current_annotations),
            ("Export Labels", self._export_labels_csv),
            ("Export Annotations", self._export_annotations_csv),
            ("Import Annotations", self._import_annotations_csv),
        ]

        for text, cmd in buttons:
            ttk.Button(btn_frame, text=text, command=cmd).pack(fill=tk.X, pady=2)

        self.label_tree = ttk.Treeview(left_frame, show="tree")
        self.label_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.label_tree.bind("<<TreeviewSelect>>", self._on_label_item_clicked)

        # ---------------- Right panel ----------------
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        self.image_with_controls = ImageWithControls(right_frame, self, self.db)
        self.image_with_controls.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Folder / Labels
    # ------------------------------------------------------------------
    def _choose_image_folder(self) -> None:
        """Select the image root folder, scan labels/images, and refresh the tree."""
        folder = filedialog.askdirectory(title="Select image folder")
        if not folder:
            return

        root = Path(folder)
        if not root.exists():
            messagebox.showwarning("Folder not found", str(root))
            return

        self.root_folder = root
        self._scan_labels_and_images()
        self._remake_label_tree()

    def _scan_labels_and_images(self) -> None:
        """Build the label-to-image-path mapping from subfolders under the root folder."""
        self.image_dict.clear()
        if not self.root_folder:
            return

        for child in sorted(self.root_folder.iterdir()):
            if child.is_dir():
                label = child.name
                paths = sorted(
                    [p for p in child.iterdir() if p.is_file() and is_image(p)],
                    key=lambda p: p.name.lower()
                )
                self.image_dict[label] = paths

    def _remake_label_tree(self, preferred_selection=None) -> None:
        """
        Rebuild the label tree while preserving expanded labels and selection.

        Args:
            preferred_selection: Optional item to select after rebuilding.
                Use ("label", label) for a label node or
                ("image", label, image_name) for an image node.
        """
        # 現在開いているラベルを保存
        open_labels = set()
        for item_id in self.label_tree.get_children():
            label = self.label_tree.item(item_id, "text")
            if self.label_tree.item(item_id, "open"):
                open_labels.add(label)

        # 現在選択中の項目を保存（preferred_selection が無いときの復元用）
        selected_value = None
        if preferred_selection is None:
            selected = self.label_tree.selection()
            if selected:
                item_id = selected[0]
                parent_id = self.label_tree.parent(item_id)
                if parent_id:
                    label = self.label_tree.item(parent_id, "text")
                    image_name = self.label_tree.item(item_id, "text")
                    selected_value = ("image", label, image_name)
                else:
                    label = self.label_tree.item(item_id, "text")
                    selected_value = ("label", label)
        else:
            selected_value = preferred_selection

        # 再構築
        self.label_tree.delete(*self.label_tree.get_children())

        restore_selection_id = None

        for label in sorted(self.image_dict.keys(), key=str.lower):
            should_open = (label in open_labels)

            # 優先選択先がこのラベル配下なら開く
            if selected_value:
                if selected_value[0] == "label" and selected_value[1] == label:
                    should_open = True
                elif selected_value[0] == "image" and selected_value[1] == label:
                    should_open = True

            parent_id = self.label_tree.insert(
                "",
                "end",
                text=label,
                values=("label", label),
                open=should_open
            )

            if selected_value == ("label", label):
                restore_selection_id = parent_id

            for img_path in self.image_dict[label]:
                child_id = self.label_tree.insert(
                    parent_id,
                    "end",
                    text=img_path.name,
                    values=("image", label, img_path.name)
                )

                if selected_value == ("image", label, img_path.name):
                    restore_selection_id = child_id

        if restore_selection_id:
            self.label_tree.selection_set(restore_selection_id)
            self.label_tree.focus(restore_selection_id)
            self.label_tree.see(restore_selection_id)

    def _add_label(self) -> None:
        """Prompt for a new label, create its folder, and refresh the label tree."""
        if not self.root_folder:
            messagebox.showinfo("Tip", "Please set the image folder first.")
            return

        text = simpledialog.askstring("New Label", "Label:")
        if text:
            new_dir = self.root_folder / text
            new_dir.mkdir(parents=True, exist_ok=True)
            self.image_dict.setdefault(text, [])
            self._remake_label_tree()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_label_item_clicked(self, event=None) -> None:
        """Handle tree selection changes and display the selected image."""
        selected = self.label_tree.selection()
        if not selected:
            return

        item_id = selected[0]
        parent_id = self.label_tree.parent(item_id)

        if parent_id:
            label = self.label_tree.item(parent_id, "text")
            image_name = self.label_tree.item(item_id, "text")
            full_path = self.root_folder / label / image_name

            self.current_label = label
            self.current_images = self.image_dict.get(label, [])
            try:
                self.current_index = self.current_images.index(full_path)
            except ValueError:
                self.current_index = 0
        else:
            label = self.label_tree.item(item_id, "text")
            self.current_label = label
            self.current_images = self.image_dict.get(label, [])
            self.current_index = 0

        self._update_image_display()

    def _show_next_image(self) -> None:
        """Advance to the next image in the current label, if available."""
        if self.current_index + 1 < len(self.current_images):
            self.current_index += 1
            self._update_image_display()

    def _show_prev_image(self) -> None:
        """Move to the previous image in the current label, if available."""
        if self.current_index - 1 >= 0:
            self.current_index -= 1
            self._update_image_display()

    def _update_image_display(self) -> None:
        """Display the current image and refresh the available label choices."""
        if not self.current_images:
            return

        image_path = self.current_images[self.current_index]
        labels = sorted(self.image_dict.keys(), key=str.lower)
        self.image_with_controls.set_image_path(image_path, labels)

    # ------------------------------------------------------------------
    # File Move / Label Change
    # ------------------------------------------------------------------
    def move_image_to_label(self, image_path: Path, new_label: str) -> Path:
        """
        Move an image to another label folder and refresh related UI state.

        Args:
            image_path: Current path of the image to move.
            new_label: Destination label folder name.

        Returns:
            The new image path after a successful move, or the original path if no move occurred.
        """
        old_label = image_path.parent.name
        if old_label == new_label:
            return image_path

        file_name = image_path.name
        new_dir = self.root_folder / new_label
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / file_name

        if new_path.exists():
            messagebox.showwarning(
                "File already exists",
                f"Cannot move this image because the destination already exists:\n{new_path}"
            )
            return image_path

        # 旧ラベル内での元の位置を記録
        old_list = self.image_dict.get(old_label, [])
        try:
            old_index = old_list.index(image_path)
        except ValueError:
            old_index = 0

        # ファイル移動
        image_path.replace(new_path)

        # image_dict 更新
        if image_path in old_list:
            old_list.remove(image_path)

        self.image_dict.setdefault(new_label, [])
        self.image_dict[new_label].append(new_path)
        self.image_dict[new_label].sort(key=lambda p: p.name.lower())

        # DB側の画像ラベル更新
        self.db.update_label(str(new_path))

        # 移動後は old_label 側の次画像を表示し続ける
        self.current_label = old_label
        self.current_images = self.image_dict.get(old_label, [])

        preferred_selection = None

        if self.current_images:
            self.current_index = min(old_index, len(self.current_images) - 1)
            next_image = self.current_images[self.current_index]
            preferred_selection = ("image", old_label, next_image.name)

            # Treeview再構築 + 次画像ノードを選択
            self._remake_label_tree(preferred_selection=preferred_selection)

            # 画面表示も次画像へ
            self._update_image_display()
        else:
            # 旧ラベルが空になった場合は old_label ノードを選択
            preferred_selection = ("label", old_label)
            self._remake_label_tree(preferred_selection=preferred_selection)

            self.current_index = 0
            self.current_label = old_label
            self.current_images = []

            self.image_with_controls.view.canvas.delete("all")
            self.image_with_controls.view.rect_items.clear()
            self.image_with_controls.image_path = None
            self.image_with_controls.filename_label.config(text="")
            self.image_with_controls.combo_label.set("")
            self.image_with_controls.combo_anno.set("")

        return new_path

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def _export_annotations_csv(self) -> None:
        """Prompt for a CSV file path and export saved rectangle annotations."""
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if path:
            self.db.export_to_csv(path)

    def _import_annotations_csv(self) -> None:
        """Prompt for a CSV file and import rectangle annotations into the database."""
        path = filedialog.askopenfilename(
            title="Import CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if path:
            self.db.import_from_csv(path)
            messagebox.showinfo("Import", f"Imported annotations from:\n{path}")

    def _export_labels_csv(self) -> None:
        """Prompt for a CSV file path and export the current image-label mapping."""
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file_path", "label"])
            for label, img_paths in self.image_dict.items():
                for img_path in img_paths:
                    writer.writerow([img_path.name, label])

    # ------------------------------------------------------------------
    def _clear_current_annotations(self) -> None:
        """Clear all rectangle annotations for the currently displayed image."""
        self.image_with_controls.clear_annotations()




if __name__ == "__main__":
    app = Annotator()
    app.mainloop()
