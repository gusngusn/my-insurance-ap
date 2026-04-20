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
st.title("🛡️ 배현우 고객관리 시스템 v7.2")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회/수정", "✍️ 고객정보 신규등록", "🚘 자동차증권 업데이트", "📄 보장분석 리스트 입력"])

    # [TAB 2] 고객정보 신규등록 (한 줄 간편 등록 기능 추가)
    with tab2:
        st.subheader("📝 신규 고객 등록")
        
        # --- NEW: 한 줄 간편 등록 섹션 ---
        with st.expander("🚀 한 줄로 간편 등록하기 (채팅창 내용 복사용)", expanded=True):
            quick_input = st.text_input("가공된 텍스트를 여기에 붙여넣으세요", placeholder="이흥식, 560310-1673932, 010-9646-4275, 대구 동구...")
            if st.button("즉시 등록"):
                if quick_input:
                    try:
                        data = [i.strip() for i in quick_input.split(',')]
                        # 최소 이름, 주민, 연락처, 주소 4개 항목 보장
                        q_name = data[0] if len(data) > 0 else ""
                        q_ssn = data[1] if len(data) > 1 else ""
                        q_phone = data[2] if len(data) > 2 else ""
                        q_addr = data[3] if len(data) > 3 else ""
                        
                        if q_name and q_phone:
                            new_row = [datetime.now().strftime("%Y-%m-%d"), q_name, q_ssn, q_phone, q_addr, "", "", q_name, "", "", "", "", "", "", ""]
                            sheet.append_row(new_row)
                            st.success(f"✅ {q_name}님 간편 등록 완료!")
                            st.rerun()
                        else:
                            st.error("데이터 형식이 맞지 않습니다. 이름과 연락처는 필수입니다.")
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

        st.markdown("---")
        st.write("▼ 직접 상세 입력하기")
        with st.form("detail_reg"):
            c1, c2 = st.columns(2)
            n, p = c1.text_input("성함*"), c2.text_input("연락처*")
            s, a = c1.text_input("주민번호"), c2.text_input("주소")
            m = st.text_area("특이사항")
            if st.form_submit_button("상세 등록 저장") and n and p:
                sheet.append_row([datetime.now().strftime("%Y-%m-%d"), n, s, p, a, "", m, n, "", "", "", "", "", "", ""])
                st.success(f"✅ {n}님 등록 완료!"); st.rerun()

    # [TAB 1, 3, 4] 기존 기능 유지 (생략 없이 포함)
    with tab1:
        search_name = st.text_input("🔎 고객 성함 검색")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                        with col2:
                            if row['차량번호']:
                                st.success(f"**차량:** {row['차량번호']} ({row['보험사']})")
                                st.warning(f"**만기:** {row['자동차만기일']}")
                        st.markdown("---")
                        memo = row['병력(특이사항)']
                        if "[보장분석]" in memo:
                            analysis_part = memo.split("[보장분석]")[-1]
                            raw_items = [i.strip() for i in analysis_part.split('|') if i.strip()]
                            refined_list = [{"보험사": p.split('/')[0], "상품명": p.split('/')[1], "료": p.split('/')[2] if len(p.split('/'))>2 else "-", "일": p.split('/')[3] if len(p.split('/'))>3 else "-"} for p in raw_items if len(p.split('/'))>=2]
                            if refined_list: st.table(pd.DataFrame(refined_list))
                            st.info(f"**💡 특이사항:** {memo.split('[보장분석]')[0].strip()}")
                        else: st.info(f"**💡 특이사항:** {memo}")

    with tab3:
        st.subheader("🚘 자동차 업데이트")
        v_in = st.text_input("이름, 차량번호, 보험사, 만기일")
        if st.button("자동차 반영"):
            ps = [x.strip() for x in v_in.split(',')]
            if len(ps) >= 4:
                idx = db.index[db['이름'] == ps[0]].tolist()
                if idx:
                    r = idx[-1] + 2
                    sheet.update_cell(r, 13, ps[1]); sheet.update_cell(r, 14, ps[2]); sheet.update_cell(r, 15, ps[3])
                    st.success("업데이트 완료!"); st.rerun()

    with tab4:
        st.subheader("📄 보장분석 입력")
        target_u = st.selectbox("고객 선택", ["선택"] + db['이름'].unique().tolist())
        u_input = st.text_area("보장분석 결과 (내용 복사 후 붙여넣기)")
        if st.button("보장분석 반영"):
            if target_u != "선택" and u_input:
                m_idx = db.index[db['이름'] == target_u].tolist()[-1]
                cur_m = db.iloc[m_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
                sheet.update_cell(m_idx + 2, 7, f"{cur_m} | [보장분석] {u_input}")
                st.success("반영 완료!"); st.rerun()
