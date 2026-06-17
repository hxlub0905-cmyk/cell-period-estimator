# CLAUDE.md

給 Claude Code（以及人類貢獻者）在這個儲存庫中工作的指引。

## 這個專案是什麼

**Cell Period Estimator** 是一個 PySide6 桌面工具，用來估測半導體 EBeam 掃描
影像中重複的 cell 週期（`px`、`py`，即「Golden Cell」節距），並支援
cell-to-cell 的缺陷偵測流程。估測核心是純 NumPy/OpenCV；UI 只是疊在上面的一層
薄薄的 PySide6。

進入點：`python -m cell_period_estimator`（console script：
`cell-period-estimator`）。

## 儲存庫地圖

```
cell_period_estimator/
  __init__.py        # __version__ = "0.1.0"（要與 pyproject 保持同步）
  __main__.py        # main(): apply_theme(app) -> MainWindow -> app.exec()
  core/              # ── 不含 Qt。這裡永遠不要 import PySide6。──
    __init__.py      # re-export 公開的 core API
    period_core.py   # estimate_period + PeriodResult/AxisSpectrum + choose_origin
    stacking.py      # tile_coords, stack_cells, ghosting_score, refine_period,
                     #   candidate_periods
  ui/
    theme.py         # GLAS 設計 token（TOKENS）+ QSS + apply_theme()
    widgets.py       # numpy<->Qt, ImageView, AxisBadge, SpectrumPlot, CandidateGrid
    main_window.py   # MainWindow：工具列、面板、QThread 估測、匯出
tests/
  test_synthetic.py  # 合成影像驗證，當成一般腳本執行
.github/workflows/ci.yml   # 在 3.9/3.11/3.12 上跑合成測試
```

## 硬性規則 / 慣例

- **`core/` 維持不含 Qt。** 測試與批次使用會在沒有顯示伺服器的情況下匯入
  core。匯入 `cell_period_estimator.core` 絕對不能把 PySide6 一起拉進來。
  （`__init__.py` 刻意保持精簡，這樣 `import cell_period_estimator.core` 才
  不會牽連到 Qt。）
- **主題只有單一 token 來源。** 所有顏色都放在
  `ui/theme.py::TOKENS`。QSS *與* 自繪 widget 都從這裡讀取，顏色才不會走樣。
  不要在 widget 裡寫死 hex 值——請 import `TOKENS`。
- **只有一個強調色（橙色 `#f29f4b`）。** 只用於主要動作、focus ring、選取，
  以及區段標題。不要讓整個 UI 都是這個顏色。
- **CI/測試使用 headless OpenCV。** `opencv-python-headless` 對 core 來說就
  夠了；完整的 `opencv-python` 只在 `requirements.txt` 列給桌面 app 用。測試
  不可以依賴 PySide6。
- 比照周圍的程式碼風格：type hints、用 dataclass 表示結果、用 docstring 說明
  *為什麼*、4 個空白縮排。

## 演算法參考（core/period_core.py）

`estimate_period(image, min_period=None, max_period=None,
strength_threshold=0.18) -> PeriodResult` 會對每個軸（X 與 Y）獨立執行。對 X
軸而言，「強度投影」是 `gray.mean(axis=0)`（沿寬度方向變化）；對 Y 軸則是
`gray.mean(axis=1)`。

每個軸的流程（`_analyze_axis`）：

1. **調變閘（Modulation gate）** — 如果 `projection.std() < 0.5`
   （`_MODULATION_STD_FLOOR`），代表該軸是平的 ⇒ 回傳無週期。避免把雜訊正規化
   成假的週期（例如垂直 line/space 圖案的 Y 軸）。
2. **高通去趨勢（High-pass detrend）**（`_highpass`）— 減去**邊緣補值**過的
   移動平均，視窗 ≈ length/4（夾成奇數）。邊緣補值可避免邊界處出現假的斜坡。
3. **rFFT** — 在自適應頻帶 `[lo, hi]` 內最強的峰給出粗略候選。頻帶：
   `lo = max(2, min_period or 4)`、`hi = min(max_period or length//2,
   length//2)`（`_search_band`）。
