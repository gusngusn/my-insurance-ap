import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- 보안 및 구글 시트 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

st.set_page_config(page_title="현우 통합 보험 v3.1", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.1")

sheet = get_gsheet()

if sheet:
    db = pd.DataFrame(sheet.get_all_records()).fillna("")

    tab1, tab2 = st.tabs(["🔍 고객 조회", "🚘 자동차 증권 자동 입력"])

    with tab2:
        st.subheader("📄 증권 데이터 자동 매칭")
        st.info("💡 Gemini가 분석해준 텍스트를 아래에 그대로 붙여넣으세요.")
        raw_input = st.text_area("데이터 입력창", height=150)
        
        if st.button("🚀 클라우드 데이터 즉시 업데이트"):
            # 데이터 추출 (이름, 차량번호, 보험사, 만기일 순)
            parts = [p.strip() for p in raw_input.split(',')]
            
            if len(parts) >= 4:
                target_name = parts[0]
                car_no = parts[1]
                company = parts[2]
                expiry = parts[3]
                
                try:
                    # 고객 찾기
                    row_idx = db.index[db['이름'] == target_name][0] + 2
                    
                    # 시트 업데이트 (13:차량번호, 14:보험사, 15:만기일)
                    sheet.update_cell(row_idx, 13, car_no)
                    sheet.update_cell(row_idx, 14, company)
                    sheet.update_cell(row_idx, 15, expiry)
                    
                    st.success(f"✅ {target_name} 고객님 차량({car_no}) 정보가 업데이트되었습니다!")
                    st.balloons()
                except:
                    st.error(f"'{target_name}' 고객님을 DB에서 찾을 수 없습니다.")
            else:
                st.error("데이터 형식이 올바르지 않습니다.")
