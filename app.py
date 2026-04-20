import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pdfplumber
import re
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 보안 및 구글 시트 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# --- 2. UI 구성 ---
st.set_page_config(page_title="현우 통합 보험 v2.9", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v2.9")

sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_records()
    db = pd.DataFrame(raw_data).fillna("")

    tab1, tab2 = st.tabs(["🔍 고객 조회 및 업데이트", "✍️ AI 고객 정보 자동 등록"])

    # [TAB 1] 기존 조회 및 PDF 업데이트 기능 통합
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요")
        if search_name:
            user_data = db[db['이름'].astype(str).str.contains(search_name)]
            if not user_data.empty:
                for idx, row in user_data.iterrows():
                    with st.expander(f"👤 {row['이름']} 상세 정보", expanded=True):
                        st.write(f"**연락처:** {row['연락처']} | **주민번호:** {row['주민번호']}")
                        st.write(f"**주소:** {row['주소']} | **직업:** {row['직업']}")
                        st.info(f"**특이사항:** {row['병력(특이사항)']}")

    # [TAB 2] 신규 고객 자동 등록 (로직 강화)
    with tab2:
        st.subheader("📝 텍스트로 신규 고객 등록")
        raw_text = st.text_area("고객 정보를 자유롭게 붙여넣으세요", height=200, placeholder="이름, 주민번호, 연락처, 주소, 직업 등")
        
        if st.button("🚀 분석 및 구글 시트 저장"):
            # 정규표현식으로 정보 추출
            name = ""
            ssn = ""
            phone = ""
            addr = ""
            job = ""
            
            # 1. 연락처 추출 (010-XXXX-XXXX 또는 010 XXXX XXXX)
            phone_match = re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', raw_text)
            if phone_match: phone = phone_match.group().replace(" ", "-")
            
            # 2. 주민번호 추출 (XXXXXX-XXXXXXX)
            ssn_match = re.search(r'\d{6}[ \-]?\d{7}', raw_text)
            if ssn_match: ssn = ssn_match.group()
            
            # 3. 줄바꿈으로 데이터 쪼개기
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            
            # 4. 이름/주소/직업 추측 (보통 첫 줄이 이름, 주소 키워드 포함 시 주소)
            for line in lines:
                if "대구" in line or "서울" in line or "길" in line or "동" in line:
                    if not addr: addr = line
                elif line == lines[0] and not name:
                    name = line
                elif len(line) < 10 and not job and line != name:
                    job = line

            if name and phone:
                new_row = [
                    datetime.now().strftime("%Y-%m-%d"), # 날짜
                    name, ssn, phone, addr, job, 
                    "", # 병력
                    name, # 가족대표
                    0, 0, 0, 0 # 보장금액 초기화
                ]
                sheet.append_row(new_row)
                st.balloons()
                st.success(f"✅ {name} 고객님이 성공적으로 등록되었습니다!")
                st.rerun()
            else:
                st.error("성함과 연락처를 인식하지 못했습니다. 형식을 확인해주세요.")
