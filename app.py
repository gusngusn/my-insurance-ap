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

# --- [전화번호 포맷 변환 함수] ---
def format_phone(phone_raw):
    # 숫자만 추출
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if len(clean) == 11:
        return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10:
        return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw # 형식이 맞지 않으면 원본 반환

# --- [2. 환경 설정 및 데이터 로드] ---
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
    st.caption("배현우 FC 전용 v12.2")

# --- [4. 메뉴별 기능 구현] ---

if menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함 입력")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        if not res.empty:
            for idx, row in res.iterrows():
                # 전화번호 포맷 적용
                display_phone = format_phone(row['연락처'])
                
                with st.expander(f"👤 {row['이름']} ({display_phone})", expanded=True):
                    c_info1, c_info2 = st.columns(2)
                    with c_info1:
                        st.write(f"**🆔 주민번호:** {row['주민번호']}")
                        st.write(f"**🛠️ 직업:** {row['직업']}")
                    with c_info2:
                        st.write(f"**🏠 주소:** {row['주소']}")
                        if row['차량번호']: st.success(f"**🚘 차량:** {row['차량번호']} ({row['자동차만기일']} 만기)")
                    
                    # 보장분석 리스트 (중복 제거 로직 포함)
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.markdown("#### 📋 보유계약 리스트")
                        ana_part = memo.split("[보장분석]")[-1].strip()
                        items = [i.strip() for i in ana_part.split('|') if i.strip()]
                        
                        t_data, seen = [], set()
                        for it in items:
                            p = [x.strip() for x in it.split('/') if x.strip()]
                            if len(p) >= 2:
                                date_val = p[-1]
                                price_raw = p[-2] if len(p) >= 3 else p[-1]
                                prod_name = "/".join(p[:-2]) if len(p) >= 3 else p[0]
                                price_num = re.sub(r'[^0-9]', '', price_raw)
                                price_display = f"{int(price_num):,}원" if price_num else price_raw
                                
                                contract_key = f"{prod_name}_{price_display}"
                                if contract_key not in seen:
                                    t_data.append({"보험사/상품명": prod_name, "보험료": price_display, "계약일": date_val})
                                    seen.add(contract_key)
                        if t_data: st.table(pd.DataFrame(t_data))
                        st.info(f"**💡 기타 메모:** {memo.split('[보장분석]')[0].replace('|','').strip()}")
                    else:
                        st.info(f"**💡 메모:** {memo}")
                    
                    # 정보 수정 폼
                    with st.form(key=f"edit_v122_{idx}"):
                        st.write("✏️ **정보 수정**")
                        sc1, sc2 = st.columns(2)
                        up_name = sc1.text_input("이름", value=row['이름'])
                        up_jumin = sc1.text_input("주민번호", value=row['주민번호'])
                        up_phone = sc2.text_input("연락처", value=row['연락처'])
                        up_job = sc2.text_input("직업", value=row['직업'])
                        up_addr = st.text_input("주소", value=row['주소'])
                        up_memo = st.text_area("전체 메모", value=row['병력(특이사항)'])
                        if st.form_submit_button("✅ 저장"):
                            row_num = idx + 2
                            sheet_cust.update_cell(row_num, 2, up_name)
                            sheet_cust.update_cell(row_num, 3, up_jumin)
                            sheet_cust.update_cell(row_num, 4, up_phone)
                            sheet_cust.update_cell(row_num, 5, up_addr)
                            sheet_cust.update_cell(row_num, 6, up_job)
                            sheet_cust.update_cell(row_num, 7, up_memo)
                            st.success("수정 완료"); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    # 리스트에서도 전화번호 포맷 적용
    display_db = db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '직업']].copy()
    display_db['연락처'] = display_db['연락처'].apply(format_phone)
    st.dataframe(display_db, use_container_width=True)

# (나머지 홈, 실적 관리 등은 v12.1과 동일하게 유지)