4. **由自相關（Autocorrelation）決定基頻。** *重要：* 當 cell 內容很豐富時，
   強度 FFT 的峰可能落在**諧波**上（每個 cell 裡的某個特徵會以次 cell 頻率重複）。
   所以我們在 lag 頻帶內挑出正規化自相關最強的**局部極大值**——這會跳過 lag 0
   附近的單調高相關區，也跳過諧波的低谷——再用拋物線（`_parabolic`）細修到
   次像素。FFT 結果只當作後備提示與顯示用的頻譜。
5. **諧波修正（Harmonic correction）** — `if ac(2p) > 1.15·ac(p): p = 2p`；
   `elif p 為偶數 and ac(p/2) >= 0.9·ac(p): p = p/2`。
6. **接受 / 拒絕** — 若 `period < lo` 或 `strength < strength_threshold` 則
   拒絕。`confidence = strength * 100`。

`axis_mode` ∈ {`X`, `Y`, `XY`, `NONE`}，由哪些軸有週期決定。

### 資料結構

- `AxisSpectrum(periods, magnitude, peak_period)`，附帶
  `normalized_magnitude()`（峰值縮放到 1.0）供繪圖用。
- `PeriodResult(px, py, confidence_x, confidence_y, axis_mode,
  peak_strength_x, peak_strength_y, spectrum_x, spectrum_y, candidates,
  warnings)`。`px/py` 為 `int` 或 `None`；strength 為 0–1；confidence 為 0–100。
- `choose_origin(shape, px, py)` 回傳晶格原點（預設 `(0, 0)`）。

## 堆疊參考（core/stacking.py）

- `tile_coords(shape, px, py, origin=(0,0))` — 每個**完整** cell 的左上角
  `(x, y)`（會略過邊界不完整的 cell）。是 cell 擺放的單一真實來源；堆疊與
  細修都用它。
- `stack_cells(image, px, py, method="mean", origin=(0,0), sample_n=None,
  seed=0) -> uint8 (py, px)`。`mean`（預設）對相位敏感、會暴露疊影；`median`
  對缺陷較穩健。`sample_n` 會隨機取樣 cell 子集（用帶 seed 的 RNG）。
- `ghosting_score(stacked) -> (score_0_100, laplacian_var, edge_contrast)`。
  `score` 是會飽和的顯示用映射；**`laplacian_var` 才是用來排名的原始值。**
- `refine_period(image, px, py, search=6, method="mean") -> (best_px, best_py,
  best_lap_var)`。鄰域掃描，依**原始** Laplacian 變異數（不是 0–100 的 score，
  因為它在高分區會 clip 而失去排序）排名。
- `candidate_periods(px, py, lo, hi)` — 主要值 + 各軸 / 組合的半 / 倍諧波，
  過濾到範圍內並去重。

## UI 參考（ui/）

- `apply_theme(app)`（在 `theme.py`）會設定 Fusion 樣式、一組溫暖的
  `QPalette`，以及由 `TOKENS` 建出的 QSS。在 `__main__.main()` 裡呼叫一次。
- `widgets.py`
  - `numpy_to_qimage` / `numpy_to_qpixmap` — 灰階/RGB/RGBA uint8 轉換。
  - `qimage_to_gray` — 把 QImage（剪貼簿 / 拖曳的像素）轉成灰階陣列。
  - `StatCard` — 標題 / 大數值 / 副標的讀數卡（樣式由 QSS 透過 object name 控制）。
  - `ImageView(QGraphicsView)` — 滾輪縮放、橡皮筋 ROI
    （`cropChanged(x, y, w, h)`，影像座標）、週期格線疊圖（暗色描邊 + 橙色主線，
    並標出晶格原點）。
  - `AxisBadge` — 柔和的語意晶片（XY=success、X/Y=min-accent、NONE=danger）。
  - `SpectrumPlot` — 自繪 X/Y FFT 頻譜；X=accent、Y=cool marker、peak=accent-active。
  - `CandidateGrid` — 縮圖網格，`candidateChosen(px, py)`；最佳候選會有 accent 邊框。
