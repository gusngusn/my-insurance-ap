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

# 시스템 필수 헤더
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 보험 v4.0", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v4.0")

sheet = get_gsheet()

if sheet:
    # 데이터 로드
    all_values = sheet.get_all_values()
    if not all_values:
        sheet.insert_row(EXPECTED_HEADERS, 1)
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    else:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
        db = db.fillna("")

    # --- 탭 구성 ---
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 상세", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 PDF 매칭"])

    # [TAB 1] 고객 조회
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']}) 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row.get('주민번호', '-')}")
                            st.write(f"**주소:** {row.get('주소', '-')}")
                            st.success(f"**💡 특이사항/계좌/보험목록:** {row.get('병력(특이사항)', '-')}")
                        with col2:
                            st.warning(f"**차량:** {row.get('차량번호', '미등록')} / **보험사:** {row.get('보험사', '미등록')}")
                            st.write(f"**만기:** {row.get('자동차만기일', '미등록')}")
                            try:
                                vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself', line_color='#E91E63'))
                                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=300, margin=dict(l=20,r=20,b=20,t=20))
                                st.plotly_chart(fig, use_container_width=True)
                            except: pass
            else: st.info("검색 결과가 없습니다.")

    # [TAB 2] AI 정보 등록 및 자동 병합
    with tab2:
        st.subheader("📝 텍스트로 정보 등록 및 자동 병합")
        raw_text = st.text_area("이름, 연락처, 주민번호, 주소, 계좌 등을 자유롭게 입력하세요", height=200)
        if st.button("🚀 데이터 분석 및 반영"):
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
                match_idx = db.index[(db['이름'] == name) & (db['연락처'] == phone)].tolist()
                if match_idx:
                    row_num = match_idx[-1] + 2
                    target_row = db.iloc[match_idx[-1]]
                    if not target_row['주민번호'] and ssn: sheet.update_cell(row_num, 3, ssn)
                    if not target_row['주소'] and addr: sheet.update_cell(row_num, 5, addr)
                    if memo:
                        new_memo = (target_row['병력(특이사항)'] + " " + memo).strip()
                        sheet.update_cell(row_num, 7, new_memo)
                    st.success(f"✅ {name} 고객님 정보 업데이트 완료!")
                    st.rerun()
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, memo.strip(), name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 신규 등록 완료!")
                    st.rerun()
            else: st.error("이름과 연락처를 확인해주세요.")

    # [TAB 3] 자동차 증권 업데이트
    with tab3:
        st.subheader("🚘 자동차 보험 증권 업데이트")
        update_input = st.text_input("입력 형식: 이름, 차량번호, 보험사, 만기일")
        if st.button("✅ 증권 정보 클라우드 반영"):
            parts = [p.strip() for p in update_input.split(',')]
            if len(parts) >= 4:
                t_name, t_car, t_comp, t_exp = parts[0], parts[1], parts[2], parts[3]
                idx_list = db.index[db['이름'] == t_name].tolist()
                if idx_list:
                    row_num = idx_list[-1] + 2
                    sheet.update_cell(row_num, 13, t_car)
                    sheet.update_cell(row_num, 14, t_comp)
                    sheet.update_cell(row_num, 15, t_exp)
                    st.success(f"✅ {t_name}님 차량 정보 업데이트 완료!")
                    st.rerun()
                else: st.error("고객을 찾을 수 없습니다.")

    # [TAB 4] 보장분석 PDF 매칭
    with tab4:
        st.subheader("📄 보장분석 PDF 데이터 자동 매칭")
        up_file = st.file_uploader("PDF 파일을 업로드하세요", type=['pdf'])
        target_u = st.selectbox("업데이트할 고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        if up_file and target_u != "선택하세요":
            if st.button("🔍 PDF 분석 실행"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        text = "".join([page.extract_text() for page in pdf.pages])
                    ins_matches = re.findall(r'([가-힣]+보험|[가-힣]+공제)\s*(\d{1,3}(?:,\d{3})*원)?', text)
                    extracted = ", ".join(list(set([f"{m[0]}({m[1]})" for m in ins_matches]))[:10])
                    
                    match_idx = db.index[db['이름'] == target_u].tolist()
                    if match_idx:
                        row_num = match_idx[-1] + 2
                        new_memo = (db.iloc[match_idx[-1]]['병력(특이사항)'] + " | [보장분석] " + extracted).strip()
                        sheet.update_cell(row_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 데이터에 보험 목록이 반영되었습니다.")
                        st.write("**분석된 내용:**", extracted)
                        st.rerun()
                except Exception as e: st.error(f"분석 오류: {e}")
