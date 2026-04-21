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

# --- [2. PDF 보유계약 리스트 정밀 분석] ---
def parse_contract_list(file):
    results = []
    with pdfplumber.open(file) as pdf:
        target_pages = []
        # 1단계: '보유계약' 키워드가 있는 페이지 검색
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and ("보유계약" in text or "계약현황" in text or "보험료 납입" in text):
                target_pages.append(page)
        
        # 2단계: 해당 페이지에서 증권 리스트 추출
        for page in target_pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # 행 데이터 합치기
                    row_text = " ".join([str(item) for item in row if item])
                    # 날짜와 금액이 동시에 존재하는 '증권 라인'만 필터링
                    date_m = re.search(r'\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}', row_text)
                    price_m = re.search(r'[\d,]{3,}원?', row_text)
                    
                    if date_m and price_m:
                        dt = date_m.group()
                        pr = price_m.group()
                        # 리스트의 첫 번째 칸을 대개 보험사로 인식
                        comp = str(row[0]).split('\n')[0] if row[0] else "미확인"
                        prod = row_text.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                        results.append({"comp": comp, "prod": prod, "date": dt, "price": pr})
    return results

# --- [3. 메인 화면] ---
st.set_page_config(page_title="보장분석 시스템 v38.0", layout="wide")
sheet = get_gsheet()
if sheet:
    raw_data = sheet.get_all_values()
    headers = raw_data[0] if raw_data else []
    db_cust = pd.DataFrame(raw_data[1:], columns=headers) if len(raw_data) > 1 else pd.DataFrame()
    col_map = {col: i+1 for i, col in enumerate(headers)}

st.title("📄 보유계약 리스트 정밀 추출 및 전송")

# 열 번호 설정 (현우님 시트 구조에 맞게 수정 가능)
st.sidebar.header("⚙️ 시트 열 설정")
c_col = st.sidebar.number_input("보험사 열", value=9)
p_col = st.sidebar.number_input("상품명 열", value=10)
d_col = st.sidebar.number_input("가입날짜 열", value=11)
m_col = st.sidebar.number_input("금액 열", value=12)

target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else [])
up_file = st.file_uploader("PDF 업로드 (보유계약 페이지 포함 필수)", type="pdf")

if up_file and target != "선택":
    if st.button("🚀 보유계약만 추출해서 시트 전송"):
        items = parse_contract_list(up_file)
        if items:
            row_idx = db_cust[db_cust['이름'] == target].index[-1] + 2
            
            # 중복 제거 및 데이터 생성
            c_v = "\n".join([i['comp'] for i in items])
            p_v = "\n".join([i['prod'] for i in items])
            d_v = "\n".join([i['date'] for i in items])
            m_v = "\n".join([i['price'] for i in items])
            
            try:
                sheet.update_cell(row_idx, c_col, c_v)
                sheet.update_cell(row_idx, p_col, p_v)
                sheet.update_cell(row_idx, d_col, d_v)
                sheet.update_cell(row_idx, m_col, m_v)
                st.success(f"✅ {target}님 보유계약 {len(items)}건 추출 및 전송 완료!")
                st.table(pd.DataFrame(items)) # 화면에 확인용 리스트 출력
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
        else:
            st.error("❌ PDF 내에서 '보유계약 리스트' 패턴을 찾지 못했습니다.")
