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

# PDF 분석 함수
def analyze_insurance_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text()
    patterns = {
        "암": r"(암진단비|일반암진단비)\s*([\d,]+)",
        "뇌": r"(뇌혈관질환진단비|뇌혈관진단비)\s*([\d,]+)",
        "심": r"(허혈성심장질환진단비|허혈성진단비)\s*([\d,]+)",
        "수술": r"(질병수술비)\s*([\d,]+)"
    }
    res = {}
    for k, p in patterns.items():
        match = re.search(p, text)
        res[k] = int(match.group(2).replace(',', '')) // 10000 if match else 0
    return res

# --- 2. UI 구성 ---
st.set_page_config(page_title="현우 통합 보험 v2.8", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v2.8")

sheet = get_gsheet()

if sheet:
    data = pd.DataFrame(sheet.get_all_records()).fillna("")

    tab1, tab2, tab3 = st.tabs(["🔍 고객 조회", "✍️ 신규 고객 자동 등록", "📄 보장분석 업데이트"])

    # [TAB 1] 고객 조회 (기존 기능)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요")
        if search_name:
            user_data = data[data['이름'].astype(str).str.contains(search_name)]
            if not user_data.empty:
                for idx, row in user_data.iterrows():
                    with st.expander(f"👤 {row['이름']} 상세 정보", expanded=True):
                        btn_col, _ = st.columns([1, 4])
                        show_car = btn_col.toggle("🚗 자동차보험 모드", key=f"car_tgl_{idx}")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.info(f"**특이사항:** {row['병력(특이사항)']}")
                        with col2:
                            if show_car:
                                st.warning(f"**차량번호:** {row.get('차량번호', '미등록')} / **보험사:** {row.get('보험사', '미등록')}")
                            else:
                                vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself'))
                                st.plotly_chart(fig, use_container_width=True)

    # [TAB 2] 신규 고객 자동 등록 (현우님의 요청 기능)
    with tab2:
        st.subheader("📝 텍스트로 신규 고객 등록")
        st.write("채팅창의 정보를 아래에 붙여넣으면 자동으로 분류되어 저장됩니다.")
        
        raw_text = st.text_area("고객 정보를 입력하세요 (예: 홍길동, 010-1111-2222, 대구 달서구, 암 3000)", height=150)
        
        if st.button("🚀 분석 및 구글 시트 저장"):
            # 간단한 텍스트 파싱 로직 (현우님이 주시는 데이터 형식에 따라 최적화 가능)
            lines = [l.strip() for l in raw_text.split(',')]
            if len(lines) >= 2:
                new_row = [
                    datetime.now().strftime("%Y-%m-%d"), # 날짜
                    lines[0], # 이름
                    "", # 주민번호 (텍스트에 없을 시 공란)
                    lines[1] if len(lines) > 1 else "", # 연락처
                    lines[2] if len(lines) > 2 else "", # 주소
                    "", # 직업
                    "", # 특이사항
                    lines[0], # 가족대표
                    0, 0, 0, 0 # 암, 뇌, 심, 수술 (초기값)
                ]
                # 시트에 행 추가
                sheet.append_row(new_row)
                st.balloons()
                st.success(f"✅ {lines[0]} 고객님이 구글 시트에 등록되었습니다!")
                st.rerun()
            else:
                st.error("이름과 연락처를 포함하여 입력해주세요.")

    # [TAB 3] PDF 업데이트 (기존 기능)
    with tab3:
        st.subheader("📄 보장분석 PDF 실시간 업데이트")
        target_customer = st.selectbox("고객 선택", ["선택하세요"] + list(data['이름'].unique()))
        pdf_file = st.file_uploader("PDF 파일을 올려주세요", type="pdf")
        if target_customer != "선택하세요" and pdf_file:
            analysis = analyze_insurance_pdf(pdf_file)
            if st.button("✅ 구글 시트에 즉시 반영"):
                row_num = data.index[data['이름'] == target_customer][0] + 2
                sheet.update_cell(row_num, 9, analysis['암'])
                sheet.update_cell(row_num, 10, analysis['뇌'])
                sheet.update_cell(row_num, 11, analysis['심'])
                sheet.update_cell(row_num, 12, analysis['수술'])
                st.success("업데이트 완료!")
                st.rerun()
