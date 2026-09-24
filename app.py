#!/usr/bin/env python3
"""
Genius VR Quotation System — Interactive Quotation Webpage
FastAPI + PostgreSQL + Bootstrap5 + Three.js (Phase 1: 2D interactive)
"""

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict
import psycopg2
import psycopg2.extras
import uuid
import os
from datetime import datetime, timedelta
import xmlrpc.client
import logging
import json
from whatsapp_notify import get_ssyy_whatsapp_link, build_confirmation_message

logger = logging.getLogger(__name__)

app = FastAPI(title="Genius VR Quotation", version="1.0")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    import sys; print("=== FASTAPI STARTUP - INIT_DB ==="); sys.stdout.flush()
    init_db()

# ============================================================
# WebSocket Connection Manager
# ============================================================

class ConnectionManager:
    """Manage WebSocket connections for real-time sync"""
    
    def __init__(self):
        # Map of link_token -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, link_token: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        if link_token not in self.active_connections:
            self.active_connections[link_token] = []
        self.active_connections[link_token].append(websocket)
        logger.info(f"WebSocket connected: {link_token} (total: {len(self.active_connections[link_token])})")
    
    def disconnect(self, websocket: WebSocket, link_token: str):
        """Remove WebSocket connection"""
        if link_token in self.active_connections:
            if websocket in self.active_connections[link_token]:
                self.active_connections[link_token].remove(websocket)
            if not self.active_connections[link_token]:
                del self.active_connections[link_token]
        logger.info(f"WebSocket disconnected: {link_token}")
    
    async def broadcast(self, link_token: str, message: dict, exclude: WebSocket = None):
        """Broadcast message to all connections for a link_token"""
        if link_token not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[link_token]:
            if connection != exclude:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn, link_token)
    
    def get_viewer_count(self, link_token: str) -> int:
        """Get number of active viewers"""
        return len(self.active_connections.get(link_token, []))

manager = ConnectionManager()

# Mount static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "img"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Custom Jinja2 filter for JSON serialization (handles Decimal, datetime)
import json
from decimal import Decimal

def safe_tojson(obj):
    """JSON serialize with Decimal/datetime support"""
    def default_serializer(o):
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    return json.dumps(obj, default=default_serializer)

templates.env.filters['safe_tojson'] = safe_tojson

# ============================================================
# Database Configuration
# ============================================================

# Support both local Docker PostgreSQL and Railway's DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Railway / Cloud PostgreSQL (uses DATABASE_URL environment variable)
    DB_CONFIG = DATABASE_URL
else:
    # Local Docker PostgreSQL
    DB_CONFIG = {
        "host": "172.20.0.2",  # Docker network IP for genius_erp_db
        "port": 5432,
        "database": "genius",
        "user": "genius_user",
        "password": "sa1234567890"
    }

def get_db():
    """Get PostgreSQL connection"""
    if isinstance(DB_CONFIG, str):
        # Railway / Cloud: use connection string
        conn = psycopg2.connect(DB_CONFIG, sslmode='require')
    else:
        # Local: use config dict
        conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

def query_db(sql, params=None, fetch=True):
    """Execute query and return results"""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetch:
                return cur.fetchall()
            return None
    finally:
        conn.close()

