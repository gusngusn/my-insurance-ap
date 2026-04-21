import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- [1. 구글 시트 연결 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).worksheets()[index]
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
                    results.append([dt, comp, prod, pr]) # 가입날짜, 보험사, 상품명, 금액 순
    return results

# --- [3. 초기 세팅] ---
st.set_page_config(page_title="고객 보장분석 시스템", layout="wide")
sheet_cust = get_gsheet(0)  # 1번째 시트: 고객정보
sheet_analysis = get_gsheet(1) # 2번째 시트: 보장분석데이터

# 데이터 불러오기
if sheet_cust and sheet_analysis:
    cust_raw = sheet_cust.get_all_values()
    db_cust = pd.DataFrame(cust_raw[1:], columns=cust_raw[0]) if len(cust_raw) > 1 else pd.DataFrame()
    
    analysis_raw = sheet_analysis.get_all_values()
    db_analysis = pd.DataFrame(analysis_raw[1:], columns=analysis_raw[0]) if len(analysis_raw) > 1 else pd.DataFrame(columns=["가입날짜", "보험회사", "상품명", "금액", "고객명"])
else:
    st.error("시트 연결에 실패했습니다.")
    st.stop()

# --- [4. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴")
    menu = st.radio("이동할 메뉴 선택", ["👤 고객정보 및 내역조회", "📄 보장분석 파일업로드"])

# --- [5. 메인 화면 로직] ---

# (1) 고객정보 및 내역조회
if menu == "👤 고객정보 및 내역조회":
    st.title("👤 고객 상세 정보 조회")
    search_name = st.text_input("고객 이름을 입력하세요")
    
    if search_name:
        cust_info = db_cust[db_cust['이름'] == search_name]
        if not cust_info.empty:
            st.subheader(f"✅ {search_name} 고객님 기본 정보")
            st.table(cust_info)
            
            st.markdown("---")
            st.subheader(f"📑 {search_name} 고객님 보험 가입 리스트")
            # 2번째 시트 데이터에서 해당 고객 이름으로 필터링
            personal_list = db_analysis[db_analysis['고객명'] == search_name]
            
            if not personal_list.empty:
                st.dataframe(personal_list[["가입날짜", "보험회사", "상품명", "금액"]], use_container_width=True)
            else:
                st.info("등록된 보험 내역이 없습니다. PDF를 업로드해 주세요.")
        else:
            st.warning("등록되지 않은 고객입니다.")

# (2) 보장분석 파일업로드
elif menu == "📄 보장분석 파일업로드":
    st.title("📄 PDF 보장분석 데이터 입력")
    target_user = st.selectbox("데이터를 입력할 고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    pdf_file = st.file_uploader("보장분석 PDF 업로드", type="pdf")
    
    if pdf_file and target_user != "선택":
        if st.button("🚀 분석 데이터 시트 저장"):
            with st.spinner("데이터 분석 중..."):
                extracted_items = parse_pdf(pdf_file)
                if extracted_items:
                    # 2번째 시트(보장분석시트)에 각 행별로 추가 (마지막 열에 고객명 추가)
                    for item in extracted_items:
                        item.append(target_user) # [날짜, 회사, 상품, 금액, 고객명]
                        sheet_analysis.append_row(item)
                    
                    st.success(f"✅ {target_user}님의 데이터 {len(extracted_items)}건이 2번째 시트에 저장되었습니다!")
                    st.balloons()
                else:
                    st.error("PDF에서 데이터를 추출하지 못했습니다.")
