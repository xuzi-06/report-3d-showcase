# Blender MCP 檢查與安裝（Windows）

Blender MCP 由兩半組成，兩半都要就緒才能建模：

1. **Blender 端外掛**（在 Blender 裡開一個 socket，預設 port 9876）
2. **MCP 伺服器** `mcp-for-blender`（舊名 `blender-mcp`，由 `uvx` 啟動，註冊進 Claude Code）

## 檢查（依序）

1. 本工作階段是否有 `mcp__blender__*` 工具（可能是延遲載入，用 ToolSearch 搜 `blender` 取得 schema）。
2. 有工具 → 呼叫 `get_addon_status`：
   - 成功 → 已就緒，看一下 `warning`（外掛版本落後通常不影響 `execute_blender_code` / `look`），跳到步驟 3。
   - 「Could not connect to Blender」→ 多半只是 **Blender 沒開**。見下方「啟動 Blender」。
3. 沒有工具 → 需要安裝，見下方。

```powershell
claude mcp list                                   # 是否有 blender 項目且 Connected
where.exe uvx; Test-Path "$env:USERPROFILE\.local\bin\uvx.exe"
Get-ChildItem "$env:APPDATA\Blender Foundation\Blender\*\scripts\addons\*mcp*.py"   # 外掛是否已放入
netstat -ano | findstr ":9876"                    # 外掛 socket 是否在聽
```

## 啟動 Blender（外掛已裝、只是沒開）

新版外掛（1.8+）在 Blender 開啟時會**自動啟動** socket，不必手動按 Connect，所以可以直接幫使用者開：

```powershell
$bl = Get-ChildItem 'C:\Program Files\Blender Foundation' -Recurse -Filter blender.exe -Depth 2 | Select -First 1 -Expand FullName
Start-Process $bl
foreach ($i in 1..30) { Start-Sleep 2; if (netstat -ano | findstr ":9876.*LISTENING") { "ready after $($i*2)s"; break } }
```

約 20 秒會開始監聽。若 60 秒仍沒有，請使用者在 Blender 3D 視窗按 `N` → BlenderMCP 分頁 → Start/Connect。

## 安裝（缺哪半補哪半）

1. 安裝 uv（提供 `uvx`）：
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. 註冊 MCP 伺服器到 Claude Code（使用者層級）：
   ```powershell
   claude mcp add blender --scope user -- "$env:USERPROFILE\.local\bin\uvx.exe" mcp-for-blender
   ```
   - 套件已由 `blender-mcp` 改名為 `mcp-for-blender`（https://github.com/ahujasid/mcp-for-blender）；舊名仍可用（相容包裝），已註冊舊名者不必改。
   - 用 uvx 的**絕對路徑**：剛裝好 uv 時 PATH 尚未更新，從舊終端機啟動的 Claude Code 會找不到 `uvx`。
3. Blender 外掛：`uvx mcp-for-blender install-addon`，或從上面 GitHub 下載 `addon.py`，
   Blender → Edit → Preferences → Add-ons → Install from Disk → 勾選。
4. 新的 MCP 伺服器要**重新啟動 Claude Code** 後工具才會出現。請使用者用 `claude --continue` 重開（保留對話脈絡），再說「繼續」。

安裝會改動使用者環境：先說明要做什麼、取得同意再執行。Blender 本體需使用者自行安裝。

## 無法使用 Blender 時的備案

- 有裝 Blender、但不想用 MCP：`blender --background --python build.py` 執行同一份 bpy 腳本並匯出 GLB（看不到即時截圖）。
- 完全沒有 Blender：在 `main.html` 內用 three.js 程式化建模，但先告知使用者細節會較少。
