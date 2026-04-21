import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import pdfplumber

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

# --- [데이터 정제 및 PDF 파싱 함수] ---
def format_phone(phone_raw):
    if not phone_raw: return ""
    clean = re.sub(r'[^0-9]', '', str(phone_raw))
    if clean.startswith('10') and len(clean) == 10: clean = '0' + clean
    return f"{clean[:3]}-{clean[3:7]}-{clean[7:]}" if len(clean) >= 10 else phone_raw

def parse_pdf_to_details(file):
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                date_match = re.search(r'\d{4}[.\-]\d{2}[.\-]\d{2}', line)
                price_match = re.search(r'\d{1,3}(,\d{3})*원?', line)
                if date_match and price_match:
                    parts = line.split()
                    company = parts[0]
                    date = date_match.group()
                    price = price_match.group()
                    product = line.replace(company, "").replace(date, "").replace(price, "").strip()
                    results.append({"회사": company, "상품": product, "날짜": date, "금액": price})
    return results

# --- [2. 메인 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 v20.0", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_data = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_data[1:], columns=cust_data[0]) if len(cust_data) > 1 else pd.DataFrame()
col_map = {col: i+1 for i, col in enumerate(db_cust.columns)}

sales_data = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_data[1:], columns=sales_data[0]) if len(sales_data) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴 (누락 없이 전체 복구)] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 가이드"])
    st.caption("배현우 FC 전용 v20.0")

# --- [4. 메뉴별 상세 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    if not db_sales.empty:
        db_sales['보험료_n'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'].str.replace('.', '-'), errors='coerce')
        curr_m, curr_y = datetime.now().month, datetime.now().year
        this_m = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 이번 달 보험료 합계", f"{int(this_m['보험료_n'].sum()):,}원")
        m2.metric("📈 이번 달 체결 건수", f"{len(this_m)}건")
        m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료_n'].sum()):,}원")
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎂 이번 달 생일 고객")
        this_m_s = datetime.now().strftime("%m")
        birth = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_m_s] if not db_cust.empty else []
        for _, r in birth.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]})")
    with c2:
        st.subheader("🚘 자동차 보험 만기 (30일 내)")
        today = datetime.now()
        for _, r in db_cust.iterrows():
            m_date = str(r.get('자동차만기일', '')).replace('.', '-').strip()
            try:
                dt = datetime.strptime(m_date, "%Y-%m-%d")
                if today <= dt <= today + timedelta(days=30): st.warning(f"⚠️ **{r['이름']}** : {m_date}")
            except: pass

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 입력 및 자동 보장 연동")
    with st.form("sales_f"):
        c1, c2, c3, c4, c5 = st.columns(5)
        in_date, in_name, in_birth = c1.date_input("계약일"), c2.text_input("고객명"), c3.text_input("생일(6자리)")
        in_prod, in_price = c4.text_input("상품명"), c5.text_input("보험료")
        if st.form_submit_button("🚀 저장"):
            p_p = re.sub(r'[^0-9]', '', in_price)
            sheet_sales.append_row([str(in_date), in_name, in_birth, in_prod, p_p])
            st.success("실적 저장 완료"); st.rerun()

