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
        return all_worksheets[index] if len(all_worksheets) > index else None
    except: return None

# --- [전화번호/날짜 정제 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    if len(clean) == 11: return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}"
    elif len(clean) == 10: return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return phone_raw

def clean_date_to_str(date_val):
    # '2026.01.10' -> '20260110' 같이 숫자만 남겨서 형식을 통일
    return re.sub(r'[^0-9]', '', str(date_val))

# --- [2. 환경 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

# 고객/실적 데이터 로드
cust_values = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_values[1:], columns=cust_values[0]) if len(cust_values) > 1 else pd.DataFrame()

sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "생년월일", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if len(sales_values) > 1 else pd.DataFrame(columns=sales_headers)

# --- [3. 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v13.0")

# --- [4. 메뉴별 기능 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    if not db_sales.empty:
        # 날짜 정제 후 월별 계산
        db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'].str.replace('.', '-'), errors='coerce')
        db_sales['보험료_n'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        curr_m, curr_y = datetime.now().month, datetime.now().year
        this_m = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 이번 달 보험료 합계", f"{int(this_m['보험료_n'].sum()):,}원")
        m2.metric("📈 이번 달 체결 건수", f"{len(this_m)}건")
        m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료_n'].sum()):,}원")
        
        st.markdown("---")
        st.subheader("🎂 이번 달 생일 고객")
        today_m = datetime.now().strftime("%m")
        birth_list = db_cust[db_cust['주민번호'].str.slice(2, 4) == today_m]
        if not birth_list.empty:
            for _, r in birth_list.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {format_phone(r['연락처'])}")
        else: st.write("생일인 고객이 없습니다.")

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 입력 및 자동 보장 연동")
    with st.expander("➕ 실적 정보 입력", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        i_date = c1.date_input("계약날짜", datetime.now())
        i_name = c2.text_input("고객명")
        i_birth = c3.text_input("생일(6자리)")
        i_prod = c4.text_input("상품명")
        i_price = c5.text_input("보험료")
        
        if st.button("🚀 실적 저장"):
            if i_name and i_prod and i_price:
                price_c = re.sub(r'[^0-9]', '', i_price)
                # 1. 실적 시트 저장
                sheet_sales.append_row([str(i_date), i_name, i_birth, i_prod, price_c])
                
                # 2. 보장 연동 (중복 방지용 날짜 정제 포함)
                match = db_cust[(db_cust['이름'] == i_name) & (db_cust['주민번호'].str.startswith(i_birth))]
                if not match.empty:
                    row_idx = match.index[-1] + 2
                    old = match.iloc[-1]['병력(특이사항)']
                    new_e = f"{i_prod}/{price_c}/{i_date}"
                    updated = f"{old} | {new_e}" if "[보장분석]" in old else f"{old.strip()} | [보장분석] {new_e}".strip(" | ")
                    sheet_cust.update_cell(row_idx, 7, updated)
                st.success("실적 저장 및 보장 연동 완료"); st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("이름 검색")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**🆔 주민번호:** {row['주민번호']}")
                    st.write(f"**🛠️ 직업:** {row['직업']}")
                with col2:
                    st.write(f"**🏠 주소:** {row['주소']}")
                    # 자동차보험 정보 표시 추가
                    if row.get('차량번호'):
                        st.info(f"**🚘 자동차:** {row['차량번호']} / {row.get('보험사','-')} ({row.get('자동차만기일','-')})")
                
                memo = row['병력(특이사항)']
                if "[보장분석]" in memo:
                    st.markdown("#### 📋 보유계약 리스트")
                    items = [i.strip() for i in memo.split("[보장분석]")[-1].split('|') if i.strip()]
                    
                    t_data, seen_keys = [], set()
                    for it in items:
                        p = [x.strip() for x in it.split('/') if x.strip()]
                        if len(p) >= 2:
                            d_v = p[-1] # 날짜
                            p_v = p[-2] if len(p) >= 3 else p[-1] # 보험료
                            prod_v = "/".join(p[:-2]) if len(p) >= 3 else p[0] # 상품명
                            
                            p_num = re.sub(r'[^0-9]', '', p_v)
                            # 날짜 형식과 상관없이 숫자만 뽑아서 중복 체크 (2026.01.10 == 2026-01-10)
                            dup_key = f"{p_num}_{clean_date_to_str(d_v)}"
                            
                            if dup_key not in seen_keys:
                                p_disp = f"{int(p_num):,}원" if p_num else p_v
                                t_data.append({"보험사/상품명": prod_v, "보험료": p_disp, "계약일": d_v})
                                seen_keys.add(dup_key)
                    if t_data: st.table(pd.DataFrame(t_data))
                    st.caption(f"💡 메모: {memo.split('[보장분석]')[0].strip()}")
                else: st.info(f"💡 메모: {memo}")

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    df_list = db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '직업', '자동차만기일']].copy()
    df_list['연락처'] = df_list['연락처'].apply(format_phone)
    st.dataframe(df_list, use_container_width=True)

# (신규등록, 자동차 업데이트, 보험청구 메뉴 유지)
