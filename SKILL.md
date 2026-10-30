---
name: report-3d-showcase
description: 把使用者提供的報告文案／講稿／大綱，做成一套本地端 3D 互動展示（文案由使用者給，skill 負責演出）：檢查並安裝 Blender MCP、用 Blender 建構具藝術感的主題 3D 模型（匯出 GLB）、製作帶資訊卡與流暢動畫的 three.js 前端 main.html，最後打包成「雙擊即開、可離線、播放端免安裝任何東西（不需 Python／Blender／伺服器／網路）」的單一 HTML 檔。只要使用者想把報告做成 3D 互動網頁、要用 Blender 建模搭配網頁展示、提到「3D 簡報」「互動導覽」「模型展示網頁」「單一 HTML 簡報」，或貼上這套工作流，就使用這個 skill——即使沒有明說「skill」或「Blender」。
---

# 報告主題 3D 互動展示

把**使用者的報告文案**做成：**Blender 模型 (GLB) → three.js 互動簡報 `main.html` → 打包成單一 HTML（`dist/<標題>.html`）**。

分工：**文案（說什麼）由使用者提供，你負責把它「演出來」（模型、鏡頭、動畫、版面）**。報告是使用者的作品，上台和被評分的是使用者；代寫會失去使用者的觀點，也會讓每份成品長得一樣。

## 硬性要求：播放端零環境

報告用的電腦只要有 Chrome 或 Edge，雙擊 HTML 就要能完整播放，離線也行。成品不得依賴 Python、Blender、Node、本機伺服器、.bat、CDN 或任何安裝；Blender、PowerShell 只在製作端使用。
- three.js 用範本資料夾內附的 `vendor/three.bundle.min.js`（three@0.169.0，含 GLTFLoader、RoomEnvironment、EffectComposer、RenderPass、UnrealBloomPass、OutputPass、ShaderPass，掛在 `window.THREE`／`window.THREE_ADDONS`）。**不可**用 importmap 或 CDN 的 `import`。
- 專案資料夾必須自成一體：所有檔案都在資料夾內，不可用 `../` 指向外面。整個資料夾複製到別台電腦也要能雙擊 `main.html` 開啟。
- 字型：`--sans`／`--mono`／`--serif` 一定要有系統後備字型（微軟正黑體、Consolas、新細明體），Google Fonts 只是加分。

## 範本

三份範本只示範**格式與動畫手法**，它們的頁面結構是各自報告的故事，**不是要套用的大綱**。每個範本資料夾都含 `main.html`、`vendor/`、`assets/models/`，雙擊 `main.html` 即可預覽。
- `assets/example/`：淺色生活風（「資通訊科技與住」，13 頁、含講稿 `簡報講稿.md`）——住宅、生活類主題
- `assets/example-dark/`：夜景霓虹風（「科技與未來城市」，10 頁）——科技、未來類主題：霓虹光暈、車流與無人機
- `assets/example-story/`：灰暗→明亮敘事風（「斷在學校」，9 頁、含講稿）——社會議題、故事敘事類：角色小人走位、氛圍隨頁面由灰轉亮

## 流程

### 0. 收集文案（在任何建模之前）
需要：**文案、輸出資料夾**（預設為目前工作目錄）。
- 已有文案（貼上、檔案、大綱、講稿、PPT／Word）→ 整理成逐頁清單請使用者確認：每頁標題、重點、畫面要看到什麼。文案沒寫到的畫面需求，你可以提建議，確認後才採用。
- 還沒有文案 → 把 `assets/文案範本.md` 複製到專案資料夾請使用者填寫。只有主題沒有內容時不要自己開寫。
- 使用者**明確要求**代擬（例如「你幫我寫」「先放測試用」）→ 才起草，並標明「草稿，待使用者替換」；涉及事實的句子附可查證的來源。

套用文案的規則：
- **照原文放**：標題、說明、條列用使用者的字句。太長放不進卡片時提出精簡版讓使用者選，不要默默改寫或增刪論點。
- **頁數與順序跟著文案走**，不必湊成範本的頁數；一頁只有一句話也可以。
- 沒附講稿 → 講稿面板留空或只放該頁重點，不要代寫整段講稿。
- 數據看起來可疑或缺來源 → 提醒使用者，不要擅自改數字。

