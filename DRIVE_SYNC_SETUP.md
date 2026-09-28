# Google Drive → VR Texture Sync 設定指南

## 已完成 ✅
- [x] `sync_drive_textures.py` 同步腳本
- [x] `POST /api/sync-from-drive` endpoint（app.py）
- [x] `google-api-python-client` 加入 requirements
- [x] Railway 部署成功
- [x] Railway 環境變數 `GOOGLE_DRIVE_FOLDER_ID` 已建立（placeholder）

## 你需要做（~5分鐘）

### Step 1: 建立 Google Drive 資料夾
1. 打開 https://drive.google.com
2. 建立新資料夾：`OKKA_VR_Textures`
3. 複製資料夾 ID（URL 中 `folders/` 後面嘅一長串字）

### Step 2: 分享資料夾俾 Service Account
1. 右鍵 `OKKA_VR_Textures` → Share
2. 加入 email：`okka-sheets@okka-vr-quotation.iam.gserviceaccount.com`
3. 權限選 **Viewer**（只需要讀取）
4. 按 Send

### Step 3: 上傳第一批素材
檔案命名規則：`{material_id}_{name}.jpg`

| 檔案名 | 對應 Material |
|--------|-------------|
| `1_拋光石英磚.jpg` | ID=1 拋光石英磚 60x60 (floor) |
| `2_仿木紋磚.jpg` | ID=2 仿木紋磚 60x60 (floor) |
| `3_大理石紋磚.jpg` | ID=3 大理石紋磚 80x80 (floor) |
| `4_乳膠漆白.jpg` | ID=4 乳膠漆（白色）(wall) |
| `5_乳膠漆灰.jpg` | ID=5 乳膠漆（淺灰）(wall) |
| `6_藝術漆.jpg` | ID=6 藝術漆 (wall) |
| `7_平頂天花.jpg` | ID=7 平頂天花 (ceiling) |
| `8_假天花.jpg` | ID=8 假天花（含燈槽）(ceiling) |
| `9_入牆櫃基本.jpg` | ID=9 入牆櫃（基本）(cabinet) |
| `10_入牆櫃中級.jpg` | ID=10 入牆櫃（中級）(cabinet) |
| `11_廚房櫥櫃.jpg` | ID=11 廚房櫥櫃 (cabinet) |
| `12_筒燈.jpg` | ID=12 筒燈（基本）(lighting) |
| `13_射燈.jpg` | ID=13 射燈（可調角度）(lighting) |
| `14_燈帶.jpg` | ID=14 燈帶（間接照明）(lighting) |

### Step 4: 更新 Railway 環境變數
```bash
cd ~/genie/vr_quotation
railway variables set "GOOGLE_DRIVE_FOLDER_ID=你嘅資料夾ID"
```

### Step 5: 觸發同步
```bash
curl -X POST "https://okka-vr-quotation-production.up.railway.app/api/sync-from-drive"
```

或者用獨立腳本：
```bash
GOOGLE_DRIVE_FOLDER_ID=你嘅資料夾ID python3 sync_drive_textures.py
```

## 日常工作流

1. 搵到好嘅牆紙/地磚 JPEG
2. 上傳到 Google Drive `OKKA_VR_Textures` 資料夾
3. 命名為 `{material_id}_{name}.jpg`
4. 執行同步（或等定時任務）
5. 客人打開 3D 報價單就見到新素材

## 定時同步（可選）
Railway 冇內建 cron，但可以：
- 用 Railway 嘅 `railway cron` 功能
- 或者用外部 cron（e.g. GitHub Actions）定時 call endpoint

## 故障排除

| 問題 | 原因 | 解決 |
|------|------|------|
| "GOOGLE_DRIVE_FOLDER_ID not configured" | 環境變數未設 | Step 4 |
| "Google Drive credentials not configured" | Service account 無權限 | 確認 credentials.json 有 Drive scope |
| "File not found" | 資料夾 ID 錯誤 | 檢查 URL 中 `folders/` 後面嘅 ID |
| 圖片同步咗但 VR 唔見到 | 前端 cache | 強制刷新 (Ctrl+Shift+R) |
