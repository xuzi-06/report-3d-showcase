# 用 Blender MCP 建構主題模型

## 依主題決定風格

| 主題類型 | 視覺方向 | 細節清單 |
|---|---|---|
| 住宅／生活 | 溫暖、可親、有人住過的感覺 | 精緻家具（沙發、餐桌、書櫃、床）、暖色燈光（2700–3200K 點光／面光）、生活小物（植物、書、地毯、抱枕）、可剖面看到的樓層 |
| 科技／未來 | 冷調、發光、秩序感 | 深色地面＋發光網格、霓虹邊光（Emission 材質）、深色玻璃帷幕＋發光窗帶、資料線路、配色（青／洋紅／深藍，點綴琥珀） |
| 其他 | 流暢、有韻律 | 曲面與重複結構、和諧配色、可做循環動畫的元件（旋轉、浮動、波動） |

主題常常是混合的（例如「資通訊科技與住」= 住宅＋科技）：主體用住宅風格，科技元素用科技風格點綴。

## 工作方式

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

## 匯出

```python
bpy.ops.export_scene.gltf(filepath=r"<專案>\assets\models\<名稱>.glb", export_format='GLB',
    use_selection=True, export_extras=True, export_apply=True, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=r"<專案>\assets\models\<名稱>.blend")   # 留原始檔方便之後修改
```

## 動畫：放在前端還是 Blender？

優先在 three.js 做（旋轉、漂浮、沿路移動、資料流光點、淡入淡出），能跟簡報頁面同步。只有角色或複雜機構動作才在 Blender 做 keyframe，再用 `AnimationMixer` 播放。
