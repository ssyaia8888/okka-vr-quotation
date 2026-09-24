#!/usr/bin/env python3
"""
Setup script: Create Google Sheets database structure for OKKA VR Quotation.

Run this ONCE to set up the spreadsheet:
  python setup_gsheets.py

Requirements:
  pip install gspread google-auth
  
  credentials.json in current directory (Google Service Account)
"""
import gspread
from google.oauth2.service_account import Credentials
import json
import sys

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def setup(credentials_file='credentials.json'):
    # Load credentials
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # Create spreadsheet
    print("[1/4] Creating spreadsheet...")
    ss = client.create('OKKA VR Quotation Database')
    ss.share('ssyaia8888@gmail.com', perm_type='user', role='writer')
    print(f"  Spreadsheet URL: {ss.url}")
    print(f"  Spreadsheet ID:  {ss.id}")
    
    # Tab 1: Materials
    print("[2/4] Creating Materials tab...")
    ws_mat = ss.sheet1
    ws_mat.update_title('Materials')
    ws_mat.append_row([
        'id', 'name', 'category', 'description', 'color_hex',
        'unit_price', 'unit', 'is_active', 'texture_url',
        'model_number', 'brand', 'spec', 'updated_at'
    ])
    # Sample data
    ws_mat.append_row(['1', '仿木紋磚 60x60', 'floor', '東鵬木紋磚', '#c4a882', '180', 'sqm', 'true', '', 'EM6060', '東鵬', '600x600mm', ''])
    ws_mat.append_row(['2', '大理石紋磚 80x80', 'floor', '拋光大理石磚', '#e8dcc8', '280', 'sqm', 'true', '', 'DM8080', '馬可波羅', '800x800mm', ''])
    ws_mat.append_row(['3', '乳膠漆 白色', 'wall', '多樂士白色乳膠漆', '#f5f5f5', '45', 'sqm', 'true', '', 'A991', '多樂士', '5L/桶', ''])
    ws_mat.append_row(['4', '藝術漆 米黃', 'wall', '絲絨質感藝術漆', '#f0e6d3', '120', 'sqm', 'true', '', 'AP03', '立邦', '1L/桶', ''])
    ws_mat.append_row(['5', '石膏板天花', 'ceiling', '9mm石膏板', '#fafafa', '65', 'sqm', 'true', '', 'G9', '泰山', '1200x2400', ''])
    ws_mat.append_row(['6', '衣櫃板材', 'cabinet', '18mm多層實木板', '#d4a574', '350', 'sqm', 'true', '', 'C18', '兔寶寶', '1220x2440mm', ''])
    ws_mat.append_row(['7', 'LED筒燈', 'lighting', '7W嵌入式筒燈', '#fff9e6', '85', 'pc', 'true', '', 'DL7', '歐普', '7W 3000K', ''])
    
    # Tab 2: Customers
    print("[3/4] Creating Customers tab...")
    ws_cust = ss.add_worksheet(title='Customers', rows=100, cols=15)
    ws_cust.append_row([
        'id', 'name', 'phone', 'email', 'address',
        'company', 'notes', 'created_at'
    ])
    ws_cust.append_row(['1', '林先生', '66923843', '', '麗港城22座4樓H室', '裝修工程', '', ''])
    
    # Tab 3: Quotations
    print("[4/4] Creating Quotations tab...")
    ws_quot = ss.add_worksheet(title='Quotations', rows=100, cols=15)
    ws_quot.append_row([
        'id', 'link_token', 'project_name', 'customer_name', 'customer_phone',
        'address', 'total_amount', 'status', 'valid_until', 'viewed_at',
        'created_at', 'updated_at', 'notes', 'odoo_order_id'
    ])
    
    # Tab 4: Quotation Items
    ws_items = ss.add_worksheet(title='QuotationItems', rows=500, cols=15)
    ws_items.append_row([
        'id', 'quotation_id', 'material_id', 'material_name',
        'quantity', 'unit_price', 'total_price', 'area_name', 'notes', 'created_at'
    ])
    
    # Save config
    config = {
        'spreadsheet_id': ss.id,
        'spreadsheet_url': ss.url,
        'service_account_email': creds.service_account_email
    }
    with open('gsheets_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print()
    print("=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print(f"Spreadsheet URL:  {ss.url}")
    print(f"Spreadsheet ID:   {ss.id}")
    print(f"Service Account:  {creds.service_account_email}")
    print()
    print("NEXT STEPS:")
    print(f"1. Open {ss.url}")
    print(f"2. Go to Railway > Service > Variables")
    print(f"3. Add GOOGLE_SHEET_ID = {ss.id}")
    print(f"4. Add GOOGLE_SERVICE_ACCOUNT_KEY = <contents of credentials.json>")
    print()
    print("Config saved to: gsheets_config.json")

if __name__ == '__main__':
    cred_file = sys.argv[1] if len(sys.argv) > 1 else 'credentials.json'
    setup(cred_file)
