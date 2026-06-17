# Cell Period Estimator

一個 PySide6 桌面工具，用來估測半導體 **EBeam 掃描**影像中重複的 **cell 週期**
——也就是「Golden Cell」節距——並支援 **cell-to-cell** 缺陷偵測流程。

給定一張規則陣列（記憶體 cell、標準單元列、line/space 光柵……）的掃描影像，
它會找出水平/垂直的重複週期 `(px, py)`，用畫面中每一個完整 cell 堆疊出一張
Golden Cell，並量化週期對齊的好壞，讓你在跑 cell-to-cell 比對之前就能信任它。

> **核心概念：** 如果週期正確，每個 cell 都會對齊、堆疊結果**銳利**；如果週期
> 錯誤，cell 會彼此漂移、堆疊結果**疊影（模糊）**。因此「銳利度」同時用來
> *驗證* 與 *細修* 週期。

## 功能特色

- **穩健的週期估測**（純 NumPy/OpenCV 核心，不依賴 Qt）：以強度投影 FFT 取得
  粗略週期，再用正規化自相關（搭配拋物線次像素內插與諧波修正）交叉驗證與細修。
  調變閘會在平坦的軸上抑制假週期（例如 line/space 圖案的正交軸）。
- **軸向模式偵測**：`X`、`Y`、`XY` 或 `NONE`，以彩色徽章顯示。
- **Golden Cell 堆疊**：`mean`（對相位誤差敏感、會暴露疊影）或 `median`
  （對缺陷穩健），可選擇隨機取樣。
- **銳利度 / 疊影分數**用來驗證對齊（堆疊銳利 → 已對齊，堆疊模糊 → 週期錯誤）。
- **Auto-optimize**：掃描鄰域、挑出最銳利的堆疊來自動最佳化週期。
- **FFT 頻譜圖** 與 **候選比較網格**（半 / 倍諧波），讓你一眼挑出正確的基頻。
- **匯出**：將 Golden Cell 存成 PNG，並把中繼資料
  （`period / roi / axis_mode / confidence / score`）存成 JSON。
