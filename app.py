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

# 시스템 필수 헤더 정의
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 보험 v3.6", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.6")

sheet = get_gsheet()

if sheet:
    try:
        # [중요 수정] get_all_records() 대신 get_all_values()를 사용해 중복 헤더 에러를 원천 차단합니다.
        all_values = sheet.get_all_values()
        
        if len(all_values) <= 1: # 데이터가 없거나 제목만 있는 경우
            if not all_values:
                sheet.insert_row(EXPECTED_HEADERS, 1)
            db = pd.DataFrame(columns=EXPECTED_HEADERS)
        else:
            # 첫 줄은 무시하고 미리 정의된 EXPECTED_HEADERS를 컬럼명으로 사용
            # 실제 데이터 행 개수에 맞춰 데이터프레임 생성
            db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
            db = db.fillna("")
            
    except Exception as e:
        st.error(f"⚠️ 데이터 로드 오류: {e}")
        st.info("💡 구글 시트의 1행(제목줄)을 확인해 주세요.")
        db = pd.DataFrame(columns=EXPECTED_HEADERS)

    # 탭 구성 (v3.5와 동일)
    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회 및 업데이트", "✍️ AI 고객 정보 등록", "🚘 자동차 증권 업데이트"])

    # [TAB 1] 고객 조회
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']}) 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row.get('주민번호', '-')}")
                            st.write(f"**주소:** {row.get('주소', '-')}")
                            st.success(f"**💡 특이사항/계좌:** {row.get('병력(특이사항)', '-')}")
                        with col2:
                            st.warning(f"**차량:** {row.get('차량번호', '미등록')} / **보험사:** {row.get('보험사', '미등록')}")
                            st.write(f"**만기:** {row.get('자동차만기일', '미등록')}")
            else:
                st.info("검색 결과가 없습니다.")

    # [TAB 2] 신규 등록 (중복 방지 포함)
    with tab2:
        st.subheader("📝 텍스트로 고객 등록/업데이트")
        raw_text = st.text_area("고객 정보 입력 (이름, 주민, 연락처, 주소, 직업, 계좌 등)", height=200)
        if st.button("🚀 분석 및 저장"):
            name, ssn, phone, addr, job, memo = "", "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif re.search(r'\d{3,}[ \-]?\d{3,}[ \-]?\d{3,}', line) and "010" not in line: memo += f"[계좌] {line} "
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                else: memo += f"{line} "

            if name:
                is_dup = not db[(db['이름'] == name) & (db['연락처'] == phone)].empty if not db.empty else False
                if is_dup:
                    st.warning(f"⚠️ {name}님은 이미 등록된 고객입니다.")
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, memo.strip(), name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 등록 완료!")
                    st.rerun()

    # [TAB 3] 증권 업데이트
    with tab3:
        st.subheader("🚘 자동차 증권 데이터 업데이트")
        update_input = st.text_input("입력 예시: 조영래, 60구0700, DB손해보험, 2026.12.10")
        if st.button("✅ 클라우드 반영"):
            parts = [p.strip() for p in update_input.split(',')]
            if len(parts) >= 4:
                t_name, t_car, t_comp, t_exp = parts[0], parts[1], parts[2], parts[3]
                idx_list = db.index[db['이름'] == t_name].tolist()
                if idx_list:
                    row_num = idx_list[-1] + 2
                    sheet.update_cell(row_num, 13, t_car)
                    sheet.update_cell(row_num, 14, t_comp)
                    sheet.update_cell(row_num, 15, t_exp)
                    st.success(f"✅ {t_name}님 정보 업데이트 완료!")
                    st.rerun()
                else:
                    st.error(f"'{t_name}' 고객님을 찾을 수 없습니다.")
