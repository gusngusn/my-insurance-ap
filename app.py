import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [1. 구글 시트 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        all_worksheets = client.open_by_key(SHEET_ID).worksheets()
        if len(all_worksheets) > index: return all_worksheets[index]
        return None
    except: return None

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v12.0")

# --- [4. 메뉴별 기능 구현] ---

if menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함 입력")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        if not res.empty:
            for idx, row in res.iterrows():
                with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                    st.write(f"🏠 **주소:** {row['주소']} / 🛠️ **직업:** {row['직업']}")
                    
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.markdown("#### 📋 보유계약 리스트")
                        # [보장분석] 키워드 이후의 텍스트만 추출
                        ana_part = memo.split("[보장분석]")[-1].strip()
                        # | 기호로 각 계약 건수 분리
                        items = [i.strip() for i in ana_part.split('|') if i.strip()]
                        # 중복 제거 (순서 유지)
                        unique_items = list(dict.fromkeys(items))
                        
                        t_data = []
                        for it in unique_items:
                            # / 기호로 데이터 분리
                            p = [x.strip() for x in it.split('/') if x.strip()]
                            
                            if len(p) >= 2:
                                # 1. 가장 마지막 항목은 '날짜'로 간주
                                date_val = p[-1]
                                # 2. 마지막에서 두 번째 항목은 '보험료'로 간주
                                price_raw = p[-2] if len(p) >= 3 else p[-1]
                                # 3. 나머지는 모두 '상품명'으로 합침
                                prod_name = "/".join(p[:-2]) if len(p) >= 3 else p[0]
                                
                                # 보험료 숫자만 추출해서 콤마 처리
                                price_num = re.sub(r'[^0-9]', '', price_raw)
                                price_display = f"{int(price_num):,}원" if price_num else price_raw
                                
                                t_data.append({
                                    "보험사/상품명": prod_name,
                                    "보험료": price_display,
                                    "계약일": date_val
                                })
                        
                        if t_data:
                            st.table(pd.DataFrame(t_data))
                        
                        # 기타 메모(보장분석 앞부분) 출력
                        etc_memo = memo.split('[보장분석]')[0].replace('|','').strip()
                        if etc_memo:
                            st.info(f"**💡 기타 메모:** {etc_memo}")
                    else:
                        st.info(f"**💡 메모:** {memo}")
                    
                    # 수정 폼
                    with st.form(key=f"edit_v12_{idx}"):
                        st.write("✏️ **정보 수정**")
                        c1, c2 = st.columns(2)
                        up_phone = c1.text_input("연락처", value=row['연락처'])
                        up_addr = c2.text_input("주소", value=row['주소'])
                        up_job = c1.text_input("직업", value=row['직업'])
                        up_memo = st.text_area("전체 메모(보장내역 포함)", value=row['병력(특이사항)'], height=150)
                        if st.form_submit_button("✅ 저장"):
                            row_num = idx + 2
                            sheet_cust.update_cell(row_num, 4, up_phone)
                            sheet_cust.update_cell(row_num, 5, up_addr)
                            sheet_cust.update_cell(row_num, 6, up_job)
                            sheet_cust.update_cell(row_num, 7, up_memo)
                            st.success("수정 완료"); st.rerun()

# (이외 메뉴는 이전 버전과 동일하게 유지)
