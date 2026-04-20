import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- 1. 보안 및 구글 시트 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # 첫 번째 워크시트 가져오기
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# --- 2. UI 설정 ---
st.set_page_config(page_title="현우 통합 보험 v3.2", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.2")

sheet = get_gsheet()

if sheet:
    # 데이터 로드 (에러 방지 로직 포함)
    try:
        raw_data = sheet.get_all_records()
        if not raw_data:
            db = pd.DataFrame(columns=["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"])
        else:
            db = pd.DataFrame(raw_data).fillna("")
    except Exception as e:
        st.error("⚠️ 시트 데이터를 읽는 중 오류가 발생했습니다. 헤더(1행)를 확인해주세요.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회", "✍️ 신규 고객 등록 (중복방지)", "🚘 자동차 증권 업데이트"])

    # [TAB 1] 고객 조회
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            user_data = db[db['이름'].astype(str).str.contains(search_name)]
            if not user_data.empty:
                for idx, row in user_data.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                            st.write(f"**직업:** {row['직업']}")
                        with col2:
                            st.write(f"**차량:** {row.get('차량번호', '-')}")
                            st.write(f"**보험사:** {row.get('보험사', '-')}")
                            st.write(f"**만기:** {row.get('자동차만기일', '-')}")
            else:
                st.info("검색 결과가 없습니다.")

    # [TAB 2] 신규 등록 (중복 방지 로직)
    with tab2:
        st.subheader("📝 신규 고객 자동 분류 등록")
        raw_text = st.text_area("고객 정보를 붙여넣으세요", height=200)
        
        if st.button("🚀 분석 및 저장"):
            # 파싱 로직
            name, ssn, phone, addr, job = "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                elif len(line) < 10 and not job: job = line

            if name and phone:
                # 중복 확인 (이름과 연락처가 모두 같은 경우)
                is_duplicate = not db[(db['이름'] == name) & (db['연락처'] == phone)].empty
                
                if is_duplicate:
                    st.warning(f"⚠️ '{name}({phone})'님은 이미 등록된 고객입니다. 중복 저장을 차단했습니다.")
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, "", name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 신규 등록 완료!")
                    st.rerun()
            else:
                st.error("이름과 연락처를 인식할 수 없습니다.")

    # [TAB 3] 증권 데이터 업데이트
    with tab3:
        st.subheader("🚘 증권 데이터 매칭")
        st.info("Gemini가 분석한 '이름, 차량번호, 보험사, 만기일' 형식을 입력하세요.")
        update_input = st.text_input("데이터 입력 (예: 이창권, 41누8291, 삼성화재, 2027.03.26)")
        
        if st.button("✅ 데이터 반영"):
            parts = [p.strip() for p in update_input.split(',')]
            if len(parts) >= 4:
                t_name, t_car, t_comp, t_exp = parts[0], parts[1], parts[2], parts[3]
                try:
                    # 정확히 일치하는 이름 찾기
                    idx_list = db.index[db['이름'] == t_name].tolist()
                    if idx_list:
                        row_num = idx_list[0] + 2
                        sheet.update_cell(row_num, 13, t_car)
                        sheet.update_cell(row_num, 14, t_comp)
                        sheet.update_cell(row_num, 15, t_exp)
                        st.success(f"✅ {t_name}님 정보가 클라우드에 반영되었습니다.")
                        st.rerun()
                    else:
                        st.error(f"'{t_name}' 고객님을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"업데이트 중 오류: {e}")
