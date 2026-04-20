import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- [보안 설정] 접속 비밀번호 ---
ACCESS_PASSWORD = "123456" 

# --- 1. 구글 시트 연결 설정 ---
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

st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

# --- 비밀번호 확인 로직 ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 보안 접속")
    pwd_input = st.text_input("접속 비밀번호 6자리를 입력하세요.", type="password")
    if st.button("접속하기"):
        if pwd_input == ACCESS_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 올바르지 않습니다.")
    st.stop()

# --- 메인 프로그램 시작 ---
st.title("🛡️ 배현우 고객관리 시스템 v7.1")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if all_values:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
    else:
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회/수정", "✍️ 고객정보 신규등록", "🚘 자동차증권 업데이트", "📄 보장분석 리스트 입력"])

    # [TAB 1] 고객 조회 (기존과 동일)
    with tab1:
        search_name = st.text_input("🔎 고객 성함 검색")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("📌 기본 정보")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                        with col2:
                            st.subheader("🚘 자동차 보험 정보")
                            if row['차량번호'] and row['차량번호'] != "":
                                st.success(f"**차량번호:** {row['차량번호']}")
                                st.write(f"**가입보험사:** {row['보험사']}")
                                st.warning(f"**📅 자동차 만기일: {row['자동차만기일']}**")
                            else:
                                st.info("등록된 자동차 정보 없음")
                        st.markdown("---")
                        memo = row['병력(특이사항)']
                        if "[보장분석]" in memo:
                            st.subheader("📋 보유계약현황")
                            analysis_part = memo.split("[보장분석]")[-1]
                            raw_items = [i.strip() for i in analysis_part.split('|') if i.strip()]
                            refined_list = []
                            for item in raw_items:
                                p = item.split('/')
                                if len(p) >= 2:
                                    refined_list.append({"보험회사": p[0].strip(), "상품명": p[1].strip(), "월 보험료": p[2].strip() if len(p) > 2 else "-", "가입날짜": p[3].strip() if len(p) > 3 else "-"})
                            if refined_list:
                                st.table(pd.DataFrame(refined_list).drop_duplicates())
                            st.info(f"**💡 특이사항:** {memo.split('[보장분석]')[0].strip()}")
                        else:
                            st.info(f"**💡 특이사항/병력:** {memo}")

    # [TAB 2] 고객정보 신규등록 (항목 확대 수정 완료)
    with tab2:
        st.subheader("📝 신규 고객 상세 등록")
        with st.form("comprehensive_reg"):
            c1, c2 = st.columns(2)
            new_name = c1.text_input("고객 성함*", help="필수 입력")
            new_phone = c2.text_input("연락처*", help="필수 입력")
            new_ssn = c1.text_input("주민번호")
            new_addr = c2.text_input("주소")
            new_memo = st.text_area("병력 및 특이사항")
            new_family = st.text_input("가족대표 (본인이면 이름 재입력)")
            
            submit_btn = st.form_submit_button("🚀 고객 정보 저장")
            
            if submit_btn:
                if new_name and new_phone:
                    # 구글 시트 양식에 맞춰 데이터 배열 생성 (15개 컬럼)
                    new_row = [
                        datetime.now().strftime("%Y-%m-%d"), # 날짜
                        new_name,                            # 이름
                        new_ssn,                             # 주민번호
                        new_phone,                           # 연락처
                        new_addr,                            # 주소
                        "",                                  # 직업 (공란)
                        new_memo,                            # 병력(특이사항)
                        new_family if new_family else new_name, # 가족대표
                        "", "", "", "",                      # 암, 뇌, 심, 수술 (공란)
                        "", "", ""                           # 차량번호, 보험사, 만기일 (공란)
                    ]
                    sheet.append_row(new_row)
                    st.success(f"✅ {new_name}님 정보가 성공적으로 등록되었습니다!"); st.rerun()
                else:
                    st.error("❌ 이름과 연락처는 필수 입력 항목입니다.")

    # [TAB 3, 4] 기존 기능 유지
    with tab3:
        st.subheader("🚘 자동차 보험 정보 업데이트")
        v_in = st.text_input("이름, 차량번호, 보험사, 만기일")
        if st.button("✅ 반영하기"):
            ps = [x.strip() for x in v_in.split(',')]
            if len(ps) >= 4:
                idx_list = db.index[db['이름'] == ps[0]].tolist()
                if idx_list:
                    r_num = idx_list[-1] + 2
                    sheet.update_cell(r_num, 13, ps[1])
                    sheet.update_cell(r_num, 14, ps[2])
                    sheet.update_cell(r_num, 15, ps[3])
                    st.success(f"✅ {ps[0]}님 차량 정보 업데이트 완료!"); st.rerun()

    with tab4:
        st.subheader("📄 보장분석 리스트 입력")
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        u_input = st.text_area("보장분석 결과 (보험사/상품명/보험료/날짜 | ...)")
        if st.button("🚀 데이터 반영"):
            if target_u != "선택하세요" and u_input:
                match_idx = db.index[db['이름'] == target_u].tolist()[-1]
                current_memo = db.iloc[match_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
                sheet.update_cell(match_idx + 2, 7, f"{current_memo} | [보장분석] {u_input}")
                st.success("보장분석 리스트 반영 완료!"); st.rerun()
