import streamlit as st
from langchain_community.llms import Ollama
from supabase import create_client

# --- 1. 初期化 ---
if "messages" not in st.session_state: st.session_state.messages = []
if "user" not in st.session_state: st.session_state.user = None
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None
if "reg_step" not in st.session_state: st.session_state.reg_step = "input"

supabase_url = "https://jzjwuhpqrkfogbxhibru.supabase.co"
supabase_key = "sb_publishable_ltrBPergvNFxjAUmSXJf-w_dq-TE8mK"
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(supabase_url, supabase_key)

llm = Ollama(model="qwen2.5-coder:3b")

st.set_page_config(page_title="RunaAI Pro", layout="wide")
st.title("⚡ RunaAI Pro")

# --- 2. 認証・自動ログイン ---
query_params = st.query_params
if not st.session_state.user and "token" in query_params:
    try:
        user = st.session_state.supabase.auth.get_user(query_params["token"]).user
        st.session_state.user = {"id": user.id, "name": user.email.split("@")[0]}
    except: st.query_params.clear()

if not st.session_state.user:
    tab1, tab2 = st.tabs(["🔒 ログイン", "📝 新規登録"])
    with tab1:
        email, pw = st.text_input("メール", key="li_e"), st.text_input("パスワード", type="password", key="li_p")
        if st.button("ログイン"):
            try:
                res = st.session_state.supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.user = {"id": res.user.id, "name": email.split("@")[0]}
                st.query_params["token"] = res.session.access_token
                st.rerun()
            except Exception as e: st.error(f"ログインエラー: {e}")
    with tab2:
        if st.session_state.reg_step == "input":
            email, pw = st.text_input("メール", key="su_e"), st.text_input("パスワード", type="password", key="su_p")
            if st.button("登録"):
                try:
                    st.session_state.supabase.auth.sign_up({"email": email, "password": pw})
                    st.session_state.temp_email = email
                    st.session_state.reg_step = "verify"
                    st.rerun()
                except Exception as e: st.error(f"登録失敗: {e}")
        else:
            code = st.text_input("確認コードを入力")
            if st.button("認証完了"):
                try:
                    st.session_state.supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": code, "type": "signup"})
                    st.success("認証成功！ログインしてください")
                    st.session_state.reg_step = "input"
                except Exception as e: st.error(f"認証失敗: {e}")
else:
    # --- 3. メインアプリ機能 ---
    st.sidebar.write(f"👤 {st.session_state.user['name']} さん")
    if st.sidebar.button("➕ 新規チャット"):
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.rerun()
    
    st.sidebar.divider()
    
    # 履歴表示・ゴミ箱
    try:
        sessions = st.session_state.supabase.table("chat_sessions").select("*").eq("user_id", st.session_state.user["id"]).execute().data
        for s in sessions:
            c1, c2 = st.sidebar.columns([4, 1])
            if c1.button(f"📝 {s.get('title', '無題')[:10]}", key=f"btn_{s['id']}"):
                st.session_state.current_session_id = s['id']
                msgs = st.session_state.supabase.table("chat_messages").select("*").eq("session_id", s['id']).execute().data
                st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in msgs]
                st.rerun()
            if c2.button("🗑️", key=f"del_{s['id']}"):
                st.session_state.supabase.table("chat_messages").delete().eq("session_id", s['id']).execute()
                st.session_state.supabase.table("chat_sessions").delete().eq("id", s['id']).execute()
                st.rerun()
    except Exception as e: st.sidebar.error("履歴取得エラー")

    uploaded_file = st.sidebar.file_uploader("コード添付")
    if st.sidebar.button("🔒 ログアウト"):
        st.query_params.clear()
        st.session_state.user = None
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("コードや質問を入力..."):
        file_text = uploaded_file.read().decode('utf-8', errors='ignore') if uploaded_file else ""
        resp = llm.invoke(f"シニアエンジニアとして【分析→検討→結論】の順で思考し回答してください。\nUser: {prompt} {file_text}")
        
        if not st.session_state.current_session_id:
            res = st.session_state.supabase.table("chat_sessions").insert({"user_id": st.session_state.user["id"], "title": prompt[:15]}).execute()
            st.session_state.current_session_id = res.data[0]["id"]
            
        st.session_state.supabase.table("chat_messages").insert({"session_id": st.session_state.current_session_id, "role": "user", "content": prompt}).execute()
        st.session_state.supabase.table("chat_messages").insert({"session_id": st.session_state.current_session_id, "role": "assistant", "content": resp}).execute()
        st.session_state.messages.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": resp}])
        st.rerun()