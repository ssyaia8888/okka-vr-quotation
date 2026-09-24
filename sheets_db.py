#!/usr/bin/env python3
"""
Google Sheets Database Layer for OKKA VR Quotation System

Architecture:
- Google Sheets = Master database (materials, customers, quotations)
- Railway = Customer-facing read-only views
- Local = Admin/editing interface
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ============================================================
# Google Sheets Config
# ============================================================
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet names (tabs in the spreadsheet)
SHEETS = {
    'materials': 'Materials',
    'customers': 'Customers',
    'quotations': 'Quotations',
    'quotation_items': 'QuotationItems'
}

class SheetsDB:
    """Google Sheets database wrapper"""
    
    def __init__(self, spreadsheet_id: str, credentials_json: str = None):
        self.spreadsheet_id = spreadsheet_id
        self._client = None
        self._spreadsheet = None
        self._credentials_json = credentials_json
        
    def _get_client(self) -> gspread.Client:
        """Get authenticated Google Sheets client"""
        if self._client is None:
            if self._credentials_json:
                # From string (Railway env var)
                creds_dict = json.loads(self._credentials_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                # From file (local development)
                creds = Credentials.from_service_account_file(
                    os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', 'credentials.json'),
                    scopes=SCOPES
                )
            self._client = gspread.authorize(creds)
        return self._client
    
    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """Get spreadsheet handle"""
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet
    
    def _get_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Get worksheet by name"""
        spreadsheet = self._get_spreadsheet()
        try:
            return spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # Create sheet if not exists
            return spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    def _rows_to_dicts(self, worksheet: gspread.Worksheet) -> List[Dict]:
        """Convert worksheet rows to list of dicts"""
        all_values = worksheet.get_all_values()
        if len(all_values) < 2:
            return []
        
        headers = [h.strip() for h in all_values[0]]
        rows = []
        for row in all_values[1:]:
            if any(row):  # Skip empty rows
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        row_dict[header] = row[i]
                    else:
                        row_dict[header] = ''
                rows.append(row_dict)
        return rows
    
    def _find_row(self, worksheet: gspread.Worksheet, id_value: str) -> int:
        """Find row number by ID column (1-indexed for gspread)"""
        all_values = worksheet.get_all_values()
        if not all_values:
            return -1
        
        # Assume first column is ID
        for i, row in enumerate(all_values[1:], start=2):
            if row and row[0] == id_value:
                return i
        return -1
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        import uuid
        return str(uuid.uuid4())[:8].upper()
    
    # ============================================================
    # Materials CRUD
    # ============================================================
    
    def get_materials(self) -> List[Dict]:
        """Get all materials"""
        ws = self._get_worksheet(SHEETS['materials'])
        materials = self._rows_to_dicts(ws)
        
        # Convert types
        for m in materials:
            try:
                m['id'] = int(m.get('id', 0))
            except:
                m['id'] = 0
            try:
                m['unit_price'] = float(m.get('unit_price', 0))
            except:
                m['unit_price'] = 0
            m['is_active'] = m.get('is_active', 'true').lower() == 'true'
        
        return materials
    
    def get_material(self, material_id: int) -> Optional[Dict]:
        """Get single material by ID"""
        materials = self.get_materials()
        for m in materials:
            if m['id'] == material_id:
                return m
        return None
    
    def create_material(self, data: Dict) -> Dict:
        """Create new material"""
        ws = self._get_worksheet(SHEETS['materials'])
        
        # Get next ID
        materials = self.get_materials()
        next_id = max([m['id'] for m in materials], default=0) + 1
        
        row = [
            str(next_id),
            data.get('name', ''),
            data.get('category', ''),
            data.get('description', ''),
            data.get('color_hex', '#cccccc'),
            data.get('unit_price', 0),
            data.get('unit', 'sqm'),
            data.get('is_active', 'true'),
            data.get('texture_url', ''),
            data.get('model_number', ''),
            data.get('brand', ''),
            data.get('spec', ''),
            datetime.now().isoformat()
        ]
        
        ws.append_row(row)
        return {'id': next_id, 'success': True}
    
    def update_material(self, material_id: int, data: Dict) -> bool:
        """Update existing material"""
        ws = self._get_worksheet(SHEETS['materials'])
        row_num = self._find_row(ws, str(material_id))
        
        if row_num == -1:
            return False
        
        # Get current row
        current = ws.row_values(row_num)
        
        # Update fields
        headers = ['id', 'name', 'category', 'description', 'color_hex', 
                   'unit_price', 'unit', 'is_active', 'texture_url',
                   'model_number', 'brand', 'spec', 'updated_at']
        
        for i, header in enumerate(headers):
            if header in data and i < len(current):
                current[i] = str(data[header])
        
        # Update timestamp
        current[-1] = datetime.now().isoformat()
        
        # Pad if needed
        while len(current) < len(headers):
            current.append('')
        
        ws.update_row(row_num, current[:len(headers)])
        return True
    
    def delete_material(self, material_id: int) -> bool:
        """Soft delete material (set inactive)"""
        return self.update_material(material_id, {'is_active': 'false'})
    
    # ============================================================
    # Quotations CRUD
    # ============================================================
    
    def get_quotations(self) -> List[Dict]:
        """Get all quotations"""
        ws = self._get_worksheet(SHEETS['quotations'])
        quotations = self._rows_to_dicts(ws)
        
        for q in quotations:
            try:
                q['id'] = int(q.get('id', 0))
            except:
                q['id'] = 0
            try:
                q['total_amount'] = float(q.get('total_amount', 0))
            except:
                q['total_amount'] = 0
        
        return quotations
    
    def get_quotation_by_token(self, token: str) -> Optional[Dict]:
        """Get quotation by link token"""
        quotations = self.get_quotations()
        for q in quotations:
            if q.get('link_token') == token:
                return q
        return None
    
    def get_quotation_items(self, quotation_id: int) -> List[Dict]:
        """Get items for a quotation"""
        ws = self._get_worksheet(SHEETS['quotation_items'])
        all_items = self._rows_to_dicts(ws)
        
        items = []
        for item in all_items:
            try:
                if int(item.get('quotation_id', 0)) == quotation_id:
                    try:
                        item['unit_price'] = float(item.get('unit_price', 0))
                    except:
                        item['unit_price'] = 0
                    try:
                        item['quantity'] = float(item.get('quantity', 0))
                    except:
                        item['quantity'] = 0
                    try:
                        item['total_price'] = float(item.get('total_price', 0))
                    except:
                        item['total_price'] = 0
                    items.append(item)
            except:
                pass
        
        return items
    
    def create_quotation(self, data: Dict) -> Dict:
        """Create new quotation"""
        ws = self._get_worksheet(SHEETS['quotations'])
        
        quotations = self.get_quotations()
        next_id = max([q['id'] for q in quotations], default=0) + 1
        
        token = self._generate_id()
        valid_until = (datetime.now() + timedelta(days=data.get('valid_days', 30))).strftime('%Y-%m-%d')
        
        row = [
            str(next_id),
            token,
            data.get('project_name', '未命名項目'),
            data.get('customer_name', ''),
            data.get('customer_phone', ''),
            data.get('address', ''),
            data.get('total_amount', 0),
            'pending',
            valid_until,
            '',
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            data.get('notes', ''),
            data.get('odoo_order_id', '')
        ]
        
        ws.append_row(row)
        return {'id': next_id, 'link_token': token, 'success': True}
    
    def update_quotation(self, quotation_id: int, data: Dict) -> bool:
        """Update quotation"""
        ws = self._get_worksheet(SHEETS['quotations'])
        row_num = self._find_row(ws, str(quotation_id))
        
        if row_num == -1:
            return False
        
        current = ws.row_values(row_num)
        headers = ['id', 'link_token', 'project_name', 'customer_name', 'customer_phone',
                   'address', 'total_amount', 'status', 'valid_until', 'viewed_at',
                   'created_at', 'updated_at', 'notes', 'odoo_order_id']
        
        for i, header in enumerate(headers):
            if header in data and i < len(current):
                current[i] = str(data[header])
        
        current[headers.index('updated_at')] = datetime.now().isoformat()
        
        while len(current) < len(headers):
            current.append('')
        
        ws.update_row(row_num, current[:len(headers)])
        return True
    
    def update_quotation_viewed(self, quotation_id: int) -> bool:
        """Mark quotation as viewed"""
        return self.update_quotation(quotation_id, {
            'viewed_at': datetime.now().isoformat()
        })
    
    def add_quotation_item(self, quotation_id: int, data: Dict) -> bool:
        """Add item to quotation"""
        ws = self._get_worksheet(SHEETS['quotation_items'])
        
        all_items = self._rows_to_dicts(ws)
        next_id = max([int(i.get('id', 0)) for i in all_items], default=0) + 1
        
        row = [
            str(next_id),
            str(quotation_id),
            str(data.get('material_id', '')),
            data.get('material_name', ''),
            data.get('quantity', 0),
            data.get('unit_price', 0),
            data.get('total_price', 0),
            data.get('area_name', ''),
            data.get('notes', ''),
            datetime.now().isoformat()
        ]
        
        ws.append_row(row)
        return True

# ============================================================
# Global DB instance (lazy init)
# ============================================================
_db: Optional[SheetsDB] = None

def get_db() -> SheetsDB:
    """Get or create database instance"""
    global _db
    if _db is None:
        spreadsheet_id = os.getenv('GOOGLE_SHEET_ID', '')
        credentials_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', '')
        
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEET_ID environment variable not set")
        
        _db = SheetsDB(spreadsheet_id, credentials_json if credentials_json else None)
    return _db