def init_db():
    """Create VR tables if they don't exist (for Railway/new database)"""
    import sys
    print("=== INIT_DB START ===", flush=True)
    try:
        print(f"DB URL set: {bool(DATABASE_URL)}", flush=True)
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
        else:
            conn = psycopg2.connect(**DB_CONFIG)
        print("Connected OK", flush=True)
        cur = conn.cursor()
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vr_materials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            category VARCHAR(50) NOT NULL,
            color_hex VARCHAR(7) DEFAULT '#808080',
            unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
            unit VARCHAR(20) DEFAULT 'sqm',
            texture_url TEXT,
            description TEXT,
            model_number VARCHAR(100),
            brand VARCHAR(100),
            spec VARCHAR(200),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)
        print("Created vr_materials", flush=True)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vr_quotation_links (
            id SERIAL PRIMARY KEY,
            link_token VARCHAR(64) UNIQUE NOT NULL,
            customer_name VARCHAR(200) NOT NULL,
            customer_phone VARCHAR(50),
            customer_email VARCHAR(200),
            project_address TEXT,
            total_amount DECIMAL(12,2) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'pending',
            valid_until TIMESTAMP,
            odoo_order_id INTEGER,
            confirmed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """)
        print("Created vr_quotation_links", flush=True)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vr_quotation_items (
            id SERIAL PRIMARY KEY,
            link_id INTEGER REFERENCES vr_quotation_links(id) ON DELETE CASCADE,
            material_id INTEGER REFERENCES vr_materials(id),
            quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
            unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
            area_name VARCHAR(200),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        # Add missing columns to existing tables (safe for Railway rebuild)
        alter_cols = [
            "ALTER TABLE vr_materials ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE vr_materials ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE vr_materials ADD COLUMN IF NOT EXISTS model_number VARCHAR(100)",
            "ALTER TABLE vr_materials ADD COLUMN IF NOT EXISTS brand VARCHAR(100)",
            "ALTER TABLE vr_materials ADD COLUMN IF NOT EXISTS spec VARCHAR(200)",
            "ALTER TABLE vr_quotation_links ADD COLUMN IF NOT EXISTS viewed_at TIMESTAMP",
            "ALTER TABLE vr_quotation_links ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE vr_quotation_links ADD COLUMN IF NOT EXISTS project_name VARCHAR(200)",
            "ALTER TABLE vr_quotation_links ADD COLUMN IF NOT EXISTS address TEXT",
            "ALTER TABLE vr_quotation_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE vr_quotation_items ADD COLUMN IF NOT EXISTS total_price DECIMAL(12,2) DEFAULT 0",
            "ALTER TABLE vr_quotation_items ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE vr_quotation_items ADD COLUMN IF NOT EXISTS quotation_link_id INTEGER REFERENCES vr_quotation_links(id) ON DELETE CASCADE",
        ]
        for sql in alter_cols:
            try:
                cur.execute(sql)
            except Exception:
                pass  # Column already exists
        
        # Insert sample materials if empty
        cur.execute("SELECT COUNT(*) FROM vr_materials")
        count = cur.fetchone()[0]
        if count == 0:
            materials = [
                ('意大利大理石地磚', 'floor', '#E8E0D4', 280.00, 'sqm'),
                ('木地板', 'floor', '#8B6914', 180.00, 'sqm'),
                ('瓷磚', 'floor', '#D4D0C8', 120.00, 'sqm'),
                ('牆身乳膠漆', 'wall', '#F5F5DC', 45.00, 'sqm'),
                ('牆紙', 'wall', '#DEB887', 85.00, 'sqm'),
                ('木饰面', 'wall', '#A0522D', 320.00, 'sqm'),
                ('石膏板天花', 'ceiling', '#FFFEF7', 95.00, 'sqm'),
                ('鋁扣板天花', 'ceiling', '#C0C0C0', 150.00, 'sqm'),
                ('廚房櫥櫃', 'cabinet', '#4A4A4A', 2800.00, 'set'),
                ('浴室櫃', 'cabinet', '#5C4033', 3500.00, 'set'),
                ('衣櫃', 'cabinet', '#DEB887', 4200.00, 'set'),
                ('LED筒燈', 'lighting', '#FFFACD', 85.00, 'pcs'),
                ('吊燈', 'lighting', '#FFD700', 1200.00, 'pcs'),
                ('射燈', 'lighting', '#FFFAF0', 120.00, 'pcs'),
            ]
            for m in materials:
                cur.execute(
                    "INSERT INTO vr_materials (name, category, color_hex, unit_price, unit) VALUES (%s, %s, %s, %s, %s)", m
                )
        
        # Insert sample quotation for A363FC09
        cur.execute("SELECT COUNT(*) FROM vr_quotation_links WHERE link_token='A363FC09'")
        exists = cur.fetchone()[0]
        if not exists:
            cur.execute("""
                INSERT INTO vr_quotation_links 
                (link_token, customer_name, customer_phone, project_address, total_amount, status, valid_until)
                VALUES ('A363FC09', '林先生', '91511033', '麗港城22座4樓H室', 51570.00, 'pending', NOW() + INTERVAL '30 days')
                RETURNING id
            """)
            link_id = cur.fetchone()[0]
            
            items = [
                (1, 2, 35.0, 280.0, '客廳'),
                (4, 1, 28.0, 45.0, '客廳'),
                (7, 1, 28.0, 95.0, '客廳'),
                (9, 1, 1, 2800.0, '廚房'),
                (12, 6, 6, 85.0, '全屋'),
                (2, 2, 15.0, 180.0, '主人房'),
                (5, 1, 15.0, 85.0, '主人房'),
                (8, 1, 15.0, 150.0, '主人房'),
                (2, 2, 10.0, 180.0, '客房'),
                (4, 1, 10.0, 45.0, '客房'),
                (7, 1, 10.0, 95.0, '客房'),
                (10, 1, 1, 3500.0, '浴室'),
                (1, 1, 5.0, 280.0, '浴室'),
                (11, 1, 1, 4200.0, '主人房'),
                (13, 1, 2, 1200.0, '客廳'),
            ]
            for item in items:
                cur.execute(
                    "INSERT INTO vr_quotation_items (material_id, link_id, quantity, unit_price, area_name) VALUES (%s, %s, %s, %s, %s)",
                    (item[0], link_id, item[2], item[3], item[4])
                )
        
        conn.commit()
        cur.close()
        conn.close()
        print("=== INIT_DB DONE ===", flush=True)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        print(f"=== INIT_DB ERROR: {e} ===", flush=True)
        logger.error(f"Database init error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================
# Odoo ERP Integration
# ============================================================

ODOO_URL = os.getenv("ODOO_URL", "http://127.0.0.1:8069")
ODOO_DB = os.getenv("ODOO_DB", "genius")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

def get_odoo_connection():
    """Get Odoo XML-RPC connection"""
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def find_or_create_partner(name, phone="", email=""):
    """Find or create customer in Odoo"""
    uid, models = get_odoo_connection()
    
    # Search by phone first
    if phone:
        partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search_read',
            [[['phone', '=', phone]]],
            {'fields': ['id', 'name'], 'limit': 1})
        if partners:
            return partners[0]['id']
    
    # Search by name
    partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'search_read',
        [[['name', '=', name]]],
        {'fields': ['id', 'name'], 'limit': 1})
    if partners:
        return partners[0]['id']
    
    # Create new partner
    partner_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
        'res.partner', 'create', [{
            'name': name,
            'phone': phone,
            'email': email,
            'customer_rank': 1
        }])
    logger.info(f"Created new partner: {name} (id={partner_id})")
    return partner_id

def sync_to_odoo(quotation_data, items_data):
    """Sync confirmed quotation to Odoo as sale.order"""
    try:
        uid, models = get_odoo_connection()
        
        # Find or create customer
        partner_id = find_or_create_partner(
            quotation_data['customer_name'] or 'VR 客戶',
            quotation_data.get('customer_phone', ''),
            ''
        )
        
        # Create sale.order
        order_vals = {
            'partner_id': partner_id,
            'date_order': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'state': 'draft',
            'note': f"VR 報價單自動建立\nToken: {quotation_data['link_token']}\n項目: {quotation_data['project_name']}\n地址: {quotation_data.get('address', '-')}",
            'origin': f"VR-{quotation_data['link_token']}"
        }
        
        order_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'sale.order', 'create', [order_vals])
        
        logger.info(f"Created sale.order: id={order_id}")
        
        # Create sale.order.line for each item
        for item in items_data:
            line_vals = {
                'order_id': order_id,
                'name': f"{item.get('area_name', '')} - {item.get('material_name', '')}",
                'product_uom_qty': item.get('quantity', 1),
                'price_unit': item.get('unit_price', 0),
                'price_subtotal': item.get('total_price', 0)
            }
            
            line_id = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
                'sale.order.line', 'create', [line_vals])
            
            logger.info(f"Created sale.order.line: id={line_id}")
        
        # Confirm the order
        models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'sale.order', 'action_confirm', [[order_id]])
        
        logger.info(f"Confirmed sale.order: {order_id}")
        
        return {
            'success': True,
            'order_id': order_id,
            'partner_id': partner_id,
            'message': f'已建立並確認銷售訂單 SO{order_id:05d}'
        }
        
    except Exception as e:
        logger.error(f"Odoo sync error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# ============================================================
# API Models
# ============================================================

class MaterialUpdate(BaseModel):
    material_id: int
    quantity: float = 1

class QuotationUpdate(BaseModel):
    items: List[MaterialUpdate]

class QuotationConfirm(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    notes: Optional[str] = None

# ============================================================
# Routes — Main Dashboard
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Admin Dashboard — list all quotation links"""
    links = query_db("""
        SELECT * FROM vr_quotation_links 
        ORDER BY created_at DESC
    """)
    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request,
        "links": links,
        "page": "dashboard"
    })

