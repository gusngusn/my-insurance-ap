import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber

# --- [1. 구글 시트 연결] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except: return None

# --- [2. PDF 보유계약 리스트 정밀 분석] ---
def parse_contract_list(file):
    results = []
    with pdfplumber.open(file) as pdf:
        # '보유계약' 관련 키워드가 있는 페이지만 필터링
        for page in pdf.pages:
            text = page.extract_text()
            if text and any(k in text for k in ["보유계약", "계약현황", "보험료 납입"]):
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_text = " ".join([str(item) for item in row if item])
                        # 날짜와 금액이 모두 있는 '계약 라인'만 추출
                        date_m = re.search(r'\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2}', row_text)
                        price_m = re.search(r'[\d,]{3,}원?', row_text)
                        
                        if date_m and price_m:
                            dt, pr = date_m.group(), price_m.group()
                            comp = str(row[0]).split('\n')[0] if row[0] else "미확인"
                            prod = row_text.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                            results.append({"comp": comp, "prod": prod, "date": dt, "price": pr})
    return results

# --- [3. 메인 화면 구성] ---
st.set_page_config(page_title="보유계약 자동 입력", layout="wide")

# 시트 데이터 로드
sheet = get_gsheet()
if sheet:
    raw_data = sheet.get_all_values()
    headers = raw_data[0] if raw_data else []
    db_cust = pd.DataFrame(raw_data[1:], columns=headers) if len(raw_data) > 1 else pd.DataFrame()

# 불필요한 사이드바 설정 제거
st.title("📄 보유계약 리스트 자동 매칭 시스템")
st.write("PDF의 [보유계약 현황] 페이지 데이터만 추출하여 시트의 지정된 셀에 입력합니다.")

# 메인 UI
target = st.selectbox("1. 대상 고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else [])
up_file = st.file_uploader("2. 보장분석 PDF 업로드", type="pdf")

if up_file and target != "선택":
    if st.button("🚀 보유계약 리스트 추출 및 시트 전송"):
        with st.spinner("보유계약 페이지만 골라 분석 중입니다..."):
            items = parse_contract_list(up_file)
            
            if items:
                # 행 번호 확인
                row_idx = db_cust[db_cust['이름'] == target].index[-1] + 2
                
                # 셀별 줄바꿈 데이터 생성
                c_v = "\n".join([i['comp'] for i in items])
                p_v = "\n".join([i['prod'] for i in items])
                d_v = "\n".join([i['date'] for i in items])
                m_v = "\n".join([i['price'] for i in items])
                
                # 열 위치 고정 (I=9, J=10, K=11, L=12)
                try:
                    sheet.update_cell(row_idx, 9, c_v)  # 보험사
                    sheet.update_cell(row_idx, 10, p_v) # 상품명
                    sheet.update_cell(row_idx, 11, d_v) # 가입날짜
                    sheet.update_cell(row_idx, 12, m_v) # 금액
                    
                    st.success(f"✅ {target}님 보유계약 {len(items)}건 입력 성공!")
                    st.table(pd.DataFrame(items)) # 화면에 리스트 확인용 출력
                except Exception as e:
                    st.error(f"시트 전송 실패: {e}")
            else:
                st.error("PDF에서 보유계약 리스트를 찾지 못했습니다. 파일 내용을 확인해주세요.")
