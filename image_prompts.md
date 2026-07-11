# 近視控制設計圖 — AI 生圖指令(prompt)+ 規格

用法:把下面每張圖的 **PROMPT** 貼到 AI 生圖工具(Midjourney / DALL·E 3 / Adobe Firefly /
Google 生圖 等),產出後存成 PNG 放進本 `assets/` 資料夾,再到 index.html 的
`DIAGRAMS` 對應那張加 `img:"assets/檔名.png"` 即可(見 assets/README.txt)。

小訣竅:
- AI 產生的「文字標籤」常會亂碼,建議 prompt 內加「no text, no labels」,
  文字說明交給網頁右側的編號清單(notes)顯示。
- 想要一致風格,可把下面【共同風格】那段接在每個 prompt 前面。

---------------------------------------------------------------
【共同風格 STYLE(建議每個 prompt 前面都加這段)】
Clean modern medical infographic illustration, professional ophthalmology
education style, soft gradients and gentle shadows, crisp edges, cohesive
palette of cobalt blue, fresh green and warm amber on a white background,
high detail, centered composition, no text, no labels, no watermark.
---------------------------------------------------------------


## 1. 角膜塑型片(Orthokeratology)

### 1a 側面橫切
Anatomical cross-section of a human cornea with a rigid reverse-geometry
orthokeratology lens resting on it during overnight wear. Show the four lens
curves (central base/treatment curve, reverse curve, alignment curve,
peripheral curve), a thin tear-film layer between lens and cornea, and the
reshaped corneal surface: a flattened central zone (~6 mm) with a steeper
mid-peripheral ring. Side view, schematic but polished.

### 1b 正面地形圖
Front-view corneal topography map (bull's-eye) after orthokeratology: a cool
blue flattened central disc surrounded by a warm orange/red steepened annular
ring, smooth color gradient like a real Placido topographer map, circular.

規格:中央治療區 ~6mm;夜戴、白天免鏡;形成周邊近視離焦。


## 2. 低濃度阿托品(Low-dose Atropine 0.05%)

Anatomically detailed cross-section of a human eyeball (cornea, anterior
chamber, iris, pupil, crystalline lens, ciliary body with zonules, vitreous,
retina, choroid, sclera, fovea, optic nerve). A single eye-drop falling onto
the cornea from a small dropper bottle. Subtly highlight a thickened choroid
layer in soft green. Clean medical illustration, side view.

規格:每晚點眼 0.05%;蕈毒鹼受體拮抗;推測脈絡膜增厚;主要延緩度數。


## 3. 周邊離焦框架眼鏡 — DIMS(Hoya MiYOSMART)

### 3a 正面(蜂巢)
Front view of a round myopia-control spectacle lens. A clear circular central
zone (about 9.4 mm diameter) for distance vision, surrounded by a dense
hexagonal honeycomb array of hundreds of tiny identical round micro-segments
(about 400 of them) filling the mid-periphery. Subtle glossy lens reflection.

### 3b 側面光路
Optics side-view diagram: parallel light rays passing through the clear central
zone converge to a sharp focus on the retina, while rays through the +3.50D
honeycomb micro-segments focus in front of the retina (myopic defocus). Show a
simple clean eye on the right.

規格:中央清晰區 Ø9.4mm;蜂巢 396 段、每段 +3.50D;離焦:清晰 ≈ 50:50。


## 4. 周邊離焦框架眼鏡 — HAL(Essilor Stellest)

### 4a 正面(11 環)
Front view of a round myopia-control spectacle lens. A clear central zone
(about 9 mm) surrounded by 11 concentric rings made of many tiny contiguous
(touching) aspherical lenslets (1021 total, each ~1.1 mm), with thin clear
single-vision gaps between the rings. Precise, elegant, glossy.

### 4b 側面 VoMD
Optics side-view: aspherical lenslets do not focus to a single point but spread
light into a three-dimensional "volume of myopic defocus" in front of the
retina, shown as a soft green translucent shell ahead of the retina, while the
central clear zone focuses sharply on the retina.

規格:中央清晰區 Ø9mm;11 環、1021 顆非球面微透鏡(Ø1.12mm);形成前方離焦體積 VoMD。


## 5. 離焦軟式隱形眼鏡 — MiSight(dual-focus)

### 5a 正面(同心圓雙焦)
Front view of a soft daily-disposable contact lens with a concentric dual-focus
design: a central circular distance-correction zone (about 3.36 mm) surrounded
by alternating rings — two treatment rings (+2.00D myopic defocus) and two
correction rings. Soft translucent tinted lens, gentle highlights.

### 5b 側面(配戴 + 雙焦)
A soft contact lens draped on the cornea, with dual-focus rays: the central
correction zone focuses on the retina, the +2.00D treatment rings focus in
front of the retina (myopic defocus). Clean eye cross-section.

規格:中央 distance 區 Ø3.36mm;4 環交替(矯正 1,3 / 治療 2,4)、治療 +2.00D;日拋。


## 6. 重複低強度紅光(RLRL 650nm)

### 6a 儀器與使用
A child looking into a desktop red-light therapy device with two round
eyepieces glowing soft red (650 nm). Warm, safe, clinical home setting.

### 6b 側面光路
Cross-section of an eye with soft red 650 nm light entering and reaching the
retina and choroid; subtly show increased choroidal blood flow / thickening in
green. Clean medical illustration.

規格:650nm 低強度;每次 3 分、每日 2 次、每週 5 天;推測脈絡膜血流↑;停用易反彈,建議 OCT 追蹤。


## 7. 戶外活動(Outdoor time)

### 7a 機轉
A cheerful child outdoors under bright natural sunlight; alongside, a small
inset cross-section of the retina releasing dopamine that inhibits eyeball
elongation. Bright, healthy, hopeful mood.

### 7b 光照強度對比
Simple elegant bar comparison of light intensity: indoor (~300 lux) vs cloudy
outdoor (~10,000 lux) vs sunny outdoor (~100,000 lux), with a marked
"≥1000 lux protective threshold" line.

規格:建議約 2 小時/天;≥1000 lux;多巴胺↑ → 抑制眼軸;主要延緩近視『發生』。

---------------------------------------------------------------
產圖後:存到 assets/,在 index.html 的 DIAGRAMS 對應圖加 img:"assets/xxx.png"。
右側編號說明(notes)不受影響、會照常顯示;點圖可放大。
