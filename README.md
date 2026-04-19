# Image Annotator

- A simple Tkinter-based image labeling and bounding box annotation tool
- Manages images under folders by label, and supports both image-level label changes and rectangle annotations
- Annotation data is stored in SQLite and can also be imported/exported as CSV

---

## Main Features

- Load image folders organized by label
- Select labels and images from the Treeview in the left pane
- Change the label of each image
- Add rectangle annotations
- Delete rectangle annotations by right-clicking
- Clear all annotations for the current image
- Export image labels to CSV
- Export / import annotations as CSV

## Screen Layout

### Left Pane

- **Set image folder**: Select the image folder
- **Add Label**: Add a new label folder
- **Clear Annotations**: Delete all rectangle annotations for the current image
- **Export Labels**: Export the list of image labels to CSV
- **Export Annotations**: Export annotations to CSV
- **Import Annotations**: Import annotation CSV
- **Treeview**: Display a list of labels and images

### Right Pane

- File name display
- Combo box for changing the image label
- Combo box for selecting the annotation label
- Image display canvas

## Expected Folder Structure

Create subfolders for each label under the root folder and store images in them.

```text
images_root/
├─ good/
│  ├─ img001.jpg
│  ├─ img002.jpg
│  └─ ...
├─ ng/
│  ├─ img101.jpg
│  ├─ img102.jpg
│  └─ ...
└─ other/
   ├─ img201.jpg
   └─ ...
```

Each subfolder name is treated as an image label.

---

## Supported Image Formats

The currently supported file extensions are:

- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`

---

## Setup

### Requirements

- Python 3.10 or later recommended
- Tkinter
- Pillow
- SQLite3

## How to Run

Example project structure:

```text
project/
├─ main.py
└─ src/
   ├─ canvas.py
   └─ db.py
```

Run:

```bash
python main.py
```

---

## Usage

### 1. Select the Image Folder

- Use **Set image folder** in the left pane to select the root folder that contains label subfolders
- After selection, the image list for each label is displayed in the Treeview

### 2. Select an Image

- When you select an image from the Treeview, it is displayed in the right pane
- If a label node is selected, the first image in that label is displayed

### 3. Change the Image Label

- When you change the label from the combo box in the upper right, the image file itself is moved to the corresponding label folder
- After moving, the **next image in the original label** is displayed, and the Treeview selection also follows that image

### 4. Add a Rectangle Annotation

- Drag the mouse on the image with the left button to create a rectangle
- The rectangle label uses the selected value in the `Annotation Label` combo box; if nothing is selected, the image label is used

### 5. Delete a Rectangle Annotation

- Right-click inside an existing rectangle to delete that rectangle

### 6. Move Between Images

- `←`: Previous image
- `→`: Next image

---

## Data Storage Specification

Annotations are stored in the SQLite `annotations` table.

### Table Structure

- `filename`: Image file name
- `x`, `y`, `width`, `height`: Rectangle coordinates
- `rect_label`: Rectangle label
- `img_label`: Image label

### Database File

- `annotations.db` is used at startup
- If it does not exist, it is created automatically

---

## CSV Import / Export

### Export Labels

Exports a CSV list of image file names and labels

Output columns:

- `file_path`
- `label`

### Export Annotations

Exports annotation data to CSV

Output columns:

- `filename`
- `img_label`
- `x`
- `y`
- `width`
- `height`
- `rect_label`

### Import Annotations

Imports annotation CSV data and adds it to the database

During import, data is saved using `filename`, coordinates, and labels

---

## Current Design Assumptions

### File Names Are Assumed to Be Unique

In the current implementation, image identification mainly uses `filename`.

Therefore, it is assumed that **file names are unique across all images**.

## TODO

- Move / resize / relabel existing rectangles
- Undo / Redo
- Zoom / Pan
- Thumbnail list
