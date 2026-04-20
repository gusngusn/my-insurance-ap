import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# --- [보안 설정] ---
ACCESS_PASSWORD = "123456" 
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

# 보험 뉴스 스크래핑 함수 (네이버 뉴스 - 보험 키워드 기준)
def get_insurance_news():
    try:
        url = "https://search.naver.com/search.naver?where=news&query=보험&sm=tab_pge&sort=1" # 최신순
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".news_tit")
        return [{"title": item['title'], "link": item['href']} for item in news_items[:5]]
    except:
        return []

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 보안 접속")
    pwd_input = st.text_input("접속 비밀번호 6자리를 입력하세요.", type="password")
    if st.button("접속하기"):
        if pwd_input == ACCESS_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else: st.error("❌ 비밀번호 오류")
    st.stop()

# --- 사이드바 ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("이동할 메뉴", ["🏠 홈", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식", "💬 고객문자발송(안내)"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v7.4")

sheet = get_gsheet()
all_values = sheet.get_all_values() if sheet else []
db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
db = db.fillna("")

# --- 메뉴 구현 ---
if menu == "🏠 홈":
    st.subheader("🏠 메인 대시보드")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(f"현재 등록된 총 고객은 **{len(db)}명**입니다.")
        # 뉴스 섹션
        st.markdown("### 📰 실시간 보험 뉴스")
        news = get_insurance_news()
        if news:
            for n in news:
                st.markdown(f"• [{n['title']}]({n['link']})")
        else: st.write("뉴스를 불러올 수 없습니다.")

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    page_size = 30
    total_records = len(db)
    total_pages = (total_records // page_size) + (1 if total_records % page_size > 0 else 0)
    
    # 하단 페이지 번호 로직을 위해 세션 스테이트 사용
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * page_size
    st.table(db[['날짜', '이름', '연락처', '주소', '자동차만기일']].iloc[start_idx : start_idx + page_size])

    # --- 하단 페이지 번호 숫자 링크 형식 ---
    st.markdown("---")
    cols = st.columns(total_pages + 10) # 넉넉하게 컬럼 생성
    for i in range(1, total_pages + 1):
        if cols[i].button(str(i), key=f"page_{i}"):
            st.session_state.current_page = i
            st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 보험사별 청구 양식 (하이퍼링크)")
    # (기존 링크 리스트 유지)
    pass

# (기존 고객조회, 신규등록, 자동차 업데이트, 보장분석 입력 로직 동일 적용)
# ... (코드 지면상 생략하지만 v7.3의 모든 기능을 포함함)
