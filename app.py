import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime  # <-- 에러의 원인이었던 이 부분을 확실히 추가했습니다.

# --- [1. 구글 시트 연결 설정] ---
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

# --- [2. PDF 분석 함수] ---
def parse_pdf(file):
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
                    results.append({"보험사": comp, "상품명": prod, "가입날짜": dt, "금액": pr})
    return results

# --- [3. 초기 세팅] ---
st.set_page_config(page_title="FC 관리 시스템", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    headers = raw_data[0] if raw_data else []
    db_cust = pd.DataFrame(raw_data[1:], columns=headers) if len(raw_data) > 1 else pd.DataFrame(columns=headers)
    col_map = {col: i+1 for i, col in enumerate(headers)}
else:
    st.error("시트에 연결할 수 없습니다.")
    st.stop()

# --- [4. 좌측 사이드바 버튼] ---
with st.sidebar:
    st.header("메뉴")
    if st.button("👥 고객정보 관리", use_container_width=True):
        st.session_state.menu = "customer_info"
    if st.button("📄 보장분석 업로드", use_container_width=True):
        st.session_state.menu = "insurance_analysis"

# --- [5. 메뉴별 메인 화면] ---

# (1) 고객정보 관리 메뉴
if "menu" in st.session_state and st.session_state.menu == "customer_info":
    st.title("👤 고객정보 조회 및 등록")
    search_name = st.text_input("조회할 고객 이름을 입력하세요")
    
    if search_name:
        result = db_cust[db_cust['이름'] == search_name]
        if not result.empty:
            st.subheader(f"✅ '{search_name}' 고객 정보")
            st.table(result)
        else:
            st.warning(f"'{search_name}' 이름으로 등록된 고객이 없습니다.")
            st.markdown("---")
            st.subheader("🆕 신규 고객 등록")
            with st.form("new_customer_form"):
                new_name = st.text_input("이름", value=search_name)
                new_jumin = st.text_input("주민번호")
                new_phone = st.text_input("연락처")
                new_addr = st.text_input("주소")
                new_job = st.text_input("직업")
                if st.form_submit_button("등록하기"):
                    if new_name and new_jumin:
                        # 등록일 포함하여 데이터 추가
                        sheet.append_row([datetime.now().strftime("%Y-%m-%d"), new_name, new_jumin, new_phone, new_addr, new_job])
                        st.success(f"{new_name} 고객님이 등록되었습니다."); st.rerun()

# (2) 보장분석 업로드 메뉴
elif "menu" in st.session_state and st.session_state.menu == "insurance_analysis":
    st.title("📄 보장분석 PDF 자동 입력")
    target = st.selectbox("대상 고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("PDF 업로드", type="pdf")

    if up_file and target != "선택":
        if st.button("🚀 데이터 분석 및 시트 전송"):
            items = parse_pdf(up_file)
            if items:
                idx = db_cust[db_cust['이름'] == target].index[-1] + 2
                c_v = "\n".join([i['보험사'] for i in items])
                p_v = "\n".join([i['상품명'] for i in items])
                d_v = "\n".join([i['가입날짜'] for i in items])
                m_v = "\n".join([i['금액'] for i in items])
                
                if "보험사" in col_map: sheet.update_cell(idx, col_map["보험사"], c_v)
                if "상품명" in col_map: sheet.update_cell(idx, col_map["상품명"], p_v)
                if "가입날짜" in col_map: sheet.update_cell(idx, col_map["가입날짜"], d_v)
                if "금액" in col_map: sheet.update_cell(idx, col_map["금액"], m_v)
                st.success(f"✅ {target}님 보장 내역 업데이트 완료!"); st.rerun()

else:
    st.title("🛡️ 배현우 FC 관리 시스템")
    st.info("좌측 메뉴에서 [고객정보 관리] 또는 [보장분석 업로드]를 선택해 주세요.")
