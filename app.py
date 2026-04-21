import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime
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

# --- [2. PDF 분석 및 카테고리 분류 함수] ---
def analyze_and_classify_pdf(file):
    # 결과를 담을 딕셔너리 (현우님 시트 컬럼명과 매칭)
    classified_data = {
        "암": [],
        "뇌": [],
        "심": [],
        "수술": []
    }
    
    with pdfplumber.open(file) as pdf:
        text = "".join([page.extract_text() for page in pdf.pages])
        lines = text.split('\n')
        
        for line in lines:
            # 기본 데이터 추출 (보험사/상품명/금액/날짜 패턴 검색)
            # 예: 삼성화재 무배당 건강보험 50,000 2024.01.01
            if re.search(r'\d{1,3}(,\d{3})*원?', line) and re.search(r'\d{4}[.\-]\d{2}', line):
                clean_line = re.sub(r'\s+', ' ', line).strip()
                
                # 키워드 기반 카테고리 자동 분류
                if any(k in clean_line for k in ["암", "표적", "항암"]):
                    classified_data["암"].append(clean_line)
                elif any(k in clean_line for k in ["뇌", "혈관", "졸중"]):
                    classified_data["뇌"].append(clean_line)
                elif any(k in clean_line for k in ["심", "심장", "허혈", "심근"]):
                    classified_data["심"].append(clean_line)
                elif any(k in clean_line for k in ["수술", "종수술", "수술비"]):
                    classified_data["수술"].append(clean_line)
                # 분류되지 않은 데이터는 기본 '암' 또는 기타 로그로 처리 가능
    
    return classified_data

# --- [3. 메인 UI 및 로직] ---
st.set_page_config(page_title="배현우 성과관리 시스템 v18.0", layout="wide")
sheet_cust = get_gsheet(0)
values = sheet_cust.get_all_values()
headers = values[0]
db_cust = pd.DataFrame(values[1:], columns=headers)

# 컬럼 인덱스 확인 (암:9, 뇌:10, 심:11, 수술:12 번째 열 가정 - 시트 상황에 맞게 자동 매칭)
col_map = {col: i+1 for i, col in enumerate(headers)}

menu = st.sidebar.radio("메뉴", ["🔍 고객조회", "📄 보장분석 PDF 업로드"])

if menu == "📄 보장분석 PDF 업로드":
    st.subheader("📄 보장분석 PDF 담보별 자동 분류 입력")
    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("PDF 업로드", type="pdf")
    
    if up_file and target_name != "선택" and st.button("🚀 분석 및 해당 셀 입력"):
        results = analyze_and_classify_pdf(up_file)
        match = db_cust[db_cust['이름'] == target_name]
        row_idx = match.index[-1] + 2
        
        # 각 카테고리별로 시트 업데이트
        for category, items in results.items():
            if items:
                # 줄바꿈(\n)으로 상품 구분하여 텍스트 생성
                new_entry = "\n".join(items)
                col_idx = col_map.get(category)
                if col_idx:
                    # 기존 데이터 확인 후 추가 (또는 덮어쓰기 선택 가능)
                    current_val = sheet_cust.cell(row_idx, col_idx).value or ""
                    final_val = f"{current_val}\n{new_entry}".strip()
                    sheet_cust.update_cell(row_idx, col_idx, final_val)
        
        st.success("✅ 암/뇌/심/수술 각 항목별 셀에 상품 정보가 자동으로 분류되어 저장되었습니다."); st.rerun()

elif menu == "🔍 고객조회":
    search = st.text_input("고객명 검색")
    if search:
        res = db_cust[db_cust['이름'].str.contains(search)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} 보장내역 상세"):
                # 각 셀의 데이터를 표로 시각화
                st.write("### 📊 보장 항목별 리스트")
                display_data = {
                    "구분": ["암", "뇌", "심", "수술"],
                    "가입 내역": [row.get('암', ''), row.get('뇌', ''), row.get('심', ''), row.get('수술', '')]
                }
                st.table(pd.DataFrame(display_data))
