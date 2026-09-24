#!/usr/bin/env python3
"""Initialize VR Quotation tables on Railway PostgreSQL"""
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    exit(1)

print(f"Connecting to: {DATABASE_URL[:30]}...")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
conn.autocommit = True
cur = conn.cursor()

# Create VR materials table
cur.execute("""
CREATE TABLE IF NOT EXISTS vr_materials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    color_hex VARCHAR(7) DEFAULT '#808080',
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit VARCHAR(20) DEFAULT 'sqm',
    texture_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
)
""")
print("✅ vr_materials table created")

# Create VR quotation links table
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
print("✅ vr_quotation_links table created")

# Create VR quotation items table
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
print("✅ vr_quotation_items table created")

# Insert sample materials
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
            "INSERT INTO vr_materials (name, category, color_hex, unit_price, unit) VALUES (%s, %s, %s, %s, %s)",
            m
        )
    print(f"✅ Inserted {len(materials)} sample materials")
else:
    print(f"ℹ️  Already {count} materials, skipping insert")

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
    
    # Insert 15 sample items
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
    print(f"✅ Sample quotation A363FC09 created with {len(items)} items")
else:
    print("ℹ️  Quotation A363FC09 already exists, skipping")

conn.close()
print("\n🎉 Database initialization complete!")
