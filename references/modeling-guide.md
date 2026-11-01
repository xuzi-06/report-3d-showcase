# 用 Blender 建構主題模型

## 依主題決定風格

| 主題類型 | 視覺方向 | 細節清單 |
|---|---|---|
| 住宅／生活 | 溫暖、可親、有人住過的感覺 | 精緻家具（沙發、餐桌、書櫃、床）、暖色燈光（2700–3200K 點光／面光）、生活小物（植物、書、地毯、抱枕）、可剖面看到的樓層 |
| 科技／未來 | 冷調、發光、秩序感 | 深色地面＋發光網格、霓虹邊光（Emission 材質）、深色玻璃帷幕＋發光窗帶、資料線路、配色（青／洋紅／深藍，點綴琥珀） |
| 社會議題／故事 | 簡潔低多邊形、讓角色成為焦點 | 一個主場景（學校、街區）、可拆成四肢子物件的角色小人、能隨氛圍變色的材質（灰暗→明亮），參考 `assets/example-story/` |
| 歷史／古風 | 宣紙水墨、留白、朱砂點綴 | 台基與屋頂分明的建築、松樹與山形剪影、跨場景的道路與橋，參考 `assets/example-ink/`（主體要清楚，雲霧只是點綴） |
| 其他 | 流暢、有韻律 | 曲面與重複結構、和諧配色、可做循環動畫的元件（旋轉、浮動、波動） |

主題常常是混合的（例如「資通訊科技與住」= 住宅＋科技）：主體用住宅風格，科技元素用科技風格點綴。

## 工作方式

- 沒有 MCP 時改寫成一份完整的 bpy 腳本，用 `blender --background --factory-startup --python <腳本>` 建模並匯出，再打包成 HTML 截圖檢查（範例：`assets/example-ink/assets/models/孔子生平.py`）。以下 MCP 專用的工具（`look` 等）就跳過。
- 先 `get_addon_status`、`get_scene_info`；用 `execute_blender_code` 分批建立（地面與道路 → 主體建築 → 特色設施 → 動態物件），**每批用 `look` 看一次**（`mode:"angles"`、`shading:"material"`、`max_size` 640–800 省 token；`target` 可指定物件近看細節）。
- 腳本開頭清空場景、建立材質表；之後每批用 `bpy.data.collections[...]` 與 `{m.name:m for m in bpy.data.materials}` 取回，不要依賴上一批的 Python 變數。
- Principled BSDF 用 `n.type=='BSDF_PRINCIPLED'` 找節點，輸入用 identifier 找（`'Base Color'`、`'Emission Color'`、`'Emission Strength'`、`'Alpha'`）——Blender 介面可能是中文，節點名稱會被翻譯。
- 單位公尺，模型置中原點、地面 z=0。城市／園區尺度約 ±50 m；單棟建築約 10–40 m。
- 避免程序貼圖節點（glTF 匯不出去）。單一 GLB 盡量 < 5MB。
- 小零件（窗帶、欄杆、路面光帶）**合併成一個物件**（`bpy.ops.object.join()`），減少節點數、網頁才順。

## 與 main.html 對接的命名約定（重要）

前端靠**物件名稱**定位，所以：

- 簡報要介紹的物件取**唯一的中文名稱**（如 `一樓｜智慧電表`、`城市營運中心`）；前端 `DEVICES`、`focus`、`P('…')` 用同一字串。只做裝飾的物件可用編號名（`城市大樓_3`）。
- **會動的零件獨立成物件**並把原點設在轉軸上（`origin_set(type='ORIGIN_CURSOR')`）：風機葉片、旋轉光環、車輛、無人機。名稱加統一前綴（`自駕車_1…`、`無人機_1…`），前端用 `startsWith` 一次抓全部。
- 多層建築外牆要能剖面淡化：加自訂屬性 `cutaway = "1F"`，匯出勾 Custom Properties，前端讀 `userData.cutaway`。

## 發光強度（網頁有光暈後製時）

Blender 的 Emission Strength 到了網頁會偏亮，且會整片被光暈吃掉。建議：
- 霓虹線條 3–6（要發光暈）；窗光 ≤ 1.5（只亮、不發暈）。前端仍會再壓一次，見 frontend-guide。
- 大面積的白色材質在夜景中容易過曝，底色用 0.7–0.8 而不是純白。

## 座標換算（寫鏡頭時用）

glTF 匯出會把 Blender 的 z-up 轉成 three.js 的 y-up：**Blender (x, y, z) → three (x, z, −y)**。
例：Blender 中 (−6, −15, 4) 的路燈，在網頁裡是 (−6, 4, 15)。寫 `shotFor()` 時用換算後的座標，並確認鏡頭位置不在任何建築的範圍內。

## 精度（不要停在方塊示意）

簡報會特寫，粗糙的方塊和圓錐一放大就很明顯。`assets/example-ink/assets/models/孔子生平.py` 有下列做法的完整函式（`lathe`、`tube`、`blob`、`roof`、`column`、`window`、`door`、`stairs`、`balustrade`），可直接搬用：
- **倒角**：方塊邊緣倒一點角（約短邊的 15%，上限 4–5cm），受光和描邊都會柔和很多；小於 10cm 的小零件不倒角，省頂點。
- **旋轉體**：柱子（收分＋柱礎）、袍子、井欄、倉廩、花瓶用輪廓線旋轉（lathe），可壓成橢圓。
- **管狀體**：樹枝、屋脊、鬍鬚、馬腿、欄杆扶手沿點列建管（tube），半徑可逐點收細，也能壓扁成帶狀（衣襟）。
- **屋頂**：凹曲面（近簷平緩、近脊陡）、四角起翹、瓦壟起伏、正脊與戧脊、兩端鴟吻；兩坡頂要補山牆。
- **人物**：袍子下襬外張、腰帶、交領、寬袖、手、五官（眼、眉、鼻、耳）、髮或冠；四肢仍是子物件、原點在關節。
- **植物**：主幹彎曲分枝，樹冠是加噪聲的不規則團塊，不要用整顆球或疊圓錐。
- **地面細節**：田壟、河岸、零星石塊，讓場景不空。

注意：
- 多個零件 `join` 成一個物件後要移動時，先把原點設回 (0,0,0)（`origin_set`），否則會以第一個零件的中心當原點，整組偏掉。
- 匯出的材質是雙面的：鏡頭進到樹冠、屋頂裡面時整個畫面會是一片顏色。新增大樹冠後，要確認沒有鏡位（含環繞鏡頭的整圈路徑）落在裡面。
- 台階要和前端 `groundY()` 一致（逐級升高），否則人物會浮在台階上或陷進去，穿模檢查也會誤報。
- 精度提高後檔案會變大：遠山網格 32×32 左右就夠，瓦壟間距 15cm，GLB 仍要在 5MB 內。

## 匯出

```python
bpy.ops.export_scene.gltf(filepath=r"<專案>\assets\models\<名稱>.glb", export_format='GLB',
    use_selection=True, export_extras=True, export_apply=True, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=r"<專案>\assets\models\<名稱>.blend")   # 留原始檔方便之後修改
```

## 動畫：放在前端還是 Blender？

優先在 three.js 做（旋轉、漂浮、沿路移動、資料流光點、淡入淡出），能跟簡報頁面同步。只有角色或複雜機構動作才在 Blender 做 keyframe，再用 `AnimationMixer` 播放。
