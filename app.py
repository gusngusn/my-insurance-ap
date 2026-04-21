import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [0. 디자인 설정 (한글 최적화 및 레이아웃)] ---
def apply_custom_design():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        html, body, [data-testid="stapp"] {
            font-family: 'Noto Sans KR', sans-serif;
            background-color: #F4F7F9;
        }
        .main-title {
            color: #1A374D;
            font-weight: 700;
            font-size: 2rem;
            margin-bottom: 1.5rem;
            border-left: 6px solid #AD8B73;
            padding-left: 15px;
        }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #DDE6ED;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        }
        .stButton>button {
            border-radius: 8px;
            background-color: #1A374D;
            color: white;
            width: 100%;
        }
        [data-testid="stSidebar"] {
            background-color: #1A374D;
        }
        [data-testid="stSidebar"] * {
            color: #FFFFFF !important;
        }
        </style>
    """, unsafe_allow_html=True)

# --- [1. 보안 로그인] ---
def check_password():
    def password_entered():
        if st.session_state["username"] == "gusngusn" and st.session_state["password"] == "akqthtk1**":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center; color: #1A374D;'>🛡️ 배현우 FC 관리시스템 로그인</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1.5,1])
        with col2:
            st.text_input("아이디", key="username")
            st.text_input("비밀번호", type="password", key="password", on_change=password_entered)
            if st.button("로그인"):
                password_entered()
                st.rerun()
        return False
    elif not st.session_state["password_correct"]:
        st.error("정보가 일치하지 않습니다.")
        return False
    return True

if not check_password():
    st.stop()

# --- [2. 데이터 연결] ---
apply_custom_design()
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheets():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)
        ws = spreadsheet.worksheets()
        while len(ws) < 3:
            spreadsheet.add_worksheet(title=f"시트{len(ws)+1}", rows="100", cols="20")
            ws = spreadsheet.worksheets()
        return ws[0], ws[1], ws[2]
    except: return None, None, None

@st.cache_data(ttl=3600)
def get_insurance_news():
    url = "https://news.google.com/rss/search?q=%EB%B3%B4%ED%97%98&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        return [{"제목": item.find('title').text, "링크": item.find('link').text} for item in root.findall('.//item')[:5]]
    except: return []

sheet1, sheet2, sheet3 = get_gsheets()
h1 = ["등록일자", "이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
h2 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]
h3 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]

if sheet1 and sheet2 and sheet3:
    d1 = sheet1.get_all_values(); db_cust = pd.DataFrame(d1[1:], columns=h1[:len(d1[0])]) if len(d1) > 1 else pd.DataFrame(columns=h1)
    d2 = sheet2.get_all_values(); db_contract = pd.DataFrame(d2[1:], columns=h2[:len(d2[0])]) if len(d2) > 1 else pd.DataFrame(columns=h2)
    d3 = sheet3.get_all_values(); db_perf = pd.DataFrame(d3[1:], columns=h3[:len(d3[0])]) if len(d3) > 1 else pd.DataFrame(columns=h3)
    if not db_perf.empty:
        db_perf['금액_숫자'] = db_perf['금액'].replace('[^0-9]', '', regex=True).apply(lambda x: int(x) if x else 0)
        db_perf['가입날짜_dt'] = pd.to_datetime(db_perf['가입날짜'].str.replace('.', '-'), errors='coerce')
else: st.stop()

# --- [3. 메뉴 구성] ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #AD8B73;'>🛡️ 배현우 FC</h2>", unsafe_allow_html=True)
    st.markdown("---")
    menu_options = ["📊 실적 대시보드", "🔍 고객 통합 조회", "➕ 신규 고객 등록", "📄 보유계약 입력", "💰 실적 입력/분석", "📂 CSV 일괄 업로드", "📩 단체 문자 발송"]
    choice = st.radio("메뉴 선택", menu_options)
    st.markdown("---")
    if st.button("🔓 로그아웃"):
        del st.session_state["password_correct"]; st.rerun()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [4. 메뉴별 기능 구현] ---

# (1) 실적 대시보드
if choice == "📊 실적 대시보드":
    st.markdown("<h1 class='main-title'>실적 현황 및 알림</h1>", unsafe_allow_html=True)
    m_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month] if not db_perf.empty else pd.DataFrame()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 계약", f"{len(m_df)}건")
    c2.metric("이번 달 실적", f"{m_df['금액_숫자'].sum() if not m_df.empty else 0:,}원")
    c3.metric("관리 고객수", f"{len(db_cust)}명")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🎂 이번 달 생일 고객")
        bdays = []
        for _, r in db_cust.iterrows():
            jumin = str(r.get('주민번호',''))
            if len(jumin)>=6 and jumin[2:4] == str(today.month).zfill(2):
                bdays.append({"고객명": r['이름'], "생일": f"{jumin[2:4]}월 {jumin[4:6]}일"})
        st.dataframe(pd.DataFrame(bdays), use_container_width=True, hide_index=True) if bdays else st.info("생일자 없음")

    with col_r:
        st.subheader("🚗 자동차보험 만기 도래 (D-45)")
        autos = []
        for _, r in db_cust.iterrows():
            d_str = str(r.get('가입일자','')).replace('.','-')
            comp = str(r.get('자동차보험회사',''))
            if len(d_str) > 8 and comp != '-':
                try:
                    exp = datetime.strptime(d_str, "%Y-%m-%d") + timedelta(days=365)
                    d_day = (exp - today).days
                    if 0 <= d_day <= 45:
                        autos.append({"고객명": r['이름'], "만기일": exp.strftime("%Y-%m-%d"), "보험사": comp, "남은일수": f"D-{d_day}"})
                except: pass
        st.dataframe(pd.DataFrame(autos), use_container_width=True, hide_index=True) if autos else st.info("만기 예정 없음")

    st.subheader("📰 최신 보험 뉴스")
    for n in get_insurance_news(): st.markdown(f"• [{n['제목']}]({n['링크']})")

# (2) 고객 통합 조회
elif choice == "🔍 고객 통합 조회":
    st.markdown("<h1 class='main-title'>고객 정보 및 보장분석</h1>", unsafe_allow_html=True)
    name = st.text_input("고객 성함을 입력하세요")
    if name:
        res = db_cust[db_cust['이름'] == name]
        if not res.empty:
            c = res.iloc[0]
            st.markdown(f"### 👤 {name} 고객님 상세정보")
            col1, col2 = st.columns(2)
            col1.write(f"**주민번호:** {c['주민번호']} | **연락처:** {c['연락처']}")
            col1.write(f"**주소:** {c['주소']} | **직업:** {c['직업']}")
            col2.write(f"**차량번호:** {c.get('차량번호','-')}")
            col2.write(f"**자동차보험사:** {c.get('자동차보험회사','-')} | **가입일:** {c.get('가입일자','-')}")
            
            st.markdown("---")
            st.subheader("📋 보유 계약 리스트")
            matched = db_contract[db_contract['계약자'] == name]
            st.table(matched[["가입날짜", "보험회사", "상품명", "금액"]]) if not matched.empty else st.info("내역 없음")
        else: st.error("검색 결과가 없습니다.")

# (3) 신규 고객 등록
elif choice == "➕ 신규 고객 등록":
    st.markdown("<h1 class='main-title'>신규 고객 정보 등록</h1>", unsafe_allow_html=True)
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        r_name = c1.text_input("고객명"); r_jumin = c1.text_input("주민번호"); r_phone = c1.text_input("연락처")
        r_addr = c2.text_input("주소"); r_job = c2.text_input("직업"); r_car = c2.text_input("차량번호")
        r_comp = c1.text_input("자동차보험사"); r_date = c2.date_input("자동차보험 가입일")
        if st.form_submit_button("✅ 시스템 등록"):
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, "", r_car, r_comp, r_date.strftime("%Y-%m-%d")])
            st.success("등록 완료!"); st.rerun()

# (4) 보유계약 입력
elif choice == "📄 보유계약 입력":
    st.markdown("<h1 class='main-title'>보유계약 수동 입력</h1>", unsafe_allow_html=True)
    sel = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].tolist())
    if sel != "선택":
        with st.form("con_form"):
            d = st.text_input("가입일 (2026.01.01)"); c = st.text_input("보험사"); p = st.text_input("상품명"); m = st.text_input("보험료")
            if st.form_submit_button("🚀 보장분석 전송"):
                sheet2.append_row([sel, d, c, p, m, datetime.now().strftime("%Y-%m-%d")])
                st.success("반영 완료!"); st.rerun()

# (5) 실적 입력/분석
elif choice == "💰 실적 입력/분석":
    st.markdown("<h1 class='main-title'>성과 관리 및 분석</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["✍️ 실적 입력", "📈 통계 분석"])
    with t1:
        with st.form("p_form"):
            p_n = st.selectbox("계약자", db_cust['이름'].tolist())
            p_d = st.date_input("체결일"); p_c = st.text_input("보험회사"); p_p = st.text_input("상품명"); p_m = st.text_input("금액")
            if st.form_submit_button("🚀 실적 등록"):
                now = datetime.now().strftime("%Y-%m-%d")
                sheet3.append_row([p_n, p_d.strftime("%Y.%m.%d"), p_c, p_p, p_m, now])
                # 보장분석 자동 연동 로직
                is_dup = not db_contract[(db_contract['계약자']==p_n)&(db_contract['상품명']==p_p)].empty
                if not is_dup: sheet2.append_row([p_n, p_d.strftime("%Y.%m.%d"), p_c, p_p, p_m, now])
                st.success("실적 및 보장분석 반영 완료!"); st.rerun()
    with t2:
        period = st.radio("분석 기준", ["주간", "월간", "연간"], horizontal=True)
        if not db_perf.empty:
            if period=="주간": f = db_perf[db_perf['가입날짜_dt'] >= (today - timedelta(days=today.weekday()))]
            elif period=="월간": f = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
            else: f = db_perf[db_perf['가입날짜_dt'].dt.year == today.year]
            st.metric(f"{period} 누적 실적", f"{f['금액_숫자'].sum():,}원")
            st.dataframe(f[["계약자","가입날짜","보험회사","상품명","금액"]], use_container_width=True)

# (6) CSV 일괄 업로드
elif choice == "📂 CSV 일괄 업로드":
    st.markdown("<h1 class='main-title'>DB 대량 병합</h1>", unsafe_allow_html=True)
    file = st.file_uploader("CSV 파일 선택", type=['csv'])
    if file:
        df = pd.read_csv(file).fillna(""); st.dataframe(df.head())
        mapping = {}
        target = ["이름", "주민번호", "연락처", "주소", "직업", "차량번호", "자동차보험회사", "가입일자"]
        cols = st.columns(3)
        for i, h in enumerate(target):
            with cols[i%3]: mapping[h] = st.selectbox(f"➡️ {h}", ["선택 안 함"] + list(df.columns), index=0)
        if st.button("🚀 데이터 병합 시작"):
            for _, row in df.iterrows():
                n_val = str(row[mapping["이름"]]).strip()
                if not n_val: continue
                exist = db_cust[db_cust['이름'] == n_val]
                if exist.empty:
                    row_data = [datetime.now().strftime("%Y-%m-%d"), n_val] + [str(row[mapping[k]]) if mapping[k] != "선택 안 함" else "" for k in target[1:]]
                    sheet1.append_row(row_data)
            st.success("병합 완료!"); st.rerun()

# (7) 단체 문자 발송
elif choice == "📩 단체 문자 발송":
    st.markdown("<h1 class='main-title'>고객 안부 및 만기 문자</h1>", unsafe_allow_html=True)
    target = st.multiselect("수신인 선택", db_cust['이름'].tolist())
    msg = st.text_area("문자 내용", height=200)
    if st.button("🚀 발송 (시뮬레이션)"):
        st.success(f"{len(target)}명에게 발송 완료되었습니다!")
