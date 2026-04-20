import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- [보안 설정] ---
ACCESS_PASSWORD = "123456" 
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

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 보안 접속")
    pwd_input = st.text_input("접속 비밀번호 6자리를 입력하세요.", type="password")
    if st.button("접속하기"):
        if pwd_input == ACCESS_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else: st.error("❌ 비밀번호 오류")
    st.stop()

# --- 사이드바 메뉴 리스트 ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio(
        "이동할 메뉴를 선택하세요",
        ["🏠 홈", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트 (전체)", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식", "💬 고객문자발송(안내)"]
    )
    st.markdown("---")
    st.caption("v7.3 배현우 FC 전용 시스템")

sheet = get_gsheet()
all_values = sheet.get_all_values() if sheet else []
db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
db = db.fillna("")

# --- 메뉴별 화면 구현 ---

if menu == "🏠 홈":
    st.subheader("🏠 메인 대시보드")
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 고객 수", f"{len(db)}명")
    col2.metric("이번 달 신규", f"{len(db[db['날짜'].str.contains(datetime.now().strftime('%Y-%m'))])}명")
    st.info("왼쪽 메뉴를 통해 업무를 시작하세요.")

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name = st.text_input("고객 성함 입력")
    if name:
        res = db[db['이름'].str.contains(name)]
        for _, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                st.write(f"주소: {row['주소']} / 주민번호: {row['주민번호']}")
                if row['차량번호']: st.success(f"자동차: {row['차량번호']} ({row['보험사']}) - 만기: {row['자동차만기일']}")

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 등록")
    quick = st.text_input("🚀 한 줄 간편 등록 (이름, 주민, 번호, 주소)")
    if st.button("즉시 등록") and quick:
        d = [i.strip() for i in quick.split(',')]
        new_row = [datetime.now().strftime("%Y-%m-%d"), d[0], d[1] if len(d)>1 else "", d[2] if len(d)>2 else "", d[3] if len(d)>3 else "", "", "", d[0]] + [""]*7
        sheet.append_row(new_row); st.success("완료"); st.rerun()

elif menu == "📑 고객리스트 (전체)":
    st.subheader("📑 전체 고객 리스트 (페이지당 30명)")
    page_size = 30
    total_pages = (len(db) // page_size) + (1 if len(db) % page_size > 0 else 0)
    page = st.number_input("페이지 선택", min_value=1, max_value=max(1, total_pages), step=1)
    start_idx = (page - 1) * page_size
    st.table(db[['날짜', '이름', '연락처', '주소', '자동차만기일']].iloc[start_idx : start_idx + page_size])

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    v_in = st.text_input("양식: 이름, 차량번호, 보험사, 만기일")
    if st.button("반영"):
        p = [x.strip() for x in v_in.split(',')]
        idx = db.index[db['이름'] == p[0]].tolist()
        if idx:
            r = idx[-1] + 2
            sheet.update_cell(r, 13, p[1]); sheet.update_cell(r, 14, p[2]); sheet.update_cell(r, 15, p[3])
            st.success("반영 완료"); st.rerun()

elif menu == "📄 보장분석리스트 입력":
    st.subheader("📄 보장분석 결과 입력")
    target = st.selectbox("고객 선택", db['이름'].unique())
    u_in = st.text_area("내용 붙여넣기 (사/품/료/일 | ...)")
    if st.button("업데이트"):
        idx = db.index[db['이름'] == target].tolist()[-1]
        old = db.iloc[idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
        sheet.update_cell(idx + 2, 7, f"{old} | [보장분석] {u_in}")
        st.success("업데이트 완료"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 주요 보험사 보험청구 양식 다운로드")
    st.markdown("""
    * [삼성화재 청구양식](https://www.samsungfire.com/customer/claim/reward/reward_01.html)
    * [DB손해보험 청구양식](https://www.idbins.com/FWCRRE1001.do)
    * [현대해상 청구양식](https://www.hi.co.kr/service/claim/guide/form.do)
    * [메리츠화재 청구양식](https://www.meritzfire.com/compensation/guide/claim-guide.do)
    * [KB손해보험 청구양식](https://www.kbinsure.co.kr/CG302010001.ec)
    """)

elif menu == "💬 고객문자발송(안내)":
    st.subheader("💬 고객 문자 발송 시스템 안내")
    st.write("시스템에서 직접 문자를 보내려면 **알리고(Aligo)** 같은 SMS API 연동이 필요합니다.")
    st.info("""
    **[문자 발송 구현 방법]**
    1. **알리고(aligo.in)** 회원가입 후 API Key 발급
    2. 파이썬 `requests` 라이브러리를 통해 API 호출 코드 삽입
    3. 버튼 하나로 '자동차 만기 안내' 또는 '생일 축하' 문자 자동 발송 가능
    
    *필요하시면 알리고 연동 코드를 짜드릴 수 있습니다. (발송당 비용 약 8~10원 발생)*
    """)
