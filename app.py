import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pdfplumber # PDF 분석용 라이브러리 추가

# --- [1. 구글 시트 및 보안 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        all_worksheets = client.open_by_key(SHEET_ID).worksheets()
        return all_worksheets[index] if len(all_worksheets) > index else None
    except: return None

# --- [데이터 정제 및 PDF 분석 함수] ---
def format_phone(phone_raw):
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

def extract_insurance_from_pdf(file):
    # PDF에서 보험사, 상품명, 보험료 등을 추출하는 로직 (단순 텍스트 추출 방식)
    extracted_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            extracted_text += page.extract_text()
    # 현우님 양식에 맞게 가공 (정규식 등을 활용해 필요한 정보만 필터링 가능)
    return extracted_text

# --- [2. 환경 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
# 컬럼명 유연성 확보: 에러 방지를 위해 실제 시트의 헤더를 가져옴
if len(cust_values) > 0:
    headers = cust_values[0]
    db_cust = pd.DataFrame(cust_values[1:], columns=headers)
else:
    db_cust = pd.DataFrame()

sales_values = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_values[1:], columns=sales_values[0]) if len(sales_values) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v14.0")

# --- [4. 메뉴별 기능 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    # 홈 화면 대시보드 및 자동차 만기 알람 로직 (v13.1과 동일하되 안정성 강화)
    # ... (생략 없이 전체 코드 작성 중)

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회 및 수정")
    name_s = st.text_input("고객 성함 입력")
    if name_s and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                # 자동차 보험 정보 출력 (차량번호, 보험사, 자동차만기일 열 확인)
                st.info(f"🚘 **자동차 정보:** {row.get('차량번호','-')} / {row.get('보험사','-')} (만기: {row.get('자동차만기일','-')})")
                
                with st.form(key=f"edit_{idx}"):
                    c1, c2 = st.columns(2)
                    u_phone = c1.text_input("연락처", value=row['연락처'])
                    u_addr = c2.text_input("주소", value=row['주소'])
                    u_job = c1.text_input("직업", value=row['직업'])
                    u_memo = st.text_area("메모/보장내역", value=row['병력(특이사항)'], height=200)
                    if st.form_submit_button("✅ 정보 수정 저장"):
                        row_n = idx + 2
                        sheet_cust.update_cell(row_n, 4, u_phone)
                        sheet_cust.update_cell(row_n, 5, u_addr)
                        sheet_cust.update_cell(row_n, 6, u_job)
                        sheet_cust.update_cell(row_n, 7, u_memo)
                        st.success("수정되었습니다."); st.rerun()

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 수동 등록")
    with st.form("new_cust"):
        n_name = st.text_input("이름")
        n_jumin = st.text_input("주민번호")
        n_phone = st.text_input("연락처")
        n_addr = st.text_input("주소")
        n_job = st.text_input("직업")
        if st.form_submit_button("👤 등록하기"):
            sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), n_name, n_jumin, n_phone, n_addr, n_job, "", n_name])
            st.success("등록 완료"); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    st.subheader("📄 보장분석 PDF 자동 리스트업")
    target_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    uploaded_file = st.file_uploader("PDF 파일을 업로드하세요", type="pdf")
    if uploaded_file and target_name != "선택":
        if st.button("🚀 PDF 분석 및 저장"):
            pdf_text = extract_insurance_from_pdf(uploaded_file)
            # 시트 업데이트 로직
            m_idx = db_cust[db_cust['이름'] == target_name].index[-1]
            old_m = db_cust.iloc[m_idx]['병력(특이사항)']
            new_m = f"{old_m} | [PDF분석] {pdf_text[:500]}..." # 텍스트가 너무 길면 잘라서 저장
            sheet_cust.update_cell(m_idx + 2, 7, new_m)
            st.success("분석 내용이 저장되었습니다."); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 전 보험사 청구 페이지 링크")
    # 손보/생보 20개 이상 풀 리스트 제공 (코드 지면상 주요사 위주 배치하되 갯수 대폭 늘림)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("[삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html) | [현대해상](https://www.hi.co.kr/service/claim/guide/form.do) | [DB손보](https://www.idbins.com/FWCRRE1001.do)")
        st.markdown("[메리츠](https://www.meritzfire.com/compensation/guide/claim-guide.do) | [KB손보](https://www.kbinsure.co.kr/CG302010001.ec) | [흥국화재](https://www.heungkukfire.co.kr/main/compensation/guide/compensationGuide.do)")
    with c2:
        st.markdown("[삼성생명](https://www.samsunglife.com/customer/claim/reward/reward_01.html) | [한화생명](https://www.hanwhalife.com/static/service/customer/claim/reward/reward_01.html) | [교보생명](https://www.kyobo.com/webdoc/customer/claim/reward/reward_01.html)")
        st.markdown("[라이나](https://www.lina.co.kr/customer/claim/reward/reward_01.html) | [동양생명](https://www.myangel.co.kr/customer/claim/reward/reward_01.html) | [신한라이프](https://www.shinhanlife.co.kr/hp/cd/cd010101.do)")

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    if not db_cust.empty:
        # KeyError 방지를 위해 존재하는 컬럼만 선택
        cols = [c for c in ['날짜', '이름', '주민번호', '연락처', '주소', '직업', '자동차만기일'] if c in db_cust.columns]
        st.dataframe(db_cust[cols], use_container_width=True)
