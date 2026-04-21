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
        return all_worksheets[index] if len(all_worksheets) > index else None
    except Exception as e:
        return None

# --- [데이터 정제 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

def clean_date_id(date_val):
    # 날짜에서 숫자만 추출 (중복 제거용)
    return re.sub(r'[^0-9]', '', str(date_val))

# --- [2. 보험 뉴스 스크래핑] ---
def get_insurance_news():
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        for item in news_items[:5]:
            results.append({"title": item.get_text().strip(), "link": "https://www.insnews.co.kr" + item.get('href')})
    except: pass
    return results

# --- [3. 메인 로직 시작] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

# 데이터 로드
cust_values = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_values[1:], columns=cust_values[0]) if len(cust_values) > 1 else pd.DataFrame()

sales_values = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_values[1:], columns=sales_values[0]) if len(sales_values) > 1 else pd.DataFrame()

# 사이드바 메뉴 (모든 메뉴 복구)
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 업로드", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v13.1")

# --- [4. 메뉴별 상세 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    
    # 1. 실적 요약
    if not db_sales.empty:
        db_sales['보험료_n'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'].str.replace('.', '-'), errors='coerce')
        curr_m, curr_y = datetime.now().month, datetime.now().year
        this_m = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 이번 달 보험료 합계", f"{int(this_m['보험료_n'].sum()):,}원")
        m2.metric("📈 이번 달 체결 건수", f"{len(this_m)}건")
        m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료_n'].sum()):,}원")
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎂 이번 달 생일 고객")
        this_month = datetime.now().strftime("%m")
        birth_list = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_month]
        if not birth_list.empty:
            for _, r in birth_list.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {format_phone(r['연락처'])}")
        else: st.write("없음")
        
    with c2:
        st.subheader("🚘 자동차 보험 만기 (30일 이내)")
        today = datetime.now()
        car_list = []
        for _, r in db_cust.iterrows():
            m_date = str(r.get('자동차만기일', '')).replace('.', '-').strip()
            try:
                dt = datetime.strptime(m_date, "%Y-%m-%d")
                if today <= dt <= today + timedelta(days=30):
                    car_list.append(f"⚠️ **{r['이름']}** : {m_date} ({r.get('차량번호','')})")
            except: pass
        if car_list: 
            for item in car_list: st.write(item)
        else: st.write("만기 예정 고객 없음")

    st.markdown("---")
    st.subheader("📰 최신 보험 뉴스")
    for n in get_insurance_news(): st.markdown(f"• [{n['title']}]({n['link']})")

