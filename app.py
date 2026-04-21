import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
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

# --- [데이터 정제 및 PDF 분석 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

def clean_date_id(date_val):
    return re.sub(r'[^0-9]', '', str(date_val))

def analyze_and_classify_pdf(file):
    classified_data = {"암": [], "뇌": [], "심": [], "수술": []}
    with pdfplumber.open(file) as pdf:
        text = "".join([page.extract_text() for page in pdf.pages])
        lines = text.split('\n')
        for line in lines:
            if re.search(r'\d{1,3}(,\d{3})*원?', line) and re.search(r'\d{4}[.\-]\d{2}', line):
                clean_line = re.sub(r'\s+', ' ', line).strip()
                # 키워드별 담보 분류
                if any(k in clean_line for k in ["암", "표적", "항암"]): classified_data["암"].append(clean_line)
                elif any(k in clean_line for k in ["뇌", "혈관", "졸중"]): classified_data["뇌"].append(clean_line)
                elif any(k in clean_line for k in ["심", "심장", "허혈", "심근"]): classified_data["심"].append(clean_line)
                elif any(k in clean_line for k in ["수술", "종수술", "수술비"]): classified_data["수술"].append(clean_line)
    return classified_data

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
headers = cust_values[0] if cust_values else []
db_cust = pd.DataFrame(cust_values[1:], columns=headers) if len(cust_values) > 1 else pd.DataFrame()
col_map = {col: i+1 for i, col in enumerate(headers)}

sales_values = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_values[1:], columns=sales_values[0]) if len(sales_values) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴 (전체 복구)] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 가이드"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v18.1")

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
        st.subheader("🎂 이번 달 생일")
        this_m_str = datetime.now().strftime("%m")
        birth = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_m_str] if not db_cust.empty else []
        for _, r in birth.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]})")
    with c2:
        st.subheader("🚘 자동차 보험 만기 (30일 내)")
        today = datetime.now()
        for _, r in db_cust.iterrows():
            m_date = str(r.get('자동차만기일', '')).replace('.', '-').strip()
            try:
                dt = datetime.strptime(m_date, "%Y-%m-%d")
                if today <= dt <= today + timedelta(days=30): st.warning(f"⚠️ **{r['이름']}** : {m_date}")
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
            st.success("실적 저장 완료"); st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    s_name = st.text_input("이름 검색")
    if s_name and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                st.write(f"**🆔 주민번호:** {row['주민번호']} / **🛠️ 직업:** {row['직업']}")
                st.write(f"**🏠 주소:** {row['주소']}")
                if row.get('차량번호'):
                    st.info(f"🚘 **자동차:** {row['차량번호']} / {row.get('보험사','')} ({row.get('자동차만기일','')})")
                
                st.markdown("### 📊 담보별 가입 내역")
                tab_data = []
                for cat in ["암", "뇌", "심", "수술"]:
                    content = row.get(cat, "").strip()
                    if content:
                        for line in content.split('\n'):
                            tab_data.append({"구분": cat, "상세 내역": line})
                if tab_data: st.table(pd.DataFrame(tab_data))
                else: st.write("등록된 보장 내역이 없습니다.")
                
                with st.form(f"edit_{idx}"):
                    u_jumin = st.text_input("주민번호", value=row['주민번호'])
                    u_phone = st.text_input("연락처", value=row['연락처'])
                    u_addr = st.text_input("주소", value=row['주소'])
                    u_memo = st.text_area("특이사항/메모", value=row['병력(특이사항)'])
                    if st.form_submit_button("✅ 정보 수정 저장"):
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
    st.subheader("📑 고객 리스트 (30명씩)")
    if not db_cust.empty:
        p_size = 30
        t_pages = (len(db_cust) // p_size) + (1 if len(db_cust) % p_size > 0 else 0)
        curr_p = st.selectbox("페이지 선택", range(1, t_pages + 1))
        start_idx = (curr_p - 1) * p_size
        st.table(db_cust[['이름', '주민번호', '연락처', '직업', '자동차만기일']].iloc[start_idx : start_idx + p_size])

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    with st.form("car_up"):
        target = st.text_input("고객명")
        c_num, c_ins, c_date = st.text_input("차량번호"), st.text_input("보험사"), st.date_input("만기일")
        if st.form_submit_button("🚗 반영"):
            match = db_cust[db_cust['이름'] == target]
            if not match.empty:
                r_n = match.index[-1] + 2
                sheet_cust.update_cell(r_n, 13, c_num); sheet_cust.update_cell(r_n, 14, c_ins); sheet_cust.update_cell(r_n, 15, str(c_date))
                st.success("업데이트 완료"); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    st.subheader("📄 PDF 보장분석 담보별 자동 분류")
    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("PDF 업로드", type="pdf")
    if up_file and target_name != "선택" and st.button("🚀 분석 및 담보별 셀 입력"):
        results = analyze_and_classify_pdf(up_file)
        match = db_cust[db_cust['이름'] == target_name]
        row_idx = match.index[-1] + 2
        for cat, items in results.items():
            if items:
                new_entry = "\n".join(items)
                col_idx = col_map.get(cat)
                if col_idx:
                    curr_val = sheet_cust.cell(row_idx, col_idx).value or ""
                    final_val = f"{curr_val}\n{new_entry}".strip()
                    sheet_cust.update_cell(row_idx, col_idx, final_val)
        st.success("분석 결과가 담보별 셀에 줄바꿈으로 저장되었습니다."); st.rerun()

elif menu == "🏥 보험청구 가이드":
    st.subheader("🏥 보험금 청구 서류 및 링크")
    st.code("[보험금 청구 안내]\n\n✅ 공통: 영수증, 진료비세부내역서\n✅ 입원: 입퇴원확인서, 진단서\n✅ 수술: 수술확인서", language=None)
    st.markdown("[삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html) | [현대해상](https://www.hi.co.kr/service/claim/guide/form.do) | [DB손보](https://www.idbins.com/FWCRRE1001.do)")
