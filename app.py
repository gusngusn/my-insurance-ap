import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber

# --- [1. 구글 시트 연결] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except: return None

# --- [2. PDF 정밀 분석] ---
def parse_pdf(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                date_m = re.search(r'\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}', line)
                price_m = re.search(r'[\d,]{2,}원|[\d,]{1,5}만\s?원', line)
                if date_m and price_m:
                    dt, pr = date_m.group(), price_m.group()
                    comp = line.split()[0]
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"comp": comp, "prod": prod, "date": dt, "price": pr})
    return results

# --- [3. 메인 화면] ---
st.set_page_config(page_title="보장분석 시스템 v37.0", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    db_cust = pd.DataFrame(raw_data[1:], columns=raw_data[0]) if raw_data else pd.DataFrame()

st.title("📄 보장분석 PDF 데이터 직접 전송")

# 열 번호 수동 설정 (A=1, B=2, C=3...)
st.info("💡 시트의 열 번호를 숫자로 입력해주세요 (예: A열이면 1, J열이면 10)")
c1, c2, c3, c4 = st.columns(4)
with c1: col_comp = st.number_input("보험사 열 번호", min_value=1, value=9)
with c2: col_prod = st.number_input("상품명 열 번호", min_value=1, value=10)
with c3: col_date = st.number_input("가입날짜 열 번호", min_value=1, value=11)
with c4: col_price = st.number_input("금액 열 번호", min_value=1, value=12)

st.markdown("---")

target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else [])
up_file = st.file_uploader("PDF 업로드", type="pdf")

if up_file and target != "선택":
    if st.button("🚀 데이터 분석 및 강제 전송"):
        items = parse_pdf(up_file)
        if items:
            # 해당 고객의 행(Row) 찾기
            row_idx = db_cust[db_cust['이름'] == target].index[-1] + 2
            
            # 데이터 합치기
            c_v = "\n".join([i['comp'] for i in items])
            p_v = "\n".join([i['prod'] for i in items])
            d_v = "\n".join([i['date'] for i in items])
            m_v = "\n".join([i['price'] for i in items])
            
            # 입력된 열 번호에 강제로 업데이트
            try:
                sheet.update_cell(row_idx, col_comp, c_v)
                sheet.update_cell(row_idx, col_prod, p_v)
                sheet.update_cell(row_idx, col_date, d_v)
                sheet.update_cell(row_idx, col_price, m_v)
                st.success(f"✅ {target}님 데이터 전송 성공!")
            except Exception as e:
                st.error(f"❌ 전송 실패: {e}")
        else:
            st.error("❌ PDF에서 데이터를 추출하지 못했습니다.")
