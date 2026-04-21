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

# --- [PDF 정밀 파싱 함수: 회사/상품/날짜/금액 추출] ---
def parse_pdf_to_details(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            for line in lines:
                # 날짜(0000.00.00)와 금액(원) 패턴이 있는 행 위주로 파싱
                date_match = re.search(r'\d{4}[.\-]\d{2}[.\-]\d{2}', line)
                price_match = re.search(r'\d{1,3}(,\d{3})*원?', line)
                
                if date_match and price_match:
                    # 간단한 예시 파싱 로직 (실제 PDF 구조에 따라 슬라이싱 필요)
                    parts = line.split()
                    company = parts[0] if len(parts) > 0 else "미확인"
                    date = date_match.group()
                    price = price_match.group()
                    # 회사명과 날짜/금액을 제외한 나머지를 상품명으로 간주
                    product = line.replace(company, "").replace(date, "").replace(price, "").strip()
                    results.append({"회사": company, "상품": product, "날짜": date, "금액": price})
    return results

# --- [2. 메인 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 v19.0", layout="wide")
sheet_cust = get_gsheet(0)
values = sheet_cust.get_all_values() if sheet_cust else []
headers = values[0] if values else []
db_cust = pd.DataFrame(values[1:], columns=headers) if len(values) > 1 else pd.DataFrame()
col_map = {col: i+1 for i, col in enumerate(headers)}

# --- [3. 사이드바 메뉴 (전체 복구)] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 가이드"])

# --- [4. 보장분석 PDF 업로드 (셀별 줄바꿈 입력)] ---
if menu == "📄 보장분석 PDF 업로드":
    st.subheader("📄 PDF 데이터 -> 시트 개별 셀 자동 입력")
    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("보장분석 PDF 업로드", type="pdf")
    
    if up_file and target_name != "선택" and st.button("🚀 시트 셀별 자동 입력"):
        parsed_items = parse_pdf_to_details(up_file)
        if parsed_items:
            match = db_cust[db_cust['이름'] == target_name]
            row_idx = match.index[-1] + 2
            
            # 각 항목별로 줄바꿈 문자(\n)로 합치기
            companies = "\n".join([item['회사'] for item in parsed_items])
            products = "\n".join([item['상품'] for item in parsed_items])
            dates = "\n".join([item['날짜'] for item in parsed_items])
            prices = "\n".join([item['금액'] for item in parsed_items])
            
            # 시트의 해당 셀 위치에 맞춰 업데이트 (헤더 명칭 기준)
            if "보험사" in col_map: sheet_cust.update_cell(row_idx, col_map["보험사"], companies)
            if "상품명" in col_map: sheet_cust.update_cell(row_idx, col_map["상품명"], products)
            if "가입날짜" in col_map: sheet_cust.update_cell(row_idx, col_map["가입날짜"], dates)
            if "금액" in col_map: sheet_cust.update_cell(row_idx, col_map["금액"], prices)
            
            st.success("✅ 보험사, 상품명, 가입날짜, 금액 셀에 각각 줄바꿈으로 입력되었습니다."); st.rerun()

# --- [5. 고객조회 (리스트 형식 출력)] ---
elif menu == "🔍 고객조회/수정":
    s_name = st.text_input("고객명 검색")
    if s_name and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} 상세 정보", expanded=True):
                # 개별 셀에 줄바꿈으로 들어있는 데이터를 리스트로 다시 합침
                st.markdown("### 📋 보유 계약 리스트")
                comp_list = str(row.get('보험사', '')).split('\n')
                prod_list = str(row.get('상품명', '')).split('\n')
                date_list = str(row.get('가입날짜', '')).split('\n')
                price_list = str(row.get('금액', '')).split('\n')
                
                # 리스트 길이 맞추기 및 데이터프레임 생성
                max_len = max(len(comp_list), len(prod_list), len(date_list), len(price_list))
                table_rows = []
                for i in range(max_len):
                    table_rows.append({
                        "보험사": comp_list[i] if i < len(comp_list) else "",
                        "상품명": prod_list[i] if i < len(prod_list) else "",
                        "가입날짜": date_list[i] if i < len(date_list) else "",
                        "금액": price_list[i] if i < len(price_list) else ""
                    })
                
                if any(r['보험사'] for r in table_rows):
                    st.table(pd.DataFrame(table_rows))
                else:
                    st.info("등록된 계약 내역이 없습니다.")
                
                # ... (이하 수정 폼 및 나머지 로직 유지)
