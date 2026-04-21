import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- [1. 구글 시트 연결] ---
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

# --- [2. PDF 분석 함수] ---
def parse_pdf(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                # 날짜 및 금액 패턴 정규식
                date_m = re.search(r'\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}', line)
                price_m = re.search(r'[\d,]{2,}원|[\d,]{1,5}만\s?원', line)
                if date_m and price_m:
                    dt, pr = date_m.group(), price_m.group()
                    parts = line.split()
                    comp = parts[0] if parts else "미확인"
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"보험사": comp, "상품명": prod, "가입날짜": dt, "금액": pr})
    return results

# --- [3. 메인 설정] ---
st.set_page_config(page_title="배현우 보장분석 시스템 v36.0", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    if raw_data:
        headers = [h.strip() for h in raw_data[0]] # 제목행 가져오기
        db_cust = pd.DataFrame(raw_data[1:], columns=headers)
        col_options = ["선택 안 함"] + headers
    else:
        st.error("시트에 제목(헤더) 정보가 없습니다.")
        st.stop()

# --- [4. UI: 보장분석 업로드] ---
st.title("📄 보장분석 PDF 강제 매칭 입력")

with st.sidebar:
    st.header("설정")
    st.info("시트의 제목과 데이터 항목을 수동으로 연결합니다.")

# 1단계: 시트 컬럼 수동 매칭 (입력 실패 방지 핵심)
st.subheader("1️⃣ 컬럼 매칭 설정 (시트의 실제 제목을 선택하세요)")
c1, c2, c3, c4 = st.columns(4)
with c1: target_comp = st.selectbox("🏢 보험사 항목", col_options, index=col_options.index("보험사") if "보험사" in col_options else 0)
with c2: target_prod = st.selectbox("📜 상품명 항목", col_options, index=col_options.index("상품명") if "상품명" in col_options else 0)
with c3: target_date = st.selectbox("📅 가입날짜 항목", col_options, index=col_options.index("가입날짜") if "가입날짜" in col_options else 0)
with c4: target_price = st.selectbox("💰 금액 항목", col_options, index=col_options.index("금액") if "금액" in col_options else 0)

st.markdown("---")

# 2단계: 파일 및 고객 선택
col_a, col_b = st.columns(2)
with col_a:
    target_user = st.selectbox("대상 고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
with col_b:
    up_file = st.file_uploader("보장분석 PDF 파일 선택", type="pdf")

if up_file and target_user != "선택":
    if st.button("🚀 분석 데이터 시트 강제 전송"):
        items = parse_pdf(up_file)
        if items:
            # 고객 행 위치 확인
            row_idx = db_cust[db_cust['이름'] == target_user].index[-1] + 2
            
            # 전송할 데이터 생성 (줄바꿈 결합)
            c_val = "\n".join([i['보험사'] for i in items])
            p_val = "\n".join([i['상품명'] for i in items])
            d_val = "\n".join([i['가입날짜'] for i in items])
            m_val = "\n".join([i['금액'] for i in items])
            
            # 수동 매칭된 컬럼 인덱스로 직접 업데이트
            try:
                if target_comp != "선택 안 함": sheet.update_cell(row_idx, headers.index(target_comp) + 1, c_val)
                if target_prod != "선택 안 함": sheet.update_cell(row_idx, headers.index(target_prod) + 1, p_val)
                if target_date != "선택 안 함": sheet.update_cell(row_idx, headers.index(target_date) + 1, d_val)
                if target_price != "선택 안 함": sheet.update_cell(row_idx, headers.index(target_price) + 1, m_val)
                
                st.success(f"✅ {target_user}님 데이터 전송 완료! 시트를 확인하세요.")
                st.balloons()
            except Exception as e:
                st.error(f"❌ 전송 오류: {e}")
        else:
            st.error("❌ PDF에서 날짜/금액 데이터를 찾지 못했습니다.")