elif menu == "📊 실적 관리":
    st.subheader("📊 신규 실적 입력")
    with st.form("sales_form"):
        c1, c2, c3 = st.columns(3)
        s_date = c1.date_input("계약일", datetime.now())
        s_name = c2.text_input("고객명")
        s_birth = c3.text_input("생년월일(6자리)")
        s_prod = st.text_input("상품명 (보험사 포함)")
        s_price = st.text_input("보험료 (숫자만)")
        if st.form_submit_button("🚀 실적 저장 및 보장내역 연동"):
            if s_name and s_prod and s_price:
                price_pure = re.sub(r'[^0-9]', '', s_price)
                sheet_sales.append_row([str(s_date), s_name, s_birth, s_prod, price_pure])
                # 보장분석 자동 업데이트
                match = db_cust[(db_cust['이름'] == s_name) & (db_cust['주민번호'].str.startswith(s_birth))]
                if not match.empty:
                    row_idx = match.index[-1] + 2
                    old_memo = match.iloc[-1]['병력(특이사항)']
                    entry = f"{s_prod}/{price_pure}/{s_date}"
                    new_memo = f"{old_memo} | [보장분석] {entry}" if "[보장분석]" not in old_memo else f"{old_memo} | {entry}"
                    sheet_cust.update_cell(row_idx, 7, new_memo)
                st.success("완료되었습니다."); st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 검색")
    search_name = st.text_input("조회할 고객 성함을 입력하세요")
    if search_name:
        results = db_cust[db_cust['이름'].str.contains(search_name)]
        for idx, row in results.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                # 상세 정보 표시
                sc1, sc2 = st.columns(2)
                sc1.write(f"**🆔 주민번호:** {row['주민번호']}")
                sc1.write(f"**🛠️ 직업:** {row['직업']}")
                sc2.write(f"**🏠 주소:** {row['주소']}")
                if row.get('차량번호'):
                    st.info(f"**🚘 자동차 정보:** {row['차량번호']} / {row.get('보험사','')} (만기: {row.get('자동차만기일','')})")
                
                # 보장 리스트 (중복 제거 로직)
                memo = row['병력(특이사항)']
                if "[보장분석]" in memo:
                    st.markdown("---")
                    st.write("📋 **보유 계약 리스트**")
                    raw_items = memo.split("[보장분석]")[-1].split("|")
                    t_data, seen = [], set()
                    for item in raw_items:
                        p = [x.strip() for x in item.split("/") if x.strip()]
                        if len(p) >= 2:
                            dt, pr, nm = p[-1], p[-2] if len(p)>=3 else p[-1], "/".join(p[:-2]) if len(p)>=3 else p[0]
                            pr_n = re.sub(r'[^0-9]', '', pr)
                            # 날짜 형식 무관 중복 제거 (숫자만 비교)
                            key = f"{pr_n}_{clean_date_id(dt)}"
                            if key not in seen:
                                t_data.append({"보험사/상품명": nm, "보험료": f"{int(pr_n):,}원" if pr_n else pr, "계약일": dt})
                                seen.add(key)
                    if t_data: st.table(pd.DataFrame(t_data))
                
                # [수정 기능 복구]
                with st.form(f"edit_{idx}"):
                    st.write("✏️ **정보 수정**")
                    u1, u2 = st.columns(2)
                    up_jumin = u1.text_input("주민번호", value=row['주민번호'])
                    up_phone = u1.text_input("연락처", value=row['연락처'])
                    up_job = u2.text_input("직업", value=row['직업'])
                    up_addr = u2.text_input("주소", value=row['주소'])
                    up_memo = st.text_area("메모/병력", value=row['병력(특이사항)'])
                    if st.form_submit_button("✅ 변경 내용 저장"):
                        row_n = idx + 2
                        sheet_cust.update_cell(row_n, 3, up_jumin)
                        sheet_cust.update_cell(row_n, 4, up_phone)
                        sheet_cust.update_cell(row_n, 5, up_addr)
                        sheet_cust.update_cell(row_n, 6, up_job)
                        sheet_cust.update_cell(row_n, 7, up_memo)
                        st.success("수정되었습니다."); st.rerun()

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 수동 등록")
    with st.form("new_customer"):
        c1, c2 = st.columns(2)
        n_name = c1.text_input("이름")
        n_jumin = c1.text_input("주민번호 (예: 900101-1******)")
        n_phone = c2.text_input("연락처 (숫자만)")
        n_job = c2.text_input("직업")
        n_addr = st.text_input("주소")
        n_memo = st.text_area("특이사항/병력")
        if st.form_submit_button("👤 고객 등록"):
            if n_name and n_jumin:
                sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), n_name, n_jumin, n_phone, n_addr, n_job, n_memo, n_name])
                st.success("성공적으로 등록되었습니다."); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 관리 대장")
    if not db_cust.empty:
        list_df = db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '직업', '자동차만기일']].copy()
        list_df['연락처'] = list_df['연락처'].apply(format_phone)
        st.dataframe(list_df, use_container_width=True)

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 보험 갱신 정보 입력")
    # 차량/만기일 업데이트 로직 복구
    with st.form("car_update"):
        u_name = st.text_input("고객명")
        u_car = st.text_input("차량번호")
        u_ins = st.text_input("보험사")
        u_end = st.date_input("만기일")
        if st.form_submit_button("🚗 정보 업데이트"):
            match = db_cust[db_cust['이름'] == u_name]
            if not match.empty:
                r_idx = match.index[-1] + 2
                sheet_cust.update_cell(r_idx, 13, u_car)
                sheet_cust.update_cell(r_idx, 14, u_ins)
                sheet_cust.update_cell(r_idx, 15, str(u_end))
                st.success("자동차 정보가 업데이트되었습니다."); st.rerun()

elif menu == "📄 보장분석 업로드":
    st.subheader("📄 보장분석 리스트 텍스트 입력")
    st.info("보험사/상품명/보험료/날짜 형식으로 한 줄씩 입력하세요. | 기호로 구분됩니다.")
    target_name = st.text_input("대상 고객 성함")
    raw_text = st.text_area("보장분석 내용 붙여넣기")
    if st.button("📑 데이터 추가"):
        match = db_cust[db_cust['이름'] == target_name]
        if not match.empty:
            r_idx = match.index[-1] + 2
            old = match.iloc[-1]['병력(특이사항)']
            new_val = f"{old} | [보장분석] {raw_text}" if "[보장분석]" not in old else f"{old} | {raw_text}"
            sheet_cust.update_cell(r_idx, 7, new_val)
            st.success("내역이 추가되었습니다."); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 주요 보험사 청구 서류 안내")
    st.write("1. 공통서류: 진단서, 진료비상세내역서, 영수증")
    st.write("2. 각 보험사 콜센터:")
    st.code("삼성생명: 1588-3114\n라이나생명: 1588-0058\n메리츠화재: 1566-7711")
