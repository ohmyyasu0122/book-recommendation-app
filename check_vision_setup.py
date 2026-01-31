#!/usr/bin/env python3
"""Google Cloud Vision APIのセットアップを確認"""

import os
import sys

def check_setup():
    print("=" * 50)
    print("Google Cloud Vision API セットアップ確認")
    print("=" * 50)
    
    # 1. 環境変数の確認
    credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not credentials_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS が設定されていません")
        return False
    
    print(f"✅ GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    
    # 2. 認証ファイルの存在確認
    if not os.path.exists(credentials_path):
        print(f"❌ 認証ファイルが見つかりません: {credentials_path}")
        return False
    
    print(f"✅ 認証ファイルが存在します")
    
    # 3. google-cloud-visionのインポート確認
    try:
        from google.cloud import vision
        print("✅ google-cloud-vision がインストールされています")
    except ImportError:
        print("❌ google-cloud-vision がインストールされていません")
        return False
    
    # 4. APIの動作確認
    try:
        client = vision.ImageAnnotatorClient()
        print("✅ Vision APIクライアントの初期化に成功しました")
        
        # 簡単なテスト
        from PIL import Image
        import io
        
        # 小さなテスト画像を作成
        test_image = Image.new('RGB', (100, 100), color='white')
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        vision_image = vision.Image(content=img_byte_arr)
        response = client.text_detection(image=vision_image)
        
        print("✅ Vision API接続テスト成功")
        
    except Exception as e:
        print(f"❌ Vision API接続エラー: {str(e)}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ すべてのチェックが完了しました！")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = check_setup()
    sys.exit(0 if success else 1)
