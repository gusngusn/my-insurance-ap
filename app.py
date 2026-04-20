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

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 보험 v3.7", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.7")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if not all_values:
        sheet.insert_row(EXPECTED_HEADERS, 1)
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    else:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
        db = db.fillna("")

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트"])

    # [TAB 2] 핵심 수정: 중복 시 빈칸 자동 업데이트 로직
    with tab2:
        st.subheader("📝 텍스트로 정보 등록 및 자동 병합")
        raw_text = st.text_area("고객 정보를 입력하세요 (이름과 연락처 기준 매칭)", height=200)
        
        if st.button("🚀 분석 및 데이터 반영"):
            name, ssn, phone, addr, job, memo = "", "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif re.search(r'\d{3,}[ \-]?\d{3,}[ \-]?\d{3,}', line) and "010" not in line: memo += f"[계좌] {line} "
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                else: memo += f"{line} "

            if name and phone:
                # 시트에서 동일 인물 찾기 (이름과 연락처 기준)
                match_idx = db.index[(db['이름'] == name) & (db['연락처'] == phone)].tolist()
                
                if match_idx:
                    # 이미 있는 고객이면 비어있는 칸만 업데이트
                    row_num = match_idx[-1] + 2
                    target_row = db.iloc[match_idx[-1]]
                    
                    updates = []
                    # 주민번호, 주소, 직업, 특이사항이 비어있을 때만 새 데이터로 채움
                    if not target_row['주민번호'] and ssn: sheet.update_cell(row_num, 3, ssn); updates.append("주민번호")
                    if not target_row['주소'] and addr: sheet.update_cell(row_num, 5, addr); updates.append("주소")
                    if not target_row['직업'] and job: sheet.update_cell(row_num, 6, job); updates.append("직업")
                    if memo: # 특이사항은 기존 내용 뒤에 덧붙임
                        new_memo = (target_row['병력(특이사항)'] + " " + memo).strip()
                        sheet.update_cell(row_num, 7, new_memo)
                        updates.append("특이사항(계좌)")
                    
                    if updates:
                        st.success(f"✅ {name} 고객님의 {', '.join(updates)} 정보가 추가 업데이트되었습니다!")
                    else:
                        st.info(f"ℹ️ {name} 고객님은 이미 모든 정보가 등록되어 있습니다.")
                    st.rerun()
                else:
                    # 신규 고객이면 새로 추가
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, memo.strip(), name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 신규 등록 완료!")
                    st.rerun()
            else:
                st.error("이름과 연락처는 필수 인식 항목입니다.")

    # [TAB 1, 3은 기존과 동일]
