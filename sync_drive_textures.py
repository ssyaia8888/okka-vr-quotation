#!/usr/bin/env python3
"""
Google Drive → VR Material Texture Sync
=======================================
Syncs JPEG/PNG texture images from Google Drive folder to VR materials DB.

Usage:
    python sync_drive_textures.py [--dry-run]

Environment variables:
    GOOGLE_SERVICE_ACCOUNT_KEY  - Service account JSON (base64 or raw JSON)
    GOOGLE_DRIVE_FOLDER_ID      - Drive folder ID containing texture images
    DATABASE_URL                - PostgreSQL connection string (Railway)
    # or local DB:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import os
import sys
import json
import base64
import logging
import argparse
from datetime import datetime
from typing import Optional

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Allowed image types
ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
EXT_TO_MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
}


def get_drive_service():
    """Build Google Drive API service from service account key."""
    key_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY', '')
    if not key_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_KEY not set")
    
    # Handle base64-encoded JSON
    try:
        if key_json.startswith('{'):
            creds_dict = json.loads(key_json)
        else:
            creds_dict = json.loads(base64.b64decode(key_json).decode('utf-8'))
    except Exception:
        creds_dict = json.loads(key_json)
    
    scopes = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
    ]
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build('drive', 'v3', credentials=creds)


def get_db_connection():
    """Get PostgreSQL connection (Railway or local)."""
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url, sslmode='require')
    
    # Local Docker DB
    host = os.environ.get('DB_HOST', '172.20.0.3')
    port = os.environ.get('DB_PORT', '5432')
    name = os.environ.get('DB_NAME', 'genius')
    user = os.environ.get('DB_USER', 'genius_user')
    password = os.environ.get('DB_PASSWORD', 'sa1234567890')
    return psycopg2.connect(host=host, port=port, database=name, user=user, password=password)


def list_drive_files(service, folder_id: str) -> list:
    """List all files in a Drive folder (recursive)."""
    files = []
    page_token = None
    
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime, size)",
            pageSize=100,
            pageToken=page_token,
            spaces='drive'
        ).execute()
        
        for f in response.get('files', []):
            files.append(f)
        
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    
    return files


def download_file(service, file_id: str) -> Optional[bytes]:
    """Download a file from Drive, returns bytes or None."""
    request = service.files().get_media(fileId=file_id)
    chunk = io.BytesIO()
    while True:
        data = request.next_chunk()
        chunk.write(data.get_data())
        if data is None:
            break
    return chunk.getvalue()


def file_to_data_url(content: bytes, mime_type: str) -> str:
    """Convert file content to base64 data URL."""
    b64 = base64.b64encode(content).decode('utf-8')
    return f"data:{mime_type};base64,{b64}"


def parse_material_name(filename: str) -> Optional[str]:
    """
    Parse material name from filename.
    Expected format: {material_id}_{category}_{name}.jpg
    Example: 1_floor_拋光石英磚.jpg
    """
    # Try format: {id}_{category}_{name}.ext
    parts = filename.rsplit('.', 1)
    if len(parts) != 2:
        return None
    name_without_ext = parts[0]
    
    # Try to parse as id_category_name
    segments = name_without_ext.split('_', 2)
    if len(segments) >= 2 and segments[0].isdigit():
        return name_without_ext
    return None


def sync_materials(dry_run: bool = False) -> dict:
    """Main sync function: Drive → DB."""
    folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
    if not folder_id:
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID not set")
    
    logger.info(f"Connecting to Google Drive, folder: {folder_id}")
    service = get_drive_service()
    
    logger.info(f"Connecting to database...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current materials from DB
    cur.execute("SELECT id, name, category, texture_url FROM vr_materials")
    db_materials = {row[0]: {'name': row[1], 'category': row[2], 'texture_url': row[3]} for row in cur.fetchall()}
    logger.info(f"Found {len(db_materials)} materials in DB")
    
    # List Drive files
    logger.info(f"Listing files in Drive folder...")
    drive_files = list_drive_files(service, folder_id)
    logger.info(f"Found {len(drive_files)} files in Drive")
    
    results = {
        'scanned': len(drive_files),
        'matched': 0,
        'updated': 0,
        'added': 0,
        'skipped': 0,
        'errors': [],
        'details': []
    }
    
    for f in drive_files:
        name = f['name']
        mime = f.get('mimeType', '')
        file_id = f['id']
        
        # Check if it's an image
        if mime not in ALLOWED_TYPES:
            # Try to detect from extension
            ext = os.path.splitext(name)[1].lower()
            if ext in EXT_TO_MIME:
                mime = EXT_TO_MIME[ext]
            else:
                results['skipped'] += 1
                continue
        
        # Parse material reference from filename
        # Expected: {material_id}_{name}.jpg or {material_id}.jpg
        base = os.path.splitext(name)[0]
        
        # Try to extract material ID (first numeric segment)
        mat_id = None
        for part in base.split('_'):
            if part.isdigit():
                mat_id = int(part)
                break
        
        if mat_id is None:
            logger.warning(f"  SKIP: {name} - no material ID found in filename")
            results['skipped'] += 1
            continue
        
        if mat_id not in db_materials:
            logger.warning(f"  SKIP: {name} - material ID {mat_id} not in DB")
            results['skipped'] += 1
            continue
        
        mat = db_materials[mat_id]
        results['matched'] += 1
        
        # Check if texture already exists and is the same
        old_url = mat['texture_url'] or ''
        
        if dry_run:
            logger.info(f"  DRY-RUN: {name} → material {mat_id} ({mat['name']})")
            results['updated'] += 1
            continue
        
        # Download and convert
        try:
            logger.info(f"  Download: {name} → material {mat_id} ({mat['name']})")
            content = download_file(service, file_id)
            if content is None or len(content) == 0:
                raise RuntimeError("Empty file")
            
            data_url = file_to_data_url(content, mime)
            
            # Update DB
            cur.execute(
                "UPDATE vr_materials SET texture_url = %s, updated_at = NOW() WHERE id = %s",
                (data_url, mat_id)
            )
            results['updated'] += 1
            results['details'].append(f"  ✓ {name} → {mat['name']} ({len(content)//1024}KB)")
            
        except Exception as e:
            logger.error(f"  ERROR: {name} - {e}")
            results['errors'].append(f"{name}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"\n=== Sync Complete ===")
    logger.info(f"  Scanned:  {results['scanned']}")
    logger.info(f"  Matched:  {results['matched']}")
    logger.info(f"  Updated:  {results['updated']}")
    logger.info(f"  Skipped:  {results['skipped']}")
    logger.info(f"  Errors:   {len(results['errors'])}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Sync Google Drive textures to VR materials')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    args = parser.parse_args()
    
    try:
        results = sync_materials(dry_run=args.dry_run)
        if args.dry_run:
            logger.info("  (dry run - no changes made)")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