### 1. 確認 Blender MCP
看本工作階段是否有 `mcp__blender__*` 工具（可能需 ToolSearch 載入），並呼叫 `get_addon_status` 試連線。
- 成功 → 步驟 2。
- 有工具但連不上 → 通常是 Blender 沒開，直接幫忙啟動。
- 沒有工具 → 依 `references/blender-mcp-setup.md` 安裝（uv、`claude mcp add`、Blender 外掛、按 Connect）。安裝會改動使用者環境，先說明並取得同意；新註冊的 MCP 要重啟 Claude Code 才生效，明確告訴使用者重啟後說「繼續」。
- 沒有 MCP 但電腦裝了 Blender（也可能在 Steam 資料夾，查登錄檔的解除安裝清單）→ 可以不安裝任何東西，把建模寫成 Python 腳本，用 `blender --background --factory-startup --python <腳本>` 建模並匯出 GLB，再用截圖檢查成品。腳本存在 `<專案>/assets/models/`，方便之後修改。

### 2. 建構 3D 模型
讀 `references/modeling-guide.md`。物件清單來自文案每頁的「畫面要看到什麼」：每個要特寫的東西都要有唯一中文名稱的具名物件（前端靠名稱定位），多樓層外牆加 `cutaway` 自訂屬性。風格依使用者指定的氛圍，沒指定時參考對應範本的風格。

分批建模、每批截圖檢查，匯出 GLB 到 `<專案>/assets/models/`。模型會以 base64 內嵌（約原大小 1.33 倍），GLB 盡量控制在 5MB 內：貼圖 1024px 以下，能用材質顏色就不用貼圖。

### 3. 建立互動前端 `main.html`
讀 `references/frontend-guide.md`。依主題選範本，把它的 `main.html` 與 `vendor/` 一起複製到專案根目錄（不要複製範本的 `assets/models/`）。`vendor/` 路徑不用改；把範本的模型 script 換成自己的，每個模型一行 `<script src="assets/models/<名稱>.glb.js">`。接著改：
- `SLIDES`：**整個陣列換成使用者文案**（標題→`title`、說明→`dek`、條列→`facts`、圖解→`diagram`、分幾步→`steps`、參考資料→`sources`、講稿→`notes`），不保留範本任何一頁文字
- `loadGLB` 的模型名稱、`DEVICES`、`buildFlows()` 資料流、`shotFor()` 每頁鏡位
- `:root` 配色；刪除與主題無關的範本專屬特效

保留既有的動畫系統（卡片漸顯與移位、標題逐行升起、鏡頭弧線飛行、流光資料流）——這是「藝術感」的來源，不要退化成靜態頁。

### 4. 打包成單一 HTML
```powershell
powershell -ExecutionPolicy Bypass -File <skill>/scripts/build.ps1 -Project <專案>
```
- 先把 `assets/models/*.glb` 轉成 `*.glb.js`（只轉缺少或過期的），之後 `main.html` 也能直接雙擊預覽。
- 再把所有本機 `<script src>` 內嵌，輸出 `<專案>/dist/<頁面標題>.html`。
- 找不到檔案會報錯；有 CDN script 或 importmap 會警告。**有任何警告都必須先修正。**
- 每次改完 `main.html` 或重新匯出 GLB，都要重新 build。

### 5. 驗證
1. **截圖檢查打包後的成品**（`file://`，不開伺服器、不打擾使用者的瀏覽器）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File <skill>/scripts/screenshot_slides.ps1 -Url "<專案>\dist\<標題>.html" -Slides 1,2,2.2,3,... -OutDir <scratchpad>\shots
   ```
   讀 `contact-sheet.png` 逐頁檢查：3D 有載入（沒出現「3D 模型無法載入」）、沒有洗白、鏡頭沒卡在建築內或被遮擋、指引線指到 `focus` 物件、卡片沒擋住主體。有問題就修，重新 build 再截。
2. **離線檢查**：用無頭 Edge 加 `--proxy-server=127.0.0.1:9` 截一頁，確認 3D 正常、改用系統字後版面沒跑掉。
3. **文案核對**：逐頁比對 `SLIDES` 與使用者文案，確認沒漏頁、沒改寫、沒混入範本舊文字（搜尋「智慧住宅」「未來城市」「斷在學校」等範本專屬詞）。
4. 使用者需要講稿時，依範本 `簡報講稿.md` 的格式輸出（每頁標題、時長估算、講稿、`【按 → 下一步】` 標記）。

## 回報

列出產出檔案與交付方式：雙擊 `dist/<標題>.html`，任何有 Chrome／Edge 的電腦都能播放，不需安裝也不需網路；專案資料夾整個帶走也能開，方便之後修改。附上操作鍵（→/← 換頁、N 講稿、F 全螢幕）、哪些步驟沒驗證到，以及你代擬或精簡過的文字（逐條列出，讓使用者知道要檢查哪裡）。
