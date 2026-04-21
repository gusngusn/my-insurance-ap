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
    except:
        return None

# --- [2. PDF 보유계약 리스트 정밀 분석 함수] ---
def parse_contract_list(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            # '보유계약' 페이지를 찾습니다.
            if text and any(k in text for k in ["보유계약", "계약현황"]):
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # 데이터 정제 (None 값 제거)
                        row = [str(item).replace('\n', ' ').strip() for item in row if item is not None]
                        row_text = " ".join(row)
                        
                        # 날짜와 금액 패턴 확인
                        date_m = re.search(r'\d{4}[.\-/]\d{2}[.\-/]\d{2}', row_text)
                        price_m = re.search(r'[\d,]{3,}원?', row_text)
                        
                        if date_m and price_m:
                            dt = date_m.group()
                            pr = price_m.group()
                            
                            # 회사명 및 상품명 정밀 추출
                            # 롯데손해보험 시스템의 경우 '롯데손보' 혹은 '메리츠' 등이 텍스트에 포함됨
                            comp = "미확인"
                            if "롯데" in row_text: comp = "롯데손해보험"
                            elif "메리츠" in row_text: comp = "메리츠화재"
                            elif "DB" in row_text: comp = "DB손해보험"
                            elif "현대" in row_text: comp = "현대해상"
                            
                            # 상품명: 전체 텍스트에서 날짜/금액/회사명을 제외한 긴 문장
                            prod = row_text.replace(dt, "").replace(pr, "").replace("롯데손해보험", "").replace("메리츠화재", "").strip()
                            # 불필요한 공백 및 숫자 제거
                            prod = re.sub(r'^\d+\s', '', prod) 
                            
                            results.append({"회사": comp, "상품": prod, "날짜": dt, "금액": pr})
    return results

# --- [3. 메인 화면] ---
st.set_page_config(page_title="보유계약 자동 입력 v42.0", layout="wide")
sheet = get_gsheet()
if sheet:
    raw_data = sheet.get_all_values()
    db_cust = pd.DataFrame(raw_data[1:], columns=raw_data[0]) if raw_data else pd.DataFrame()

st.title("📄 보유계약 리스트 정밀 추출")

target = st.selectbox("1. 대상 고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else [])
up_file = st.file_uploader("2. 보장분석 PDF 업로드", type="pdf")

if up_file and target != "선택":
    if st.button("🚀 보유계약 정밀 추출 및 시트 전송"):
        items = parse_contract_list(up_file)
        
        if items:
            row_idx = db_cust[db_cust['이름'] == target].index[-1] + 2
            
            # 셀별 줄바꿈 데이터 생성
            c_v = "\n".join([i['회사'] for i in items])
            p_v = "\n".join([i['상품'] for i in items])
            d_v = "\n".join([i['날짜'] for i in items])
            m_v = "\n".join([i['금액'] for i in items])
            
            try:
                # 9:보험사, 10:상품명, 11:가입날짜, 12:금액
                sheet.update_cell(row_idx, 9, c_v)
                sheet.update_cell(row_idx, 10, p_v)
                sheet.update_cell(row_idx, 11, d_v)
                sheet.update_cell(row_idx, 12, m_v)
                
                st.success(f"✅ {target}님 보유계약 {len(items)}건 입력 성공!")
                st.table(pd.DataFrame(items))
            except Exception as e:
                st.error(f"시트 전송 실패: {e}")
