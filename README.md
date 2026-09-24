# Genius VR Quotation System

Interactive quotation webpage for OKKA interior design customers — 3D viewing + material switching + real-time pricing.

## Features

- **2D Interactive Quotation**: Material switching, real-time calculation, WhatsApp sharing, QR Code
- **3D Room Viewer**: Three.js 3D room with perspective/top/front view switching
- **WebSocket Real-time Sync**: Multiple devices can view the same quotation simultaneously
- **ERP Integration**: Auto-create Odoo sale orders on customer confirmation
- **Material Management**: CRUD interface for managing materials

## Tech Stack

- **Backend**: FastAPI + PostgreSQL
- **Frontend**: Bootstrap5 + Three.js + WebSocket
- **3D**: Three.js with furniture models
- **ERP**: Odoo 18 via XML-RPC

## Deployment

### Local Development

```bash
cd ~/genie/vr_quotation
python3 app.py

# Dashboard: http://127.0.0.1:8080/
# 2D Quotation: http://127.0.0.1:8080/vr/TEST001
# 3D Quotation: http://127.0.0.1:8080/vr3d/TEST001
# Materials: http://127.0.0.1:8080/materials
```

### Railway Deployment

1. **Create GitHub Repository**
   ```bash
   cd ~/genie/vr_quotation
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Connect to Railway**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub
   - Create new project
   - Connect to your GitHub repository

3. **Add PostgreSQL**
   - In Railway dashboard, click "New" → "Database" → "PostgreSQL"
   - Railway will provide `DATABASE_URL` environment variable

4. **Set Environment Variables**
   ```
   DATABASE_URL=<provided by Railway>
   ODOO_URL=http://your-odoo-server:8069
   ODOO_DB=genius
   ODOO_USER=admin
   ODOO_PASSWORD=admin
   ```

5. **Deploy**
   - Railway will auto-deploy on git push
   - Your app will be available at `https://your-app.up.railway.app`

### Export Data to Railway

```bash
# Export from local PostgreSQL
cd ~/genie/vr_quotation
python3 export_data.py

# Import to Railway PostgreSQL
psql $DATABASE_URL < export_YYYYMMDD_HHMMSS.sql
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard |
| GET | `/vr/{token}` | 2D quotation page |
| GET | `/vr3d/{token}` | 3D quotation page |
| GET | `/materials` | Material management |
| GET | `/api/quotation/{token}` | Quotation JSON |
| GET | `/api/materials` | Materials list JSON |
| POST | `/api/quotation/{token}/confirm` | Customer confirm → ERP sync |
| POST | `/api/materials/create` | Create material |
| PUT | `/api/materials/{id}` | Update material |
| DELETE | `/api/materials/{id}` | Soft delete material |
| WS | `/ws/{link_token}` | Real-time sync |

## WebSocket Message Types

| Type | Description |
|------|-------------|
| `viewer_count` | Viewer count update |
| `material_change` | Material switch |
| `quantity_change` | Quantity change |
| `price_update` | Price update |
| `ping/pong` | Keep connection alive |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Local Docker |
| `PORT` | Server port | 8080 |
| `ODOO_URL` | Odoo ERP URL | http://127.0.0.1:8069 |
| `ODOO_DB` | Odoo database name | genius |
| `ODOO_USER` | Odoo username | admin |
| `ODOO_PASSWORD` | Odoo password | admin |

## Cost

**$0** — All open source
- Blender 5.0 (GPL)
- FastAPI + PostgreSQL
- Bootstrap5 + Three.js + WebSocket
- Odoo 18 (Enterprise trial)
- Railway free tier

## License

Internal use for OKKA Interior Design.
