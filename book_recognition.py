from google.cloud import vision
from google.oauth2 import service_account
import io
from PIL import Image
from typing import Tuple, List, Dict
import requests
import streamlit as st
import os
import re


# ---------------------------------------------------------------
# Vision API クライアント
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# ISBN 抽出
# ---------------------------------------------------------------
def extract_isbn(text: str) -> str:
    """テキストからISBNを抽出"""
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


# ---------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------
def get_api_key() -> str | None:
    """Google Books APIキーを取得"""
    if 'GOOGLE_BOOKS_API_KEY' in st.secrets:
        return st.secrets['GOOGLE_BOOKS_API_KEY']
    return None


def get_server_ip() -> str | None:
    """
    Streamlit Cloud サーバーのIPを取得する。
    userIp パラメータに渡すことで、Googleが地理位置を特定できるようにする。
    """
    try:
        resp = requests.get("https://api.ipify.org", timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------
# Google Books API（優先）
# ---------------------------------------------------------------
def search_google_books(isbn: str) -> List[Dict]:
    """Google Books APIで書籍を検索"""
    api_key = get_api_key()
    if not api_key:
        st.warning("⚠️ `GOOGLE_BOOKS_API_KEY` が Streamlit Secrets に設定されていません。")
        return []

    url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        'q': f'isbn:{isbn}',
        'maxResults': 1,
        'key': api_key,
    }

    # --- 地理制限対策: サーバーIPを userIp として追加 ---
    server_ip = get_server_ip()
    if server_ip:
        params['userIp'] = server_ip
        st.info(f"📡 サーバーIP ({server_ip}) を userIp として送信中")
    else:
        st.warning("⚠️ サーバーIPの取得に失敗しました")

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            # エラー詳細をログに表示
            try:
                error_detail = response.json().get('error', {}).get('message', '')
            except Exception:
                error_detail = response.text[:200]
            st.warning(f"⚠️ Google Books API エラー ({response.status_code}): {error_detail}")
            return []

        data = response.json()
        books = []
        for item in data.get('items', []):
            vi = item.get('volumeInfo', {})
            books.append({
                'title': vi.get('title', '不明'),
                'authors': vi.get('authors', ['不明']),
                'categories': vi.get('categories', ['未分類']),
                'cover_image': vi.get('imageLinks', {}).get('thumbnail', ''),
                'description': vi.get('description', '説明なし'),
                'average_rating': vi.get('averageRating', 0),
                'published_date': vi.get('publishedDate', '不明'),
                'isbn': isbn,
            })
        return books

    except Exception as e:
        st.warning(f"⚠️ Google Books API 例外: {e}")
        return []


# ---------------------------------------------------------------
# Open Library API（フォールバック）
# ---------------------------------------------------------------
def search_open_library(isbn: str) -> List[Dict]:
    """
    Open Library API で書籍を検索する。
    認証・地理制限なし。Google Books が失敗した場合のフォールバックとして使用。
    """
    try:
        url = f"https://openlibrary.org/api/books.json?bibkeys=ISBN:{isbn}&jscmd=data&format=json"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            st.warning(f"⚠️ Open Library API エラー: {response.status_code}")
            return []

        data = response.json()
        key = f"ISBN:{isbn}"

        if key not in data:
            # データなし→さらにOpen Library のsearch APIで書名検索を試みる
            st.info("📚 Open Library にもISBN直接データがありません。書名検索を試みます...")
            return search_open_library_by_title(isbn)

        book_data = data[key]

        # カバー画像
        cover_image = ""
        cover = book_data.get('cover', {})
        cover_id = cover.get('large') or cover.get('medium') or cover.get('small')
        if cover_id:
            cover_image = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

        # 著者
        authors = [a.get('name', '不明') for a in book_data.get('authors', [])] or ['不明']

        # カテゴリ（subjects）
        categories = book_data.get('subjects', ['未分類'])[:5]

        # 説明文（サブタイトルがあればそれを使う）
        description = book_data.get('subtitle', '') or '説明なし'

        book = {
            'title': book_data.get('title', '不明'),
            'authors': authors,
            'categories': categories,
            'cover_image': cover_image,
            'description': description,
            'average_rating': 0,  # Open Libraryにはratingデータが無い
            'published_date': str(book_data.get('publish_date', '不明')),
            'isbn': isbn,
        }

        st.success("✅ Open Library APIから書籍情報を取得しました")
        return [book]

    except Exception as e:
        st.error(f"❌ Open Library APIエラー: {e}")
        return []


def search_open_library_by_title(isbn: str) -> List[Dict]:
    """Open Library の検索API経由で書名を検索（ISBNが直接マッチしない場合用）"""
    try:
        url = f"https://openlibrary.org/search.json?isbn={isbn}&limit=1"
        response = requests.get(url, timeout=10)

        if response.status_code != 200 or response.json().get('numFound', 0) == 0:
            return []

        doc = response.json()['docs'][0]

        cover_image = ""
        if 'cover_i' in doc:
            cover_image = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"

        book = {
            'title': doc.get('title', '不明'),
            'authors': doc.get('author_name', ['不明']),
            'categories': doc.get('subject', ['未分類'])[:5],
            'cover_image': cover_image,
            'description': '説明なし',
            'average_rating': 0,
            'published_date': str(doc.get('first_publish_year', '不明')),
            'isbn': isbn,
        }

        st.success("✅ Open Library 検索APIから書籍情報を取得しました")
        return [book]

    except Exception as e:
        st.warning(f"⚠️ Open Library 検索エラー: {e}")
        return []


# ---------------------------------------------------------------
# メイン検索エントリポイント
# ---------------------------------------------------------------
def search_by_isbn(isbn: str) -> List[Dict]:
    """
    ISBNで書籍を検索。
    Google Books API を優先し、失敗した場合は Open Library API にフォールバックする。
    """
    # 1. Google Books API を試す
    books = search_google_books(isbn)
    if books:
        st.success("📚 Google Books APIから書籍情報を取得しました")
        return books

    # 2. フォールバック: Open Library API
    st.info("🔄 Open Library APIにフォールバック検索中...")
    return search_open_library(isbn)


# ---------------------------------------------------------------
# 画像から書籍情報を認識
# ---------------------------------------------------------------
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
                return [], (
                    f"ISBNで書籍が見つかりませんでした。\n\n"
                    f"ISBN: {isbn}\n\n"
                    f"抽出テキスト:\n{extracted_text[:200]}..."
                )
        else:
            return [], (
                f"ISBNが検出できませんでした。\n\n"
                f"抽出テキスト:\n{extracted_text[:200]}...\n\n"
                f"💡 ヒント: 裏表紙のISBN（978で始まる13桁の数字）を撮影してください。"
            )

    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"