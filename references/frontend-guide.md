# main.html 架構說明（以 assets/example/main.html 為範本）

範例是一份完整可用的 3D 互動簡報（13 頁，「資通訊科技與住」）。新專案**複製它再改內容**，比從零寫快且穩定。單一 HTML 檔，不使用 CDN 或 importmap：

```html
<script src="vendor/three.bundle.min.js"></script>        <!-- 範本資料夾內附，連同 vendor/ 一起複製到專案，路徑不用改 -->
<script src="assets/models/智慧住宅.glb.js"></script>      <!-- build.ps1 由 GLB 產生，每個模型一行 -->
<script type="module">
const THREE=window.THREE;
const {GLTFLoader,RoomEnvironment}=window.THREE_ADDONS;   // 只解構用得到的
...
const loader=new GLTFLoader(manager);
const loadGLB=name=>{...};                                // 解 base64 → loader.parseAsync
loadGLB('智慧住宅').then(g=>{...})                          // 取代 loader.loadAsync('assets/models/….glb')
```

`window.THREE_ADDONS` 提供：GLTFLoader、RoomEnvironment、EffectComposer、RenderPass、UnrealBloomPass、OutputPass、ShaderPass。需要其他 addon（例如 OrbitControls）時，把它加進 `assets/vendor/three.bundle.entry.js`，在暫存資料夾執行 `npm i three@0.169.0 esbuild` 和 `npx esbuild three.bundle.entry.js --bundle --minify --format=iife --outfile=three.bundle.min.js`，再覆蓋三個範本的 `vendor/three.bundle.min.js`（`assets/example*/vendor/`）。不要改回 `import ... from 'three/addons/...'`，那樣離線就打不開了。

## 檔案結構（行號為範例檔大約位置）

| 區塊 | 位置 | 新專案要改嗎 |
|---|---|---|
| CSS 色彩 tokens `:root` | ~11 | 依主題換色（`--accent`、`--paper`、`--amber`） |
| 資訊卡、進場動畫、圖解、指引線、進度軌、講稿面板 CSS | ~24–186 | 通常不用改 |
| `SLIDES` 陣列（每頁內容） | ~228–471 | **主要改這裡** |
| 卡片渲染、換頁、鍵盤／滾輪／觸控 | ~476–575 | 不用改 |
| three.js 場景、燈光、地面、程式化物件 | ~580–649 | 依主題調整或刪除專屬特效 |
| 載入 GLB（`loadGLB('名稱')`）、`DEVICES`、`buildFlows()` | ~654–694 | **改模型名稱（同時改 head 的 `.glb.js` script）、物件名稱、資料流** |
| `shotFor()` 每頁鏡位 | ~699–716 | **每頁一個 case** |
| `frame()` 每幀更新 | ~739–803 | 刪掉不用的特效段落 |

## SLIDES 每頁欄位

```js
{ id:'meter', label:'智慧電表',          // id 對應 shotFor / flows；label 顯示在進度軌
  sky:'day' | 'high',                    // 背景天空
  eyebrow:'POWER & DATA · 1F',
  title:'智慧電表<br>讀懂家的<em>用電</em>',  // <br> 分行逐行升起；<em> 為強調色
  dek:'一段說明',                         // 資訊卡主文
  facts:['<b>重點：</b>…', …],           // 編號條列
  chips:['標籤', …],
  diagram:{type:'flow'|'cols', items:[…]},// flow: {k,h,p}；cols: {k,cls:'now'|'warn',h,li:[]}
  steps:[{layout:'left',parts:['dek']},{layout:'left',parts:['dek','facts']}],
                                          // 每按一次下一步進一個 step；layout: hero/left/right/bottom
  focus:'一樓｜智慧電表', tagText:'一樓・智慧電表', // 鏡頭特寫＋指引線指向的 GLB 物件名
  floor:'1F',                             // 淡化 userData.cutaway==='1F' 的外牆
  hotspots:true,                          // 顯示 DEVICES 的可點標籤
  sources:[['顯示文字','https://…']],     // 參考資料連結
  notes:`講稿全文，（下一步）標示換步驟處` }
```

## 動畫手法（已內建，維持即可）

- 資訊卡：版面切換時 left/top/width 1s 緩動；內容 `.anim` 依 `--i` 錯開升起；標題逐行遮罩升起；圖解進度條填滿。
- 鏡頭：每次換頁沿二次貝茲弧線補間，距離越遠飛越高；`setViewOffset` 把主體推到資訊卡另一側；待機微晃；結語頁緩慢環繞。
- 3D：`Flow` 類別沿弧線流動的光點（資料流）；淡入淡出的半透明罩；逐一亮起的地面點；衛星自轉浮動。
- 支援 `prefers-reduced-motion` 與網址 `?still`（關閉動畫，方便截圖）、`#8.2`（直接跳頁與步驟）。

## 深色／霓虹主題（科技、未來類）

`assets/example/` 是淺色日間主題；`assets/example-dark/`（「科技與未來城市」，10 頁）是同一套架構的夜景霓虹版，做科技／未來類主題時以它為範本。重點：