# ============================================================
# Routes — Customer-facing VR Quotation Page
# ============================================================

@app.get("/vr/{link_token}", response_class=HTMLResponse)
async def vr_quotation_page(request: Request, link_token: str):
    """Interactive quotation page for customers"""
    # Get quotation link
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link = link[0]
    
    # Update viewed status
    query_db(
        "UPDATE vr_quotation_links SET status = 'viewed', viewed_at = NOW() WHERE link_token = %s",
        (link_token,),
        fetch=False
    )
    
    # Get quotation items with material details
    items = query_db("""
        SELECT 
            qi.id,
            qi.area_name,
            qi.quantity,
            qi.unit_price,
            qi.total_price,
            qi.notes,
            m.id as material_id,
            m.name as material_name,
            m.category,
            m.description as material_desc,
            m.color_hex,
            m.unit
        FROM vr_quotation_items qi
        JOIN vr_materials m ON qi.material_id = m.id
        WHERE qi.quotation_link_id = %s
    """, (link["id"],))
    
    # Get available materials by category
    materials = query_db("""
        SELECT * FROM vr_materials 
        WHERE is_active = TRUE 
        ORDER BY category, name
    """)
    
    # Group materials by category
    materials_by_category = {}
    for m in materials:
        cat = m["category"]
        if cat not in materials_by_category:
            materials_by_category[cat] = []
        materials_by_category[cat].append(m)
    
    # Category display names
    category_names = {
        "floor": "地板",
        "wall": "牆身",
        "ceiling": "天花",
        "cabinet": "櫃體",
        "lighting": "燈具"
    }
    
    return templates.TemplateResponse(request, "vr_quotation.html", {
        "request": request,
        "link": link,
        "items": items,
        "materials_by_category": materials_by_category,
        "category_names": category_names,
        "link_token": link_token
    })

