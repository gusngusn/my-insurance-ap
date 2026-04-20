import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pdfplumber
import re
import plotly.graph_objects as go

# --- 1. 보안 및 구글 시트 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        # Streamlit Secrets에서 보안 정보 가져오기
        creds_info = st.secrets["gcp_service_account"]
        
        # [수정됨] from_json_dict -> from_json_keyfile_dict 로 변경
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# PDF 보장 금액 추출 함수
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

# --- 2. 메인 UI ---
st.set_page_config(page_title="현우 통합 보험 v2.7", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v2.7")

sheet = get_gsheet()

if sheet:
    # 실시간 데이터 로드
    data = pd.DataFrame(sheet.get_all_records()).fillna("")

    tab1, tab2 = st.tabs(["🔍 고객 조회 및 자동차보험", "📄 보장분석 자동 업데이트"])

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
                            st.markdown("### 📋 인적사항")
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.info(f"**특이사항:** {row['병력(특이사항)']}")
                        
                        with col2:
                            if show_car:
                                st.markdown("### 🚘 자동차보험 현황")
                                st.warning(f"**차량번호:** {row.get('차량번호', '미등록')}")
                                st.write(f"**보험사:** {row.get('보험사', '미등록')}")
                                st.write(f"**만기일:** {row.get('자동차만기일', '미등록')}")
                            else:
                                st.markdown("### 📊 보장 현황")
                                try:
                                    vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                    fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself', line_color='#E91E63'))
                                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=300, margin=dict(l=20,r=20,b=20,t=20))
                                    st.plotly_chart(fig, use_container_width=True)
                                except:
                                    st.write("보장 금액 숫자를 확인해주세요.")

    with tab2:
        st.subheader("📄 보장분석 PDF 실시간 업데이트")
        target_customer = st.selectbox("고객 선택", ["선택하세요"] + list(data['이름'].unique()))
        pdf_file = st.file_uploader("PDF 파일을 올려주세요", type="pdf")
        
        if target_customer != "선택하세요" and pdf_file:
            analysis = analyze_insurance_pdf(pdf_file)
            st.success(f"분석 결과: 암 {analysis['암']}만 / 뇌 {analysis['뇌']}만 / 심 {analysis['심']}만 / 수술 {analysis['수술']}만")
            
            if st.button("✅ 분석 결과를 구글 시트에 즉시 반영"):
                row_num = data.index[data['이름'] == target_customer][0] + 2
                sheet.update_cell(row_num, 9, analysis['암'])   # I열
                sheet.update_cell(row_num, 10, analysis['뇌'])  # J열
                sheet.update_cell(row_num, 11, analysis['심'])  # K열
                sheet.update_cell(row_num, 12, analysis['수술']) # L열
                st.balloons()
                st.success(f"{target_customer}님의 데이터가 업데이트되었습니다!")
                st.rerun()
