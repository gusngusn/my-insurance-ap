import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pdfplumber

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
    except: return None

# --- [데이터 정제 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

def clean_date_id(date_val):
    return re.sub(r'[^0-9]', '', str(date_val))

# --- [2. 환경 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_values[1:], columns=cust_values[0]) if len(cust_values) > 1 else pd.DataFrame()

sales_values = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_values[1:], columns=sales_values[0]) if len(sales_values) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v15.0")

# --- [4. 메뉴별 상세 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
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
        this_m = datetime.now().strftime("%m")
        birth = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_m]
        if not birth.empty:
            for _, r in birth.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {format_phone(r['연락처'])}")
    with c2:
        st.subheader("🚘 자동차 보험 만기 (30일 내)")
        today = datetime.now()
        for _, r in db_cust.iterrows():
            m_date = str(r.get('자동차만기일', '')).replace('.', '-').strip()
            try:
                dt = datetime.strptime(m_date, "%Y-%m-%d")
                if today <= dt <= today + timedelta(days=30):
                    st.warning(f"⚠️ **{r['이름']}** : {m_date} ({r.get('차량번호','')})")
            except: pass

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 입력 및 자동 보장 연동")
    with st.form("sales_form"):
        c1, c2, c3, c4, c5 = st.columns(5)
        in_date = c1.date_input("계약일", datetime.now())
        in_name = c2.text_input("고객명")
        in_birth = c3.text_input("생일(6자리)")
        in_prod = c4.text_input("상품명")
        in_price = c5.text_input("보험료")
        if st.form_submit_button("🚀 저장 및 연동"):
            p_pure = re.sub(r'[^0-9]', '', in_price)
            sheet_sales.append_row([str(in_date), in_name, in_birth, in_prod, p_pure])
            match = db_cust[(db_cust['이름'] == in_name) & (db_cust['주민번호'].str.startswith(in_birth))]
            if not match.empty:
                row_idx = match.index[-1] + 2
                old = match.iloc[-1]['병력(특이사항)']
                entry = f"{in_prod}/{p_pure}/{in_date}"
                upd = f"{old} | [보장분석] {entry}" if "[보장분석]" not in old else f"{old} | {entry}"
                sheet_cust.update_cell(row_idx, 7, upd)
            st.success("등록 완료"); st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    s_name = st.text_input("이름 검색")
    if s_name:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                st.write(f"**🆔 주민번호:** {row['주민번호']} / **🛠️ 직업:** {row['직업']}")
                st.write(f"**🏠 주소:** {row['주소']}")
                if row.get('차량번호'):
                    st.info(f"🚘 **자동차:** {row['차량번호']} / {row.get('보험사','')} ({row.get('자동차만기일','')})")
                
                memo = row['병력(특이사항)']
                if "[보장분석]" in memo:
                    items = memo.split("[보장분석]")[-1].split("|")
                    t_data, seen = [], set()
                    for it in items:
                        p = [x.strip() for x in it.split("/") if x.strip()]
                        if len(p) >= 2:
                            dt, pr, nm = p[-1], p[-2] if len(p)>=3 else p[-1], "/".join(p[:-2]) if len(p)>=3 else p[0]
                            pr_n = re.sub(r'[^0-9]', '', pr)
                            key = f"{pr_n}_{clean_date_id(dt)}" # 날짜+금액 중복 제거
                            if key not in seen:
                                t_data.append({"상품명": nm, "보험료": f"{int(pr_n):,}원" if pr_n else pr, "날짜": dt})
                                seen.add(key)
                    if t_data: st.table(pd.DataFrame(t_data))
                
                with st.form(f"edit_{idx}"):
                    u_jumin = st.text_input("주민번호", value=row['주민번호'])
                    u_phone = st.text_input("연락처", value=row['연락처'])
                    u_addr = st.text_input("주소", value=row['주소'])
                    u_memo = st.text_area("메모", value=row['병력(특이사항)'])
                    if st.form_submit_button("✅ 수정 저장"):
                        row_n = idx + 2
                        sheet_cust.update_cell(row_n, 3, u_jumin)
                        sheet_cust.update_cell(row_n, 4, u_phone)
                        sheet_cust.update_cell(row_n, 5, u_addr)
                        sheet_cust.update_cell(row_n, 7, u_memo)
                        st.success("수정 완료"); st.rerun()

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 수동 등록")
    with st.form("new_cust"):
        c1, c2 = st.columns(2)
        n_name, n_jumin = c1.text_input("이름"), c1.text_input("주민번호")
        n_phone, n_job = c2.text_input("연락처"), c2.text_input("직업")
        n_addr = st.text_input("주소")
        if st.form_submit_button("👤 등록"):
            sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), n_name, n_jumin, n_phone, n_addr, n_job, "", n_name])
            st.success("등록 완료"); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트 (30명씩)")
    p_size = 30
    t_pages = (len(db_cust) // p_size) + (1 if len(db_cust) % p_size > 0 else 0)
    curr_p = st.selectbox("페이지 선택", range(1, t_pages + 1)) if t_pages > 0 else 1
    start_idx = (curr_p - 1) * p_size
    st.table(db_cust[['이름', '주민번호', '연락처', '주소', '직업', '자동차만기일']].iloc[start_idx : start_idx + p_size])

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    with st.form("car_form"):
        target = st.text_input("고객명")
        c_num, c_ins, c_date = st.text_input("차량번호"), st.text_input("보험사"), st.date_input("만기일")
        if st.form_submit_button("🚗 업데이트"):
            match = db_cust[db_cust['이름'] == target]
            if not match.empty:
                r_n = match.index[-1] + 2
                sheet_cust.update_cell(r_n, 13, c_num); sheet_cust.update_cell(r_n, 14, c_ins); sheet_cust.update_cell(r_n, 15, str(c_date))
                st.success("반영 완료"); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    st.subheader("📄 PDF 보장분석 자동 리스트업")
    up_file = st.file_uploader("PDF 업로드", type="pdf")
    target_name = st.text_input("고객명 입력")
    if up_file and target_name and st.button("분석 및 저장"):
        with pdfplumber.open(up_file) as pdf:
            text = "".join([page.extract_text() for page in pdf.pages])
        match = db_cust[db_cust['이름'] == target_name]
        if not match.empty:
            r_n, old = match.index[-1] + 2, match.iloc[-1]['병력(특이사항)']
            sheet_cust.update_cell(r_n, 7, f"{old} | [보장분석] PDF추출내용: {text[:300]}")
            st.success("분석 저장 완료"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 전 보험사 청구 링크")
    c1, c2, c3 = st.columns(3)
    # 손보사
    c1.markdown("**[손해보험]**\n\n[삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html)\n[현대해상](https://www.hi.co.kr/service/claim/guide/form.do)\n[DB손보](https://www.idbins.com/FWCRRE1001.do)\n[KB손보](https://www.kbinsure.co.kr/CG302010001.ec)\n[메리츠](https://www.meritzfire.com/compensation/guide/claim-guide.do)\n[한화손보](https://www.hwgeneralins.com/compensation/guide/form-download.do)\n[흥국화재](https://www.heungkukfire.co.kr/main/compensation/guide/compensationGuide.do)\n[롯데손보](https://www.lotteins.co.kr/web/CST/CLM/GLD/cstClmGld01.jsp)")
    # 생보사 1
    c2.markdown("**[생명보험 1]**\n\n[삼성생명](https://www.samsunglife.com/customer/claim/reward/reward_01.html)\n[한화생명](https://www.hanwhalife.com/static/service/customer/claim/reward/reward_01.html)\n[교보생명](https://www.kyobo.com/webdoc/customer/claim/reward/reward_01.html)\n[신한라이프](https://www.shinhanlife.co.kr/hp/cd/cd010101.do)\n[흥국생명](https://www.heungkuklife.co.kr/customer/claim/reward/reward_01.html)\n[동양생명](https://www.myangel.co.kr/customer/claim/reward/reward_01.html)")
    # 생보사 2/기타
    c3.markdown("**[생명보험 2 / 공제]**\n\n[라이나](https://www.lina.co.kr/customer/claim/reward/reward_01.html)\n[AIA생명](https://www.aia.co.kr/ko/customer-service/claim/guide.html)\n[미래에셋](https://life.miraeasset.com/customer/claim/reward/reward_01.html)\n[DB생명](https://www.idblife.com/customer/claim/reward/reward_01.html)\n[우체국보험](https://www.epostbank.go.kr/claim/reward/reward_01.html)\n[새마을금고](https://insu.kfcc.co.kr/customer/claim/guide.do)")
