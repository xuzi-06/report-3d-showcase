# report-3d-showcase · 報告主題 3D 互動展示

> 把你的報告文案，變成一套可以上台操作的 **3D 互動簡報**。
> A Claude Code skill that turns your report script into a local, interactive 3D presentation — Blender model → three.js slides → one-click launcher.

這是一個 [Claude Code](https://claude.com/claude-code) Skill。你提供文案（說什麼），Claude 負責把它「演出來」：

| 產出 | 內容 |
|---|---|
| `assets/models/*.glb` | 用 Blender（透過 Blender MCP）建構的主題 3D 模型，每個要特寫的物件都有具名節點 |
| `main.html` | three.js 互動簡報：資訊卡漸顯與移位、標題逐行升起、鏡頭弧線飛行、流光資料流、講稿面板 |
| `server.bat` | 一鍵啟動本機伺服器並開啟瀏覽器，附控制選單（重開／狀態／停止） |
| `簡報講稿.md`（選用） | 逐頁講稿，含時長估算與「按 → 下一步」標記 |

## 範例

三份範例只示範格式與動畫手法，不是要套用的大綱：

- **淺色生活風** `assets/example/` —「資通訊科技與住」，13 頁、含完整講稿
- **夜景霓虹風** `assets/example-dark/` —「科技與未來城市」，10 頁
- **灰暗→明亮敘事風** `assets/example-story/` —「斷在學校：從輔導觀點看中途離校與輟學」，9 頁、含完整講稿；角色小人（學生、警察、老師、社工）依頁面走位，畫面從灰暗雨天逐步調亮

直接預覽範例：在範例資料夾放一份 `assets/server.bat` 後雙擊（或在該資料夾執行 `python -m http.server`，再開 `http://127.0.0.1:8000/main.html`）。

## 安裝

```powershell
git clone https://github.com/xuzi-06/report-3d-showcase.git "$env:USERPROFILE\.claude\skills\report-3d-showcase"
```

資料夾名稱必須是 `report-3d-showcase`（與 `SKILL.md` 的 `name` 一致）。重新啟動 Claude Code 後即可使用。

### 需求

- Windows（`server.bat` 為 Windows 批次檔）
- [Blender](https://www.blender.org/) 4.x 以上與 Blender MCP（skill 會檢查並引導安裝，見 `references/blender-mcp-setup.md`）
- Python 3（本機伺服器用）
- 報告時需連網（three.js 與字型由 CDN 載入）

## 使用方式

在 Claude Code 裡說：

> 幫我把這份報告做成 3D 互動簡報：（貼上文案、大綱或講稿）

流程：

0. **收集文案**：整理成逐頁清單給你確認。沒有文案時會給你 `assets/文案範本.md` 填寫，不會自行代寫
1. **檢查 Blender MCP** 是否可連線
2. **安裝 Blender MCP**（若未就緒，會先徵求同意）
3. **建模**：依文案決定要建哪些物件，分批建模並截圖檢查，匯出 GLB
4. **前端**：把範本的 `SLIDES` 整個換成你的文案，設定鏡位與資料流
5. **server.bat**：複製啟動器，改標題即可

完成後雙擊 `server.bat` 開始報告。

### 簡報操作

| 按鍵 | 功能 |
|---|---|
| → / 空白鍵 / 滾輪 | 下一步 |
| ← | 上一步 |
| N | 開關講稿面板（含計時器） |
| F | 全螢幕 |
| 網址加 `#8.2` | 直接跳到第 8 頁第 2 步 |

## server.bat 的設計

多個專案可以同時開啟、互不干擾：

- **端口佔用清單**：啟動時列出 8780～8899 中已被占用的 port、PID 與程式名稱；選單 [2] 可隨時查看，並標示 `[this presentation]`
- **自動找空的 port**：從 8780 往上找第一個沒人監聽的 port（到 8899），被占用時會在視窗中回報改用哪個
- **只停自己的伺服器**：在 `.server.state` 記下 port 與 PID，兩者都吻合才停，不會關到別的專案或程式
- **不快取**：回應一律加 `Cache-Control: no-store`，不同專案輪流用到同一個 port 時，瀏覽器不會顯示上一個專案的頁面
- **純 ASCII＋CRLF**：避免中文亂碼與 `goto` 失效
- `server.bat stop`：只停止本資料夾的伺服器

## 檔案結構

```
report-3d-showcase/
├─ SKILL.md                    # Skill 主說明（Claude 讀這份）
├─ assets/
│  ├─ server.bat               # 啟動器範本
│  ├─ 文案範本.md               # 給使用者填寫的文案格式
│  ├─ example/                 # 淺色生活風範例
│  ├─ example-dark/            # 夜景霓虹風範例
│  └─ example-story/           # 灰暗→明亮敘事風範例（角色動畫）
├─ references/
│  ├─ blender-mcp-setup.md     # Blender MCP 安裝與檢查
│  ├─ modeling-guide.md        # 建模規範（具名物件、cutaway、匯出）
│  └─ frontend-guide.md        # main.html 改寫指南
└─ scripts/
   └─ screenshot_slides.ps1    # 無頭瀏覽器逐頁截圖、產生 contact sheet
```

## 作者

- **xuzi-06**：工作流程設計、報告文案與需求、測試回饋
- **Claude**（Anthropic，透過 Claude Code）：協作開發 SKILL、Blender 建模腳本、three.js 前端與 server.bat

本專案是人與 AI 協作完成的成果。

## 授權

範例中的文案與模型屬於原報告作者；範本程式碼可自由修改使用。
