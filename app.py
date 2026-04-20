import streamlit as st
import pdfplumber
import re
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime

# --- 설정 및 초기화 ---
st.set_page_config(page_title="현우 통합 보험 솔루션 v1.9", layout="wide")
DB_FILE = "customer_database.csv"

# 필수 컬럼 정의
REQUIRED_COLUMNS = [
    "날짜", "이름", "주민번호", "연락처", "주소", "직업", 
    "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술"
]

# DB 파일 초기화 및 업데이트 로직
if not os.path.exists(DB_FILE):
    pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(DB_FILE, index=False, encoding='utf-8-sig')
else:
    db_check = pd.read_csv(DB_FILE)
    for col in REQUIRED_COLUMNS:
        if col not in db_check.columns:
            db_check[col] = ""
    db_check.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# 자동 데이터 입력 로직 (김예리, 박경숙 가족 등)
def seed_data():
    db = pd.read_csv(DB_FILE)
    initial_list = [
        {"날짜": "2023-11-02", "이름": "김예리", "주민번호": "850104-2690824", "연락처": "010-3685-3619", "주소": "대구 동구 과학로 23 608동 708호", "직업": "병원상담실장", "병력(특이사항)": "현대, DB, 동양생명 고등", "가족대표": "김예리", "암": 0, "뇌": 0, "심": 0, "수술": 0},
        {"날짜": "2026-04-20", "이름": "박경숙", "주민번호": "", "연락처": "", "주소": "", "직업": "", "병력(특이사항)": "가족 대표", "가족대표": "박경숙", "암": 0, "뇌": 0, "심": 0, "수술": 0},
        {"날짜": "2026-04-20", "이름": "정지효", "주민번호": "", "연락처": "", "주소": "", "직업": "", "병력(특이사항)": "박경숙 가족", "가족대표": "박경숙", "암": 0, "뇌": 0, "심": 0, "수술": 0}
    ]
    updated = False
    for item in initial_list:
        if item["이름"] not in db["이름"].values:
            db = pd.concat([db, pd.DataFrame([item])], ignore_index=True)
            updated = True
    if updated:
        db.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

seed_data()

st.title("🛡️ 배현우 설계사 통합 영업 시스템 v1.9")

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["🔍 보장 분석 및 등록", "👥 고객 상세 관리", "👨‍👩‍👧‍👦 가족 연동 현황"])

with tab1:
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.subheader("📋 신규 고객 정보")
        c_name = st.text_input("고객 성함")
        c_ssn = st.text_input("주민등록번호")
        c_phone = st.text_input("연락처")
        c_addr = st.text_input("주소")
        c_job = st.text_input("직업")
        c_history = st.text_area("병력 및 특이사항")
        
        st.write("---")
        is_head = st.checkbox("이 고객이 가족 대표입니까?")
        f_head_input = st.text_input("가족 대표자 성함 (본인이 아닐 경우 입력)")
        
        uploaded_file = st.file_uploader("보장분석 PDF 업로드", type="pdf")

    def run_analysis(file):
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text()
        patterns = {
            "일반암": r"(암진단비|일반암진단비)\s*([\d,]+)",
            "뇌혈관": r"(뇌혈관질환진단비|뇌혈관진단비)\s*([\d,]+)",
            "허혈성": r"(허혈성심장질환진단비|허혈성진단비)\s*([\d,]+)",
            "질병수술": r"(질병수술비)\s*([\d,]+)"
        }
        targets = {"일반암": 5000, "뇌혈관": 2000, "허혈성": 2000, "질병수술": 100}
        data = []
        for label, pattern in patterns.items():
            match = re.search(pattern, text)
            val = int(match.group(2).replace(',', '')) // 10000 if match else 0
            pct = min(100, int((val / targets[label]) * 100)) if targets[label] > 0 else 0
            data.append({"항목": label, "현재": val, "목표": targets[label], "충족률": pct})
        return pd.DataFrame(data)

    with col2:
        if uploaded_file:
            df_res = run_analysis(uploaded_file)
            st.subheader(f"📊 {c_name}님 분석 리포트")
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=df_res['충족률'], theta=df_res['항목'], fill='toself', line_color='#E91E63'))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, height=450)
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("💾 이 고객 정보 최종 저장"):
                final_head = c_name if is_head else f_head_input
                new_row = [
                    datetime.now().strftime("%Y-%m-%d"), c_name, c_ssn, c_phone, c_addr, c_job, c_history, 
                    final_head, df_res.iloc[0]['현재'], df_res.iloc[1]['현재'], df_res.iloc[2]['현재'], df_res.iloc[3]['현재']
                ]
                db = pd.read_csv(DB_FILE)
                db.loc[len(db)] = new_row
                db.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
                st.success(f"{c_name}님의 정보가 저장되었습니다.")

with tab2:
    st.subheader("📥 외부 데이터(노션/엑셀) 대량 등록")
    st.write("양식에 맞는 CSV 파일을 업로드하면 수백 명의 고객을 한 번에 등록할 수 있습니다.")
    
    upload_csv = st.file_uploader("업로드할 CSV 파일을 선택하세요", type="csv")
    
    if upload_csv:
        new_data_df = pd.read_csv(upload_csv)
        st.write("▼ 업로드된 데이터 미리보기")
        st.dataframe(new_data_df.head(), use_container_width=True)
        
        if st.button("✅ 명단에 모두 추가하기"):
            db = pd.read_csv(DB_FILE)
            # 이름과 연락처가 모두 중복되는 경우 제외하고 합침
            combined = pd.concat([db, new_data_df], ignore_index=True).drop_duplicates(subset=['이름', '연락처'], keep='first')
            combined.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.success(f"총 {len(new_data_df)}명의 고객 데이터 처리가 완료되었습니다!")

    st.write("---")
    st.subheader("🗂️ 전체 고객 관리 명부")
    db_df = pd.read_csv(DB_FILE)
    st.dataframe(db_df, use_container_width=True)

with tab3:
    st.subheader("👨‍👩‍👧‍👦 가족 단위 통합 조회")
    db_df = pd.read_csv(DB_FILE)
    if '가족대표' in db_df.columns:
        heads = db_df['가족대표'].replace("", pd.NA).dropna().unique()
        if len(heads) > 0:
            selected_head = st.selectbox("가족 대표 선택", heads)
            family_group = db_df[db_df['가족대표'] == selected_head]
            st.table(family_group[["이름", "직업", "연락처", "병력(특이사항)", "암", "뇌", "심"]])
            st.info(f"💡 가족 보장 합산: 암 {family_group['암'].sum()}만 / 뇌 {family_group['뇌'].sum()}만 / 심 {family_group['심'].sum()}만")