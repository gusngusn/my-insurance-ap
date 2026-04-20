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
        st.error("⚠️ 시트 데이터를 읽는 중 오류가 발생했습니다. 헤더(1행)를 확인해주세요.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회 및 업데이트", "✍️ 신규 고객 등록", "🚘 자동차 증권 업데이트"])

    # [TAB 1] 고객 조회 (중복 출력 방지)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요")
        if search_name:
            # 시트에 중복 데이터가 있어도 화면에는 '이름+연락처' 기준 최신 것 하나만 표시
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']}) - 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                            st.write(f"**직업:** {row['직업']}")
                            st.info(f"**특이사항:** {row['병력(특이사항)']}")
                        with col2:
                            st.warning(f"**차량:** {row.get('차량번호', '미등록')} / **보험사:** {row.get('보험사', '미등록')}")
                            st.write(f"**만기일:** {row.get('자동차만기일', '미등록')}")
                            # 보장 그래프
                            try:
                                vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself', line_color='#E91E63'))
                                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=300, margin=dict(l=20,r=20,b=20,t=20))
                                st.plotly_chart(fig, use_container_width=True)
                            except:
                                st.write("보장 수치를 확인해주세요.")
            else:
                st.info("검색 결과가 없습니다.")

    # [TAB 2] 신규 등록 (저장 전 중복 체크)
    with tab2:
        st.subheader("📝 신규 고객 자동 분류 등록")
        raw_text = st.text_area("고객 정보를 입력하세요", height=200)
        if st.button("🚀 분석 및 저장"):
            name, ssn, phone, addr, job = "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                elif len(line) < 10 and not job: job = line

            if name and phone:
                # 실시간 중복 체크
                if not db[(db['이름'] == name) & (db['연락처'] == phone)].empty:
                    st.warning(f"⚠️ {name}({phone})님은 이미 등록된 고객입니다.")
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, "", name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 등록 완료!")
                    st.rerun()
            else:
                st.error("이름과 연락처를 인식할 수 없습니다.")

    # [TAB 3] 증권 데이터 업데이트 (가장 최신 행에 업데이트)
    with tab3:
        st.subheader("🚘 자동차 증권 데이터 매칭")
        st.info("💡 '이름, 차량번호, 보험사, 만기일' 형식으로 입력하세요.")
        update_input = st.text_input("데이터 입력 (예: 이창권, 41누8291, 삼성화재, 2027.03.26)")
        
        if st.button("✅ 클라우드 반영"):
            parts = [p.strip() for p in update_input.split(',')]
            if len(parts) >= 4:
                t_name, t_car, t_comp, t_exp = parts[0], parts[1], parts[2], parts[3]
                # 해당 이름의 고객 중 가장 마지막 행 번호 찾기
                idx_list = db.index[db['이름'] == t_name].tolist()
                if idx_list:
                    row_num = idx_list[-1] + 2 # 가장 마지막 인덱스 사용
                    sheet.update_cell(row_num, 13, t_car)
                    sheet.update_cell(row_num, 14, t_comp)
                    sheet.update_cell(row_num, 15, t_exp)
                    st.success(f"✅ {t_name}님의 차량 정보가 최신 데이터로 업데이트되었습니다.")
                    st.rerun()
                else:
                    st.error(f"'{t_name}' 고객님을 찾을 수 없습니다.")
