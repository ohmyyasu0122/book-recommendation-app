import streamlit as st
from firebase_admin import auth
from database import initialize_firebase

def create_user(email, password):
    """新規ユーザーを作成"""
    try:
        initialize_firebase()
        user = auth.create_user(
            email=email,
            password=password
        )
        return user.uid, None
    except Exception as e:
        return None, str(e)

def verify_user(email, password):
    """ユーザー認証(簡易版)"""
    try:
        initialize_firebase()
        # Firebase Admin SDKでは直接パスワード認証ができないため
        # 実際のアプリではFirebase Authentication REST APIを使用
        # ここでは簡易的にメールでユーザーを取得
        user = auth.get_user_by_email(email)
        return user.uid, None
    except Exception as e:
        return None, str(e)

def login_page():
    """ログインページ"""
    st.title("📚 Book Recommendation App")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])
    
    with tab1:
        st.subheader("ログイン")
        email = st.text_input("メールアドレス", key="login_email")
        password = st.text_input("パスワード", type="password", key="login_password")
        
        if st.button("ログイン", type="primary"):
            if email and password:
                user_id, error = verify_user(email, password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.session_state['user_email'] = email
                    st.success("ログインしました!")
                    st.rerun()
                else:
                    st.error(f"ログインに失敗しました: {error}")
            else:
                st.warning("メールアドレスとパスワードを入力してください")
    
    with tab2:
        st.subheader("新規登録")
        new_email = st.text_input("メールアドレス", key="signup_email")
        new_password = st.text_input("パスワード (6文字以上)", type="password", key="signup_password")
        confirm_password = st.text_input("パスワード確認", type="password", key="confirm_password")
        
        if st.button("登録", type="primary"):
            if new_email and new_password and confirm_password:
                if new_password != confirm_password:
                    st.error("パスワードが一致しません")
                elif len(new_password) < 6:
                    st.error("パスワードは6文字以上にしてください")
                else:
                    user_id, error = create_user(new_email, new_password)
                    if user_id:
                        st.success("登録が完了しました! ログインしてください")
                    else:
                        st.error(f"登録に失敗しました: {error}")
            else:
                st.warning("すべての項目を入力してください")

def logout():
    """ログアウト"""
    st.session_state.clear()
    st.rerun()