- `main_window.py::MainWindow`
  - 工具列動作：Load Image、**Estimate Period**、Crop ROI（可勾選）、Clear ROI、
    Export GC、Export JSON。工具列依用途分組（File | Analysis | Export），用分隔線
    隔開。
  - 右側結果欄放在一個垂直的 `QScrollArea`（單欄）裡，這樣各區段不會互相擠壓。
  - **載入影像有三種方式**：Load Image 對話框、把檔案 / 圖片拖曳到視窗，或用
    Ctrl+V 貼上（剪貼簿影像或複製的圖檔）。所有路徑都透過 `np.fromfile` +
    `cv2.imdecode` 讀取，因此**支援非 ASCII（中文）路徑**。
  - **Estimate Period** 是唯一的主要動作：既出現在工具列，也在結果欄頂端有一顆
    全寬的橙色主按鈕（`variant="primary"`，工具列那顆 `objectName="primary"`）；
    兩者共用同一個 handler，並透過 `_set_estimate_enabled` 一起啟用 / 停用。
  - 估測在 `QThread` 中透過 `_EstimateWorker`（`finished`/`failed` 訊號）執行，
    讓 UI 保持回應。
  - PERIOD 區段是「讀數」設計：全寬 axis badge + 兩張 `StatCard`（X/Y 週期、
    confidence 作副標），可編輯的 px/py/min/optimize 控制放在下方的微調表單。
  - Crop 會把分析限制在 ROI（`_refresh_analysis_image`）。
  - Export GC → PNG；Export JSON → `{px, py, roi, axis_mode, confidence,
    score}`。

### 要記得的 Qt-QSS 限制

- QSS 沒有 `text-transform` 或 `letter-spacing`。區段 / 群組標題在程式碼裡轉成
  大寫（例如 `QGroupBox("PERIOD")`）；accent 顏色、10px 大小與 700 字重來自 QSS。
- 按鈕變體用動態 property：`setProperty("variant",
  "primary"|"secondary"|"ghost"|"success")`，由 QSS 的屬性選擇器匹配。

## 執行與測試

```bash
# 安裝開發環境（core/測試用 headless OpenCV 就好）
pip install numpy opencv-python-headless        # core + 測試
pip install PySide6                               # 跑桌面 app 才需要

# 執行 app（需要顯示，或用 QT_QPA_PLATFORM=offscreen 做 smoke 測試）
python -m cell_period_estimator

# 執行合成測試套件（成功時印出 ALL CHECKS PASSED）
python tests/test_synthetic.py
```

Offscreen smoke 測試（無顯示，例如 CI/容器）：

```bash
QT_QPA_PLATFORM=offscreen python -m cell_period_estimator   # 若以腳本驅動則建構後結束
```

注意：在精簡的 Linux 映像上，Qt 平台外掛需要系統函式庫
（`libegl1`、`libgl1`、`libxkbcommon0`、`libdbus-1-3`）。core 與合成測試都不需要
這些。

## 常見修改食譜

- **調整偵測靈敏度** → `period_core.py` 裡的 `strength_threshold`（接受/拒絕）
  與 `_MODULATION_STD_FLOOR`（平軸閘）。
- **修改諧波修正門檻** → `_analyze_axis` 中的 `1.15` / `0.9` 常數。
- **新增 / 調整主題顏色** → 編輯 `ui/theme.py` 的 `TOKENS`；QSS 與自繪 widget
  都會吃到。不要在別處寫死 hex。
- **新增匯出欄位** → `MainWindow._on_export_json`。
- **放寬 Auto-optimize 範圍** → `refine_period(search=...)`（以及
  `main_window.py` 裡的 `spin_opt` 範圍）。

## 注意事項（Gotchas）

- 不要用 0–100 的 `score` 來排名 refinement/candidates——它會飽和。請用
  `laplacian_var`。
- `px/py` 維持 `int` 或 `None`；UI spinbox 把 `0` 當作「未設定」。
- `estimate_period` 接受彩色或灰階；會在內部轉換（`_to_gray`）。彩色假設為
  BGR（OpenCV 慣例）/ 4 通道為 BGRA。
- 在棘手的圖案上，偵測到的週期合理地可能是半 / 倍諧波；candidate 網格 +
  Auto-optimize 就是用來找回正確值的。

## 指引

- 面向使用者的用法、按鈕參考、以及「如何閱讀各視圖」放在
  [`README.md`](README.md)。
- 版本同時放在 `cell_period_estimator/__init__.py` 與 `pyproject.toml`——
  兩者要一起更新。
