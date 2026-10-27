---
name: report-3d-showcase
description: 把使用者提供的報告文案／講稿／大綱，做成一套本地端 3D 互動展示（文案由使用者給，skill 負責演出）：檢查並安裝 Blender MCP、用 Blender 建構具藝術感的主題 3D 模型（匯出 GLB）、製作帶資訊卡與流暢動畫的 three.js 前端 main.html，以及一鍵開啟本機伺服器、管理 port 並自動開瀏覽器的 server.bat。只要使用者想把報告做成 3D 互動網頁、要用 Blender 建模搭配網頁展示、提到「3D 簡報」「互動導覽」「模型展示網頁」「main.html + bat」，或貼上這套五步驟工作流，就使用這個 skill——即使沒有明說「skill」或「Blender」。
---

# 報告主題 3D 互動展示

把**使用者的報告文案**做成：**Blender 模型 (GLB) → three.js 互動簡報 `main.html` → 一鍵啟動 `server.bat`**。

分工很重要：**文案（說什麼）由使用者提供，你負責把它「演出來」（模型、鏡頭、動畫、版面）**。報告是使用者的作品，評分與上台的人是他；代寫的內容會失去他的觀點，而且每份成品都會長成同一個樣子。

兩份範本只示範**格式與動畫手法**，它們的頁面結構（開場→問題→逐一介紹設施→資料隱私→結語）是那兩份報告自己的故事，**不是要套用的大綱**：
- `assets/example/`：淺色生活風（「資通訊科技與住」，13 頁、含講稿 `簡報講稿.md`）
- `assets/example-dark/`：夜景霓虹風（「科技與未來城市」，10 頁）

## 流程

### 0. 收集文案（第一步，在任何建模之前）
需要：**文案、輸出資料夾**（預設為目前工作目錄）。
- 使用者已提供文案（貼上、檔案、大綱、講稿、甚至 PPT／Word 檔）→ 讀完後整理成逐頁清單給他確認：每頁標題、要呈現的重點、畫面要看到什麼。文案沒寫到的畫面需求，由你提出建議，經他確認後才採用。
- 使用者還沒有文案 → 把 `assets/文案範本.md` 複製到專案資料夾，請他填寫後再繼續。只有主題沒有內容時不要自己開寫。
- 使用者**明確要求**你代擬（例如「你幫我寫」「先隨便放測試用」）→ 才起草，並在回報與檔案中標明「草稿，待使用者替換」；涉及事實的句子要附可查證的來源。

套用文案的規則：
- **照原文放**：標題、說明、條列用使用者的字句。太長放不進卡片時，提出精簡版讓他選，不要默默改寫，也不要增刪論點。
- **頁數與順序跟著文案走**，不必湊成範本的頁數或結構；一頁只有一句話也可以。
- 使用者沒附講稿 → 講稿面板留空或只放該頁重點，不要代寫整段講稿（除非他要求）。
- 文案中的數據若看起來可疑或缺來源，提醒使用者，但不要擅自改數字。

文案決定**要建哪些模型、要特寫哪些物件、每頁做什麼動畫**——這些是步驟 3、4 的輸入。

### 1. 確認 Blender MCP 狀態
看本工作階段是否有 `mcp__blender__*` 工具（可能需 ToolSearch 載入），並呼叫 `get_addon_status` 試連線。
- 成功 → 跳到步驟 3。
- 有工具但連不上 → 通常只是 Blender 沒開，可直接幫忙啟動（外掛會自動開 socket）。
- 沒有工具 → 步驟 2。
細節與檢查指令見 `references/blender-mcp-setup.md`。

### 2. 安裝 Blender MCP（若未就緒）
依 `references/blender-mcp-setup.md` 補齊缺的部分（uv、`claude mcp add`、Blender 外掛、按 Connect）。安裝會改動使用者環境，先說明並取得同意。新註冊的 MCP 需要重啟 Claude Code 才生效——明確告訴使用者重啟後再說「繼續」。

### 3. 建構主題 3D 模型
讀 `references/modeling-guide.md`。要建的物件清單來自步驟 0 文案裡每頁的「畫面要看到什麼」：每個需要特寫的東西都要有一個具名物件。風格依使用者指定的氛圍；沒指定時依主題判斷：
- **住宅／生活**：精緻家具、溫馨燈光、生活感細節
- **科技／未來**：網格、霓虹光暈、賽博風
- **其他**：流暢、有美感的造型與可做循環動畫的元件