- **光暈後製**：`EffectComposer` → `RenderPass` → `UnrealBloomPass(size, .6, .4, 1.0)` → `OutputPass`，每幀用 `composer.render()`，resize 時 `composer.setSize()`。閾值設 **1.0**：只有發光值 > 1 的霓虹會發暈，一般受光表面不會。
- 光暈需要不透明背景：renderer 不開 alpha，改用 `scene.background` ＋ `scene.fog = FogExp2`，移除 CSS `.sky`。
- 燈光要暗：Hemisphere ~0.45、Directional ~0.7、`scene.environmentIntensity` ~0.15、exposure ~0.85。太亮整個畫面會被光暈洗白。
- 載入 GLB 後壓低發光值。**材質是多個網格共用的**，用 Set 確保每個材質只調一次，否則會被重複相乘：
  ```js
  const tuned=new Set();
  city.traverse(o=>{if(!o.isMesh)return;const m=o.material;if(tuned.has(m))return;tuned.add(m);
    if(m.emissiveIntensity>0)m.emissiveIntensity=/窗光/.test(m.name)?.75:m.emissiveIntensity*.5});
  ```
- CSS：`:root` 換深色 tokens，並把範例裡寫死的淺色（`.dek`、`.facts li`、`.col`、`.chip`、`.tool` 背景等）改用 token；標題 `<em>` 可用漸層文字＋`animation` 流動；卡片上緣加一道掃過的流光（`::after` + `background-position` 動畫）。
- 外圍可加 `GridHelper` 與星空 `Points`，讓城市邊緣融入霧中。

## 敘事／角色主題（社會議題、故事類）

`assets/example-story/`（「斷在學校」，9 頁）在深色架構上加了「角色走位」與「氛圍轉換」，適合有主角、有情緒起伏的報告：

- **角色**：GLB 內每個小人是一個物件，子物件 `{名}_左腳／右腳／左手／右手` 的原點設在關節，前端以正弦擺動做走路；`planFor(id, step)` 回傳每頁每步的 `{r:路徑, face, pose:'sit'|'slump'|'wave'…, delay, hideEnd, loop}`，`applyPlan()` 在換步時套用，`updateActor()` 每幀沿路徑移動。不出場的角色 `hideEnd` 隱藏。
- **氛圍值 `mood`（0～1）**：每頁（或每步）設一個值，連動天空／霧色、燈光強度、曝光、雨、光點，以及最後一道自訂 `ShaderPass`（`sat` 飽和度、`warm` 暖色、`vig` 暗角）。`mood≥.8` 時把 `<html data-mood="bright">`，卡片改淺色 tokens。故事前段灰暗、解方段逐步調亮。
- **注意**：低飽和度時紅藍警示燈也會變灰；需要彩色重點時，讓該物件不受 grade pass 影響或在該頁暫時提高 `sat`。
- 車輛進出場：以 `parked` 條件決定目標 x，每幀插值；閃燈只在特定頁啟用。
- **鏡頭跟拍主角**：主角長距離走位時，`shotFor` 回傳 `{follow:'角色名', pos, tgt}`，`pos`／`tgt` 當成相對主角腳下的位移；`setShot` 記下位移，`frame()` 每幀用主角目前位置更新 `cam.to`／`cam.toT`，鏡頭就會沿弧線飛到主角身邊後跟著走。位移要選在主角整條路線上都不會被建築擋住的方向。
- **穿模檢查**：在頁面加一個 `?check` 模式，模型載入後逐頁逐步呼叫 `planFor()`，對每段路線用 `THREE.Raycaster` 在腳、腰、頭三個高度（約 0.35／1.0／1.6m）、身體中線與左右兩側打水平射線，射線長度＝該段長度（車輛再加車頭長度）；材質暫時設 `DoubleSide` 才抓得到「站在物件裡面」；落在台基、橋面高度以下的命中（走上台階）略過。另外檢查每步終點站位彼此距離是否小於兩人半徑和。結果寫進頁面的 `<pre id="checkOut">`，用 `msedge --headless=new --dump-dom "<檔案>?check"` 讀出來，清單為空才算通過。

## 動態物件

以名稱前綴抓物件（`city.children.filter(o=>o.name.startsWith('自駕車_'))`），在 `frame()` 中更新：
- 旋轉：`ring.rotation.y=t*.4`、`blades.rotation.z=-t*1.1`（葉片的原點要在 Blender 中設在轉軸）。
- 沿道路循環：記下初始位置與移動軸（看 bbox 長邊），`pos[axis]=wrap(base+dir*speed*t)`。
- 依頁面觸發：例如無人機在 drone 頁鏡頭到位後才起飛（用 `now-cam.start` 計時）。
- `?still` 模式下把 `t` 固定為 0，截圖才穩定。

## 改寫時的注意事項

- `DEVICES`、`focus`、`P('…')` 內的名稱必須與 GLB 物件名稱完全一致，否則位置會退回 (0,5,0)。
- 刪除某頁時，同步刪 `shotFor` 的 case、`flows` 的 key 與 `frame()` 中專屬該頁的特效。
- 鏡位常見錯誤：鏡頭落在建築內部（整片白／灰）或被近處高樓擋住。特寫時把鏡頭放在道路上空或開闊處，用 modeling-guide 的座標換算確認。
- 用 Edit 工具改 HTML；用 PowerShell 字串替換含中文的程式碼容易靜默失敗。
- `file://` 下不能用 `fetch`／`loadAsync` 讀取任何本機檔案，也不能 `import` 外部模組檔，但 `<script src>` 和行內 `<script type="module">` 可以。所有資源（模型、JSON、貼圖）都要嵌進 `.js` 或 data URI，不要新增任何需要 fetch 的檔案。
- 新增本機 `<script src>` 時，屬性只寫 `src`（`<script src="…"></script>`），build.ps1 才會內嵌它。
- 引用的事實與數據要附 `sources`，不確定的內容寫成「研議中／構想」而非斷言。
