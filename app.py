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

# --- [보험매일 뉴스 스크래핑] ---
def get_insurance_news():
    results = []
    try:
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'; soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        for item in news_items[:5]:
            results.append({"title": item.get_text().strip(), "link": "https://www.insnews.co.kr" + item.get('href')})
    except: pass
    return results

# --- [기본 설정] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")

with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v8.6")

# 데이터 로드
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1) # 실적 시트

cust_values = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_values[1:], columns=cust_values[0]) if cust_values else pd.DataFrame()

sales_values = sheet_sales.get_all_values() if sheet_sales else []
# 수수료 제외, 4개 항목으로 고정
sales_headers = ["날짜", "고객명", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if sales_values else pd.DataFrame(columns=sales_headers)
db_sales['보험료'] = pd.to_numeric(db_sales['보험료'].str.replace(',', ''), errors='coerce').fillna(0)

# --- [메뉴 1: 🏠 홈] ---
if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    
    db_sales['날짜'] = pd.to_datetime(db_sales['날짜'], errors='coerce')
    today = datetime.now()
    this_month_sales = db_sales[db_sales['날짜'].dt.month == today.month]
    last_month_sales = db_sales[db_sales['날짜'].dt.month == (today.month - 1 if today.month > 1 else 12)]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 당월 보험료 합계", f"{int(this_month_sales['보험료'].sum()):,}원", 
              delta=f"{int(this_month_sales['보험료'].sum() - last_month_sales['보험료'].sum()):,}원 (전월비)")
    m2.metric("📈 당월 체결 건수", f"{len(this_month_sales)}건")
    m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜'].dt.year == today.year]['보험료'].sum()):,}원")

    st.markdown("### 📊 월별 실적 추이")
    if not db_sales.empty:
        chart_data = db_sales.resample('M', on='날짜')['보험료'].sum().reset_index()
        chart_data['날짜'] = chart_data['날짜'].dt.strftime('%Y-%m')
        st.bar_chart(chart_data.set_index('날짜'))

    st.markdown("---")
    c_news, c_birth = st.columns([1.5, 1])
    with c_news:
        st.markdown("### 📰 실시간 보험 뉴스")
        for n in get_insurance_news(): st.markdown(f"• [{n['title']}]({n['link']})")
    with c_birth:
        st.markdown("### 🎂 이번 달 생일")
        # 생일 로직 생략(v8.0 준용)

# --- [메뉴 2: 📊 실적 관리] ---
elif menu == "📊 실적 관리":
    st.subheader("📊 실적 등록 및 현황")
    
    st.info("💡 입력 예시: 2026-01-13, 배현우, 삼성생명 치아보험, 25230")
    sales_input = st.text_input("한 줄 실적 입력 (날짜, 고객명, 상품명, 보험료)")
    
    if st.button("🚀 실적 기록") and sales_input:
        try:
            s_data = [i.strip() for i in sales_input.split(',')]
            # 4개 항목만 저장
            new_sales_row = [s_data[0], s_data[1], s_data[2], s_data[3].replace(',', '')]
            sheet_sales.append_row(new_sales_row)
            st.success(f"✅ {s_data[1]}님 실적 반영 완료!"); st.rerun()
        except:
            st.error("입력 형식을 확인해주세요. (콤마 구분)")

    st.markdown("---")
    st.write("### 📑 실적 리스트")
    st.dataframe(db_sales.sort_values(by="날짜", ascending=False), use_container_width=True)

# (나머지 기능 v8.0과 동일하게 유지)
