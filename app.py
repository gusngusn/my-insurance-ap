import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- [1. 구글 시트 연결 및 검증] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        st.error(f"❌ 시트 연결 실패: {e}")
        return None

# --- [2. PDF 분석 (정규식 강화)] ---
def parse_pdf(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            for line in lines:
                # 날짜 및 금액 패턴 (더 유연하게 수정)
                date_m = re.search(r'\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}', line)
                price_m = re.search(r'[\d,]{2,}원|[\d,]{1,5}만\s?원', line)
                
                if date_m and price_m:
                    dt, pr = date_m.group(), price_m.group()
                    parts = line.split()
                    comp = parts[0] if parts else "미확인"
                    # 상품명 추출 로직 개선
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"보험사": comp, "상품명": prod, "가입날짜": dt, "금액": pr})
    return results

# --- [3. 메인 로직] ---
st.set_page_config(page_title="배현우 FC 시스템 v35.0", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    if raw_data:
        headers = [h.strip() for h in raw_data[0]] # 공백 제거
        db_cust = pd.DataFrame(raw_data[1:], columns=headers)
        col_map = {col: i+1 for i, col in enumerate(headers)}
    else:
        st.error("시트에 헤더 정보가 없습니다.")
        st.stop()

# 메뉴 구성
menu = st.sidebar.radio("작업 선택", ["📄 보장분석 업로드", "🔍 고객정보 조회"])

if menu == "📄 보장분석 업로드":
    st.title("📄 보장분석 PDF 전송 테스트")
    
    # 디버깅 정보 (현재 시트에서 인식된 컬럼명 보여주기)
    with st.expander("📌 시트 컬럼 인식 상태 확인 (문제가 있다면 여기를 확인하세요)"):
        st.write("인식된 컬럼명:", list(col_map.keys()))
        check_cols = ["보험사", "상품명", "가입날짜", "금액"]
        for c in check_cols:
            if c in col_map: st.success(f"'{c}' 컬럼 확인됨")
            else: st.error(f"'{c}' 컬럼을 찾을 수 없음 (시트의 제목을 확인하세요)")

    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("보장분석 PDF 파일 선택", type="pdf")

    if up_file and target_name != "선택":
        if st.button("🚀 분석 및 시트 전송 시작"):
            with st.spinner("PDF 분석 중..."):
                items = parse_pdf(up_file)
                
                if not items:
                    st.error("❌ PDF에서 날짜와 금액 정보를 추출하지 못했습니다. 파일 내용이 텍스트 형식이 맞는지 확인해주세요.")
                else:
                    st.info(f"📋 {len(items)}건의 데이터를 찾았습니다. 전송을 시도합니다.")
                    
                    target_row_idx = db_cust[db_cust['이름'] == target_name].index[-1] + 2
                    
                    # 데이터 병합 (줄바꿈)
                    new_comp = "\n".join([i['보험사'] for i in items])
                    new_prod = "\n".join([i['상품명'] for i in items])
                    new_date = "\n".join([i['가입날짜'] for i in items])
                    new_price = "\n".join([i['금액'] for i in items])
                    
                    # 실제 시트 업데이트 로직
                    try:
                        success_count = 0
                        if "보험사" in col_map: 
                            sheet.update_cell(target_row_idx, col_map["보험사"], new_comp)
                            success_count += 1
                        if "상품명" in col_map: 
                            sheet.update_cell(target_row_idx, col_map["상품명"], new_prod)
                            success_count += 1
                        if "가입날짜" in col_map: 
                            sheet.update_cell(target_row_idx, col_map["가입날짜"], new_date)
                            success_count += 1
                        if "금액" in col_map: 
                            sheet.update_cell(target_row_idx, col_map["금액"], new_price)
                            success_count += 1
                        
                        if success_count > 0:
                            st.success(f"✅ {target_name} 고객님의 {success_count}개 항목 셀 업데이트 완료!")
                            st.balloons()
                        else:
                            st.error("⚠️ 시트의 컬럼명(보험사, 상품명 등)이 일치하지 않아 입력에 실패했습니다.")
                    except Exception as e:
                        st.error(f"❌ 시트 전송 중 오류 발생: {e}")

elif menu == "🔍 고객정보 조회":
    st.title("🔍 고객 정보 및 보유계약 현황")
    # (이전과 동일한 조회 로직...)
