import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta

# --- [1. 구글 시트 설정] ---
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

# --- [전화번호 포맷 변환 함수: 공백/특수문자 완벽 대응] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    # 모든 공백 및 특수문자 제거 후 숫자만 추출
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if len(clean) == 11:
        return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10:
        return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

# --- [3. 메뉴 구성] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🔍 고객조회/수정", "📊 실적 관리", "📑 고객리스트", "🏠 홈"])
    st.caption("배현우 FC 전용 v12.3")

# --- [4. 고객조회 핵심 로직] ---
if menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함 입력")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        if not res.empty:
            for idx, row in res.iterrows():
                # 1. 전화번호 형식 강제 교정
                display_phone = format_phone(row['연락처'])
                
                with st.expander(f"👤 {row['이름']} ({display_phone})", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**🆔 주민번호:** {row['주민번호']}")
                        st.write(f"**🛠️ 직업:** {row['직업']}")
                    with c2:
                        st.write(f"**🏠 주소:** {row['주소']}")
                        if row['차량번호']: st.info(f"**🚘 차량:** {row['차량번호']} ({row['자동차만기일']})")

                    # 2. 보장분석 중복 제거 로직 강화
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.markdown("#### 📋 보유계약 리스트")
                        ana_part = memo.split("[보장분석]")[-1].strip()
                        items = [i.strip() for i in ana_part.split('|') if i.strip()]
                        
                        t_data, seen_keys = [], set()
                        for it in items:
                            p = [x.strip() for x in it.split('/') if x.strip()]
                            if len(p) >= 2:
                                date_v, price_v = p[-1], p[-2] if len(p) >= 3 else p[-1]
                                prod_v = "/".join(p[:-2]) if len(p) >= 3 else p[0]
                                
                                price_num = re.sub(r'[^0-9]', '', price_v)
                                price_disp = f"{int(price_num):,}원" if price_num else price_v
                                
                                # 중복 판단 기준: 보험사/상품명에서 공백 제거 후 앞 10글자 + 가격 조합
                                # 이렇게 하면 '삼성생명 치아'와 '삼성생명/삼성 치아' 같은 유사 중복을 더 잘 잡아냅니다.
                                simplified_name = re.sub(r'[^가-힣A-Za-z0-9]', '', prod_v)[:10]
                                check_key = f"{simplified_name}_{price_num}"
                                
                                if check_key not in seen_keys:
                                    t_data.append({"보험사/상품명": prod_v, "보험료": price_disp, "계약일": date_v})
                                    seen_keys.add(check_key)
                        
                        if t_data: st.table(pd.DataFrame(t_data))
                        st.info(f"**💡 기타 메모:** {memo.split('[보장분석]')[0].strip()}")
                    
                    # 3. 수정 폼 (주민번호/연락처 포함)
                    with st.form(key=f"edit_v123_{idx}"):
                        st.write("✏️ **정보 수정**")
                        sc1, sc2 = st.columns(2)
                        up_jumin = sc1.text_input("주민번호", value=row['주민번호'])
                        up_phone = sc2.text_input("연락처", value=row['연락처'])
                        up_addr = st.text_input("주소", value=row['주소'])
                        up_memo = st.text_area("전체 메모", value=row['병력(특이사항)'])
                        if st.form_submit_button("✅ 저장"):
                            row_num = idx + 2
                            sheet_cust.update_cell(row_num, 3, up_jumin)
                            sheet_cust.update_cell(row_num, 4, up_phone)
                            sheet_cust.update_cell(row_num, 5, up_addr)
                            sheet_cust.update_cell(row_num, 7, up_memo)
                            st.success("정보가 업데이트되었습니다."); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    display_db = db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '직업']].copy()
    display_db['연락처'] = display_db['연락처'].apply(format_phone)
    st.dataframe(display_db, use_container_width=True)
