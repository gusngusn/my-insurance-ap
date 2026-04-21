import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- [1. 구글 시트 연결] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1  # 고객정보가 있는 메인 시트
    except Exception as e:
        st.error(f"시트 연결 실패: {e}")
        return None

# --- [2. PDF 분석 함수] ---
def parse_pdf(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            for line in lines:
                date_m = re.search(r'\d{4}[.\-]\d{2}[.\-]\d{2}', line)
                price_m = re.search(r'\d{1,3}(,\d{3})*원?', line)
                if date_m and price_m:
                    parts = line.split()
                    comp = parts[0]
                    dt, pr = date_m.group(), price_m.group()
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"보험사": comp, "상품명": prod, "가입날짜": dt, "금액": pr})
    return results

# --- [3. 데이터 로드 및 UI] ---
st.set_page_config(page_title="배현우 FC 보유계약 관리", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    headers = raw_data[0]
    db_cust = pd.DataFrame(raw_data[1:], columns=headers)
    col_map = {col: i+1 for i, col in enumerate(headers)}
else:
    st.stop()

# 사이드바 메뉴
menu = st.sidebar.radio("메뉴", ["🔍 고객정보 및 보유계약", "📄 보장분석 PDF 업로드"])

# --- [4. 메뉴별 기능] ---

if menu == "📄 보장분석 PDF 업로드":
    st.title("📄 PDF 분석 -> 보유계약 셀 자동 매칭")
    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    up_file = st.file_uploader("보장분석 PDF 업로드", type="pdf")

    if up_file and target_name != "선택":
        if st.button("🚀 분석 데이터 해당 셀에 자동 입력"):
            items = parse_pdf(up_file)
            if items:
                # 해당 고객의 행 번호 찾기
                target_idx = db_cust[db_cust['이름'] == target_name].index[-1] + 2
                
                # 각 항목별 줄바꿈 데이터 생성
                new_comp = "\n".join([i['보험사'] for i in items])
                new_prod = "\n".join([i['상품명'] for i in items])
                new_date = "\n".join([i['가입날짜'] for i in items])
                new_price = "\n".join([i['금액'] for i in items])
                
                # 시트의 [보험사, 상품명, 가입날짜, 금액] 컬럼에 각각 입력
                # (주의: 시트 헤더 명칭이 아래와 정확히 일치해야 합니다)
                try:
                    if "보험사" in col_map: sheet.update_cell(target_idx, col_map["보험사"], new_comp)
                    if "상품명" in col_map: sheet.update_cell(target_idx, col_map["상품명"], new_prod)
                    if "가입날짜" in col_map: sheet.update_cell(target_idx, col_map["가입날짜"], new_date)
                    if "금액" in col_map: sheet.update_cell(target_idx, col_map["금액"], new_price)
                    
                    st.success(f"✅ {target_name} 고객님의 보유계약 셀 업데이트 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"시트 업데이트 중 오류: {e}")
            else:
                st.error("PDF에서 데이터를 추출하지 못했습니다.")

elif menu == "🔍 고객정보 및 보유계약":
    st.title("🔍 고객 상세 조회")
    search = st.text_input("고객명 검색")
    
    if search:
        res = db_cust[db_cust['이름'].str.contains(search)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} 고객 정보 상세", expanded=True):
                # 1. 기본 정보 출력
                st.write(f"**연락처:** {row.get('연락처', '')} | **주민번호:** {row.get('주민번호', '')}")
                
                # 2. 보유계약 리스트업 (줄바꿈된 셀 데이터를 표로 분리)
                st.markdown("### 📋 보유계약 현황")
                
                c_list = str(row.get('보험사', '')).split('\n')
                p_list = str(row.get('상품명', '')).split('\n')
                d_list = str(row.get('가입날짜', '')).split('\n')
                m_list = str(row.get('금액', '')).split('\n')
                
                # 데이터 행 맞추기
                max_row = max(len(c_list), len(p_list), len(d_list), len(m_list))
                table_data = []
                for i in range(max_row):
                    # 보험사나 상품명 중 하나라도 정보가 있는 경우에만 리스트 추가
                    comp_val = c_list[i] if i < len(c_list) else ""
                    prod_val = p_list[i] if i < len(p_list) else ""
                    if comp_val.strip() or prod_val.strip():
                        table_data.append({
                            "보험사": comp_val,
                            "상품명": prod_val,
                            "가입날짜": d_list[i] if i < len(d_list) else "",
                            "금액": m_list[i] if i < len(m_list) else ""
                        })
                
                if table_data:
                    st.table(pd.DataFrame(table_data))
                else:
                    st.info("등록된 보유계약 리스트가 없습니다.")
