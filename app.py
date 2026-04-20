import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

# --- 2. 화면 구성 ---
st.set_page_config(page_title="현우 통합 보험 v3.4", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.4")

sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_records()
    db = pd.DataFrame(raw_data).fillna("")

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회 및 업데이트", "✍️ AI 고객 정보 등록", "🚘 자동차 증권 업데이트"])

    # [TAB 1] 고객 조회
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요")
        if search_name:
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.success(f"**💡 특이사항/계좌:** {row['병력(특이사항)']}") # 계좌정보가 여기에 표시됨
                        with col2:
                            st.warning(f"**차량:** {row.get('차량번호', '미등록')} / **만기:** {row.get('자동차만기일', '미등록')}")

    # [TAB 2] 신규 등록 (계좌번호 인식 로직 추가)
    with tab2:
        st.subheader("📝 텍스트로 고객 등록/업데이트")
        raw_text = st.text_area("고객 정보를 입력하세요", height=200)
        
        if st.button("🚀 분석 및 저장"):
            name, ssn, phone, addr, job, memo = "", "", "", "", "", ""
            
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                # 연락처 패턴
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                # 주민번호 패턴
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                # 계좌번호 패턴 (숫자가 길게 나열된 경우)
                elif re.search(r'\d{3,}[ \-]?\d{3,}[ \-]?\d{3,}', line) and "010" not in line:
                    memo += f"[계좌] {line} "
                # 주소 키워드
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                # 이름
                elif line == lines[0]: name = line
                # 기타 (은행명 등)
                else: memo += f"{line} "

            if name:
                # 중복 확인
                dup = db[(db['이름'] == name) & (db['연락처'] == phone)]
                if not dup.empty:
                    # 기존 고객이면 특이사항만 업데이트 제안하거나 자동 병합
                    st.warning(f"⚠️ {name}님은 이미 등록된 고객입니다. 시트에서 직접 계좌 정보를 추가해 주세요.")
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, memo.strip(), name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님(계좌 포함) 등록 완료!")
                    st.rerun()