分批建模、每批截圖檢查。報告中要特寫的每個物件取唯一中文名稱（前端靠名稱定位），多樓層外牆加 `cutaway` 自訂屬性。匯出 GLB 到 `<專案>/assets/models/`。

### 4. 建立互動前端 `main.html`
讀 `references/frontend-guide.md`，複製範本到專案後改寫——淺色／生活類用 `assets/example/main.html`，科技／未來類用 `assets/example-dark/main.html`（夜景、霓虹光暈、車流與無人機動畫）：
- `SLIDES`：**整個陣列換成使用者文案**（逐頁對應：標題→`title`、說明→`dek`、條列→`facts`、圖解→`diagram` 的 flow/cols、分幾步→`steps`、參考資料→`sources`、講稿→`notes`），不要保留範本的任何一頁文字
- GLB 路徑、`DEVICES` 名稱、`buildFlows()` 資料流、`shotFor()` 每頁鏡位
- 依主題調 `:root` 配色，刪除不相關的專屬特效（例如地政紅點、資料邊界罩）
保留既有的動畫系統（卡片漸顯與移位、標題逐行升起、鏡頭弧線飛行、流光資料流）——這是「藝術感」的來源，不要退化成靜態頁。

### 5. 編寫 `server.bat`
複製 `assets/server.bat` 到專案根目錄，通常只需改 `APP_TITLE`。它會：
- 停掉**本資料夾上次啟動**的伺服器（記在 `.server.state` 的 port＋PID，兩者都吻合才停，絕不動別的程式）
- 啟動時先列出 `PORT_START`～`PORT_END` 範圍內被占用的 port（PID、程式名稱）；選單 [2] 可隨時再看一次，並以 `[this presentation]` 標示本專案的伺服器
- 從 `PORT_START`（8780）往上找第一個沒人監聽的 port（到 `PORT_END`）——需要自己檢查，因為 Windows 上 Python `http.server` 會設 SO_REUSEADDR，綁到已被占用的 port 也不會報錯
- 回應一律加 `Cache-Control: no-store`（內嵌的 Python 一行伺服器）：不同專案輪流用到同一個 port 時，瀏覽器才不會顯示上一個專案的快取頁面或模型
- 用 Python `http.server` 只綁 127.0.0.1 啟動 → 開預設瀏覽器 → 重開／狀態／停止選單；`server.bat stop` 只停本資料夾的伺服器

bat 檔必須是**純 ASCII＋CRLF 換行**（中文會亂碼；LF 換行會讓 `goto`／標籤失效）。Write 工具寫出的是 LF，複製範本後用 PowerShell 轉換並檢查：
```powershell
$t=[IO.File]::ReadAllText($src) -replace "`r`n","`n" -replace "`n","`r`n"; [IO.File]::WriteAllText($dst,$t,[Text.Encoding]::ASCII)
```

## 收尾與驗證

1. 測試 bat 的啟動邏輯但不開瀏覽器、不進選單：複製一份 `_test_server.bat`，把 `start "" "%URL%"` 換成 `echo OPEN %URL%` 並在其後 `exit /b 0`；執行後讀 `.server.state` 取得 port，確認 `main.html` 與 GLB 都回 200。測完 `_test_server.bat stop` 並刪除測試檔。
2. 視覺檢查（不打擾使用者的瀏覽器）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File <skill>/scripts/screenshot_slides.ps1 -Url http://127.0.0.1:<port>/main.html -Slides 1,2,2.2,3,... -OutDir <scratchpad>\shots
   ```
   讀 `contact-sheet.png`，逐頁檢查：曝光（是否洗白）、鏡頭是否在建築內或被遮擋、指引線是否指到 `focus` 物件、卡片是否擋住主體。有問題就修、再截一次。
3. 驗證後停止伺服器並刪除測試檔。
4. 若使用者需要，依範例的 `簡報講稿.md` 格式輸出講稿（每頁標題、時長估算、講稿、`【按 → 下一步】` 標記）。

5. 文案核對：逐頁比對 `SLIDES` 與使用者文案，確認沒有漏頁、沒有被改寫的句子、沒有混入範本的舊文字（例如搜尋範本專屬詞「智慧住宅」「未來城市」）。

回報時列出產出檔案、啟動方式（雙擊 server.bat）與操作鍵（→/← 換頁、N 講稿、F 全螢幕），以及哪些步驟沒驗證到。若有任何文字是你代擬或精簡的，逐條列出，讓使用者知道要檢查哪裡。
