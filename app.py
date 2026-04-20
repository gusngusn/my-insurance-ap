import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

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

st.set_page_config(page_title="현우 통합 관리 v6.8", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.8")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if all_values:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
    else:
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회/수정", "✍️ 고객정보 신규등록", "🚘 자동차증권 업데이트", "📄 보장분석 리스트 입력"])

    # [TAB 1] 고객 조회 - 오타 수정 및 깔끔한 출력
    with tab1:
        search_name = st.text_input("🔎 고객 성함 검색")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**주민번호:** {row['주민번호']}")
                        with c2:
                            st.write(f"**주소:** {row['주소']}")
                        
                        st.markdown("---")
                        
                        memo = row['병력(특이사항)']
                        if "[보장분석]" in memo:
                            st.subheader("📋 보유계약현황 리스트")
                            # 오타 수정: analysis_data를 analysis_part로 통일
                            analysis_part = memo.split("[보장분석]")[-1]
                            raw_items = [i.strip() for i in analysis_part.split('|') if i.strip()]
                            
                            refined_list = []
                            for item in raw_items:
                                if any(trash in item for trash in ["No", "회사", "상품명", "계약일"]): continue
                                p = item.split('/')
                                if len(p) >= 2:
                                    refined_list.append({
                                        "보험회사": p[0].strip(),
                                        "상품명": p[1].strip(),
                                        "월 보험료": p[2].strip() if len(p) > 2 else "-",
                                        "가입날짜": p[3].strip() if len(p) > 3 else "-"
                                    })
                            
                            if refined_list:
                                st.table(pd.DataFrame(refined_list).drop_duplicates())
                            
                            st.markdown("---")
                            st.info(f"**💡 특이사항:** {memo.split('[보장분석]')[0].strip()}")
                        else:
                            st.info(f"**💡 특이사항:** {memo}")

    # [TAB 4] 수동 입력 - 양식 덮어쓰기 로직
    with tab4:
        st.subheader("📄 보장분석 데이터 수동 입력")
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        u_input = st.text_area("보장분석 결과 입력 (보험사/상품명/보험료/날짜 | ...)")
        
        if st.button("🚀 반영하기"):
            if target_u != "선택하세요" and u_input:
                match_idx = db.index[db['이름'] == target_u].tolist()[-1]
                current_memo = db.iloc[match_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
                # 깔끔하게 기존 보장분석 덮어쓰기
                sheet.update_cell(match_idx + 2, 7, f"{current_memo} | [보장분석] {u_input}")
                st.success("데이터가 반영되었습니다!"); st.rerun()

    # [TAB 2, 3] 기존 로직 유지
    with tab2:
        st.subheader("📝 신규 등록")
        with st.form("new"):
            n, p = st.text_input("이름*"), st.text_input("연락처*")
            if st.form_submit_button("등록") and n and p:
                sheet.append_row([datetime.now().strftime("%Y-%m-%d"), n, "", p, "", "", "", n])
                st.success("등록 완료!"); st.rerun()

    with tab3:
        st.subheader("🚘 자동차 업데이트")
        v_in = st.text_input("이름, 차량, 보험사, 만기")
        if st.button("업데이트"):
            ps = [x.strip() for x in v_in.split(',')]
            if len(ps) >= 4:
                idx = db.index[db['이름'] == ps[0]].tolist()
                if idx:
                    sheet.update_cell(idx[-1]+2, 13, ps[1])
                    sheet.update_cell(idx[-1]+2, 14, ps[2])
                    sheet.update_cell(idx[-1]+2, 15, ps[3])
                    st.success("반영 완료!"); st.rerun()