@app.get("/vr3d/{link_token}", response_class=HTMLResponse)
async def vr_3d_page(request: Request, link_token: str):
    """3D interactive quotation page for customers"""
    # Get quotation link
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link = link[0]
    
    # Update viewed status
    query_db(
        "UPDATE vr_quotation_links SET status = 'viewed', viewed_at = NOW() WHERE link_token = %s",
        (link_token,),
        fetch=False
    )
    
    # Get available materials by category
    materials = query_db("""
        SELECT * FROM vr_materials 
        WHERE is_active = TRUE 
        ORDER BY category, name
    """)
    
    return templates.TemplateResponse(request, "vr_3d.html", {
        "request": request,
        "link": link,
        "project_name": link.get("project_name", "單位裝修"),
        "materials": materials,
        "link_token": link_token
    })

@app.get("/edit/{link_token}", response_class=HTMLResponse)
async def edit_quotation_page(request: Request, link_token: str):
    """Edit quotation page for admin"""
    # Get quotation link
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link = link[0]
    
    # Get quotation items
    items = query_db("""
        SELECT qi.*, m.name as material_name, m.category, m.color_hex
        FROM vr_quotation_items qi
        LEFT JOIN vr_materials m ON qi.material_id = m.id
        WHERE qi.link_id = %s
        ORDER BY qi.id
    """, (link["id"],))
    
    # Get available materials
    materials = query_db("""
        SELECT * FROM vr_materials 
        WHERE is_active = TRUE 
        ORDER BY category, name
    """)
    
    return templates.TemplateResponse(request, "edit_quotation.html", {
        "request": request,
        "link": link,
        "items": items,
        "materials": materials
    })

