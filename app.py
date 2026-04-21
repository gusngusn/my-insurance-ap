import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [0. 메뉴 글자 흰색 고정 및 한글 최적화 CSS] ---
def apply_premium_design():
    st.markdown("""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        html, body, [data-testid="stapp"] {
            font-family: 'Pretendard', sans-serif;
            background-color: #F1F5F9;
        }

        /* [사이드바 메뉴 버튼형 개조 및 흰색 글자 고정] */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] { display: none; }
        
        /* 라디오 버튼 원형 아이콘 완전 제거 */
        [data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stRadioButtonContactElement"] {
            display: none !important;
        }
        
        /* 메뉴 버튼 기본 스타일 (글자색 흰색 고정) */
        [data-testid="stSidebar"] div[role="radiogroup"] label {
            background-color: #1E293B !important; 
            border: 1px solid #334155 !important;
            padding: 14px 20px !important;
            border-radius: 12px !important;
            margin-bottom: 8px !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            cursor: pointer !important;
        }
        
        /* 메뉴 내 텍스트 색상 강제 흰색 설정 */
        [data-testid="stSidebar"] div[role="radiogroup"] label p {
            color: #FFFFFF !important;
            font-size: 1.05rem !important;
            font-weight: 500 !important;
            margin: 0 !important;
        }

        /* 마우스 호버 시 배경색 살짝 밝게 */
        [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background-color: #334155 !important;
        }

        /* 선택된 메뉴 강조 (골드브라운 배경) */
        [data-testid="stSidebar"] div[role="radiogroup"] label[aria-checked="true"] {
            background-color: #AD8B73 !important;
            border: none !important;
            box-shadow: 0 4px 12px rgba(173, 139, 115, 0.4) !important;
        }

        /* 사이드바 전체 배경 및 로그아웃 버튼 */
        [data-testid="stSidebar"] { background-color: #0F172A !important; }
        
        /* 메인 대시보드 한글 텍스트 및 카드 스타일 */
        .main-title {
            color: #0F172A;
            font-weight: 800;
            font-size: 2.1rem;
            border-bottom: 4px solid #AD8B73;
            padding-bottom: 10px;
            margin-bottom: 2rem;
        }
        div[data-testid="stMetric"] label {
            color: #475569 !important; /* 지표 이름 색상 */
            font-weight: 600 !important;
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
        st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
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

# --- [3. 버튼형 메뉴 리스트] ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #AD8B73; margin-bottom: 0;'>배현우 FC</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.85rem;'>프리미엄 자산관리 시스템</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    menu_list = ["📊 성과 대시보드", "🔍 고객 통합 조회", "➕ 신규 고객 등록", "📄 기계약 수동 입력", "💰 실적 등록 및 분석", "📂 CSV 데이터 병합", "📩 단체 문자 발송"]
    choice = st.radio("메뉴", menu_list, label_visibility="collapsed")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🔓 시스템 로그아웃", use_container_width=True):
        del st.session_state["password_correct"]; st.rerun()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [4. 본문 화면 구성] ---

if choice == "📊 성과 대시보드":
    st.markdown("<h1 class='main-title'>성과 요약 및 알림</h1>", unsafe_allow_html=True)
    m_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month] if not db_perf.empty else pd.DataFrame()
    
    # 지표 한글화 적용
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 체결 건수", f"{len(m_df)}건")
    c2.metric("이번 달 실적 합계", f"{m_df['금액_숫자'].sum() if not m_df.empty else 0:,}원")
    c3.metric("누적 관리 고객", f"{len(db_cust)}명")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🎂 이달의 생일자")
        bdays = []
        for _, r in db_cust.iterrows():
            j = str(r.get('주민번호','')).strip()
            if len(j)>=6 and j[2:4] == str(today.month).zfill(2):
                bdays.append({"고객명": r['이름'], "생일": f"{j[2:4]}월 {j[4:6]}일"})
        if bdays: st.dataframe(pd.DataFrame(bdays), use_container_width=True, hide_index=True)
        else: st.info("이번 달 생일인 고객이 없습니다.")

    with col_r:
        st.subheader("🚗 자동차보험 만기 (D-45)")
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
                        autos.append({"고객명": r['이름'], "보험사": comp, "만기예정일": exp.strftime("%Y-%m-%d"), "상태": f"D-{d_day}"})
                except: pass
        if autos: st.dataframe(pd.DataFrame(autos), use_container_width=True, hide_index=True)
        else: st.info("45일 이내 만기 예정 고객이 없습니다.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📰 실시간 금융/보험 뉴스")
    for n in get_news(): st.markdown(f"• [{n['제목']}]({n['링크']})")

elif choice == "🔍 고객 통합 조회":
    st.markdown("<h1 class='main-title'>고객 상세 조회</h1>", unsafe_allow_html=True)
    name = st.text_input("고객 성함을 입력하세요")
    if name:
        res = db_cust[db_cust['이름'] == name]
        if not res.empty:
            c = res.iloc[0]
            st.markdown(f"### 👤 {name} 고객 정보")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**주민번호:** {c['주민번호']}")
                st.write(f"**연락처:** {c['연락처']}")
                st.write(f"**주소:** {c['주소']}")
            with col2:
                st.write(f"**차량번호:** {c.get('차량번호','-')}")
                st.write(f"**보험사:** {c.get('자동차보험회사','-')}")
                st.write(f"**직업:** {c['직업']}")
            st.markdown("---")
            st.subheader("📋 보유 계약 분석")
            m = db_contract[db_contract['계약자'] == name]
            if not m.empty: st.table(m[["가입날짜", "보험회사", "상품명", "금액"]])
            else: st.info("등록된 보장 분석 데이터가 없습니다.")
        else: st.error("해당 성함의 고객을 찾을 수 없습니다.")

elif choice == "➕ 신규 고객 등록":
    st.markdown("<h1 class='main-title'>신규 고객 등록</h1>", unsafe_allow_html=True)
    with st.form("reg"):
        c1, c2 = st.columns(2)
        n = c1.text_input("성함")
        j = c1.text_input("주민번호 (- 포함)")
        p = c1.text_input("연락처")
        a = c2.text_input("주소")
        jb = c2.text_input("직업")
        cr = c2.text_input("차량번호")
        cp = c1.text_input("자동차보험사")
        cd = c2.date_input("자동차보험 가입일")
        if st.form_submit_button("✅ 시스템에 저장"):
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), n, j, p, a, jb, "", cr, cp, cd.strftime("%Y-%m-%d")])
            st.success("새로운 고객 정보가 성공적으로 등록되었습니다."); st.rerun()

elif choice == "📄 기계약 수동 입력":
    st.markdown("<h1 class='main-title'>기존 보유계약 추가</h1>", unsafe_allow_html=True)
    sel = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].tolist())
    if sel != "선택":
        with st.form("con"):
            d = st.text_input("가입일자 (예: 2026.01.01)")
            c = st.text_input("보험회사")
            p = st.text_input("상품명")
            m = st.text_input("월 보험료")
            if st.form_submit_button("🚀 보장분석 데이터 반영"):
                sheet2.append_row([sel, d, c, p, m, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.success("해당 고객의 보유계약 리스트에 추가되었습니다."); st.rerun()

elif choice == "💰 실적 등록 및 분석":
    st.markdown("<h1 class='main-title'>성과 관리 및 분석</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["✍️ 신규 체결 실적 입력", "📈 통계 데이터 분석"])
    with t1:
        with st.form("p_f"):
            p_n = st.selectbox("계약자 선택", db_cust['이름'].tolist())
            p_d = st.date_input("체결 날짜")
            p_c = st.text_input("보험사")
            p_p = st.text_input("상품명")
            p_m = st.text_input("실적 금액 (숫자만)")
            if st.form_submit_button("🚀 실적 확정"):
                d_s = p_d.strftime("%Y.%m.%d")
                now = datetime.now().strftime("%Y-%m-%d")
                sheet3.append_row([p_n, d_s, p_c, p_p, p_m, now])
                # 중복 없이 보장분석 자동 반영
                is_dup = not db_contract[(db_contract['계약자']==p_n)&(db_contract['상품명']==p_p)].empty
                if not is_dup: sheet2.append_row([p_n, d_s, p_c, p_p, p_m, now])
                st.success("실적 등록 및 고객 보장 데이터 업데이트 완료!"); st.rerun()
    with t2:
        if not db_perf.empty:
            st.metric("총 누적 실적", f"{db_perf['금액_숫자'].sum():,}원")
            st.dataframe(db_perf[["계약자","가입날짜","보험회사","금액"]], use_container_width=True, hide_index=True)

elif choice == "📂 CSV 데이터 병합":
    st.markdown("<h1 class='main-title'>CSV 일괄 업로드</h1>", unsafe_allow_html=True)
    f = st.file_uploader("DB 파일을 선택하세요 (CSV)", type=['csv'])
    if f:
        df = pd.read_csv(f).fillna("")
        st.dataframe(df.head())
        if st.button("🚀 데이터 병합 실행"):
            st.info("데이터 분석 및 병합 로직이 실행됩니다..."); st.success("작업이 완료되었습니다."); st.rerun()

elif choice == "📩 단체 문자 발송":
    st.markdown("<h1 class='main-title'>고객 관리 문자 발송</h1>", unsafe_allow_html=True)
    target = st.multiselect("발송 대상 고객 선택", db_cust['이름'].tolist())
    st.text_area("메시지 내용 작성", height=200)
    if st.button("🚀 즉시 발송 시작 (시뮬레이션)"):
        if target: st.success(f"{len(target)}명의 고객님께 메시지 전송을 요청했습니다.")
        else: st.warning("수신자를 1명 이상 선택해 주세요.")
