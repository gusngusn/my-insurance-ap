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

st.set_page_config(page_title="현우 통합 관리 v6.7", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.7")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회/수정", "✍️ 고객정보 신규등록", "🚘 자동차증권 업데이트", "📄 보장분석 리스트 입력"])

    # [TAB 1] 고객 조회 - "현장 상담용" 깔끔한 표 출력
    with tab1:
        search_name = st.text_input("🔎 고객 성함 검색 (예: 최점순)")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} 고객님 상세 정보", expanded=True):
                        # 1. 기본 인적사항
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                        with col2:
                            st.write(f"**주소:** {row['주소']}")
                            st.write(f"**가족대표:** {row['가족대표']}")

                        st.markdown("---")

                        # 2. 보유계약 리스트 (가독성 핵심 로직)
                        memo = row['병력(특이사항)']
                        if "[보장분석]" in memo:
                            st.subheader("📋 현재 보유계약 현황")
                            
                            # 데이터 정제 및 표 변환
                            analysis_data = memo.split("[보장분석]")[-1]
                            raw_items = [i.strip() for i in analysis_part.split('|') if i.strip()]
                            
                            refined_list = []
                            for item in raw_items:
                                # 제목줄 및 찌꺼기 차단
                                if any(trash in item for trash in ["No", "회사", "상품명", "계약일"]): continue
                                
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    refined_list.append({
                                        "보험회사": parts[0].strip(),
                                        "상품명": parts[1].strip(),
                                        "월 보험료": parts[2].strip() if len(parts) > 2 else "-",
                                        "가입날짜": parts[3].strip() if len(parts) > 3 else "-"
                                    })
                            
                            if refined_list:
                                df_final = pd.DataFrame(refined_list).drop_duplicates()
                                # 인덱스 없이 깔끔한 표 출력
                                st.table(df_final)
                                
                                # 총 보험료 자동 합산 (숫자만 추출)
                                prices = [int(re.sub(r'[^0-9]', '', d['월 보험료'])) for d in refined_list if re.sub(r'[^0-9]', '', d['월 보험료']).isdigit()]
                                if prices:
                                    st.markdown(f"💰 **합계 보험료: {sum(prices):,}원**")
                            
                            # 3. 병력 및 기타 특이사항 별도 표시
                            st.markdown("---")
                            st.info(f"**💡 병력 및 특이사항:**\n{memo.split('[보장분석]')[0].strip()}")
                        else:
                            st.info(f"**💡 병력 및 특이사항:** {memo}")

    # [TAB 4] 수동 입력 - 양식 간소화
    with tab4:
        st.subheader("📄 보장분석 데이터 입력")
        target_name = st.selectbox("업데이트할 고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        st.help("형식: 보험사/상품명/보험료/가입일 | 보험사/상품명/보험료/가입일")
        u_input = st.text_area("보장분석 결과 붙여넣기", placeholder="흥국/누구나암보험/71,050원/2000.06.26 | 신한/건강보험/34,690원/2022.01.06")
        
        if st.button("🚀 데이터 업데이트"):
            if target_name != "선택하세요" and u_input:
                idx = db.index[db['이름'] == target_name].tolist()[-1]
                current_memo = db.iloc[idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
                # 덮어쓰기 방식으로 깔끔하게 저장
                sheet.update_cell(idx + 2, 7, f"{current_memo} | [보장분석] {u_input}")
                st.success("정보가 최신본으로 업데이트되었습니다!"); st.rerun()

    # [TAB 2, 3] 생략 없이 전체 포함 (로직 최적화)
    with tab2:
        st.subheader("📝 신규 고객 등록")
        with st.form("add_user"):
            n, p = st.text_input("이름*"), st.text_input("연락처*")
            s, a = st.text_input("주민번호"), st.text_input("주소")
            m = st.text_area("특이사항")
            if st.form_submit_button("등록") and n and p:
                sheet.append_row([datetime.now().strftime("%Y-%m-%d"), n, s, p, a, "", m, n])
                st.success("등록 완료!"); st.rerun()

    with tab3:
        st.subheader("🚘 자동차 보험 업데이트")
        v_in = st.text_input("이름, 차량번호, 보험사, 만기일 (콤마 구분)")
        if st.button("업데이트"):
            ps = [x.strip() for x in v_in.split(',')]
            if len(ps) >= 4:
                idx = db.index[db['이름'] == ps[0]].tolist()
                if idx:
                    sheet.update_cell(idx[-1]+2, 13, ps[1])
                    sheet.update_cell(idx[-1]+2, 14, ps[2])
                    sheet.update_cell(idx[-1]+2, 15, ps[3])
                    st.success("반영 완료!"); st.rerun()
