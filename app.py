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

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # 시트 인덱스 오류 방지
        all_sheets = client.open_by_key(SHEET_ID).worksheets()
        if index < len(all_sheets):
            return all_sheets[index]
        else:
            # 2번째 시트가 없으면 새로 생성
            return client.open_by_key(SHEET_ID).add_worksheet(title="보장분석데이터", rows="100", cols="20")
    except Exception as e:
        st.error(f"시트 연결 오류: {e}")
        return None

# --- [2. PDF 분석 함수 (추출 로직 강화)] ---
def parse_pdf(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            for line in lines:
                # 날짜 (0000.00.00 / 0000-00-00 / 00000000)
                date_m = re.search(r'(\d{4}[.\-]\d{2}[.\-]\d{2})|(\d{8})', line)
                # 금액 (숫자 + , + 원/만/억)
                price_m = re.search(r'(\d{1,3}(,\d{3})*원?)|(\d+만?원)', line)
                
                if date_m and price_m:
                    dt = date_m.group()
                    pr = price_m.group()
                    parts = line.split()
                    comp = parts[0] if parts else "미확인"
                    # 회사, 날짜, 금액 제외한 나머지를 상품명으로
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append([dt, comp, prod, pr])
    return results

# --- [3. 메인 로직] ---
st.set_page_config(page_title="FC 보장분석 시스템 v33.0", layout="wide")

sheet_cust = get_gsheet(0)
sheet_analysis = get_gsheet(1)

# 데이터 로드
if sheet_cust and sheet_analysis:
    c_raw = sheet_cust.get_all_values()
    db_cust = pd.DataFrame(c_raw[1:], columns=c_raw[0]) if len(c_raw) > 1 else pd.DataFrame()
    
    a_raw = sheet_analysis.get_all_values()
    # 2번째 시트 헤더가 없으면 자동 생성
    if not a_raw:
        sheet_analysis.append_row(["가입날짜", "보험회사", "상품명", "금액", "고객명"])
        db_analysis = pd.DataFrame(columns=["가입날짜", "보험회사", "상품명", "금액", "고객명"])
    else:
        db_analysis = pd.DataFrame(a_raw[1:], columns=a_raw[0])
else:
    st.error("구글 시트 로드 실패. Secrets 설정을 확인하세요.")
    st.stop()

# --- [4. UI 구성] ---
menu = st.sidebar.radio("메뉴", ["👤 고객조회", "📄 PDF 업로드"])

if menu == "📄 PDF 업로드":
    st.title("📄 보장분석 데이터 전송")
    target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else ["고객 없음"])
    upf = st.file_uploader("PDF 파일 선택", type="pdf")

    if upf and target != "선택":
        if st.button("🚀 데이터 분석 및 시트 전송"):
            items = parse_pdf(upf)
            if items:
                # 전송 데이터 생성
                final_rows = []
                for item in items:
                    item.append(target) # 고객명 추가
                    final_rows.append(item)
                
                try:
                    # 행 한꺼번에 추가 (속도 향상 및 오류 방지)
                    sheet_analysis.append_rows(final_rows)
                    st.success(f"✅ {len(items)}건의 데이터가 '보장분석데이터' 시트에 성공적으로 전송되었습니다.")
                    st.balloons()
                except Exception as e:
                    st.error(f"시트 전송 중 오류 발생: {e}")
            else:
                st.error("❌ PDF에서 날짜와 금액 정보를 찾지 못했습니다. 파일 내용을 확인해주세요.")

elif menu == "👤 고객조회":
    st.title("🔍 고객별 보험 내역 조회")
    search = st.text_input("고객명 입력")
    if search:
        # 고객 기본 정보
        c_info = db_cust[db_cust['이름'] == search]
        if not c_info.empty:
            st.subheader(f"👤 {search} 고객 정보")
            st.table(c_info)
            
            # 2번째 시트에서 내역 필터링
            st.markdown("---")
            st.subheader("📊 가입 보험 상세 내역")
            # 고객명 열이 존재하는지 확인 후 필터링
            if '고객명' in db_analysis.columns:
                p_list = db_analysis[db_analysis['고객명'] == search]
                if not p_list.empty:
                    st.dataframe(p_list[["가입날짜", "보험회사", "상품명", "금액"]], use_container_width=True)
                else:
                    st.info("등록된 내역이 없습니다.")
            else:
                st.error("2번째 시트에 '고객명' 컬럼이 없습니다.")
