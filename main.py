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

        self._init_menu()
        self._init_ui()
        self.bind("<Left>", lambda e: self._show_prev_image())
        self.bind("<Right>", lambda e: self._show_next_image())

    def _init_menu(self) -> None:
        """Create the application menu bar."""
        menu_bar = tk.Menu(self)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Close", command=self.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)

        import_menu = tk.Menu(menu_bar, tearoff=False)
        import_menu.add_command(label="Annotation", command=self._import_annotations_csv)
        menu_bar.add_cascade(label="Import", menu=import_menu)

        export_menu = tk.Menu(menu_bar, tearoff=False)
        export_menu.add_command(label="Label", command=self._export_labels_csv)
        export_menu.add_command(label="Annotation", command=self._export_annotations_csv)
        menu_bar.add_cascade(label="Export", menu=export_menu)

        self.config(menu=menu_bar)

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
        ]

        for text, cmd in buttons:
            ttk.Button(btn_frame, text=text, command=cmd).pack(fill=tk.X, pady=2)

        label_select_frame = ttk.Frame(left_frame)
        label_select_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Label(label_select_frame, text="Label:").pack(side=tk.LEFT)

        self.label_combo = ttk.Combobox(label_select_frame, state="readonly")
        self.label_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.label_combo.bind("<<ComboboxSelected>>", self._on_label_combo_selected)

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
                    key=lambda p: p.name.lower(),
                )
                self.image_dict[label] = paths

    def _remake_label_tree(self, preferred_selection=None) -> None:
        """
        Rebuild the file tree for the selected label.

        Args:
            preferred_selection: Optional item to select after rebuilding.
                Use ("label", label) to select a label or
                ("image", label, image_name) to select a file in a label.
        """
        labels = sorted(self.image_dict.keys(), key=str.lower)
        self.label_combo["values"] = labels

        selected_value = preferred_selection
        selected_image_name = None
        if selected_value is None:
            selected = self.label_tree.selection()
            if selected:
                item_id = selected[0]
                values = self.label_tree.item(item_id, "values")
                if len(values) >= 3 and values[0] == "image":
                    selected_value = ("image", values[1], values[2])

        label_to_show = self.current_label
        if selected_value:
            if selected_value[0] == "label":
                label_to_show = selected_value[1]
            elif selected_value[0] == "image":
                label_to_show = selected_value[1]
                selected_image_name = selected_value[2]

        if label_to_show not in self.image_dict:
            label_to_show = labels[0] if labels else None

        self.label_tree.delete(*self.label_tree.get_children())

        if label_to_show is None:
            self.current_label = None
            self.current_images = []
            self.current_index = 0
            self.label_combo.set("")
            return

        self.current_label = label_to_show
        self.current_images = self.image_dict.get(label_to_show, [])
        self.label_combo.set(label_to_show)

        restore_selection_id = None
        for index, img_path in enumerate(self.current_images):
            child_id = self.label_tree.insert(
                "",
                "end",
                text=img_path.name,
                values=("image", label_to_show, img_path.name),
            )
            if selected_image_name == img_path.name:
                restore_selection_id = child_id
                self.current_index = index

        if restore_selection_id is None and self.current_images:
            restore_selection_id = self.label_tree.get_children()[0]
            self.current_index = 0

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
    def _on_label_combo_selected(self, event=None) -> None:
        """Show files for the selected label."""
        label = self.label_combo.get()
        if not label:
            return

        self.current_label = label
        self.current_images = self.image_dict.get(label, [])
        self.current_index = 0
        self._remake_label_tree(preferred_selection=("label", label))
        self._update_image_display()

    def _on_label_item_clicked(self, event=None) -> None:
        """Handle file selection changes and display the selected image."""
        selected = self.label_tree.selection()
        if not selected:
            return

        item_id = selected[0]
        values = self.label_tree.item(item_id, "values")
        if len(values) < 3 or values[0] != "image":
            return

        label = values[1]
        image_name = values[2]
        full_path = self.root_folder / label / image_name

        self.current_label = label
        self.current_images = self.image_dict.get(label, [])
        try:
            self.current_index = self.current_images.index(full_path)
        except ValueError:
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
            self._clear_image_display()
            return

        image_path = self.current_images[self.current_index]
        labels = sorted(self.image_dict.keys(), key=str.lower)
        self.image_with_controls.set_image_path(image_path, labels)

    def _clear_image_display(self) -> None:
        """Clear the image display and label selector state."""
        self.image_with_controls.view.canvas.delete("all")
        self.image_with_controls.view.rect_items.clear()
        self.image_with_controls.image_path = None
        self.image_with_controls.filename_label.config(text="")
        self.image_with_controls.clear_label_buttons()

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
                f"Cannot move this image because the destination already exists:\n{new_path}",
            )
            return image_path

        # 譌ｧ繝ｩ繝吶Ν蜀・〒縺ｮ蜈・・菴咲ｽｮ繧定ｨ倬鹸
        old_list = self.image_dict.get(old_label, [])
        try:
            old_index = old_list.index(image_path)
        except ValueError:
            old_index = 0

        image_path.replace(new_path)

        if image_path in old_list:
            old_list.remove(image_path)

        self.image_dict.setdefault(new_label, [])
        self.image_dict[new_label].append(new_path)
        self.image_dict[new_label].sort(key=lambda p: p.name.lower())

        self.db.update_label(str(new_path))

        self.current_label = old_label
        self.current_images = self.image_dict.get(old_label, [])

        if self.current_images:
            self.current_index = min(old_index, len(self.current_images) - 1)
            next_image = self.current_images[self.current_index]
            self._remake_label_tree(
                preferred_selection=("image", old_label, next_image.name)
            )
            self._update_image_display()
        else:
            self.current_index = 0
            self.current_label = old_label
            self.current_images = []
            self._remake_label_tree(preferred_selection=("label", old_label))
            self._clear_image_display()

        return new_path

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def _export_annotations_csv(self) -> None:
        """Prompt for a CSV file path and export saved rectangle annotations."""
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if path:
            self.db.export_to_csv(path)

    def _import_annotations_csv(self) -> None:
        """Prompt for a CSV file and import rectangle annotations into the database."""
        path = filedialog.askopenfilename(
            title="Import CSV", filetypes=[("CSV files", "*.csv")]
        )
        if path:
            self.db.import_from_csv(path)
            messagebox.showinfo("Import", f"Imported annotations from:\n{path}")

    def _export_labels_csv(self) -> None:
        """Prompt for a CSV file path and export the current image-label mapping."""
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
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
