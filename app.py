import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- 1. 구글 시트 연결 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 관리 v6.5", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.5")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if all_values:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
    else:
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회/수정", "✍️ 고객정보 신규등록", "🚘 자동차증권 업데이트", "📄 보장분석 리스트 입력"])

    # [TAB 1] 고객 조회 및 기존 데이터 확인
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                        st.write(f"**주민번호:** {row['주민번호']} | **주소:** {row['주소']}")
                        st.info(f"**보장분석/병력:** {row['병력(특이사항)']}")
            else:
                st.warning("등록된 고객 정보가 없습니다.")

    # [TAB 2] 고객정보 신규 등록 (양식형)
    with tab2:
        st.subheader("📝 고객 정보 신규 등록")
        with st.form("new_customer"):
            c1, c2 = st.columns(2)
            name = c1.text_input("고객 성함*")
            phone = c2.text_input("연락처*")
            ssn = c1.text_input("주민번호")
            addr = c2.text_input("주소")
            memo = st.text_area("특이사항/병력")
            submit = st.form_submit_button("🚀 고객 등록")
            if submit and name and phone:
                new_data = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, "", memo, name] + [""]*7
                sheet.append_row(new_data)
                st.success(f"{name}님 등록 완료!"); st.rerun()

    # [TAB 3] 자동차 증권 업데이트 (현우님 요청 양식)
    with tab3:
        st.subheader("🚘 자동차 증권 업데이트")
        u_input = st.text_input("입력 (양식: 이름, 차량번호, 보험사, 만기일)")
        if st.button("✅ 증권 반영"):
            parts = [p.strip() for p in u_input.split(',')]
            if len(parts) >= 4:
                target_name = parts[0]
                idx_list = db.index[db['이름'] == target_name].tolist()
                if idx_list:
                    r_num = idx_list[-1] + 2
                    sheet.update_cell(r_num, 13, parts[1]) # 차량번호
                    sheet.update_cell(r_num, 14, parts[2]) # 보험사
                    sheet.update_cell(r_num, 15, parts[3]) # 만기일
                    st.success(f"{target_name}님 자동차 증권 업데이트 완료!"); st.rerun()
                else: st.error("고객을 찾을 수 없습니다.")

    # [TAB 4] 보장분석 리스트 수동 입력 (현우님 요청 양식)
    with tab4:
        st.subheader("📄 보장분석 리스트 업데이트")
        st.write("제가 요약해드린 리스트를 아래 양식에 붙여넣으세요.")
        target_name = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        update_input = st.text_area("입력 (양식: 보험사/상품명/보험료/가입일 | 보험사/상품명...)", placeholder="예: 흥국/누구나암보험/71,050원/2000.06.26 | 신한/건강보험/34,690원/2022.01.06")
        
        if st.button("🚀 보장분석 결과 반영"):
            if target_name != "선택하세요" and update_input:
                idx_list = db.index[db['이름'] == target_name].tolist()
                if idx_list:
                    r_num = idx_list[-1] + 2
                    # 기존 메모 유지하며 뒤에 보장분석 추가
                    old_memo = db.iloc[idx_list[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                    new_val = f"{old_memo} | [보장분석] {update_input}"
                    sheet.update_cell(r_num, 7, new_val)
                    st.success("보유계약 리스트 반영 완료!"); st.rerun()
