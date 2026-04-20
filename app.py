import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
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

# 필수 헤더 (보장분석 파일 링크 저장을 위해 비고/링크 칸 활용 가능하도록 구성)
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 보험 v4.2", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v4.2")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 분석결과", "✍️ AI 정보 등록", "🚘 자동차 증권", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 (리스트 및 표 형태 시각화)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            res = res.drop_duplicates(subset=['이름', '연락처'], keep='last')
            
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']}) 상세 현황", expanded=True):
                        col1, col2 = st.columns([3, 2])
                        with col1:
                            st.markdown("### 📋 보장분석 결과 요약")
                            memo_raw = row['병력(특이사항)']
                            if "[보장분석]" in memo_raw:
                                # 보장분석 내용만 추출하여 표로 구성
                                analysis_part = memo_raw.split("[보장분석]")[-1]
                                ins_items = [item.strip() for item in analysis_part.split(',') if item.strip()]
                                
                                # 데이터프레임으로 변환하여 표 생성
                                table_data = []
                                for item in ins_items:
                                    # 이름(금액) 형태 분리 로직
                                    name_match = re.match(r'([가-힣\w\s]+)(\(.*\))?', item)
                                    if name_match:
                                        ins_name = name_match.group(1).strip()
                                        ins_price = name_match.group(2).replace("(", "").replace(")", "").strip() if name_match.group(2) else "확인필요"
                                        table_data.append({"보험상품명": ins_name, "월 보험료": ins_price, "상태": "유지"})
                                
                                if table_data:
                                    st.table(pd.DataFrame(table_data))
                                else:
                                    st.write(analysis_part)
                            else:
                                st.info("등록된 보장분석 데이터가 없습니다. [보장분석 파일 업로드] 탭을 이용해 주세요.")
                            
                            st.markdown("---")
                            st.write(f"**🏠 주소:** {row['주소']} | **직업:** {row['직업']}")
                            st.write(f"**💡 기타 특이사항:** {memo_raw.split('[보장분석]')[0]}")

                        with col2:
                            st.markdown("### 📊 보장 지표")
                            try:
                                vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself', fillcolor='rgba(233, 30, 99, 0.3)', line_color='#E91E63'))
                                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=300, margin=dict(l=40,r=40,b=20,t=40))
                                st.plotly_chart(fig, use_container_width=True)
                            except: st.write("차트 데이터가 없습니다.")

    # [TAB 4] 보장분석 PDF 업로드 및 분석
    with tab4:
        st.subheader("📄 보장분석 데이터 추출 및 저장")
        up_file = st.file_uploader("보장분석 PDF 파일을 업로드하세요", type=['pdf'])
        target_u = st.selectbox("업데이트할 고객", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 분석 후 시트 반영"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        text = "".join([page.extract_text() for page in pdf.pages])
                    
                    # 보험명 및 금액 추출 시도
                    ins_matches = re.findall(r'([가-힣\w\s]+보험|[가-힣\w\s]+공제)\s*(\d{1,3}(?:,\d{3})*원)?', text)
                    new_entries = [f"{m[0]}({m[1] if m[1] else ''})" for m in ins_matches]
                    unique_entries = list(set(new_entries))
                    
                    match_idx = db.index[db['이름'] == target_u].tolist()
                    if match_idx:
                        row_num = match_idx[-1] + 2
                        current_memo = db.iloc[match_idx[-1]]['병력(특이사항)']
                        
                        # 중복 제외 합치기
                        analysis_str = ", ".join(unique_entries)
                        final_memo = f"{current_memo.split('[보장분석]')[0].strip()} | [보장분석] {analysis_str}"
                        
                        sheet.update_cell(row_num, 7, final_memo)
                        st.success(f"✅ {target_u}님 보장분석 리스트 업데이트 완료!")
                        st.rerun()
                except Exception as e: st.error(f"오류: {e}")
