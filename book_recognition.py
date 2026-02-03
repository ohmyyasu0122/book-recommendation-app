from google.cloud import vision
from google.oauth2 import service_account
import io
from PIL import Image
from typing import Tuple, List, Dict
import requests
import streamlit as st
import os
import re

# 楽天ブックスジャンルコード→名前マッピング
RAKUTEN_GENRE_MAP = {
    '001004008': '日本の小説',
    '001004009': '外国の小説',
    '001004001': 'ミステリー・サスペンス',
    '001004002': 'SF・ホラー',
    '001004003': 'エッセイ',
    '001004004': 'ノンフィクション',
    '001004016': 'ロマンス',
    '001004015': 'その他',
    '001017005': '少年',
    '001017006': '少女',
    '001019001': '小説・エッセイ',
    '001019002': '美容・暮らし・健康・料理',
    '001019003': 'ホビー・スポーツ・美術',
    '001019005': '語学・学習参考書',
    '001019006': '旅行・留学・アウトドア',
    '001019007': '人文・思想・社会',
    '001019008': 'ビジネス・経済・就職',
    '001019009': 'パソコン・システム開発',
    '001019010': '科学・医学・技術',
    '001019011': '漫画（コミック）',
    '001019012': 'ライトノベル',
    '001019013': 'エンタメ',
    '001019014': '写真集・タレント',
    '001020001': '小説・エッセイ',
    '001020002': '美容・暮らし・健康・料理',
    '001020003': 'ホビー・スポーツ・美術',
    '001020004': '絵本・児童書・図鑑',
    '001020007': '人文・思想・社会',
    '001020008': 'ビジネス・経済・就職',
    '001020010': '科学・医学・技術',
    '001020011': 'エンタメ',
    '001010001': '恋愛',
    '001010002': '妊娠・出産・子育て',
    '001010003': 'ペット',
    '001010010': '健康',
    '001010011': '料理',
    '001010013': '生き方・リラクゼーション',
    '001010014': 'ファッション・美容',
    '001021001': '小説',
    '001021002': 'コミック',
    '001029001': '小説',
    '001029002': 'コミック',
}

def resolve_genre_name(books_genre_id: str) -> str:
    if not books_genre_id:
        return '未分類'
    codes = books_genre_id.split('/')
    specific = []  # 001004xxx（小説サブカテゴリ）
    general = []   # その他カテゴリ
    for code in codes:
        matched = None
        if code in RAKUTEN_GENRE_MAP:
            matched = RAKUTEN_GENRE_MAP[code]
        elif len(code) > 9:
            prefix = code[:9]
            if prefix in RAKUTEN_GENRE_MAP:
                matched = RAKUTEN_GENRE_MAP[prefix]
        if matched:
            if code.startswith('001004') and matched not in specific:
                specific.append(matched)
            elif not code.startswith('001004') and matched not in general:
                general.append(matched)
    # 小説サブカテゴリを優先
    if specific:
        return specific[0]
    if general:
        return general[0]
    return 'その他'

def get_vision_client():
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
    patterns = [
        r'ISBN[\s:-]*97[89][\d\-\s]{10,}',
        r'97[89][\d\-\s]{10,}',
        r'ISBN[\s:-]*[\d\-\s]{13,}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            isbn = ''.join(filter(str.isdigit, matches[0]))
            if len(isbn) >= 13:
                isbn = isbn[:13]
                if isbn.startswith('978') or isbn.startswith('979'):
                    return isbn
    return None

def get_rakuten_app_id():
    if 'RAKUTEN_APP_ID' in st.secrets:
        return st.secrets['RAKUTEN_APP_ID']
    return None

def search_rakuten_books(isbn: str) -> List[Dict]:
    app_id = st.secrets.get('RAKUTEN_APP_ID', '')
    if not app_id:
        st.warning("⚠️ RAKUTEN_APP_ID が設定されていません")
        return []
    try:
        url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        params = {
            'applicationId': app_id,
            'isbn': isbn,
            'format': 'json',
            'hits': 1,
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.warning(f"⚠️ 楽天書籍API エラー ({response.status_code}): {response.text[:200]}")
            return []
        data = response.json()
        books = []
        for book_item in data.get('Items', []):
            item = book_item.get('Item', {})
            books.append({
                'title': item.get('title', '不明'),
                'authors': [item.get('author', '不明')],
                'categories': [resolve_genre_name(item.get('booksGenreId', ''))],
                'cover_image': item.get('mediumImageUrl', ''),
                'description': item.get('itemCaption', '') or '説明なし',
                'average_rating': item.get('reviewAverage', 0),
                'published_date': item.get('salesDate', '不明'),
                'isbn': isbn,
            })
        if books:
            st.success("📚 楽天書籍APIから書籍情報を取得しました")
        else:
            st.warning("⚠️ この書籍は楽天書籍に収録されていません")
        return books
    except Exception as e:
        st.error(f"❌ 楽天書籍API エラー: {e}")
        return []

def search_by_isbn(isbn: str) -> List[Dict]:
    return search_rakuten_books(isbn)

def recognize_book_from_image(image: Image.Image) -> Tuple[List[Dict], str]:
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
