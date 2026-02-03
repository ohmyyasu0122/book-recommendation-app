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


def extract_title_from_ocr(text: str) -> str | None:
    """
    OCR抽出テキストから書名の候補を取り出す。
    ISBN行や価格行・数字だけの行を除いて、最も長い行を書名候補とする。
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    skip_patterns = [
        r'^ISBN',
        r'^97[89]',
        r'¥\d+',
        r'^\d+$',
        r'^c\d+',
    ]

    candidates = []
    for line in lines:
        if any(re.search(p, line) for p in skip_patterns):
            continue
        if len(line) >= 2:
            candidates.append(line)

    if not candidates:
        return None

    # 最も長い行を書名候補とする
    return max(candidates, key=len)


# ---------------------------------------------------------------
# Google Books API
# ---------------------------------------------------------------
def search_google_books(query: str, is_isbn: bool = True) -> List[Dict]:
    """
    Google Books APIで検索。
    1回目: APIキー付きで試行。
    2回目: 403になった場合はキーなしで再試行。
           Streamlit Cloud は GCP 上で動くため、キー付きリクエストに
           地理制限が発動する。キーなしだと制限なしで動く。
           無認証の制限は100件/日なので、個人利用で十分。
    """
    api_key = get_api_key()
    q_param = f'isbn:{query}' if is_isbn else query

    attempts = [
        {"label": "APIキー付き", "use_key": True},
        {"label": "APIキーなし（GCP地理制限回避）", "use_key": False},
    ]

    for attempt in attempts:
        params = {
            'q': q_param,
            'maxResults': 1 if is_isbn else 5,
            'hl': 'ja',
        }

        if attempt["use_key"] and api_key:
            params['key'] = api_key

        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                timeout=10,
            )

            if response.status_code == 403:
                try:
                    err_msg = response.json().get('error', {}).get('message', '')
                except Exception:
                    err_msg = response.text[:100]
                st.warning(f"⚠️ Google Books [{attempt['label']}] 403: {err_msg}")

                if attempt["use_key"]:
                    st.info("🔄 APIキーなしで再試行中（GCP地理制限回避）...")
                    continue
                else:
                    return []

            if response.status_code != 200:
                st.warning(f"⚠️ Google Books [{attempt['label']}] エラー: {response.status_code}")
                return []

            # 成功
            books = []
            for item in response.json().get('items', []):
                vi = item.get('volumeInfo', {})
                books.append({
                    'title': vi.get('title', '不明'),
                    'authors': vi.get('authors', ['不明']),
                    'categories': vi.get('categories', ['未分類']),
                    'cover_image': vi.get('imageLinks', {}).get('thumbnail', ''),
                    'description': vi.get('description', '説明なし'),
                    'average_rating': vi.get('averageRating', 0),
                    'published_date': vi.get('publishedDate', '不明'),
                    'isbn': query if is_isbn else '',
                })

            if books:
                st.success(f"📚 Google Books [{attempt['label']}] で書籍情報を取得しました")
            return books

        except Exception as e:
            st.warning(f"⚠️ Google Books [{attempt['label']}] 例外: {e}")
            return []

    return []


# ---------------------------------------------------------------
# Open Library API
# ---------------------------------------------------------------
def search_open_library_by_isbn(isbn: str) -> List[Dict]:
    """Open Library の直接ISBN検索"""
    try:
        url = f"https://openlibrary.org/api/books.json?bibkeys=ISBN:{isbn}&jscmd=data&format=json"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        key = f"ISBN:{isbn}"
        if key not in data:
            return []

        book_data = data[key]

        cover_image = ""
        cover = book_data.get('cover', {})
        cover_id = cover.get('large') or cover.get('medium') or cover.get('small')
        if cover_id:
            cover_image = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

        authors = [a.get('name', '不明') for a in book_data.get('authors', [])] or ['不明']

        st.success("✅ Open Library（直接ISBN）から書籍情報を取得しました")
        return [{
            'title': book_data.get('title', '不明'),
            'authors': authors,
            'categories': book_data.get('subjects', ['未分類'])[:5],
            'cover_image': cover_image,
            'description': book_data.get('subtitle', '') or '説明なし',
            'average_rating': 0,
            'published_date': str(book_data.get('publish_date', '不明')),
            'isbn': isbn,
        }]

    except Exception as e:
        st.warning(f"⚠️ Open Library ISBN検索エラー: {e}")
        return []


def search_open_library_flexible(query: str) -> List[Dict]:
    """
    Open Library の検索API。
    language フィルタを使わず、ISBNまたは書名で検索する。
    """
    try:
        if query.isdigit() and len(query) == 13:
            params = {'isbn': query, 'limit': 3}
        else:
            params = {'q': query, 'limit': 3}

        response = requests.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=10,
        )

        if response.status_code != 200:
            st.warning(f"⚠️ Open Library 検索エラー: {response.status_code}")
            return []

        docs = response.json().get('docs', [])
        if not docs:
            return []

        books = []
        for doc in docs:
            cover_image = ""
            if 'cover_i' in doc:
                cover_image = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"

            books.append({
                'title': doc.get('title', '不明'),
                'authors': doc.get('author_name', ['不明']),
                'categories': doc.get('subject', ['未分類'])[:5],
                'cover_image': cover_image,
                'description': '説明なし',
                'average_rating': 0,
                'published_date': str(doc.get('first_publish_year', '不明')),
                'isbn': query if query.isdigit() else '',
            })

        st.success(f"✅ Open Library（検索API）から{len(books)}件の書籍情報を取得しました")
        return books

    except Exception as e:
        st.warning(f"⚠️ Open Library 検索エラー: {e}")
        return []


# ---------------------------------------------------------------
# メイン検索エントリポイント
# ---------------------------------------------------------------
def search_by_isbn(isbn: str, extracted_text: str = "") -> List[Dict]:
    """
    ISBNで書籍を検索。検索優先順位：
      1. Google Books API（キー付き）
      2. Google Books API（キーなし・GCP制限回避）
      3. Open Library API（直接ISBN）
      4. Open Library API（検索API・ISBN）
      5. Google Books API（書名検索・キーなし）← OCR書名を使用
      6. Open Library API（検索API・書名）    ← OCR書名を使用
    """
    # --- 1-2. Google Books（キー付き→キーなし自動リトライ）---
    books = search_google_books(isbn, is_isbn=True)
    if books:
        return books

    # --- 3. Open Library 直接ISBN ---
    st.info("🔄 Open Library（直接ISBN）で検索中...")
    books = search_open_library_by_isbn(isbn)
    if books:
        return books

    # --- 4. Open Library 検索API（ISBN）---
    st.info("🔄 Open Library（検索API・ISBN）で検索中...")
    books = search_open_library_flexible(isbn)
    if books:
        return books

    # --- 5-6. OCRから書名を抽出して検索 ---
    title_candidate = extract_title_from_ocr(extracted_text)
    if title_candidate:
        st.info(f"🔍 書名候補「{title_candidate}」で検索中...")

        books = search_google_books(title_candidate, is_isbn=False)
        if books:
            return books

        st.info("🔄 Open Library（書名検索）で検索中...")
        books = search_open_library_flexible(title_candidate)
        if books:
            return books

    return []


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
            books = search_by_isbn(isbn, extracted_text)

            if books:
                return books, f"ISBN: {isbn}\n\n{extracted_text}"
            else:
                return [], (
                    f"ISBNで書籍が見つかりませんでした。\n\n"
                    f"ISBN: {isbn}\n\n"
                    f"抽出テキスト:\n{extracted_text[:200]}..."
                )
        else:
            # ISBNが検出できない場合も書名で検索を試みる
            title_candidate = extract_title_from_ocr(extracted_text)
            if title_candidate:
                st.info(f"📖 ISBN未検出。書名候補「{title_candidate}」で検索中...")
                books = search_google_books(title_candidate, is_isbn=False)
                if not books:
                    books = search_open_library_flexible(title_candidate)
                if books:
                    return books, f"書名検索: {title_candidate}\n\n{extracted_text}"

            return [], (
                f"ISBNが検出できませんでした。\n\n"
                f"抽出テキスト:\n{extracted_text[:200]}...\n\n"
                f"💡 ヒント: 裏表紙のISBN（978で始まる13桁の数字）を撮影してください。"
            )

    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"