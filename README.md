# report-3d-showcase · 報告主題 3D 互動展示

> 把你的報告文案，變成一套可以上台操作的 **3D 互動簡報**。
> A Claude Code skill that turns your report script into a local, interactive 3D presentation — Blender model → three.js slides → one self-contained HTML file that opens offline by double-click, with nothing to install.

這是一個 [Claude Code](https://claude.com/claude-code) Skill。你提供文案（說什麼），Claude 負責把它「演出來」：

| 產出 | 內容 |
|---|---|
| `assets/models/*.glb` | 用 Blender（透過 Blender MCP）建構的主題 3D 模型，每個要特寫的物件都有具名節點 |
| `main.html` | three.js 互動簡報原始檔：資訊卡漸顯與移位、標題逐行升起、鏡頭弧線飛行、流光資料流、講稿面板 |
| **`dist/<標題>.html`** | **交付物**：three.js、模型、程式全部內嵌的單一檔案。任何有 Chrome／Edge 的電腦雙擊即可播放，可以離線，**不需要 Python、Blender、伺服器或網路** |
| `簡報講稿.md`（選用） | 逐頁講稿，含時長估算與「按 → 下一步」標記 |

## 範例

三份範例只示範格式與動畫手法，不是要套用的大綱：

- **淺色生活風** `assets/example/` —「資通訊科技與住」，13 頁、含完整講稿
- **夜景霓虹風** `assets/example-dark/` —「科技與未來城市」，10 頁
- **灰暗→明亮敘事風** `assets/example-story/` —「斷在學校：從輔導觀點看中途離校與輟學」，9 頁、含完整講稿；角色小人（學生、警察、老師、社工）依頁面走位，畫面從灰暗雨天逐步調亮

直接預覽範例：雙擊範例資料夾裡的 `main.html` 即可。要產生單一檔案：`powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Project assets\example`。

## 安裝

```powershell
git clone https://github.com/xuzi-06/report-3d-showcase.git "$env:USERPROFILE\.claude\skills\report-3d-showcase"
```

資料夾名稱必須是 `report-3d-showcase`（與 `SKILL.md` 的 `name` 一致）。重新啟動 Claude Code 後即可使用。

### 需求

**製作端**（跑 Claude Code 的電腦）：
- Windows（打包與截圖腳本使用內建的 PowerShell 和 Edge）
- [Blender](https://www.blender.org/) 4.x 以上與 Blender MCP（skill 會檢查並引導安裝，見 `references/blender-mcp-setup.md`）

**播放端**（報告用的電腦）：只要有 Chrome 或 Edge，不需安裝任何東西，也不需網路。有網路時會載入 Noto 字型，離線時自動改用微軟正黑體。

## 使用方式

在 Claude Code 裡說：

> 幫我把這份報告做成 3D 互動簡報：（貼上文案、大綱或講稿）

流程：

0. **收集文案**：整理成逐頁清單給你確認。沒有文案時會給你 `assets/文案範本.md` 填寫，不會自行代寫
1. **檢查 Blender MCP** 是否可連線
2. **安裝 Blender MCP**（若未就緒，會先徵求同意）
3. **建模**：依文案決定要建哪些物件，分批建模並截圖檢查，匯出 GLB
4. **前端**：把範本的 `SLIDES` 整個換成你的文案，設定鏡位與資料流
5. **打包**：`scripts/build.ps1` 把模型與程式全部內嵌成 `dist/<標題>.html`，並以 `file://` 和斷網兩種情況截圖驗證

完成後把 `dist/<標題>.html` 複製到報告用的電腦，雙擊開始報告。

### 簡報操作

| 按鍵 | 功能 |
|---|---|
| → / 空白鍵 / 滾輪 | 下一步 |
| ← | 上一步 |
| N | 開關講稿面板（含計時器） |
| F | 全螢幕 |
| 網址加 `#8.2` | 直接跳到第 8 頁第 2 步 |

## 為什麼不用伺服器也能跑

瀏覽器禁止 `file://` 頁面用 fetch 讀取本機檔案，舊版因此需要 Python 伺服器。新版的做法：
- three.js 與用到的 addons 預先打包成 `vendor/three.bundle.min.js`，放在每個範本資料夾內，整個資料夾可直接帶到別台電腦（IIFE，掛在 `window.THREE`／`window.THREE_ADDONS`），不再透過 CDN 用 import 載入
- GLB 轉成 base64 的 `.glb.js`，用 `<script src>` 載入後交給 `GLTFLoader.parseAsync` 解析
- `build.ps1` 再把所有 `<script src>` 內嵌進同一個 HTML，三份範例打包後約 1.8～3.6MB

## 檔案結構

```
report-3d-showcase/
├─ SKILL.md                    # Skill 主說明（Claude 讀這份）
├─ assets/
│  ├─ vendor/                  # three.js 打包入口（重新打包用）與授權
│  ├─ 文案範本.md               # 給使用者填寫的文案格式
│  ├─ example/                 # 淺色生活風範例（每個範例資料夾都含 main.html、vendor/three.bundle.min.js、assets/models/）
│  ├─ example-dark/            # 夜景霓虹風範例
│  └─ example-story/           # 灰暗→明亮敘事風範例（角色動畫）
├─ references/
│  ├─ blender-mcp-setup.md     # Blender MCP 安裝與檢查
│  ├─ modeling-guide.md        # 建模規範（具名物件、cutaway、匯出）
│  └─ frontend-guide.md        # main.html 改寫指南
└─ scripts/
   ├─ build.ps1                # GLB → .glb.js，並把專案打包成單一 HTML
   └─ screenshot_slides.ps1    # 無頭瀏覽器逐頁截圖（支援 file:// 路徑）、產生 contact sheet
```

## 作者

- **xuzi-06**：工作流程設計、報告文案與需求、測試回饋
- **Claude**（Anthropic，透過 Claude Code）：協作開發 SKILL、Blender 建模腳本、three.js 前端與單檔打包流程

本專案是人與 AI 協作完成的成果。

## 授權

範例中的文案與模型屬於原報告作者；範本程式碼可自由修改使用。各範例的 `vendor/three.bundle.min.js` 內含 [three.js](https://threejs.org/)（MIT，見 `assets/vendor/three.LICENSE.txt`）。
