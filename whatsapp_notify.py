#!/usr/bin/env python3
"""
WhatsApp Notification Helper — Send confirmation alerts to SSY
Uses WhatsApp URL scheme (no API key needed)
"""

import urllib.parse

WHATSAPP_NUMBER = "85266923843"  # SSY WhatsApp

def build_whatsapp_link(phone: str, message: str) -> str:
    """Build WhatsApp click-to-chat link"""
    encoded_msg = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded_msg}"

def build_confirmation_message(quotation_data: dict, erp_result: dict) -> str:
    """Build confirmation message for SSY"""
    msg = f"""🔔 *新報價單已確認！*

📋 *項目*: {quotation_data.get('project_name', '-')}
👤 *客戶*: {quotation_data.get('customer_name', '-')}
📱 *電話*: {quotation_data.get('customer_phone', '-')}
📍 *地址*: {quotation_data.get('address', '-')}
💰 *金額*: ${quotation_data.get('total_amount', 0):,.0f}
🔗 *Token*: {quotation_data.get('link_token', '-')}
⏰ *確認時間*: {quotation_data.get('confirmed_at', '-')}

"""
    
    if erp_result.get('success'):
        msg += f"""✅ *ERP 已同步*
📝 訂單: {erp_result.get('message', '-')}
"""
    else:
        msg += f"""❌ *ERP 同步失敗*
⚠️ 錯誤: {erp_result.get('error', '-')}
"""
    
    msg += f"\n🔗 查看報價單: http://127.0.0.1:8080/vr/{quotation_data.get('link_token', '')}"
    
    return msg

def get_ssyy_whatsapp_link(quotation_data: dict, erp_result: dict) -> str:
    """Get WhatsApp link to notify SSY"""
    message = build_confirmation_message(quotation_data, erp_result)
    return build_whatsapp_link(WHATSAPP_NUMBER, message)

if __name__ == "__main__":
    # Test
    test_data = {
        'project_name': '李先生單位裝修',
        'customer_name': '李先生',
        'customer_phone': '98765432',
        'address': '九龍灣MegaBox附近',
        'total_amount': 10250,
        'link_token': '4B94A5E5',
        'confirmed_at': '2026-09-23 12:00:00'
    }
    
    test_erp = {
        'success': True,
        'message': '已建立並確認銷售訂單 SO00047'
    }
    
    print("=== WhatsApp Message ===")
    print(build_confirmation_message(test_data, test_erp))
    print("\n=== WhatsApp Link ===")
    print(get_ssyy_whatsapp_link(test_data, test_erp))
