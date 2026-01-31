from google.cloud import vision
from google.oauth2 import service_account
import io
from PIL import Image
from typing import Tuple, List, Dict
import requests
import streamlit as st
import os
import re

def get_vision_client():
    """Vision APIクライアントを取得"""
    try:
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return vision.ImageAnnotatorClient(credentials=credentials)
        elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            return vision.ImageAnnotatorClient()
        else:
            raise Exception("Google Cloud認証情報が設定されていません")
    except Exception as e:
        raise Exception(f"Vision APIクライアントの初期化に失敗: {str(e)}")

def extract_isbn(text: str) -> str:
    """テキストからISBNを抽出"""
    # ISBN-13 (978 or 979で始まる13桁)
    # より厳密なパターン
    patterns = [
        r'ISBN[\s:-]*97[89][\d\-\s]{10,}',  # ISBN: 978...
        r'97[89][\d\-\s]{10,}',  # 978...
        r'ISBN[\s:-]*[\d\-\s]{13,}',  # ISBN: 数字13桁
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # 最初のマッチから数字のみを抽出
            isbn = ''.join(filter(str.isdigit, matches[0]))
            # 13桁のISBNを探す
            if len(isbn) >= 13:
                isbn = isbn[:13]
                if isbn.startswith('978') or isbn.startswith('979'):
                    return isbn
    
    return None

def get_api_key():
    """Google Books APIキーを取得"""
    if 'GOOGLE_BOOKS_API_KEY' in st.secrets:
        key = st.secrets['GOOGLE_BOOKS_API_KEY']
        st.info(f"🔑 APIキー取得成功: {key[:10]}...")
        return key
    else:
        st.warning("⚠️ APIキーが設定されていません")
        return None

def search_by_isbn(isbn: str) -> List[Dict]:
    """ISBNで書籍を検索"""
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            'q': f'isbn:{isbn}',
            'maxResults': 1
        }
        
        api_key = get_api_key()
        if api_key:
            params['key'] = api_key
        
        st.info(f"🔍 検索URL: {url}")
        st.info(f"📋 検索パラメータ: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        
        st.info(f"📡 レスポンスステータス: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        st.info(f"📊 検索結果: {data.get('totalItems', 0)}件")
        
        books = []
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            
            book = {
                'title': volume_info.get('title', '不明'),
                'authors': volume_info.get('authors', ['不明']),
                'categories': volume_info.get('categories', ['未分類']),
                'cover_image': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                'description': volume_info.get('description', '説明なし'),
                'average_rating': volume_info.get('averageRating', 0),
                'published_date': volume_info.get('publishedDate', '不明'),
                'isbn': isbn
            }
            books.append(book)
        
        return books
        
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ HTTPエラー: {e.response.status_code}")
        st.error(f"レスポンス: {e.response.text}")
        return []
    except Exception as e:
        st.error(f"❌ エラー: {str(e)}")
        return []

def recognize_book_from_image(image: Image.Image) -> Tuple[List[Dict], str]:
    """画像から書籍情報を認識"""
    try:
        client = get_vision_client()
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        vision_image = vision.Image(content=img_byte_arr)
        response = client.text_detection(image=vision_image)
        
        if response.error.message:
            raise Exception(f'Vision API Error: {response.error.message}')
        
        texts = response.text_annotations
        
        if not texts:
            return [], "画像からテキストを検出できませんでした"
        
        extracted_text = texts[0].description
        
        # ISBNを抽出
        isbn = extract_isbn(extracted_text)
        
        if isbn:
            st.success(f"📚 ISBN検出: {isbn}")
            books = search_by_isbn(isbn)
            
            if books:
                return books, f"ISBN: {isbn}\n\n{extracted_text}"
            else:
                return [], f"ISBNで書籍が見つかりませんでした。\n\nISBN: {isbn}\n\n抽出テキスト:\n{extracted_text[:200]}..."
        else:
            return [], f"ISBNが検出できませんでした。\n\n抽出テキスト:\n{extracted_text[:200]}...\n\n💡 ヒント: 裏表紙のISBN（978で始まる13桁の数字）を撮影してください。"
            
    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"