@app.put("/api/quotation/{link_token}")
async def update_quotation(link_token: str, request: Request):
    """Update quotation basic info"""
    body = await request.json()
    
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link_id = link[0]["id"]
    
    # Update fields
    fields = ['project_name', 'customer_name', 'customer_phone', 'address', 'valid_until']
    updates = []
    values = []
    
    for field in fields:
        if field in body:
            updates.append(f"{field} = %s")
            values.append(body[field])
    
    if updates:
        updates.append("updated_at = NOW()")
        values.append(link_id)
        query_db(f"""
            UPDATE vr_quotation_links 
            SET {', '.join(updates)}
            WHERE id = %s
        """, values, fetch=False)
    
    return {"success": True, "message": "報價單已更新"}

@app.delete("/api/quotation/item/{item_id}")
async def delete_quotation_item(item_id: int):
    """Delete quotation item"""
    link = query_db(
        "SELECT ql.id FROM vr_quotation_items qi JOIN vr_quotation_links ql ON qi.link_id = ql.id WHERE qi.id = %s",
        (item_id,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="項目不存在")
    
    # Get item price for recalculation
    item = query_db("SELECT total_price, link_id FROM vr_quotation_items WHERE id = %s", (item_id,))
    if not item:
        raise HTTPException(status_code=404, detail="項目不存在")
    
    item_data = item[0]
    link_id = item_data['link_id']
    
    # Delete item
    query_db("DELETE FROM vr_quotation_items WHERE id = %s", (item_id,), fetch=False)
    
    # Recalculate total
    total = query_db("SELECT COALESCE(SUM(total_price), 0) as total FROM vr_quotation_items WHERE link_id = %s", (link_id,))
    if total:
        query_db(
            "UPDATE vr_quotation_links SET total_amount = %s, updated_at = NOW() WHERE id = %s",
            (total[0]['total'], link_id), fetch=False
        )
    
    return {"success": True, "message": "項目已刪除"}

# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/quotation/{link_token}")
async def get_quotation(link_token: str):
    """Get quotation data as JSON"""
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link = link[0]
    items = query_db("""
        SELECT 
            qi.*,
            m.name as material_name,
            m.category,
            m.color_hex,
            m.unit
        FROM vr_quotation_items qi
        JOIN vr_materials m ON qi.material_id = m.id
        WHERE qi.quotation_link_id = %s
    """, (link["id"],))
    
    return {
        "quotation": dict(link),
        "items": [dict(i) for i in items]
    }

@app.get("/api/materials")
async def get_materials(category: Optional[str] = None):
    """Get available materials"""
    if category:
        materials = query_db(
            "SELECT * FROM vr_materials WHERE category = %s AND is_active = TRUE",
            (category,)
        )
    else:
        materials = query_db(
            "SELECT * FROM vr_materials WHERE is_active = TRUE"
        )
    return {"materials": [dict(m) for m in materials]}

@app.post("/api/quotation/{link_token}/update")
async def update_quotation(link_token: str, update: QuotationUpdate):
    """Update quotation items"""
    link = query_db(
        "SELECT id FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link_id = link[0]["id"]
    
    # Clear existing items
    query_db(
        "DELETE FROM vr_quotation_items WHERE quotation_link_id = %s",
        (link_id,),
        fetch=False
    )
    
    # Insert new items
    total = 0
    for item in update.items:
        material = query_db(
            "SELECT unit_price FROM vr_materials WHERE id = %s",
            (item.material_id,)
        )
        if material:
            unit_price = material[0]["unit_price"]
            total_price = unit_price * item.quantity
            total += total_price
            query_db("""
                INSERT INTO vr_quotation_items 
                (quotation_link_id, material_id, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (link_id, item.material_id, item.quantity, unit_price, total_price),
                fetch=False)
    
    # Update total
    query_db(
        "UPDATE vr_quotation_links SET total_amount = %s WHERE id = %s",
        (total, link_id),
        fetch=False
    )
    
    return {"success": True, "total_amount": total}

@app.post("/api/quotation/{link_token}/confirm")
async def confirm_quotation(link_token: str, confirm: QuotationConfirm):
    """Customer confirms quotation — auto-sync to Odoo ERP"""
    link = query_db(
        "SELECT * FROM vr_quotation_links WHERE link_token = %s",
        (link_token,)
    )
    if not link:
        raise HTTPException(status_code=404, detail="報價單不存在")
    
    link_data = link[0]
    link_id = link_data["id"]
    
    # Update status in DB
    query_db("""
        UPDATE vr_quotation_links 
        SET status = 'confirmed', 
            confirmed_at = NOW(),
            customer_name = COALESCE(%s, customer_name),
            customer_phone = COALESCE(%s, customer_phone)
        WHERE id = %s
    """, (confirm.customer_name, confirm.customer_phone, link_id),
        fetch=False)
    
    # Get items for ERP sync
    items = query_db("""
        SELECT 
            qi.area_name,
            qi.quantity,
            qi.unit_price,
            qi.total_price,
            m.name as material_name
        FROM vr_quotation_items qi
        JOIN vr_materials m ON qi.material_id = m.id
        WHERE qi.quotation_link_id = %s
    """, (link_id,))
    
    # Sync to Odoo ERP
    erp_result = sync_to_odoo(
        dict(link_data),
        [dict(i) for i in items]
    )
    
    # Save ERP order ID
    if erp_result['success']:
        query_db("""
            UPDATE vr_quotation_links 
            SET odoo_order_id = %s 
            WHERE id = %s
        """, (erp_result['order_id'], link_id), fetch=False)
    
    return {
        "success": True, 
        "message": "報價單已確認！",
        "erp": erp_result,
        "whatsapp_notify": get_ssyy_whatsapp_link(dict(link_data), erp_result)
    }

# ============================================================
# Admin API — Create new quotation link
# ============================================================

@app.post("/api/quotation/create")
async def create_quotation(request: Request):
    """Create new quotation link (admin)"""
    body = await request.json()
    
    token = str(uuid.uuid4())[:8].upper()
    project_name = body.get("project_name", "未命名項目")
    customer_name = body.get("customer_name", "")
    customer_phone = body.get("customer_phone", "")
    address = body.get("address", "")
    valid_days = body.get("valid_days", 30)
    
    valid_until = (datetime.now() + timedelta(days=valid_days)).date()
    
    query_db("""
        INSERT INTO vr_quotation_links 
        (link_token, project_name, customer_name, customer_phone, address, valid_until)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (token, project_name, customer_name, customer_phone, address, valid_until),
        fetch=False)
    
    return {
        "success": True,
        "link_token": token,
        "url": f"/vr/{token}"
    }

# ============================================================
# Admin API — Material Management CRUD
# ============================================================

@app.get("/materials", response_class=HTMLResponse)
async def materials_page(request: Request):
    """Material management page"""
    materials = query_db("""
        SELECT * FROM vr_materials 
        ORDER BY category, name
    """)
    # Convert datetime/Decimal fields to JSON-safe types
    import json
    from decimal import Decimal
    
    def make_serializable(obj):
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(v) for v in obj]
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj
    
    materials = [make_serializable(dict(m)) for m in materials]
    return templates.TemplateResponse(request, "materials.html", {
        "request": request,
        "materials": materials,
        "page": "materials"
    })

@app.post("/api/materials/create")
async def create_material(request: Request):
    """Create new material"""
    body = await request.json()
    
    required = ['name', 'category', 'unit_price', 'unit']
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"缺少必填欄位: {field}")
    
    result = query_db("""
        INSERT INTO vr_materials (name, category, description, color_hex, unit_price, unit, model_number, brand, spec, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        body['name'],
        body['category'],
        body.get('description', ''),
        body.get('color_hex', '#cccccc'),
        body['unit_price'],
        body['unit'],
        body.get('model_number', ''),
        body.get('brand', ''),
        body.get('spec', ''),
        body.get('is_active', True)
    ))
    
    return {"success": True, "message": "物料已建立", "id": result[0]['id'] if result else None}

@app.put("/api/materials/{material_id}")
async def update_material(material_id: int, request: Request):
    """Update material"""
    body = await request.json()
    
    query_db("""
        UPDATE vr_materials 
        SET name = COALESCE(%s, name),
            category = COALESCE(%s, category),
            description = COALESCE(%s, description),
            color_hex = COALESCE(%s, color_hex),
            unit_price = COALESCE(%s, unit_price),
            unit = COALESCE(%s, unit),
            model_number = COALESCE(%s, model_number),
            brand = COALESCE(%s, brand),
            spec = COALESCE(%s, spec),
            is_active = COALESCE(%s, is_active)
        WHERE id = %s
    """, (
        body.get('name'),
        body.get('category'),
        body.get('description'),
        body.get('color_hex'),
        body.get('unit_price'),
        body.get('unit'),
        body.get('model_number'),
        body.get('brand'),
        body.get('spec'),
        body.get('is_active'),
        material_id
    ), fetch=False)
    
    return {"success": True, "message": "物料已更新"}

@app.delete("/api/materials/{material_id}")
async def delete_material(material_id: int):
    """Soft delete material (set inactive)"""
    query_db("""
        UPDATE vr_materials SET is_active = FALSE WHERE id = %s
    """, (material_id,), fetch=False)
    return {"success": True, "message": "物料已停用"}

@app.post("/api/materials/{material_id}/texture")
async def upload_texture(material_id: int, file: UploadFile = File(...)):
    """Upload texture image for material"""
    import base64
    
    # Read file content
    content = await file.read()
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="只接受 JPEG/PNG/WebP 圖片")
    
    # Convert to base64 data URL
    b64 = base64.b64encode(content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{b64}"
    
    # Update DB
    query_db("""
        UPDATE vr_materials SET texture_url = %s WHERE id = %s
    """, (data_url, material_id), fetch=False)
    
    return {"success": True, "message": "貼圖已上傳"}

@app.delete("/api/materials/{material_id}/texture")
async def delete_texture(material_id: int):
    """Remove texture from material"""
    query_db("""
        UPDATE vr_materials SET texture_url = NULL WHERE id = %s
    """, (material_id,), fetch=False)
    return {"success": True, "message": "貼圖已移除"}

# ============================================================
# WebSocket — Real-time Sync
# ============================================================

@app.websocket("/ws/{link_token}")
async def websocket_endpoint(websocket: WebSocket, link_token: str):
    """WebSocket for real-time quotation sync"""
    await manager.connect(websocket, link_token)
    
    # Send initial viewer count
    await websocket.send_json({
        "type": "viewer_count",
        "count": manager.get_viewer_count(link_token)
    })
    
    # Broadcast updated viewer count
    await manager.broadcast(link_token, {
        "type": "viewer_count",
        "count": manager.get_viewer_count(link_token)
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "material_change":
                # Broadcast material change to all other viewers
                await manager.broadcast(link_token, {
                    "type": "material_change",
                    "category": data.get("category"),
                    "material_id": data.get("material_id"),
                    "color": data.get("color"),
                    "price": data.get("price"),
                    "sender_id": data.get("sender_id")
                }, exclude=websocket)
            
            elif data.get("type") == "quantity_change":
                # Broadcast quantity change
                await manager.broadcast(link_token, {
                    "type": "quantity_change",
                    "item_id": data.get("item_id"),
                    "quantity": data.get("quantity"),
                    "sender_id": data.get("sender_id")
                }, exclude=websocket)
            
            elif data.get("type") == "price_update":
                # Broadcast price update
                await manager.broadcast(link_token, {
                    "type": "price_update",
                    "total": data.get("total"),
                    "sender_id": data.get("sender_id")
                }, exclude=websocket)
            
            elif data.get("type") == "ping":
                # Keepalive
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, link_token)
        # Broadcast updated viewer count
        await manager.broadcast(link_token, {
            "type": "viewer_count",
            "count": manager.get_viewer_count(link_token)
        })


# ============================================================
# Google Sheets Sync
# ============================================================

def get_sheets_client():
    """Get authorized gspread client"""
    import gspread
    from google.oauth2.service_account import Credentials
    key_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY', '')
    if not key_json:
        return None
    creds = Credentials.from_service_account_info(
        json.loads(key_json),
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return gspread.authorize(creds)

@app.post("/api/sync-from-sheets")
async def sync_from_sheets():
    """Sync materials from Google Sheets to PostgreSQL"""
    SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')
    if not SHEET_ID:
        return {"error": "GOOGLE_SHEET_ID not configured"}
    client = get_sheets_client()
    if not client:
        return {"error": "Google Sheets credentials not configured"}
    try:
        ss = client.open_by_key(SHEET_ID)
        ws = ss.worksheet('Materials')
        records = ws.get_all_records()
        conn = get_db()
        synced = 0
        with conn.cursor() as cur:
            for r in records:
                try:
                    sheet_id = r.get('id', '')
                    name = r.get('name', '')
                    if not name or not sheet_id:
                        continue
                    cur.execute("SELECT id FROM vr_materials WHERE id = %s", (int(sheet_id),))
                    exists = cur.fetchone()
                    if exists:
                        cur.execute("""UPDATE vr_materials SET name=%s, category=%s, description=%s,
                            color_hex=%s, unit_price=%s, unit=%s, is_active=%s,
                            texture_url=%s, model_number=%s, brand=%s, spec=%s WHERE id=%s""",
                            (name, r.get('category',''), r.get('description',''),
                             r.get('color_hex',''), float(r.get('unit_price',0)), r.get('unit',''),
                             r.get('is_active','true').lower()=='true', r.get('texture_url',''),
                             r.get('model_number',''), r.get('brand',''), r.get('spec',''), int(sheet_id)))
                    else:
                        cur.execute("""INSERT INTO vr_materials (id,name,category,description,color_hex,
                            unit_price,unit,is_active,texture_url,model_number,brand,spec)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (int(sheet_id), name, r.get('category',''), r.get('description',''),
                             r.get('color_hex',''), float(r.get('unit_price',0)), r.get('unit',''),
                             r.get('is_active','true').lower()=='true', r.get('texture_url',''),
                             r.get('model_number',''), r.get('brand',''), r.get('spec','')))
                    synced += 1
                except: pass
            conn.commit()
        conn.close()
        return {"synced": synced, "total": len(records)}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sync-to-sheets")
async def sync_to_sheets():
    """Sync materials from PostgreSQL to Google Sheets"""
    SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')
    if not SHEET_ID:
        return {"error": "GOOGLE_SHEET_ID not configured"}
    client = get_sheets_client()
    if not client:
        return {"error": "Google Sheets credentials not configured"}
    try:
        materials = query_db("SELECT * FROM vr_materials ORDER BY id")
        ss = client.open_by_key(SHEET_ID)
        ws = ss.worksheet('Materials')
        if ws.row_count > 1:
            ws.delete_rows(2, ws.row_count)
        rows = []
        for m in materials:
            rows.append([str(m.get('id','')), m.get('name',''), m.get('category',''),
                m.get('description',''), m.get('color_hex',''), str(m.get('unit_price',0)),
                m.get('unit',''), 'true' if m.get('is_active') else 'false',
                m.get('texture_url',''), m.get('model_number',''), m.get('brand',''),
                m.get('spec',''), str(m.get('updated_at',''))])
        if rows:
            ws.append_rows(rows)
        return {"synced": len(rows)}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    host = "0.0.0.0" if os.getenv("DATABASE_URL") else "127.0.0.1"
    uvicorn.run(app, host=host, port=port)
