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
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

st.set_page_config(page_title="현우 통합 보험 v3.3", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v3.3")

sheet = get_gsheet()

if sheet:
    try:
        raw_data = sheet.get_all_records()
        if not raw_data:
            db = pd.DataFrame(columns=["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"])
        else:
            db = pd.DataFrame(raw_data).fillna("")
    except:
        st.error("⚠️ 시트 헤더를 확인해주세요.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회", "✍️ 신규 등록", "🚘 증권 업데이트"])

    # [TAB 1] 고객 조회 (중복 출력 방지 로직 적용)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            # 검색된 결과 중 이름과 연락처가 같은 중복 데이터는 제거하고 가장 마지막(최신) 것만 남김
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']}) - 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                            st.info(f"**특이사항:** {row['병력(특이사항)']}")
                        with col2:
                            st.warning(f"**차량:** {row.get('차량번호', '-')} / **만기:** {row.get('자동차만기일', '-')}")
                            vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                            fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself'))
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("검색 결과가 없습니다.")

    # [TAB 2] 신규 등록 (저장 전 시트 중복 체크 강화)
    with tab2:
        st.subheader("📝 신규 고객 등록")
        raw_text = st.text_area("정보를 입력하세요")
        if st.button("🚀 분석 및 저장"):
            # (중략된 파싱 로직은 동일)
            # ... 이름(name), 연락처(phone) 추출 완료 후 ...
            if name and phone:
                # 저장 전 실시간으로 시트를 다시 확인하여 중복 체크
                current_db = pd.DataFrame(sheet.get_all_records())
                if not current_db[(current_db['이름'] == name) & (current_db['연락처'] == phone)].empty:
                    st.warning("⚠️ 이미 시트에 존재하는 고객입니다.")
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, "", name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success("등록 완료!")
                    st.rerun()

    # [TAB 3] 증권 업데이트 (동일 인물 중 가장 마지막 행에 업데이트)
    with tab3:
        # (중략) 업데이트 시에도 최신 행 번호를 찾아 업데이트하도록 수정
