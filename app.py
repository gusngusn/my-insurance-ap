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

# --- [전화번호 포맷 함수: 010 유지] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

# --- [2. 데이터 로드 및 홈 화면 데이터 전처리] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

# 고객 데이터
cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

# 실적 데이터 (홈 화면용)
sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "생년월일", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if len(sales_values) > 1 else pd.DataFrame(columns=sales_headers)

# 홈 화면 실적 계산을 위한 데이터 정제
if not db_sales.empty:
    db_sales['보험료_num'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    # 다양한 날짜 형식(2026.04.21, 2026-04-21 등) 대응
    db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'].str.replace('.', '-'), errors='coerce')

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v12.5")

# --- [4. 메뉴별 기능] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    curr_m, curr_y = datetime.now().month, datetime.now().year
    
    if not db_sales.empty:
        this_m_data = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
        this_y_data = db_sales[db_sales['날짜_dt'].dt.year == curr_y]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 이번 달 합계", f"{int(this_m_data['보험료_num'].sum()):,}원")
        m2.metric("📈 이번 달 건수", f"{len(this_m_data)}건")
        m3.metric("🏆 올해 누적 실적", f"{int(this_y_data['보험료_num'].sum()):,}원")
    else:
        st.info("데이터가 없습니다.")

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함 입력")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        if not res.empty:
            for idx, row in res.iterrows():
                display_phone = format_phone(row['연락처'])
                with st.expander(f"👤 {row['이름']} ({display_phone})", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**🆔 주민번호:** {row['주민번호']}")
                        st.write(f"**🛠️ 직업:** {row['직업']}")
                    with c2:
                        st.write(f"**🏠 주소:** {row['주소']}")

                    # [보장분석 중복 제거: 금액+날짜 기준 절대 필터링]
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.markdown("#### 📋 보유계약 리스트")
                        items = [i.strip() for i in memo.split("[보장분석]")[-1].split('|') if i.strip()]
                        
                        t_data, seen_duplicates = [], set()
                        for it in items:
                            p = [x.strip() for x in it.split('/') if x.strip()]
                            if len(p) >= 2:
                                d_v, p_raw = p[-1], p[-2] if len(p) >= 3 else p[-1]
                                prod_v = "/".join(p[:-2]) if len(p) >= 3 else p[0]
                                p_num = re.sub(r'[^0-9]', '', p_raw)
                                
                                # 중복 체크 키: 금액과 날짜가 같으면 무조건 동일 상품 처리
                                dup_key = f"{p_num}_{d_v}"
                                if dup_key not in seen_duplicates:
                                    t_data.append({"보험사/상품명": prod_v, "보험료": f"{int(p_num):,}원" if p_num else p_raw, "계약일": d_v})
                                    seen_duplicates.add(dup_key)
                        
                        if t_data: st.table(pd.DataFrame(t_data))
                    
                    with st.form(key=f"edit_v125_{idx}"):
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
                            st.success("수정 완료"); st.rerun()

# (이외 메뉴는 v12.4 로직 유지)
