#!/usr/bin/env python3
"""
Export data from local PostgreSQL to SQL file for Railway import
"""

import psycopg2
import psycopg2.extras
import json
from datetime import datetime

# Local database config
LOCAL_DB = {
    "host": "172.20.0.2",
    "port": 5432,
    "database": "genius",
    "user": "genius_user",
    "password": "sa1234567890"
}

def export_data():
    """Export VR quotation tables to SQL"""
    conn = psycopg2.connect(**LOCAL_DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    sql_lines = []
    sql_lines.append("-- Genius VR Quotation Data Export")
    sql_lines.append(f"-- Generated: {datetime.now().isoformat()}")
    sql_lines.append("-- For Railway deployment import")
    sql_lines.append("")
    sql_lines.append("BEGIN;")
    sql_lines.append("")
    
    # Export vr_materials
    print("Exporting vr_materials...")
    cur.execute("SELECT * FROM vr_materials ORDER BY id")
    materials = cur.fetchall()
    
    sql_lines.append("-- VR Materials")
    sql_lines.append("DELETE FROM vr_materials;")
    for mat in materials:
        values = (
            mat['id'],
            mat['name'],
            mat['category'],
            mat['color_hex'],
            mat['unit_price'],
            mat['unit'],
            mat['is_active']
        )
        sql_lines.append(
            f"INSERT INTO vr_materials (id, name, category, color_hex, unit_price, unit, is_active) "
            f"VALUES ({values[0]}, '{values[1]}', '{values[2]}', '{values[3]}', {values[4]}, '{values[5]}', {values[6]});"
        )
    sql_lines.append("")
    
    # Export vr_quotation_links
    print("Exporting vr_quotation_links...")
    cur.execute("SELECT * FROM vr_quotation_links ORDER BY id")
    links = cur.fetchall()
    
    sql_lines.append("-- VR Quotation Links")
    sql_lines.append("DELETE FROM vr_quotation_links;")
    for link in links:
        values = (
            link['id'],
            link['link_token'],
            link['project_name'],
            link['customer_name'],
            link['customer_phone'],
            link['customer_address'],
            link['total_amount'],
            link['status'],
            link['valid_until'].isoformat() if link['valid_until'] else 'NULL',
            link['odoo_order_id']
        )
        valid_until_str = 'NULL' if values[8] == 'NULL' else "'" + values[8] + "'"
        odoo_order_str = 'NULL' if values[9] is None else str(values[9])
        sql_lines.append(
            f"INSERT INTO vr_quotation_links (id, link_token, project_name, customer_name, customer_phone, "
            f"customer_address, total_amount, status, valid_until, odoo_order_id) "
            f"VALUES ({values[0]}, '{values[1]}', '{values[2]}', '{values[3]}', '{values[4]}', "
            f"'{values[5]}', {values[6]}, '{values[7]}', {valid_until_str}, {odoo_order_str});"
        )
    sql_lines.append("")
    
    # Export vr_quotation_items
    print("Exporting vr_quotation_items...")
    cur.execute("SELECT * FROM vr_quotation_items ORDER BY id")
    items = cur.fetchall()
    
    sql_lines.append("-- VR Quotation Items")
    sql_lines.append("DELETE FROM vr_quotation_items;")
    for item in items:
        values = (
            item['id'],
            item['link_id'],
            item['material_id'],
            item['quantity'],
            item['unit_price'],
            item['area_name']
        )
        sql_lines.append(
            f"INSERT INTO vr_quotation_items (id, link_id, material_id, quantity, unit_price, area_name) "
            f"VALUES ({values[0]}, {values[1]}, {values[2]}, {values[3]}, {values[4]}, '{values[5]}');"
        )
    sql_lines.append("")
    
    sql_lines.append("COMMIT;")
    
    # Write to file
    output_file = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    with open(output_file, 'w') as f:
        f.write('\n'.join(sql_lines))
    
    print(f"Exported to {output_file}")
    print(f"  - {len(materials)} materials")
    print(f"  - {len(links)} quotation links")
    print(f"  - {len(items)} quotation items")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    export_data()
