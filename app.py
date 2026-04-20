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

    # [TAB 1] 고객 조회
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

    # [TAB 2] 신규 고객 자동 등록 (고급 파싱 로직 적용)
    with tab2:
        st.subheader("📝 텍스트로 신규 고객 등록")
        st.write("주신 정보를 아래 칸에 그대로 복사해서 붙여넣으세요.")
        raw_text = st.text_area("고객 정보 입력란", height=250, placeholder="이름\n주민번호\n연락처\n주소\n직업 순으로 입력 시 가장 정확합니다.")
        
        if st.button("🚀 분석 및 구글 시트 저장"):
            # 데이터 추출용 변수 초기화
            name, ssn, phone, addr, job = "", "", "", "", ""
            
            # 1. 줄바꿈 기준으로 데이터 분리
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            
            for line in lines:
                # 연락처 패턴 (010으로 시작하는 숫자 조합)
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line):
                    phone = line.replace(" ", "-")
                # 주민번호 패턴 (6자리-7자리 또는 13자리 숫자)
                elif re.search(r'\d{6}[ \-]?\d{7}', line):
                    ssn = line
                # 주소 키워드 (시, 구, 로, 길, 동 등 주소 관련 단어 포함 시)
                elif any(keyword in line for keyword in ["시", "구", "로", "길", "동", "번지"]):
                    addr = line
                # 이름 (보통 첫 번째 줄이 이름일 확률이 높음)
                elif line == lines[0]:
                    name = line
                # 직업 (그 외 짧은 문구는 직업으로 간주)
                elif len(line) < 10 and not job:
                    job = line

            if name and phone:
                new_row = [
                    datetime.now().strftime("%Y-%m-%d"), # 날짜
                    name, ssn, phone, addr, job, 
                    "", # 병력 특이사항 (초기값)
                    name, # 가족대표 (본인)
                    0, 0, 0, 0 # 암, 뇌, 심, 수술 (보장 금액 초기화)
                ]
                sheet.append_row(new_row)
                st.balloons()
                st.success(f"✅ {name} 고객님이 성공적으로 등록되었습니다!")
                st.rerun()
            else:
                st.error("성함과 연락처 정보를 인식하지 못했습니다. 형식을 다시 확인해주세요.")
