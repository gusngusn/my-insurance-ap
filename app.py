import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [1. 구글 시트 및 보안 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        all_worksheets = client.open_by_key(SHEET_ID).worksheets()
        if len(all_worksheets) > index: return all_worksheets[index]
        return None
    except: return None

# --- [2. 보험 뉴스 스크래핑] ---
def get_insurance_news():
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'; soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        for item in news_items[:5]:
            results.append({"title": item.get_text().strip(), "link": "https://www.insnews.co.kr" + item.get('href')})
    except: pass
    return results

# --- [3. 데이터 로드 및 전처리] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "생년월일", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if len(sales_values) > 1 else pd.DataFrame(columns=sales_headers)
db_sales['보험료'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'], errors='coerce')

# --- [4. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v11.9")

# --- [5. 메뉴별 기능 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    curr_m, curr_y = datetime.now().month, datetime.now().year
    this_m_data = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 이번 달 합계", f"{int(this_m_data['보험료'].sum()):,}원")
    m2.metric("📈 이번 달 건수", f"{len(this_m_data)}건")
    m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료'].sum()):,}원")
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎂 이번 달 생일")
        this_m = datetime.now().strftime("%m")
        birth = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_m]
        if not birth.empty:
            for _, r in birth.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {r['연락처']}")
        else: st.write("없음")
    with c2:
        st.subheader("🚘 자동차 만기 (30일내)")
        today, count = datetime.now(), 0
        for _, r in db_cust.iterrows():
            m_str = r['자동차만기일'].replace('.', '-').strip()
            try:
                m_dt = datetime.strptime(m_str, "%Y-%m-%d")
                if today <= m_dt <= today + timedelta(days=30):
                    st.warning(f"⚠️ **{r['이름']}** : {r['자동차만기일']}")
                    count += 1
            except: pass
        if count == 0: st.write("없음")
    st.markdown("---")
    for n in get_insurance_news(): st.markdown(f"• [{n['title']}]({n['link']})")

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 입력 및 자동 고객 등록")
    with st.expander("➕ 실적 정보 입력", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: in_date = st.date_input("날짜", datetime.now())
        with c2: in_name = st.text_input("고객 이름")
        with c3: in_birth = st.text_input("생일(6자리)")
        with c4: in_prod = st.text_input("상품명")
        with c5: in_price = st.text_input("보험료")
        if st.button("🚀 저장"):
            p_val = re.sub(r'[^0-9]', '', in_price)
            match = db_cust[(db_cust['이름'] == in_name) & (db_cust['주민번호'].str.startswith(in_birth))]
            new_entry = f"{in_prod}/{p_val}/{in_date}"
            if match.empty:
                sheet_cust.append_row([str(in_date), in_name, f"{in_birth}-*******", "미기입", "미기입", "미기입", f"[보장분석] {new_entry}", in_name, "", "", "", "", "", "", ""])
            else:
                row_idx = match.index[-1] + 2
                old = match.iloc[-1]['병력(특이사항)']
                upd = f"{old} | {new_entry}" if "[보장분석]" in old else f"{old.strip()} | [보장분석] {new_entry}".strip(" | ")
                sheet_cust.update_cell(row_idx, 7, upd)
            if sheet_sales:
                sheet_sales.append_row([str(in_date), in_name, in_birth, in_prod, p_val])
            st.success("완료"); st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함 입력")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        if not res.empty:
            for idx, row in res.iterrows():
                with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                    st.write(f"**🏠 주소:** {row['주소']} / **🛠️ 직업:** {row['직업']}")
                    
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.markdown("#### 📋 보유계약 리스트")
                        ana_part = memo.split("[보장분석]")[-1].strip()
                        items = [i.strip() for i in ana_part.split('|') if i.strip()]
                        unique_items = list(dict.fromkeys(items))
                        
                        t_data = []
                        for it in unique_items:
                            p = [x.strip() for x in it.split('/') if x.strip()]
                            # 데이터가 3개 미만이면(구형 데이터 등) 유연하게 처리
                            if len(p) >= 3:
                                # 보험사/상품명 / 보험료 / 날짜 순서 고정
                                t_data.append({"보험사/상품명": p[0], "보험료": f"{int(re.sub(r'[^0-9]', '', p[1])):,}원" if re.sub(r'[^0-9]', '', p[1]) else p[1], "계약일": p[2]})
                            elif len(p) == 2:
                                t_data.append({"보험사/상품명": p[0], "보험료": p[1], "계약일": "-"})
                        
                        if t_data:
                            st.table(pd.DataFrame(t_data))
                        st.info(f"**💡 기타 메모:** {memo.split('[보장분석]')[0].replace('|','').strip()}")
                    else:
                        st.info(f"**💡 메모:** {memo}")
                    
                    with st.form(key=f"edit_{idx}"):
                        c1, c2 = st.columns(2)
                        new_phone = c1.text_input("연락처", value=row['연락처'])
                        new_addr = c2.text_input("주소", value=row['주소'])
                        new_job = c1.text_input("직업", value=row['직업'])
                        new_memo = st.text_area("전체 메모 수정", value=row['병력(특이사항)'])
                        if st.form_submit_button("✅ 저장"):
                            row_num = idx + 2
                            sheet_cust.update_cell(row_num, 4, new_phone)
                            sheet_cust.update_cell(row_num, 5, new_addr)
                            sheet_cust.update_cell(row_num, 6, new_job)
                            sheet_cust.update_cell(row_num, 7, new_memo)
                            st.success("수정 완료"); st.rerun()

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 등록")
    raw_in = st.text_area("이름, 주민번호, 연락처, 주소, 직업")
    if st.button("🚀 등록") and raw_in:
        d = [i.strip() for i in raw_in.split(',')]
        new_row = [datetime.now().strftime("%Y-%m-%d"), d[0], d[1], d[2], d[3], d[4] if len(d)>4 else "", "", d[0], "", "", "", "", "", "", ""]
        sheet_cust.append_row(new_row); st.success("완료"); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    st.dataframe(db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '직업']], use_container_width=True)

# ... (업데이트, 보장분석, 청구양식 등 나머지 메뉴 v11.8 동일 유지)
