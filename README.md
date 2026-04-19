# Image Annotator
- Tkinter ベースのシンプルな画像ラベリング・バウンディングボックスアノテーションツール  
- フォルダ配下の画像をラベル別に管理し、画像単位のラベル変更と矩形アノテーションの付与を実施  
- アノテーション情報は SQLite に保存。CSV での入出力にも対応  
---

## 主な機能
- ラベルごとの画像フォルダを読み込み
- 左ペインの Treeview でラベル・画像を選択
- 画像ごとのラベル変更
- 矩形アノテーションの追加
- 右クリックによる矩形アノテーション削除
- 画像ごとのアノテーション全削除
- 画像ラベル一覧の CSV 出力
- アノテーションの CSV 出力 / 取込

## 画面構成
### 左ペイン
- **Set image folder**: 画像フォルダ選択
- **Add Label**: ラベル用フォルダを追加
- **Clear Annotations**: 現在画像の矩形アノテーションを全削除
- **Export Labels**: 画像ラベル一覧を CSV 出力
- **Export Annotations**: アノテーションを CSV 出力
- **Import Annotations**: アノテーション CSV を取込
- **Treeview**: ラベルと画像の一覧表示

### 右ペイン
- ファイル名表示
- 画像ラベル変更用コンボボックス
- アノテーションラベル選択用コンボボックス
- 画像表示キャンバス

## 想定するフォルダ構成
ルートフォルダ配下に、ラベル名ごとのサブフォルダを作成して画像を格納します。

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

各サブフォルダ名が画像ラベルとして扱われます。
---

## 対応画像形式
現在の対応拡張子は以下です。
- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`

`IMAGE_EXTS` で判定しています。 fileciteturn1file0L14-L17

---
## セットアップ
### 必要環境
- Python 3.10 以上推奨
- Tkinter
- Pillow
- SQLite3（Python 標準ライブラリ）

## 実行方法
プロジェクト構成の例:

```text
project/
├─ main.py
└─ src/
   ├─ canvas.py
   └─ db.py
```

実行:

```bash
python main.py
```

---

## 使い方

### 1. 画像フォルダを選択

左ペインの **Set image folder** から、ラベル別サブフォルダを含むルートフォルダを選択します。  
選択後、ラベルごとの画像一覧が Treeview に表示されます。 fileciteturn1file0L70-L79

### 2. 画像を選択

Treeview から画像を選択すると、右ペインに画像が表示されます。  
ラベルノードを選んだ場合は、そのラベル内の先頭画像が表示されます。 fileciteturn1file0L223-L246

### 3. 画像ラベルを変更

右上のコンボボックスからラベルを変更すると、画像ファイル自体が該当ラベルのフォルダへ移動します。  
現在の実装では、移動後は**元ラベル側の次画像**を表示し、Treeview もその画像へ追従します。  
また、Treeview の展開状態は保持されます。 fileciteturn1file1L56-L64 fileciteturn1file0L154-L218 fileciteturn1file0L276-L330

### 4. 矩形アノテーションを追加

画像上で左ドラッグすると矩形を作成できます。  
矩形ラベルは `Annotation Label` コンボボックスの選択値が使われ、未選択時は画像ラベルが使われます。 fileciteturn1file1L84-L95 fileciteturn1file1L222-L257

### 5. 矩形アノテーションを削除

既存矩形の内側で右クリックすると、その矩形を削除します。 fileciteturn1file1L259-L281

### 6. 画像移動

- `←`: 前の画像
- `→`: 次の画像

同一ラベル内の画像リストに対して移動します。 fileciteturn1file0L31-L32 fileciteturn1file0L248-L255

---

## データ保存仕様

アノテーションは SQLite の `annotations` テーブルに保存されます。

### テーブル構造

- `filename`: 画像ファイル名
- `x`, `y`, `width`, `height`: 矩形座標
- `rect_label`: 矩形ラベル
- `img_label`: 画像ラベル

テーブル作成処理は `AnnotationDB.create_table()` で行っています。 fileciteturn1file2L13-L24

### DB ファイル

起動時に `annotations.db` を使用します。  
存在しない場合は自動作成されます。 fileciteturn1file0L29-L31

---

## CSV 入出力

### Export Labels

画像ファイル名とラベルの一覧を CSV 出力します。

出力列:

- `file_path`
- `label`

現状は `file_path` 列にフルパスではなくファイル名を書き出しています。 fileciteturn1file0L346-L359

### Export Annotations

アノテーション情報を CSV 出力します。

出力列:

- `filename`
- `img_label`
- `x`
- `y`
- `width`
- `height`
- `rect_label`

`AnnotationDB.export_to_csv()` で出力しています。 fileciteturn1file2L74-L89

### Import Annotations
アノテーション CSV を取り込み、DB に追加します。  
取込時は `filename` と座標・ラベルを使って保存します。 fileciteturn1file2L90-L107

---

## 現在の設計上の前提
### ファイル名は一意である前提
現在の実装では、画像識別に主に `filename` を使っています。  
そのため、**全画像でファイル名が重複しない**前提で使う想定です。  
アノテーションの保存・検索・削除・画像ラベル更新も、この前提に強く依存しています。 fileciteturn1file2L27-L41 fileciteturn1file2L43-L63

## TODO
- 既存矩形の移動 / リサイズ / ラベル変更
- Undo / Redo
- ズーム / パン
- サムネイル一覧

---



