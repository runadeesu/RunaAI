import streamlit as st
from langchain_community.llms import Ollama
from supabase import create_client

# --- 1. 初期化 ---
if "messages" not in st.session_state: st.session_state.messages = []
if "user" not in st.session_state: st.session_state.user = None
if "current_session_id" not in st.session_state: st.session_state.current_session_id = None

# Supabase接続情報
supabase_url = "https://jzjwuhpqrkfogbxhibru.supabase.co"
supabase_key = "sb_publishable_ltrBPergvNFxjAUmSXJf-w_dq-TE8mK"
if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(supabase_url, supabase_key)

llm = Ollama(model="qwen2.5-coder:3b")

st.set_page_config(page_title="RunaAI Pro", layout="wide")
st.title("⚡ RunaAI Pro")

# --- 2. 認証処理 ---
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
            except Exception as e: st.error(f"ログイン失敗: {e}")
    with tab2:
        email, pw = st.text_input("メール", key="su_e"), st.text_input("パスワード", type="password", key="su_p")
        if st.button("登録"):
            st.session_state.supabase.auth.sign_up({"email": email, "password": pw})
            st.warning("確認メールをチェックしてください")
else:
    # --- 3. サイドバー機能 ---
    st.sidebar.write(f"👤 {st.session_state.user['name']} さん")
    if st.sidebar.button("🔒 ログアウト"):
        st.query_params.clear()
        st.session_state.user = None
        st.rerun()
    if st.sidebar.button("➕ 新規チャット"):
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.rerun()
    
    st.sidebar.divider()
    
    # 履歴表示・読み込み・削除 (テーブル名を chat_sessions に修正)
    try:
        # ここが取得の要です
        sessions = st.session_state.supabase.table("chat_sessions").select("*").eq("user_id", st.session_state.user["id"]).order("created_at", desc=True).execute().data
        for s in sessions:
            col1, col2 = st.sidebar.columns([4, 1])
            if col1.button(f"📝 {s.get('title', '無題')[:10]}", key=f"btn_{s['id']}"):
                st.session_state.current_session_id = s['id']
                msgs = st.session_state.supabase.table("chat_messages").select("*").eq("session_id", s['id']).order("created_at", desc=False).execute().data
                st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in msgs]
                st.rerun()
            if col2.button("🗑️", key=f"del_{s['id']}"):
                st.session_state.supabase.table("chat_messages").delete().eq("session_id", s['id']).execute()
                st.session_state.supabase.table("chat_sessions").delete().eq("id", s['id']).execute()
                st.rerun()
    except Exception as e: 
        st.sidebar.error(f"履歴取得エラー: {e}")

    uploaded_file = st.sidebar.file_uploader("コードファイル添付")

    # --- 4. メインチャット ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("コードや質問を入力..."):
        file_text = uploaded_file.read().decode('utf-8', errors='ignore') if uploaded_file else ""
        system_instr = "シニアエンジニアです。回答前に【分析→検討→結論】の順に論理的に思考してから回答してください。"
        context = f"System: {system_instr}\n\nUser: {prompt} {file_text}\nAssistant: (思考プロセスから出力)"
        resp = llm.invoke(context)
        
        if not st.session_state.current_session_id:
            res = st.session_state.supabase.table("chat_sessions").insert({"user_id": st.session_state.user["id"], "title": prompt[:15]}).execute()
            st.session_state.current_session_id = res.data[0]["id"]
            
        st.session_state.supabase.table("chat_messages").insert({"session_id": st.session_state.current_session_id, "role": "user", "content": prompt}).execute()
        st.session_state.supabase.table("chat_messages").insert({"session_id": st.session_state.current_session_id, "role": "assistant", "content": resp}).execute()
        
        st.session_state.messages.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": resp}])
        st.rerun()