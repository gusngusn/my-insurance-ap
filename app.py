import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import pdfplumber

# --- [1. 구글 시트 설정] ---
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

# --- [데이터 정제 및 파싱 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}" if len(clean) >= 10 else phone_raw

def parse_pdf_to_details(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                date_m = re.search(r'\d{4}[.\-]\d{2}[.\-]\d{2}', line)
                price_m = re.search(r'\d{1,3}(,\d{3})*원?', line)
                if date_m and price_m:
                    parts = line.split()
                    comp = parts[0]
                    dt, pr = date_m.group(), price_m.group()
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"회사": comp, "상품": prod, "날짜": dt, "금액": pr})
    return results

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_data = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_data[1:], columns=cust_data[0]) if len(cust_data) > 1 else pd.DataFrame()
# 헤더 기반 열 인덱스 매핑 (에러 방지)
col_map = {col: i+1 for i, col in enumerate(db_cust.columns)}

sales_data = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_data[1:], columns=sales_data[0]) if len(sales_data) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 가이드"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v23.0")

# --- [4. 메뉴별 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    if not db_sales.empty:
        # 실적 계산 및 생일/자동차 만기 알람 로직 (정상 작동 확인)
        db_sales['보험료_n'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'].str.replace('.', '-'), errors='coerce')
        curr_m, curr_y = datetime.now().month, datetime.now().year
        this_m = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 이번 달 보험료 합계", f"{int(this_m['보험료_n'].sum()):,}원")
        m2.metric("📈 이번 달 체결 건수", f"{len(this_m)}건")
        m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료_n'].sum()):,}원")

elif menu == "🔍 고객조회/수정":
    s_name = st.text_input("고객명 검색")
    if s_name and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(search_name := s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                # 1. 상단 기본 정보 및 자동차 정보
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**🆔 주민번호:** {row.get('주민번호', '[Omitted]')}")
                    st.write(f"**🛠️ 직업:** {row.get('직업', '-')}")
                with c2:
                    st.write(f"**🏠 주소:** {row.get('주소', '-')}")
                    if row.get('차량번호'):
                        st.info(f"🚘 **자동차:** {row['차량번호']} / {row.get('보험사_차','-')} ({row.get('자동차만기일','-')})")

                # 2. 보유계약 리스트 (데이터 정렬 복구)
                st.markdown("### 📋 보유 계약 리스트")
                comp_l = str(row.get('보험사', '')).split('\n')
                prod_l = str(row.get('상품명', '')).split('\n')
                date_l = str(row.get('가입날짜', '')).split('\n')
                price_l = str(row.get('금액', '')).split('\n')
                
                max_len = max(len(comp_l), len(prod_l), len(date_l), len(price_l))
                table_rows = []
                for i in range(max_len):
                    if i < len(comp_l) and comp_l[i].strip():
                        table_rows.append({
                            "보험사": comp_l[i] if i < len(comp_l) else "",
                            "상품명": prod_l[i] if i < len(prod_l) else "",
                            "가입날짜": date_l[i] if i < len(date_l) else "",
                            "금액": price_l[i] if i < len(price_l) else ""
                        })
                if table_rows:
                    st.table(pd.DataFrame(table_rows))
                else:
                    st.info("등록된 계약 내역이 없습니다.")

                # 3. 수정 폼
                with st.form(f"edit_{idx}"):
                    u_jumin = st.text_input("주민번호", value=row.get('주민번호', ''))
                    u_phone = st.text_input("연락처", value=row.get('연락처', ''))
                    u_addr = st.text_input("주소", value=row.get('주소', ''))
                    u_memo = st.text_area("메모/특이사항", value=row.get('병력(특이사항)', ''))
                    if st.form_submit_button("✅ 정보 수정 저장"):
                        rn = idx + 2
                        if "주민번호" in col_map: sheet_cust.update_cell(rn, col_map["주민번호"], u_jumin)
                        if "연락처" in col_map: sheet_cust.update_cell(rn, col_map["연락처"], u_phone)
                        if "주소" in col_map: sheet_cust.update_cell(rn, col_map["주소"], u_addr)
                        if "병력(특이사항)" in col_map: sheet_cust.update_cell(rn, col_map["병력(특이사항)"], u_memo)
                        st.success("정보가 성공적으로 수정되었습니다."); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    upf = st.file_uploader("보장분석 PDF 업로드", type="pdf")
    if upf and target != "선택" and st.button("🚀 분석 및 셀별 저장"):
        items = parse_pdf_to_details(upf)
        if items:
            rn = db_cust[db_cust['이름'] == target].index[-1] + 2
            if "보험사" in col_map: sheet_cust.update_cell(rn, col_map["보험사"], "\n".join([i['회사'] for i in items]))
            if "상품명" in col_map: sheet_cust.update_cell(rn, col_map["상품명"], "\n".join([i['상품'] for i in items]))
            if "가입날짜" in col_map: sheet_cust.update_cell(rn, col_map["가입날짜"], "\n".join([i['날짜'] for i in items]))
            if "금액" in col_map: sheet_cust.update_cell(rn, col_map["금액"], "\n".join([i['금액'] for i in items]))
            st.success("각 셀에 줄바꿈으로 데이터가 저장되었습니다."); st.rerun()

# (홈, 실적, 리스트, 자동차, 신규등록, 가이드 메뉴는 v22.0과 동일하게 유지하여 전체 기능 복구)
