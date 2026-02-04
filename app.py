import streamlit as st
from datetime import datetime
from PIL import Image
import pandas as pd

# 自作モジュールのインポート
from auth import login_page, logout
from database import save_book, get_user_books, update_book_rating
from book_recognition import recognize_book_from_image
from recommendation import recommend_books

# ページ設定
st.set_page_config(
    page_title="Book Recommendation App",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #4CAF50;
        color: white;
    }
    .book-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    h1 {
        color: #2c3e50;
    }
    h2 {
        color: #34495e;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """メインアプリケーション"""
    
    # ログイン状態の確認
    if 'user_id' not in st.session_state:
        login_page()
        return
    
    # サイドバー
    with st.sidebar:
        st.title("📚 Book App")
        st.markdown(f"**ログイン中:** {st.session_state.get('user_email', '')}")
        st.markdown("---")
        
        page = st.radio(
            "ページを選択",
            ["📖 書籍の記録", "✨ おすすめの書籍"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        if st.button("ログアウト"):
            logout()
    
    # ページ表示
    if page == "📖 書籍の記録":
        book_recording_page()
    else:
        recommendation_page()

def book_recording_page():
    """書籍記録ページ"""
    st.title("📖 書籍の記録")
    st.markdown("表紙の写真を撮影またはアップロードして、読んだ本を記録しましょう")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📸 書籍を追加")
        
        # 撮影方法を選択
        input_method = st.radio(
            "入力方法を選択",
            ["📷 カメラで撮影", "📁 ファイルをアップロード"],
            horizontal=True
        )
        
        image = None
        
        if input_method == "📷 カメラで撮影":
            # カメラ入力
            camera_photo = st.camera_input("書籍の表紙を撮影")
            if camera_photo:
                image = Image.open(camera_photo)
                st.image(image, caption="撮影された画像", use_container_width=True)
        else:
            # ファイルアップロード
            uploaded_file = st.file_uploader(
                "表紙の写真をアップロード",
                type=['jpg', 'jpeg', 'png'],
                help="書籍の表紙を撮影してアップロードしてください"
            )
            if uploaded_file:
                image = Image.open(uploaded_file)
                st.image(image, caption="アップロードされた画像", use_container_width=True)
        
        if image:
            if st.button("書籍情報を取得", type="primary"):
                with st.spinner("書籍情報を取得中..."):
                    books, extracted_text = recognize_book_from_image(image)
                    
                    if books:
                        st.success("書籍が見つかりました!")
                        st.info(f"抽出されたテキスト: {extracted_text}")
                        
                        # 候補を表示
                        st.subheader("候補から選択してください")
                        for idx, book in enumerate(books):
                            with st.expander(f"{idx+1}. {book['title']} - {', '.join(book['authors'])}"):
                                col_a, col_b = st.columns([1, 2])
                                
                                with col_a:
                                    if book['cover_image']:
                                        st.image(book['cover_image'])
                                
                                with col_b:
                                    st.write(f"**著者:** {', '.join(book['authors'])}")
                                    st.write(f"**ジャンル:** {', '.join(book['categories'])}")
                                    st.write(f"**説明:** {book['description'][:100]}...")
                                    
                                    if st.button(f"この本を記録", key=f"save_{idx}"):
                                        book_data = {
                                            'title': book['title'],
                                            'authors': book['authors'],
                                            'categories': book['categories'],
                                            'cover_image': book['cover_image'],
                                            'description': book['description'],
                                            'completed_date': datetime.now()
                                        }
                st.info(f"DEBUG: Saving book. user_id={st.session_state.get('user_id')}, title={book_data.get('title')}")
                save_book(st.session_state['user_id'], book_data)
                st.success(f"「{book['title']}」を記録しました!")
                st.rerun()
                    else:
                        st.error(extracted_text)
    
    with col2:
        st.subheader("📚 読書履歴")
        
        # 読書履歴を取得
        books = get_user_books(st.session_state['user_id'])
        
        if books:
            for book in books:
                with st.container():
                    st.markdown('<div class="book-card">', unsafe_allow_html=True)
                    
                    col_img, col_info = st.columns([1, 3])
                    
                    with col_img:
                        if book.get('cover_image'):
                            st.image(book['cover_image'], width=100)
                    
                    with col_info:
                        st.markdown(f"**{book['title']}**")
                        st.caption(f"著者: {', '.join(book.get('authors', ['不明']))}")
                        st.caption(f"読了日: {book['completed_date'].strftime('%Y年%m月%d日')}")
                        
                        # 評価
                        rating = st.select_slider(
                            "評価",
                            options=[1, 2, 3, 4, 5],
                            value=book.get('rating', 3),
                            key=f"rating_{book['id']}"
                        )
                        
                        if rating != book.get('rating', 0):
                            update_book_rating(st.session_state['user_id'], book['id'], rating)
                            st.success("評価を更新しました!")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("まだ記録された書籍がありません")

def recommendation_page():
    """おすすめページ"""
    st.title("✨ あなたへのおすすめ")
    st.markdown("あなたの読書傾向と季節に基づいて、おすすめの書籍を提案します")
    
    # ユーザーの読書履歴を取得
    user_books = get_user_books(st.session_state['user_id'])
    
    if not user_books:
        st.warning("まず書籍を記録してください。記録された書籍に基づいておすすめを提案します。")
        return
    
    # おすすめを取得
    with st.spinner("おすすめを生成中..."):
        recommendations = recommend_books(user_books, count=3)
    
    if recommendations:
        st.subheader("📚 今日のおすすめ (3冊)")
        
        for idx, book in enumerate(recommendations, 1):
            with st.container():
                st.markdown('<div class="book-card">', unsafe_allow_html=True)
                
                col_img, col_info = st.columns([1, 3])
                
                with col_img:
                    if book['cover_image']:
                        st.image(book['cover_image'], width=150)
                
                with col_info:
                    st.markdown(f"### {idx}. {book['title']}")
                    st.markdown(f"**著者:** {', '.join(book['authors'])}")
                    st.markdown(f"**ジャンル:** {', '.join(book['categories'])}")
                    
                    if book['average_rating'] > 0:
                        st.markdown(f"⭐ 平均評価: {book['average_rating']}/5")
                    
                    st.markdown(f"**あらすじ:**")
                    st.write(book['description'])
                    
                    st.info(f"💡 **推薦理由:** {book['reason']}")
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("おすすめを取得できませんでした")

if __name__ == "__main__":
    main()