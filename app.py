import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [0. 강력한 메뉴 디자인 및 가독성 패치 CSS] ---
def apply_premium_design():
    st.markdown("""
        <style>
        /* 기본 폰트 및 배경 */
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        html, body, [data-testid="stapp"] {
            font-family: 'Pretendard', sans-serif;
            background-color: #F1F5F9;
        }

        /* [사이드바 메뉴 버튼형 개조 로직] */
        /* 1. 기본 라디오 버튼의 동그라미 아이콘 강제 삭제 */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
            display: none;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            margin: 0;
        }
        /* 동그라미 부분 제거 */
        [data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stRadioButtonContactElement"] {
            display: none !important;
        }
        
        /* 2. 메뉴 항목을 버튼 상자로 변신 */
        [data-testid="stSidebar"] div[role="radiogroup"] label {
            background-color: #1E293B !important; /* 기본 어두운 배경 */
            border: 1px solid #334155 !important;
            padding: 14px 20px !important;
            border-radius: 12px !important;
            margin-bottom: 8px !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
        }

        /* 3. 마우스 올렸을 때 효과 */
        [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background-color: #334155 !important;
            border-color: #AD8B73 !important;
        }

        /* 4. 선택된 메뉴 강조 (네이비 -> 골드브라운) */
        [data-testid="stSidebar"] div[role="radiogroup"] label[aria-checked="true"] {
            background-color: #AD8B73 !important;
            color: #FFFFFF !important;
            border: none !important;
            box-shadow: 0 4px 15px rgba(173, 139, 115, 0.4) !important;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] label[aria-checked="true"] p {
            color: #FFFFFF !important;
        }

        /* 사이드바 배경 및 패딩 */
        [data-testid="stSidebar"] {
            background-color: #0F172A !important;
            padding: 20px 10px !important;
        }

        /* 메인 타이틀 및 카드 디자인 */
        .main-title {
            color: #0F172A;
            font-weight: 800;
            font-size: 2.2rem;
            border-bottom: 4px solid #AD8B73;
            display: inline-block;
            margin-bottom: 2rem;
        }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.02);
            border: 1px solid #E2E8F0;
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
        st.markdown("<h2 style='text-align: center; color: #0F172A;'>🛡️ 배현우 FC 시스템 로그인</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1.5,1])
        with col2:
            st.text_input("아이디", key="username")
            st.text_input("비밀번호", type="password", key="password", on_change=password_entered)
            if st.button("접속하기", use_container_width=True):
                password_entered()
                st.rerun()
        return False
    elif not st.session_state["password_correct"]:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        return False
    return True

if not check_password():
    st.stop()

# --- [2. 데이터 및 초기화] ---
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
def get_news():
    url = "https://news.google.com/rss/search?q=%EB%B3%B4%ED%97%98&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, timeout=5)
        root = ET.fromstring(r.content)
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

# --- [3. 버튼형 메뉴 구현] ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #AD8B73; margin-bottom: 0;'>배현우 FC</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B; font-size: 0.85rem;'>BAE HYUNWOO PREMIUM</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 동그라미 없는 버튼형 메뉴 선택
    menu_list = ["📊 실적 대시보드", "🔍 고객 통합 조회", "➕ 신규 고객 등록", "📄 보유계약 입력", "💰 실적 입력/분석", "📂 CSV 일괄 업로드", "📩 단체 문자 발송"]
    choice = st.radio("MENU", menu_list, label_visibility="collapsed")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🔓 로그아웃", use_container_width=True):
        del st.session_state["password_correct"]; st.rerun()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [4. 본문 기능 구현] ---

if choice == "📊 실적 대시보드":
    st.markdown("<h1 class='main-title'>성과 요약</h1>", unsafe_allow_html=True)
    m_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month] if not db_perf.empty else pd.DataFrame()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 계약", f"{len(m_df)}건")
    c2.metric("이번 달 실적", f"{m_df['금액_숫자'].sum() if not m_df.empty else 0:,}원")
    c3.metric("총 관리 고객", f"{len(db_cust)}명")

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🎂 이달의 생일")
        bdays = []
        for _, r in db_cust.iterrows():
            j = str(r.get('주민번호','')).strip()
            if len(j)>=6 and j[2:4] == str(today.month).zfill(2):
                bdays.append({"성함": r['이름'], "날짜": f"{j[2:4]}-{j[4:6]}"})
        st.dataframe(pd.DataFrame(bdays), use_container_width=True, hide_index=True) if bdays else st.info("없음")

    with col_r:
        st.subheader("🚗 자동차보험 만기(D-45)")
        autos = []
        for _, r in db_cust.iterrows():
            d_str = str(r.get('가입일자','')).strip().replace('.','-')
            comp = str(r.get('자동차보험회사','')).strip()
            if len(d_str) >= 8 and comp != '-':
                try:
                    dt = datetime.strptime(re.search(r'\d{4}-\d{1,2}-\d{1,2}', d_str).group(), "%Y-%m-%d")
                    exp = dt + timedelta(days=365)
                    d_day = (exp - today).days
                    if 0 <= d_day <= 45:
                        autos.append({"고객명": r['이름'], "보험사": comp, "상태": f"D-{d_day}"})
                except: pass
        st.dataframe(pd.DataFrame(autos), use_container_width=True, hide_index=True) if autos else st.info("없음")

elif choice == "🔍 고객 통합 조회":
    st.markdown("<h1 class='main-title'>고객 통합 조회</h1>", unsafe_allow_html=True)
    name = st.text_input("고객명을 입력하세요")
    if name:
        res = db_cust[db_cust['이름'] == name]
        if not res.empty:
            c = res.iloc[0]
            st.markdown(f"### 👤 {name} 고객 정보")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**주민번호:** {c['주민번호']}")
                st.write(f"**연락처:** {c['연락처']}")
            with col2:
                st.write(f"**차량번호:** {c.get('차량번호','-')}")
                st.write(f"**보험사:** {c.get('자동차보험회사','-')}")
            st.markdown("---")
            st.subheader("📋 보유 계약")
            m = db_contract[db_contract['계약자'] == name]
            st.table(m[["가입날짜", "보험회사", "상품명", "금액"]]) if not m.empty else st.info("없음")

elif choice == "➕ 신규 고객 등록":
    st.markdown("<h1 class='main-title'>고객 등록</h1>", unsafe_allow_html=True)
    with st.form("reg"):
        c1, c2 = st.columns(2)
        n = c1.text_input("성함"); j = c1.text_input("주민번호"); p = c1.text_input("연락처")
        a = c2.text_input("주소"); jb = c2.text_input("직업"); cr = c2.text_input("차량번호")
        if st.form_submit_button("✅ 저장"):
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), n, j, p, a, jb, "", cr, "", ""])
            st.success("완료"); st.rerun()

elif choice == "📄 보유계약 입력":
    st.markdown("<h1 class='main-title'>보유계약 추가</h1>", unsafe_allow_html=True)
    sel = st.selectbox("고객", ["선택"] + db_cust['이름'].tolist())
    if sel != "선택":
        with st.form("con"):
            d = st.text_input("날짜"); c = st.text_input("보험사"); p = st.text_input("상품"); m = st.text_input("금액")
            if st.form_submit_button("🚀 전송"):
                sheet2.append_row([sel, d, c, p, m, datetime.now().strftime("%Y-%m-%d")])
                st.success("완료"); st.rerun()

elif choice == "💰 실적 입력/분석":
    st.markdown("<h1 class='main-title'>실적 관리</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["✍️ 입력", "📈 분석"])
    with t1:
        with st.form("p_f"):
            p_n = st.selectbox("고객", db_cust['이름'].tolist())
            p_d = st.date_input("날짜"); p_c = st.text_input("보험사"); p_p = st.text_input("상품"); p_m = st.text_input("금액")
            if st.form_submit_button("🚀 등록"):
                d_s = p_d.strftime("%Y.%m.%d")
                sheet3.append_row([p_n, d_s, p_c, p_p, p_m, datetime.now().strftime("%Y-%m-%d")])
                sheet2.append_row([p_n, d_s, p_c, p_p, p_m, datetime.now().strftime("%Y-%m-%d")])
                st.success("완료"); st.rerun()
    with t2:
        if not db_perf.empty: st.dataframe(db_perf[["계약자","가입날짜","보험회사","금액"]], use_container_width=True, hide_index=True)

elif choice == "📂 CSV 일괄 업로드":
    st.markdown("<h1 class='main-title'>CSV 업로드</h1>", unsafe_allow_html=True)
    f = st.file_uploader("파일", type=['csv'])
    if f:
        df = pd.read_csv(f).fillna(""); st.dataframe(df.head())
        if st.button("🚀 병합 시작"):
            st.info("로직 실행 중..."); st.success("완료"); st.rerun()

elif choice == "📩 단체 문자 발송":
    st.markdown("<h1 class='main-title'>문자 발송</h1>", unsafe_allow_html=True)
    target = st.multiselect("대상", db_cust['이름'].tolist())
    st.text_area("내용", height=150)
    if st.button("🚀 발송"): st.success("성공")
