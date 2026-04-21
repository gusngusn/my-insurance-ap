import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- [1. 구글 시트 연결] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except:
        return None

# --- [2. UI 구성] ---
st.set_page_config(page_title="시스템", layout="wide")

# 사이드바: 버튼 딱 하나만 배치
with st.sidebar:
    st.header("메뉴")
    if st.button("📄 보장분석업로드", use_container_width=True):
        st.session_state.page = "upload"

# 메인 화면
if "page" in st.session_state and st.session_state.page == "upload":
    st.title("보장분석 업로드")
    # 여기에만 업로드 관련 기능이 나타나도록 설정
    st.write("PDF 파일을 업로드하여 분석을 시작하세요.")
    # (이후 분석 로직 연결)
else:
    st.title("메뉴를 선택해주세요.")
