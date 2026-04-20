import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [접속 및 시트 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(index)
    except: return None

# --- [뉴스 스크래핑 보강] ---
def get_insurance_news():
    results = []
    try:
        # 보안 회피를 위한 헤더 설정
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        for item in news_items[:5]:
            title = item.get_text().strip()
            link = "https://www.insnews.co.kr" + item.get('href') if item.get('href').startswith('/') else item.get('href')
            if title: results.append({"title": title, "link": link})
    except: pass
    return results

# --- [기본 환경 설정] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")

with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v8.7")

# 데이터 로드
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

# 고객 DB 로드 및 헤더 강제 지정
cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

# 실적 DB 로드
sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if len(sales_values) > 1 else pd.DataFrame(columns=sales_headers)
db_sales['보험료'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# --- [메뉴 1: 🏠 홈 (알림 기능 강화)] ---
if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    
    # 실적 지표 계산
    db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'], errors='coerce')
    curr_m = datetime.now().month
    curr_y = datetime.now().year
    this_m_data = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 이번 달 보험료 합계", f"{int(this_m_data['보험료'].sum()):,}원")
    m2.metric("📈 이번 달 체결 건수", f"{len(this_m_data)}건")
    m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료'].sum()):,}원")

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🎂 이번 달 생일 고객")
        this_month_str = datetime.now().strftime("%m")
        # 주민번호 3,4번째 자리가 이번 달인 고객 추출
        birth_cust = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_month_str]
        if not birth_cust.empty:
            for _, r in birth_cust.iterrows():
                st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {r['연락처']}")
        else: st.write("이번 달 생일인 고객이 없습니다.")

    with c2:
        st.subheader("🚘 자동차보험 만기 임박 (30일내)")
        today = datetime.now()
        in_30_days = today + timedelta(days=30)
        expire_count = 0
        for _, r in db_cust.iterrows():
            m_str = r['자동차만기일'].replace('.', '-').strip()
            if m_str:
                try:
                    m_dt = datetime.strptime(m_str, "%Y-%m-%d")
                    if today <= m_dt <= in_30_days:
                        st.warning(f"⚠️ **{r['이름']}** : {r['자동차만기일']} 만기 ({r['차량번호']})")
                        expire_count += 1
                except: pass
        if expire_count == 0: st.write("30일 이내 만기 고객이 없습니다.")

    st.markdown("---")
    st.markdown("### 📰 실시간 보험 뉴스")
    news = get_insurance_news()
    if news:
        for n in news: st.markdown(f"• [{n['title']}]({n['link']})")
    else: st.info("뉴스를 불러오는 중입니다. 잠시만 기다려주세요.")

# --- [메뉴 2: 📊 실적 관리 (입력 오류 방지)] ---
elif menu == "📊 실적 관리":
    st.subheader("📊 실적 등록 및 현황")
    st.info("💡 아래 내용을 그대로 복사해서 넣으세요.")
    s_input = st.text_area("실적 내용 입력", placeholder="1/13 배현우 삼성생명/치아보험/25,230")
    
    if st.button("🚀 실적 기록") and s_input:
        # 어떠한 형식이든 '날짜, 이름, 상품명, 보험료'로 강제 추출
        try:
            # 1. 줄바꿈 제거 및 정리
            clean_text = s_input.replace('\n', ' ').strip()
            # 2. 날짜 추출 (M/D 형식 대응)
            date_match = re.search(r'(\d{1,2}/\d{1,2})', clean_text)
            date_val = f"{datetime.now().year}-{date_match.group(1).replace('/', '-')}" if date_match else datetime.now().strftime("%Y-%m-%d")
            
            # 3. 텍스트 분리 (공백이나 슬래시 기준)
            parts = [p.strip() for p in re.split(r'[\s/]+', clean_text) if p.strip()]
            
            # 4. 보험료 추출 (숫자와 콤마로 된 마지막 부분)
            price_str = re.sub(r'[^0-9]', '', parts[-1])
            
            # 5. 이름 및 상품명 (가운데 부분들 합치기)
            name_val = parts[1] if len(parts) > 1 else "미정"
            prod_val = " ".join(parts[2:-1]) if len(parts) > 3 else parts[-2]

            sheet_sales.append_row([date_val, name_val, prod_val, price_str])
            st.success(f"✅ {name_val}님 실적 등록 완료!"); st.rerun()
        except:
            st.error("데이터 해석에 실패했습니다. 형식에 맞춰 다시 시도해주세요.")

    st.markdown("---")
    st.dataframe(db_sales.sort_values(by="날짜", ascending=False), use_container_width=True)

# (고객조회 등 나머지 기능은 기존 안정적인 로직 유지)
