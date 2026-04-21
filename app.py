import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [0. 프리미엄 디자인 및 버튼형 메뉴 CSS] ---
def apply_premium_design():
    st.markdown("""
        <style>
        /* 기본 폰트 및 배경 */
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
        html, body, [data-testid="stapp"] {
            font-family: 'Pretendard', sans-serif;
            background-color: #F8FAFC;
        }

        /* 메인 타이틀 */
        .main-title {
            color: #0F172A;
            font-weight: 800;
            font-size: 2.2rem;
            margin-bottom: 2rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #AD8B73;
        }

        /* 좌측 사이드바 라디오 버튼 -> 버튼형으로 개조 */
        div[data-testid="stSidebarNav"] {display: none;}
        
        /* 라디오 버튼의 동그라미 제거 및 버튼 스타일링 */
        div[data-testid="stSidebar"] div[role="radiogroup"] {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label {
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 0px;
            color: #CBD5E1 !important;
        }
        /* 라디오 버튼 원형 표시 숨기기 */
        div[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            font-size: 1rem;
            font-weight: 500;
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label div[data-checked="true"] {
            display: none !important; /* 선택 원 숨김 */
        }
        div[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {
            display: none !important; /* 선택 원 영역 숨김 */
        }
        
        /* 선택된 메뉴 강조 */
        div[data-testid="stSidebar"] div[role="radiogroup"] label[aria-checked="true"] {
            background-color: #AD8B73 !important;
            color: #FFFFFF !important;
            border: none;
            box-shadow: 0 4px 12px rgba(173, 139, 115, 0.3);
            transform: scale(1.02);
        }

        /* 사이드바 배경 */
        [data-testid="stSidebar"] {
            background-color: #0F172A;
            padding-top: 2rem;
        }

        /* 대시보드 지표 카드 */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
            border: 1px solid #F1F5F9;
        }
        
        /* 일반 버튼 스타일 */
        .stButton>button {
            border-radius: 10px;
            background-color: #0F172A;
            color: white;
            font-weight: 600;
            padding: 0.6rem 1rem;
            border: none;
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
        st.markdown("<h2 style='text-align: center; color: #0F172A; font-weight: 800;'>🛡️ BAE HYUNWOO FC<br>PREMIUM ACCESS</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1.5,1])
        with col2:
            st.text_input("ID", key="username")
            st.text_input("PASSWORD", type="password", key="password", on_change=password_entered)
            if st.button("로그인", use_container_width=True):
                password_entered()
                st.rerun()
        return False
    elif not st.session_state["password_correct"]:
        st.error("인증 정보가 올바르지 않습니다.")
        return False
    return True

if not check_password():
    st.stop()

# --- [2. 데이터 연결] ---
apply_premium_design()
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
    st.markdown("<h2 style='text-align: center; color: #AD8B73; font-weight: 800;'>배현우 FC</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.8rem;'>종합자산관리 시스템</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    menu_options = ["📊 실적 대시보드", "🔍 고객 통합 조회", "➕ 신규 고객 등록", "📄 보유계약 입력", "💰 실적 입력/분석", "📂 CSV 일괄 업로드", "📩 단체 문자 발송"]
    choice = st.radio("메뉴", menu_options, label_visibility="collapsed")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🔓 시스템 로그아웃", use_container_width=True):
        del st.session_state["password_correct"]; st.rerun()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [4. 기능 구현] ---

if choice == "📊 실적 대시보드":
    st.markdown("<h1 class='main-title'>성과 요약 및 알림</h1>", unsafe_allow_html=True)
    m_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month] if not db_perf.empty else pd.DataFrame()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 체결", f"{len(m_df)}건")
    c2.metric("이번 달 보험료", f"{m_df['금액_숫자'].sum() if not m_df.empty else 0:,}원")
    c3.metric("관리 고객 명단", f"{len(db_cust)}명")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🎂 이달의 생일 고객")
        bdays = []
        for _, r in db_cust.iterrows():
            jumin = str(r.get('주민번호','')).strip()
            if len(jumin)>=6 and jumin[2:4] == str(today.month).zfill(2):
                bdays.append({"성함": r['이름'], "생일": f"{jumin[2:4]}월 {jumin[4:6]}일"})
        if bdays: st.dataframe(pd.DataFrame(bdays), use_container_width=True, hide_index=True)
        else: st.info("이번 달 생일자가 없습니다.")

    with col_r:
        st.subheader("🚗 자동차보험 만기 안내 (D-45)")
        autos = []
        for _, r in db_cust.iterrows():
            d_str = str(r.get('가입일자','')).strip().replace('.','-')
            comp = str(r.get('자동차보험회사','')).strip()
            if len(d_str) >= 8 and comp != '-':
                try:
                    clean_date = re.search(r'\d{4}-\d{1,2}-\d{1,2}', d_str).group()
                    exp = datetime.strptime(clean_date, "%Y-%m-%d") + timedelta(days=365)
                    d_day = (exp - today).days
                    if 0 <= d_day <= 45:
                        autos.append({"고객명": r['이름'], "만기예정": exp.strftime("%Y-%m-%d"), "보험사": comp, "상태": f"D-{d_day}"})
                except: pass
        if autos: st.dataframe(pd.DataFrame(autos), use_container_width=True, hide_index=True)
        else: st.info("45일 이내 만기 예정 건이 없습니다.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📰 금융/보험 시장 동향")
    for n in get_insurance_news(): st.markdown(f"• [{n['제목']}]({n['링크']})")

elif choice == "🔍 고객 통합 조회":
    st.markdown("<h1 class='main-title'>고객 상세 정보 조회</h1>", unsafe_allow_html=True)
    name = st.text_input("검색할 고객 성함을 입력하세요")
    if name:
        res = db_cust[db_cust['이름'] == name]
        if not res.empty:
            c = res.iloc[0]
            st.markdown(f"### 👤 {name} 고객님")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**주민번호:** {c['주민번호']}")
                st.write(f"**연락처:** {c['연락처']}")
                st.write(f"**주소:** {c['주소']}")
            with col2:
                st.write(f"**차량번호:** {c.get('차량번호','-')}")
                st.write(f"**자동차보험사:** {c.get('자동차보험회사','-')}")
                st.write(f"**직업:** {c['직업']}")
            
            st.markdown("---")
            st.subheader("📋 보유 계약 현황")
            matched = db_contract[db_contract['계약자'] == name]
            if not matched.empty: st.table(matched[["가입날짜", "보험회사", "상품명", "금액"]])
            else: st.info("등록된 보장 내역이 없습니다.")
        else: st.error("해당 성함으로 등록된 고객이 없습니다.")

elif choice == "➕ 신규 고객 등록":
    st.markdown("<h1 class='main-title'>신규 고객 데이터 등록</h1>", unsafe_allow_html=True)
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        r_name = c1.text_input("고객명")
        r_jumin = c1.text_input("주민번호")
        r_phone = c1.text_input("연락처")
        r_addr = c2.text_input("주소")
        r_job = c2.text_input("직업")
        r_car = c2.text_input("차량번호")
        r_comp = c1.text_input("자동차보험사")
        r_date = c2.date_input("자동차보험 가입일")
        if st.form_submit_button("✅ 고객 정보 저장"):
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, "", r_car, r_comp, r_date.strftime("%Y-%m-%d")])
            st.success("새로운 고객 정보가 안전하게 저장되었습니다."); st.rerun()

elif choice == "📄 보유계약 입력":
    st.markdown("<h1 class='main-title'>기보유 계약 수동 추가</h1>", unsafe_allow_html=True)
    sel = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].tolist())
    if sel != "선택":
        with st.form("con_form"):
            d = st.text_input("가입일자 (예: 2026.01.01)")
            c = st.text_input("보험사")
            p = st.text_input("상품명")
            m = st.text_input("월 보험료")
            if st.form_submit_button("🚀 보장분석 데이터 전송"):
                sheet2.append_row([sel, d, c, p, m, datetime.now().strftime("%Y-%m-%d")])
                st.success("보장분석 시트에 반영되었습니다."); st.rerun()

elif choice == "💰 실적 입력/분석":
    st.markdown("<h1 class='main-title'>성과 관리 통합 대시보드</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["✍️ 신규 계약 입력", "📈 기간별 성과 분석"])
    with t1:
        with st.form("p_form"):
            p_n = st.selectbox("계약자", db_cust['이름'].tolist())
            p_d = st.date_input("계약 체결일")
            p_c = st.text_input("보험회사")
            p_p = st.text_input("상품명")
            p_m = st.text_input("보험료/실적 금액")
            if st.form_submit_button("🚀 실적 확정 및 전송"):
                d_str = p_d.strftime("%Y.%m.%d")
                now = datetime.now().strftime("%Y-%m-%d")
                sheet3.append_row([p_n, d_str, p_c, p_p, p_m, now])
                is_dup = not db_contract[(db_contract['계약자']==p_n)&(db_contract['상품명']==p_p)].empty
                if not is_dup: sheet2.append_row([p_n, d_str, p_c, p_p, p_m, now])
                st.success("실적 등록 및 보장 분석 시트 연동 완료!"); st.rerun()
    with t2:
        period = st.radio("분석 기준", ["주간", "월간", "연간"], horizontal=True)
        if not db_perf.empty:
            if period=="주간": f = db_perf[db_perf['가입날짜_dt'] >= (today - timedelta(days=today.weekday()))]
            elif period=="월간": f = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
            else: f = db_perf[db_perf['가입날짜_dt'].dt.year == today.year]
            st.metric(f"{period} 누적 성과", f"{f['금액_숫자'].sum() if not f.empty else 0:,}원")
            st.dataframe(f[["계약자","가입날짜","보험회사","상품명","금액"]], use_container_width=True, hide_index=True)

elif choice == "📂 CSV 일괄 업로드":
    st.markdown("<h1 class='main-title'>대량 데이터 일괄 병합</h1>", unsafe_allow_html=True)
    file = st.file_uploader("DB CSV 파일 선택", type=['csv'])
    if file:
        df = pd.read_csv(file).fillna(""); st.dataframe(df.head())
        mapping = {}
        target = ["이름", "주민번호", "연락처", "주소", "직업", "차량번호", "자동차보험회사", "가입일자"]
        cols = st.columns(3)
        for i, h in enumerate(target):
            with cols[i%3]: mapping[h] = st.selectbox(f"➡️ {h}", ["선택 안 함"] + list(df.columns), index=0)
        if st.button("🚀 데이터 스마트 병합 시작"):
            for _, row in df.iterrows():
                n_val = str(row[mapping["이름"]]).strip()
                if not n_val: continue
                exist = db_cust[db_cust['이름'] == n_val]
                if exist.empty:
                    row_data = [datetime.now().strftime("%Y-%m-%d"), n_val] + [str(row[mapping[k]]) if mapping[k] != "선택 안 함" else "" for k in target[1:]]
                    sheet1.append_row(row_data)
            st.success("대량 데이터 병합 처리가 완료되었습니다!"); st.rerun()

elif choice == "📩 단체 문자 발송":
    st.markdown("<h1 class='main-title'>고객 관리 문자 전송</h1>", unsafe_allow_html=True)
    target = st.multiselect("발송 대상 선택", db_cust['이름'].tolist())
    msg = st.text_area("메시지 내용 작성", height=200)
    if st.button("🚀 SMS 발송 실행 (시뮬레이션)"):
        if target: st.success(f"선택하신 {len(target)}명의 고객님께 문자가 전송되었습니다.")
        else: st.warning("수신 고객을 선택해 주세요.")
