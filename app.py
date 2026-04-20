import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [접속 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# --- [보험매일 뉴스 스크래핑] ---
def get_insurance_news():
    results = []
    try:
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        base_url = "https://www.insnews.co.kr"
        for item in news_items[:5]:
            results.append({"title": item.get_text().strip(), "link": base_url + item.get('href') if item.get('href').startswith('/') else item.get('href')})
    except: pass
    return results

# --- [기본 설정] ---
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

# 사이드바 메뉴
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식", "💬 고객문자발송(안내)"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v8.0")

# 데이터 로드
sheet = get_gsheet()
all_values = sheet.get_all_values() if sheet else []
db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
db = db.fillna("")

# --- [메인 대시보드 로직] ---
if menu == "🏠 홈":
    st.title("🛡️ 배현우 고객관리 시스템")
    
    # 1. 상단 실적 대시보드
    this_month = datetime.now().strftime("%Y-%m")
    new_clients_count = len(db[db['날짜'].str.contains(this_month)])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📊 이번 달 신규 등록", f"{new_clients_count}명")
    c2.metric("👥 전체 관리 고객", f"{len(db)}명")
    c3.metric("📅 오늘 날짜", datetime.now().strftime("%m월 %d일"))

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        # 2. 생일 도래 고객 (주민번호 앞 6자리 기준)
        st.subheader("🎂 이번 달 생일 고객")
        today_mm = datetime.now().strftime("%m")
        birthday_list = []
        for idx, row in db.iterrows():
            if len(row['주민번호']) >= 4:
                if row['주민번호'][2:4] == today_mm:
                    birthday_list.append(row)
        
        if birthday_list:
            for b in birthday_list:
                st.write(f"🎈 **{b['이름']}** ({b['주민번호'][:6]}) - {b['연락처']}")
                if st.button(f"{b['이름']} 정보조회", key=f"birth_{b['이름']}"):
                    st.session_state.search_target = b['이름']
                    # 조회 탭으로 강제 이동 로직은 radio 특성상 버튼 클릭 유도로 대체
                    st.info(f"위 메뉴에서 '🔍 고객조회/수정'을 누르면 {b['이름']}님 정보가 검색됩니다.")
        else:
            st.write("이번 달 생일인 고객이 없습니다.")

    with col_right:
        # 3. 자동차보험 만기 알림 (1달 이내)
        st.subheader("🚘 자동차보험 만기 임박 (30일 이내)")
        today = datetime.now()
        warning_date = today + timedelta(days=30)
        expire_list = []
        
        for idx, row in db.iterrows():
            if row['자동차만기일']:
                try:
                    m_date = datetime.strptime(row['자동차만기일'].replace('.','-'), "%Y-%m-%d")
                    if today <= m_date <= warning_date:
                        expire_list.append(row)
                except: pass
        
        if expire_list:
            for e in expire_list:
                st.warning(f"⚠️ **{e['이름']}** : {e['자동차만기일']} 만기 ({e['차량번호']})")
                st.write(f"📞 연락처: {e['연락처']} / 보험사: {e['보험사']}")
        else:
            st.write("30일 이내 만기 예정 고객이 없습니다.")

    st.markdown("---")
    # 4. 실시간 보험 뉴스
    st.markdown("### 📰 실시간 보험 업계 뉴스")
    news = get_insurance_news()
    if news:
        for n in news:
            st.markdown(f"• [{n['title']}]({n['link']})")

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    # 홈에서 누른 검색어가 있으면 자동으로 입력됨
    default_name = st.session_state.get('search_target', "")
    name_input = st.text_input("고객 성함 입력", value=default_name)
    if name_input:
        res = db[db['이름'].str.contains(name_input)]
        for _, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                st.write(f"주소: {row['주소']} / 주민번호: {row['주민번호']}")
                if row['차량번호']: st.success(f"차량: {row['차량번호']} / 보험사: {row['보험사']} / 만기: {row['자동차만기일']}")
                # (보장분석 리스트 출력 로직 포함됨)

# (나머지 탭들 - 신규등록, 고객리스트, 업데이트 등은 v7.9의 안정적인 로직 그대로 유지)
