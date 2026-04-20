import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pdfplumber
import re
import plotly.graph_objects as go

# --- 구글 시트 API 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name('key.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

# PDF 분석 로직
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

st.set_page_config(page_title="현우 클라우드 보험 v2.5", layout="wide")
st.title("🚀 실시간 보장분석 자동 업데이트 시스템")

tab1, tab2 = st.tabs(["🔍 고객 조회 및 분석", "📊 전체 현황"])

with tab1:
    sheet = get_gsheet()
    data = pd.DataFrame(sheet.get_all_records())
    
    search_name = st.selectbox("고객을 선택하세요", ["선택하세요"] + list(data['이름'].unique()))
    
    if search_name != "선택하세요":
        user_idx = data.index[data['이름'] == search_name][0]
        row = data.iloc[user_idx]
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"📄 {search_name}님 보장분석 업로드")
            uploaded_pdf = st.file_uploader("보장분석 PDF 파일을 올려주세요", type="pdf")
            
            if uploaded_pdf:
                analysis = analyze_insurance_pdf(uploaded_pdf)
                st.write("🔍 **분석된 보장금액:**")
                st.write(f"암: {analysis['암']}만 / 뇌: {analysis['뇌']}만 / 심: {analysis['심']}만 / 수술: {analysis['수술']}만")
                
                if st.button("✅ 분석 결과 구글 시트에 즉시 반영"):
                    # 구글 시트의 해당 행을 찾아 업데이트 (A, B, C... 열 순서에 맞춰 수정 필요)
                    # 예: 암(I열), 뇌(J열), 심(K열), 수술(L열) 기준
                    sheet.update_cell(user_idx + 2, 9, analysis['암'])   # 9번째 열: 암
                    sheet.update_cell(user_idx + 2, 10, analysis['뇌'])  # 10번째 열: 뇌
                    sheet.update_cell(user_idx + 2, 11, analysis['심'])  # 11번째 열: 심
                    sheet.update_cell(user_idx + 2, 12, analysis['수술']) # 12번째 열: 수술
                    st.success("🎉 구글 시트 업데이트 완료! 어디서든 확인 가능합니다.")
                    st.rerun()

        with col2:
            st.subheader("📊 현재 보장 그래프")
            vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
            fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself'))
            st.plotly_chart(fig, use_container_width=True)