- **GLAS** 柔和暖色淺色系 UI 主題（見 [`UI 主題`](#ui-主題)）。

## 安裝

```bash
pip install -r requirements.txt
# 或安裝為套件（會提供 console 進入點）：
pip install .
```

需求：`PySide6`、`opencv-python`、`numpy`（Python ≥ 3.9）。

## 啟動

```bash
python -m cell_period_estimator
```

若安裝為套件，也可使用 console 進入點：

```bash
cell-period-estimator
```

## 操作流程

1. **載入影像** — 開啟一張 EBeam 掃描影像（PNG/TIFF/JPG/BMP，以灰階讀入）。
   除了 **Load Image** 按鈕，你也可以**把檔案 / 圖片直接拖曳到視窗**，或用
   **Ctrl+V** 貼上剪貼簿裡的影像或複製的圖檔。中文（非 ASCII）的檔名 / 路徑
   也完全支援。
2. **Crop ROI** *(可選)* — 勾選 Crop ROI 並拖出一個矩形，把分析限制在乾淨的
   週期區域；用 **Clear ROI** 重置。
3. **Estimate Period** — 在背景執行緒執行；結果會填入 X/Y 週期 spinbox 與
   confidence。這顆主要按鈕同時出現在工具列與右側結果欄頂端。
4. **看軸向徽章 / FFT 頻譜** — 確認偵測到的軸向模式，以及頻譜峰落在預期的週期上。
5. **用 Golden Cell 驗證** — 檢視堆疊出的 cell 及其銳利度 / 疊影判定；依需要切換
   `mean`/`median` 與取樣數。用 **Auto-optimize ±** 吸附到最銳利的週期。
6. **比較候選** — 候選網格會堆疊半 / 倍諧波，最銳利的會被標示；點任一候選即可採用。
7. **匯出** — **Export GC** 存出 Golden Cell PNG；**Export JSON** 存出
   `period / roi / axis_mode / confidence / score`。

## 控制項參考

### 載入影像的方式

| 方式 | 說明 |
|---|---|
| **Load Image 按鈕** | 開啟檔案對話框，選 PNG/TIFF/JPG/BMP。 |
| **拖曳（Drag & Drop）** | 把影像檔或圖片直接拖進視窗。 |
| **Ctrl+V 貼上** | 貼上剪貼簿裡的截圖 / 圖片，或複製的圖檔。 |

> 所有載入路徑都透過 `np.fromfile` + `cv2.imdecode` 讀取，因此**中文 / 非 ASCII
> 的檔名與資料夾路徑都能正確載入**（這是某些平台上 `cv2.imread` 會失敗的情況）。

### 工具列

| 按鈕 | 功能 |
|---|---|
| **Load Image** | 開啟 PNG/TIFF/JPG/BMP，以灰階讀入。 |
| **Estimate Period** *(主要、橙色)* | 在背景執行緒估測整張影像（或 ROI）的週期。工具列與結果欄頂端各有一顆，共用同一動作。 |
| **Crop ROI** *(切換)* | 拖出橡皮筋矩形以限制分析範圍；發出影像座標的 `(x, y, w, h)`。 |
| **Clear ROI** | 移除 ROI，重新分析整張影像。 |
| **Export GC** | 將目前的 Golden Cell 堆疊存成 PNG。 |
| **Export JSON** | 存出中繼資料：`px/py, roi, axis_mode, confidence, score`。 |

### PERIOD 面板

- **軸向模式徽章** — 偵測到的週期方向（見下表）。
- **X period / Y period** — 量到的 `px / py`；上方為大字讀數卡（含 confidence
  副標），下方為可編輯的 spinbox。
- **Confidence** — 各軸 0–100，由自相關強度推得，顯示在讀數卡的副標。
- **Min period** — 搜尋的下界（`auto` ⇒ 自適應，底限 4 px）；提高下界可避免鎖到
  很小的雜訊週期。
- **Optimize range (±N) + Auto-optimize ±** — 在目前 `px/py` 的 ±N 鄰域掃描，
  保留最銳利的堆疊（依**原始** Laplacian 變異數排名，而非會飽和的 0–100 分數）。

### Golden Cell 面板

- **method** — `mean`（預設；對相位誤差敏感、*刻意*暴露疊影）或 `median`
  （對稀疏缺陷穩健）。
- **samples** — 堆疊所有 cell，或隨機子集（16/32/64/128）以加速。
- **preview + sharpness** — 堆疊出的 cell，加上分數與判定
  （`aligned` / `marginal` / `ghosting`）。

## 如何閱讀各視圖

> 這個工具裡**沒有亮度直方圖**。那張看起來像直方圖的圖其實是 **FFT 頻譜**。

### 影像視圖與週期格線

- 偵測到週期後，影像上會疊一層**週期格線**：橙色主線配**暗色描邊**，因此在
  明亮與深色的 cell 上都看得清楚；線寬不隨縮放改變。
- 左上角的小**十字標記**是晶格原點，讓格線的相位一目了然。

### FFT 頻譜

- **X 軸 = 週期（px）**、**Y 軸 = 正規化幅度（0–1）**。
- **橙線 = X 軸**頻譜，**藍線 = Y 軸**頻譜（藍是冷色語意標記，刻意不當作第二個
  強調色）。
- **白色虛線 = 偵測到的峰週期**（`p=…`）。
- 在你預期的 cell 尺寸附近有銳利、突出的峰 ⇒ 乾淨的週期；平坦的曲線 ⇒ 該軸無週期。

### Golden Cell 預覽

- 把**每個完整 cell**取 mean/median 堆疊在一起。
- **銳利清楚 ⇒ 週期正確**（cell 對齊；雜訊被平均掉、特徵被強化）。
- **模糊 / 重影 ⇒ 週期錯誤**（cell 未對齊 ⇒ 疊影）。
- **銳利度分數**用 Laplacian 變異數量化這一點。

### 候選網格

- 主要週期的諧波鄰居：`px/2, 2px, py/2, 2py, half, double`。
- 每個都被堆疊並標上**相對銳利度 %**；最銳利的會以 **accent 邊框**標示。
  點任一候選即可採用——當估測器鎖到半 / 倍諧波時很好用。

### 軸向模式徽章

| 徽章 | 顏色 | 意義 |
|---|---|---|
| **XY** | 綠 | 兩軸都有週期（典型的 2-D cell 陣列） |
| **X** / **Y** | 暖橙 | 只有一軸有週期（例如垂直 line/space ⇒ 只有 X） |
| **NONE** | 紅 | 未偵測到週期 |

## 運作原理

`estimate_period` 會獨立處理 X 與 Y 軸：

1. **投影（Projection）** — 沿正交軸平均亮度 → 一維訊號（強度投影）。
2. **高通去趨勢（High-pass detrend）** — 減去邊緣補值的移動平均（視窗 ≈ 長度的
   ¼）以移除照明梯度 / 邊界假影。
3. **調變閘（Modulation gate）** — 若投影近乎平坦（std < 0.5），該軸判定為
   非週期。這就是為什麼垂直 line/space 圖案的 Y 軸會回傳 `None`：每一列都相同，
   Y 沒有變化，雜訊也無法被正規化成假週期。
4. **FFT 粗估 + 自相關細修** — `[lo, hi]` 頻帶內的 rFFT 峰是粗略候選，但對內容
   豐富的 cell，FFT 峰常落在**諧波**上（例如真實週期 40 在 20 處出現強峰）。
   **基頻由自相關決定**：挑出 lag 頻帶內最強的*局部極大值*（這會跳過 lag 0
   附近的高相關區與諧波低谷），再以拋物線擬合細修到次像素。
5. **諧波修正** — 若 `ac(2p) > 1.15·ac(p)` 取 `2p`（找到的是一半）；若 `p`
   為偶數且 `ac(p/2) ≥ 0.9·ac(p)` 取 `p/2`（找到的是一倍）。
6. **Confidence** = 自相關強度 × 100。

驗證與細修（`core/stacking.py`）：

- `tile_coords` — 每個**完整** cell 的左上角（cell 擺放的單一真實來源）。
- `stack_cells` — 把這些 cell 取平均/中位數堆成一張 Golden Cell。
- `ghosting_score` — Laplacian 變異數 ⇒ 對齊時高、疊影時低。
- `refine_period` — 鄰域掃描，保留最高的**原始** Laplacian 變異數（這驅動
  Auto-optimize）。

一句話總結：

> **投影 → 去趨勢 → FFT 粗估 + 自相關定基頻 → 堆疊成 Golden Cell → 用銳利度
> 驗證 / 細修週期。**

## 專案結構

```
cell_period_estimator/
  __init__.py        # __version__
  __main__.py        # 進入點：套用主題、QApplication + MainWindow；main()
  core/              # 不含 Qt 的演算法
    period_core.py   # estimate_period, PeriodResult, AxisSpectrum, choose_origin
    stacking.py      # tile_coords, stack_cells, ghosting_score, refine_period,
                     # candidate_periods
  ui/
    theme.py         # GLAS 設計 token + QSS（apply_theme）
    widgets.py       # ImageView, AxisBadge, SpectrumPlot, CandidateGrid, ...
    main_window.py   # MainWindow
tests/
  test_synthetic.py  # 合成影像驗證
```

更深入的架構 / 演算法參考（以及貢獻者注意事項）請見 [`CLAUDE.md`](CLAUDE.md)。

## UI 主題

UI 使用 **GLAS** 柔和暖色淺色系主題。所有設計 token 都放在
`cell_period_estimator/ui/theme.py`（`TOKENS`），同時供 QSS 樣式表與自繪 widget
使用，顏色永遠不會走樣。重點：奶油色的層次背景（不用純白頁面、不用純黑文字）、
單一焦糖橙強調色（`#f29f4b`，只用於主要動作、focus ring 與選取）、柔和的語意
晶片，以及 11px 的圓角捲軸。

## 測試

核心以合成影像驗證（不需要顯示）：

```bash
python tests/test_synthetic.py
```

它會檢查：XY 圖案被偵測為 `XY` 且 `px/py` 正確、正確週期堆疊得比錯誤週期更銳利
（Laplacian 變異數更高）、從略有偏差的起點細修能收斂，以及 50% 工作比的垂直
line/space 圖案被偵測為只有 `X`（`py = None`、`px ≈` 節距）。執行成功會印出
`ALL CHECKS PASSED`。CI 會在 Python 3.9 / 3.11 / 3.12 上跑這個。
