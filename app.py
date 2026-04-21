import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import pdfplumber

# --- [1. 구글 시트 및 보안 설정] ---
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

# --- [데이터 정제 및 PDF 분석 함수] ---
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
                date_m = re.search(r'\d{4}[.\-]\d{2}[.\-]\d{2}', line)
                price_m = re.search(r'\d{1,3}(,\d{3})*원?', line)
                if date_m and price_m:
                    parts = line.split()
                    comp = parts[0]
                    dt, pr = date_m.group(), price_m.group()
                    prod = line.replace(comp, "").replace(dt, "").replace(pr, "").strip()
                    results.append({"회사": comp, "상품": prod, "날짜": dt, "금액": pr})
    return results

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")
sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_data = sheet_cust.get_all_values() if sheet_cust else []
db_cust = pd.DataFrame(cust_data[1:], columns=cust_data[0]) if len(cust_data) > 1 else pd.DataFrame()
col_map = {col: i+1 for i, col in enumerate(db_cust.columns)}

sales_data = sheet_sales.get_all_values() if sheet_sales else []
db_sales = pd.DataFrame(sales_data[1:], columns=sales_data[0]) if len(sales_data) > 1 else pd.DataFrame()

# --- [3. 사이드바 메뉴 (전체 복구)] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석 PDF 업로드", "🏥 보험청구 가이드"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v21.0")

# --- [4. 메뉴별 구현] ---

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

elif menu == "🔍 고객조회/수정":
    s_name = st.text_input("고객명 검색")
    if s_name and not db_cust.empty:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for idx, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({format_phone(row['연락처'])})", expanded=True):
                # [중요] 시트의 각 셀 데이터를 가져와서 리스트업 (줄바꿈 기준 분리)
                st.markdown("### 📋 보유 계약 리스트")
                c_list = str(row.get('보험사', '')).split('\n')
                p_list = str(row.get('상품명', '')).split('\n')
                d_list = str(row.get('가입날짜', '')).split('\n')
                m_list = str(row.get('금액', '')).split('\n')
                
                max_len = max(len(c_list), len(p_list), len(d_list), len(m_list))
                t_data = []
                for i in range(max_len):
                    if i < len(c_list) and c_list[i].strip():
                        t_data.append({
                            "보험사": c_list[i] if i < len(c_list) else "",
                            "상품명": p_list[i] if i < len(p_list) else "",
                            "가입날짜": d_list[i] if i < len(d_list) else "",
                            "금액": m_list[i] if i < len(m_list) else ""
                        })
                if t_data: st.table(pd.DataFrame(t_data))
                else: st.info("등록된 계약 정보가 없습니다.")
                
                with st.form(f"edit_{idx}"):
                    u_jumin = st.text_input("주민번호", value=row['주민번호'])
                    u_phone = st.text_input("연락처", value=row['연락처'])
                    u_memo = st.text_area("메모", value=row['병력(특이사항)'])
                    if st.form_submit_button("✅ 수정 저장"):
                        rn = idx + 2
                        sheet_cust.update_cell(rn, col_map["주민번호"], u_jumin)
                        sheet_cust.update_cell(rn, col_map["연락처"], u_phone)
                        sheet_cust.update_cell(rn, col_map["병력(특이사항)"], u_memo)
                        st.success("수정 완료"); st.rerun()

elif menu == "📊 실적 관리":
    with st.form("sales_f"):
        c1, c2, c3, c4, c5 = st.columns(5)
        in_date, in_name, in_birth = c1.date_input("계약일"), c2.text_input("고객명"), c3.text_input("생일")
        in_prod, in_price = c4.text_input("상품명"), c5.text_input("보험료")
        if st.form_submit_button("🚀 저장"):
            p_p = re.sub(r'[^0-9]', '', in_price)
            sheet_sales.append_row([str(in_date), in_name, in_birth, in_prod, p_p])
            st.success("저장 완료"); st.rerun()

elif menu == "📄 보장분석 PDF 업로드":
    target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    upf = st.file_uploader("PDF", type="pdf")
    if upf and target != "선택" and st.button("🚀 분석 및 셀별 저장"):
        p_items = parse_pdf_to_details(upf)
        if p_items:
            rn = db_cust[db_cust['이름'] == target].index[-1] + 2
            # 줄바꿈으로 각 셀 데이터 생성하여 개별 업데이트
            sheet_cust.update_cell(rn, col_map["보험사"], "\n".join([i['회사'] for i in p_items]))
            sheet_cust.update_cell(rn, col_map["상품명"], "\n".join([i['상품'] for i in p_items]))
            sheet_cust.update_cell(rn, col_map["가입날짜"], "\n".join([i['날짜'] for i in p_items]))
            sheet_cust.update_cell(rn, col_map["금액"], "\n".join([i['금액'] for i in p_items]))
            st.success("보장 내역이 각 셀에 줄바꿈으로 저장되었습니다."); st.rerun()

elif menu == "📑 고객리스트":
    st.table(db_cust[['이름', '주민번호', '연락처', '직업', '자동차만기일']])

elif menu == "✍️ 고객정보 신규등록":
    with st.form("new"):
        n1, n2, n3 = st.columns(3)
        n_n, n_j, n_p = n1.text_input("이름"), n2.text_input("주민번호"), n3.text_input("연락처")
        if st.form_submit_button("👤 등록"):
            sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), n_n, n_j, n_p, "", "", "", n_n])
            st.success("등록 완료"); st.rerun()

elif menu == "🚘 자동차증권 업데이트":
    with st.form("car"):
        t_n, c_n, c_i, c_d = st.text_input("고객명"), st.text_input("차량번호"), st.text_input("보험사"), st.date_input("만기일")
        if st.form_submit_button("🚗 업데이트"):
            m = db_cust[db_cust['이름'] == t_n]
            if not m.empty:
                rn = m.index[-1] + 2
                sheet_cust.update_cell(rn, col_map["차량번호"], c_n)
                sheet_cust.update_cell(rn, col_map["보험사"], c_i)
                sheet_cust.update_cell(rn, col_map["자동차만기일"], str(c_d))
                st.success("완료"); st.rerun()

elif menu == "🏥 보험청구 가이드":
    st.info("고객용 안내문구 복사 및 보험사 링크")
    st.code("[보험금 청구 안내]\n1. 영수증\n2. 세부내역서\n3. 진단서(입원 시)", language=None)
