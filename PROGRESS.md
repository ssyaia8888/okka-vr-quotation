# Genius VR 系統 — 互動式報價單網頁 進度報告

## 📋 項目概覽
- **目標**: 建立互動式報價單網頁，客人可以 3D 瀏覽 + 換物料 + 即時睇報價
- **技術棧**: FastAPI + PostgreSQL + Bootstrap5 + Three.js + WebSocket
- **端口**: 127.0.0.1:8080 (OKKA Web)
- **DB**: genius (PostgreSQL, Docker: genius_erp_db)

## ✅ Phase 1-4 完成狀態

### Phase 1: 互動式報價單前端 ✅
- **FastAPI 後端**: `~/genie/vr_quotation/app.py`
- **互動式前端**: `~/genie/vr_quotation/templates/vr_quotation.html`
- **功能**: 物料切換、即時計算、WhatsApp 分享、QR Code

### Phase 2: ERP 整合 + 後台管理 ✅
- **ERP 整合**: 客人確認 → 自動建立 Odoo sale.order + sale.order.line
- **WhatsApp 通知**: 確認後自動生成通知連結 (`whatsapp_notify.py`)
- **Dashboard**: 顯示確認狀態 + ERP 訂單號
- **物料管理**: CRUD 頁面 (`/materials`)

### Phase 3: 3D 模型展示 ✅
- **Three.js 3D 房間**: `~/genie/vr_quotation/templates/vr_3d.html`
- **功能**: 透視圖、俯視圖、正視圖切換
- **物料即時切換**: 揀選物料即時更新 3D 模型顏色
- **即時計算**: 根據房間面積即時計算報價
- **家具模型**: 沙發、茶几、電視櫃、電視

### Phase 4: WebSocket 即時同步 ✅
- **即時同步**: 多設備同時觀看同一報價單
- **觀看人數**: 顯示當前觀看人數
- **物料切換同步**: 一台設備換物料，其他設備即時更新
- **報價同步**: 價格變更即時同步到所有設備
- **連接狀態**: 顯示即時同步中/離線狀態
- **自動重連**: 斷線後自動重連（指數退避）

## 📂 文件結構
```
~/genie/vr_quotation/
├── app.py              # FastAPI 主程式 (20KB)
├── whatsapp_notify.py  # WhatsApp 通知模組
├── requirements.txt    # Python 依賴
├── PROGRESS.md         # 本文件
├── templates/
│   ├── dashboard.html  # 管理後台
│   ├── vr_quotation.html  # 2D 互動式報價單
│   ├── vr_3d.html      # 3D 互動式報價單
│   └── materials.html  # 物料管理
└── static/             # 靜態文件
```

## 🔌 API 端點

### 前端頁面
| 路由 | 說明 |
|------|------|
| `GET /` | Dashboard (管理後台) |
| `GET /vr/{token}` | 2D 互動式報價單 (客人用) |
| `GET /vr3d/{token}` | 3D 互動式報價單 (客人用) |
| `GET /materials` | 物料管理頁面 |

### API 端點
| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/quotation/{token}` | 報價單 JSON |
| GET | `/api/materials` | 物料庫列表 |
| POST | `/api/quotation/create` | 新增報價單 |
| POST | `/api/quotation/{token}/confirm` | 客人確認 (觸發 ERP 同步) |
| POST | `/api/materials/create` | 新增物料 |
| PUT | `/api/materials/{id}` | 更新物料 |
| DELETE | `/api/materials/{id}` | 停用物料 |

### WebSocket 端點
| 路徑 | 說明 |
|------|------|
| `ws://{host}/ws/{token}` | 即時同步 |

### WebSocket 訊息類型
| 類型 | 說明 |
|------|------|
| `viewer_count` | 觀看人數更新 |
| `material_change` | 物料切換 |
| `quantity_change` | 數量變更 |
| `price_update` | 價格更新 |
| `ping/pong` | 保持連接 |

## 🔄 完整流程
1. **Admin 建立報價單** → Dashboard `/` → 產生 token + QR Code
2. **Admin 管理物料** → `/materials` → 新增/編輯/停用
3. **分享予客人** → WhatsApp / QR Code → `/vr/{token}` 或 `/vr3d/{token}`
4. **客人互動** → 揀選物料、調整數量 → 即時計算
5. **即時同步** → 多設備同時觀看，變更即時同步
6. **客人確認** → 自動建立 Odoo 訂單
7. **通知 SSY** → WhatsApp 通知連結

## 🧪 測試數據

### TEST001 — 陳先生單位裝修
- Token: `TEST001`
- 客戶: 陳先生 (91234567)
- 地址: 紅磡黃埔花園
- 金額: $13,225
- 項目: 4項 (地板/牆身/天花/櫃體)

### 4B94A5E5 — 李先生單位裝修 (ERP 測試)
- Token: `4B94A5E5`
- 客戶: 李先生 (98765432)
- 地址: 九龍灣MegaBox附近
- 金額: $10,250
- ERP 訂單: SO00047 ✅

## 📊 物料庫 (14種)
| 類別 | 數量 | 價格範圍 |
|------|------|----------|
| 地板 | 3 | $180-350/sqm |
| 牆身 | 3 | $45-120/sqm |
| 天花 | 2 | $85-180/sqm |
| 櫃體 | 3 | $1,200-2,800/sqm |
| 燈具 | 3 | $65-120/unit |

## 🚀 使用方式

### 管理員
```bash
# 啟動服務器
cd ~/genie/vr_quotation
python3 app.py

# 開啟 Dashboard
open http://127.0.0.1:8080/

# 開啟物料管理
open http://127.0.0.1:8080/materials
```

### 客人
1. 收到 WhatsApp 連結/掃 QR Code
2. 開啟 2D 或 3D 報價單頁面
3. 揀選物料、調整數量
4. 即時睇到總金額變化
5. 點擊「確認報價單」→ 自動入 ERP

### 3D 功能
- **透視圖**: 自由旋轉觀看房間
- **俯視圖**: 從上方觀看佈局
- **正視圖**: 從正面觀看
- **物料切換**: 揀選即時更新 3D 模型
- **即時報價**: 根據面積計算總金額

### 即時同步功能
- **多設備同時觀看**: 同一報價單可多人同時觀看
- **即時同步**: 物料切換、數量調整即時同步到所有設備
- **觀看人數**: 顯示當前觀看人數
- **連接狀態**: 顯示即時同步中/離線
- **自動重連**: 斷線後自動重連

## 🎯 成本
**$0** — 全部免費開源
- Blender 5.0 (GPL)
- FastAPI + PostgreSQL
- Bootstrap5 + Three.js + WebSocket
- Odoo 18 (Enterprise trial)

## 📝 下一步 (Phase 5-6)
- [ ] Phase 5: Blender 自動化建模 (匯入真實平面圖)
- [ ] Phase 6: 手機 App (React Native)

## ⚡ 快速啟動
```bash
cd ~/genie/vr_quotation
python3 app.py
# Dashboard: http://127.0.0.1:8080/
# 2D 報價單: http://127.0.0.1:8080/vr/TEST001
# 3D 報價單: http://127.0.0.1:8080/vr3d/TEST001
# 物料管理: http://127.0.0.1:8080/materials
```