elif menu == "🔍 고객조회/수정":
    s_name = st.text_input("이름 검색")
    if s_name and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                st.write(f"**🆔 주민번호:** {row['주민번호']} / **🛠️ 직업:** {row['직업']}")
                if row.get('차량번호'): st.info(f"🚘 **자동차:** {row['차량번호']} / {row.get('보험사','')} ({row.get('자동차만기일','')})")
                
                # 시트의 보험사, 상품명, 가입날짜, 금액 셀 데이터를 합쳐서 리스트 출력
                st.markdown("### 📋 보유 계약 리스트")
                comp_l, prod_l = str(row.get('보험사', '')).split('\n'), str(row.get('상품명', '')).split('\n')
                date_l, price_l = str(row.get('가입날짜', '')).split('\n'), str(row.get('금액', '')).split('\n')
                max_l = max(len(comp_l), len(prod_l), len(date_l), len(price_l))
                t_rows = []
                for i in range(max_l):
                    if comp_l[i].strip() or prod_l[i].strip():
                        t_rows.append({"보험사": comp_l[i] if i<len(comp_l) else "", "상품명": prod_l[i] if i<len(prod_l) else "", 
                                       "가입날짜": date_l[i] if i<len(date_l) else "", "금액": price_l[i] if i<len(price_l) else ""})
                if t_rows: st.table(pd.DataFrame(t_rows))
                
                with st.form(f"e_{idx}"):
                    u_jumin, u_phone = st.text_input("주민번호", value=row['주민번호']), st.text_input("연락처", value=row['연락처'])
                    u_addr, u_memo = st.text_input("주소", value=row['주소']), st.text_area("메모", value=row['병력(특이사항)'])
                    if st.form_submit_button("✅ 수정 저장"):
                        rn = idx + 2
                        sheet_cust.update_cell(rn, col_map["주민번호"], u_jumin)
                        sheet_cust.update_cell(rn, col_map["연락처"], u_phone)
                        sheet_cust.update_cell(rn, col_map["주소"], u_addr)
                        sheet_cust.update_cell(rn, col_map["병력(특이사항)"], u_memo)
                        st.success("수정 완료"); st.rerun()

elif menu == "✍️ 고객정보 신규등록":
    with st.form("n_c"):
        n_n, n_j, n_p = st.text_input("이름"), st.text_input("주민번호"), st.text_input("연락처")
        n_a, n_j_b = st.text_input("주소"), st.text_input("직업")
        if st.form_submit_button("👤 등록"):
            sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), n_n, n_j, n_p, n_a, n_j_b, "", n_n])
            st.success("등록 완료"); st.rerun()

elif menu == "📑 고객리스트":
    p_s = 30
    t_p = (len(db_cust)//p_s) + (1 if len(db_cust)%p_s > 0 else 0)
    cp = st.selectbox("페이지", range(1, t_p+1))
    st.table(db_cust[['이름', '주민번호', '연락처', '직업', '자동차만기일']].iloc[(cp-1)*p_s : cp*p_s])

elif menu == "🚘 자동차증권 업데이트":
    with st.form("car"):
        tn, cn, ci, cd = st.text_input("고객명"), st.text_input("차량번호"), st.text_input("보험사"), st.date_input("만기일")
        if st.form_submit_button("🚗 반영"):
            m = db_cust[db_cust['이름'] == tn]
            if not m.empty:
                rn = m.index[-1]+2
                sheet_cust.update_cell(rn, col_map["차량번호"], cn)
                sheet_cust.update_cell(rn, col_map["보험사"], ci)
                sheet_cust.update_cell(rn, col_map["자동차만기일"], str(cd))
                st.success("반영 완료"); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    upf = st.file_uploader("PDF", type="pdf")
    if upf and target != "선택" and st.button("🚀 분석 실행"):
        p_items = parse_pdf_to_details(upf)
        if p_items:
            rn = db_cust[db_cust['이름'] == target].index[-1]+2
            # 줄바꿈으로 각 셀 데이터 생성
            c_s, p_s, d_s, pr_s = "\n".join([i['회사'] for i in p_items]), "\n".join([i['상품'] for i in p_items]), "\n".join([i['날짜'] for i in p_items]), "\n".join([i['금액'] for i in p_items])
            sheet_cust.update_cell(rn, col_map["보험사"], c_s)
            sheet_cust.update_cell(rn, col_map["상품명"], p_s)
            sheet_cust.update_cell(rn, col_map["가입날짜"], d_s)
            sheet_cust.update_cell(rn, col_map["금액"], pr_s)
            st.success("분석 데이터가 각 셀에 줄바꿈으로 입력되었습니다."); st.rerun()

elif menu == "🏥 보험청구 가이드":
    st.subheader("🏥 전 보험사 청구 링크")
    st.markdown("[삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html) | [현대해상](https://www.hi.co.kr/service/claim/guide/form.do) | [DB손보](https://www.idbins.com/FWCRRE1001.do) | [라이나](https://www.lina.co.kr/customer/claim/reward/reward_01.html) | [메리츠](https://www.meritzfire.com/compensation/guide/claim-guide.do)")
