import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [1. 구글 시트 연결 설정] ---
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
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return None, None, None

@st.cache_data(ttl=3600)
def get_insurance_news():
    url = "https://news.google.com/rss/search?q=%EB%B3%B4%ED%97%98&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        return [{"제목": item.find('title').text, "링크": item.find('link').text} for item in root.findall('.//item')[:5]]
    except: return []

# --- [2. 데이터 로드] ---
st.set_page_config(page_title="배현우 FC 성과관리 시스템", layout="wide")
sheet1, sheet2, sheet3 = get_gsheets()

h1 = ["등록일자", "이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
h2 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]
h3 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]

if sheet1 and sheet2 and sheet3:
    d1 = sheet1.get_all_values()
    db_cust = pd.DataFrame(d1[1:], columns=h1[:len(d1[0])]) if len(d1) > 1 else pd.DataFrame(columns=h1)
    d2 = sheet2.get_all_values()
    db_contract = pd.DataFrame(d2[1:], columns=h2[:len(d2[0])]) if len(d2) > 1 else pd.DataFrame(columns=h2)
    d3 = sheet3.get_all_values()
    db_perf = pd.DataFrame(d3[1:], columns=h3[:len(d3[0])]) if len(d3) > 1 else pd.DataFrame(columns=h3)
    
    if not db_perf.empty:
        db_perf['금액_숫자'] = db_perf['금액'].replace('[^0-9]', '', regex=True).apply(lambda x: int(x) if x else 0)
        db_perf['가입날짜_dt'] = pd.to_datetime(db_perf['가입날짜'].str.replace('.', '-'), errors='coerce')
else:
    st.error("구글 시트 연결 실패"); st.stop()

if "menu" not in st.session_state: st.session_state.menu = "📊 메인 대시보드"

with st.sidebar:
    st.header("📋 관리 메뉴")
    menu_options = ["📊 메인 대시보드", "🔍 고객 조회 및 수정", "➕ 고객 신규등록", "📄 보유계약 입력", "💰 실적 입력 및 분석", "📂 CSV DB 일괄 업로드", "📩 SMS 단체 발송 (Cloud)"]
    current_idx = menu_options.index(st.session_state.menu) if st.session_state.menu in menu_options else 0
    st.session_state.menu = st.radio("메뉴 이동", menu_options, index=current_idx)

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [3. 메뉴별 기능 구현] ---

if st.session_state.menu == "📊 메인 대시보드":
    st.title("🚀 배현우 FC 성과 대시보드")
    if not db_perf.empty:
        this_month_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
        m_count = len(this_month_df); m_total = this_month_df['금액_숫자'].sum()
    else: m_count, m_total = 0, 0

    c1, c2, c3 = st.columns(3)
    c1.metric(f"🎯 {today.month}월 실적 건수", f"{m_count} 건")
    c2.metric(f"💰 {today.month}월 실적 합계", f"{m_total:,} 원")
    c3.metric("👥 총 누적 관리 고객", f"{len(db_cust)} 명")

    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("🎂 한 달 내 생일 도래 고객")
        upcoming_bdays = []
        for _, row in db_cust.iterrows():
            jumin = str(row.get('주민번호', '')).strip()
            if len(jumin) >= 6 and jumin[:6].isdigit():
                mmdd = jumin[2:6]
                try:
                    b_dt = datetime(today.year, int(mmdd[:2]), int(mmdd[2:]))
                    if b_dt < today: b_dt = b_dt.replace(year=today.year + 1)
                    days_left = (b_dt - today).days
                    if 0 <= days_left <= 30: upcoming_bdays.append({"고객명": row['이름'], "생일": f"{mmdd[:2]}월 {mmdd[2:]}일", "D-Day": f"D-{days_left}"})
                except: pass
        if upcoming_bdays: st.dataframe(pd.DataFrame(upcoming_bdays).sort_values(by="D-Day"), use_container_width=True, hide_index=True)
        else: st.info("한 달 내 생일인 고객이 없습니다.")
            
        st.subheader("🚗 자동차보험 만기 도래 (D-45)")
        upcoming_auto = []
        for _, row in db_cust.iterrows():
            car_date_str = str(row.get('가입일자', '')).strip().replace('.', '-').replace('/', '-')
            car_comp = str(row.get('자동차보험회사', '')).strip()
            if car_date_str and car_comp and car_comp != '-':
                try:
                    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', car_date_str)
                    if m:
                        y, m_val, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        exp_date = datetime(y + 1, m_val, d)
                        days_left = (exp_date - today).days
                        if 0 <= days_left <= 45: upcoming_auto.append({"고객명": row['이름'], "만기일": exp_date.strftime("%Y-%m-%d"), "보험사": car_comp, "D-Day": f"D-{days_left}"})
                except: pass
        if upcoming_auto: st.dataframe(pd.DataFrame(upcoming_auto).sort_values(by="D-Day"), use_container_width=True, hide_index=True)
        else: st.info("가까운 시일 내 만기되는 자동차보험이 없습니다.")
            
    with col_right:
        st.subheader("📰 오늘의 실시간 보험 뉴스")
        news = get_insurance_news()
        if news:
            for n in news: st.markdown(f"- [{n['제목']}]({n['링크']})")
        else: st.write("뉴스를 불러올 수 없습니다.")

elif st.session_state.menu == "🔍 고객 조회 및 수정":
    st.title("🔍 고객 정보 및 보유계약 조회")
    search_name = st.text_input("조회할 고객명을 입력하세요")
    if search_name:
        target_res = db_cust[db_cust['이름'] == search_name]
        if not target_res.empty:
            cust = target_res.iloc[0]
            if f"edit_{search_name}" not in st.session_state: st.session_state[f"edit_{search_name}"] = False
            
            if not st.session_state[f"edit_{search_name}"]:
                st.subheader(f"👤 {search_name} 고객님 정보")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**이름:** {cust['이름']}"); st.write(f"**주민번호:** {cust.get('주민번호', '-')}")
                    st.write(f"**연락처:** {cust['연락처']}"); st.write(f"**주소:** {cust['주소']}"); st.write(f"**직업:** {cust['직업']}")
                with c2:
                    st.write(f"**계좌번호:** {cust.get('계좌번호', '-')}"); st.write(f"**차량번호:** {cust.get('차량번호', '-')}")
                    st.write(f"**보험회사:** {cust.get('자동차보험회사', '-')}"); st.write(f"**가입일자:** {cust.get('가입일자', '-')}")
                if st.button("📝 정보변경"): st.session_state[f"edit_{search_name}"] = True; st.rerun()

                st.markdown("---")
                st.subheader("📋 보유계약 현황")
                matched = db_contract[db_contract['계약자'] == search_name]
                if not matched.empty: st.table(matched[["가입날짜", "보험회사", "상품명", "금액"]].reset_index(drop=True))
                else: st.info("등록된 보유계약 내역이 없습니다.")
            else:
                with st.form("update_form"):
                    u1, u2 = st.columns(2)
                    with u1:
                        up_name = st.text_input("이름", value=cust['이름']); up_jumin = st.text_input("주민번호", value=cust['주민번호'])
                        up_phone = st.text_input("연락처", value=cust['연락처']); up_addr = st.text_input("주소", value=cust['주소']); up_job = st.text_input("직업", value=cust['직업'])
                    with u2:
                        up_acc = st.text_input("계좌번호", value=cust.get('계좌번호', '')); up_car = st.text_input("차량번호", value=cust.get('차량번호', ''))
                        up_car_comp = st.text_input("자동차보험회사", value=cust.get('자동차보험회사', '')); up_date = st.text_input("가입일자", value=cust.get('가입일자', ''))
                    if st.form_submit_button("💾 저장"):
                        updated_row = [datetime.now().strftime("%Y-%m-%d"), up_name, up_jumin, up_phone, up_addr, up_job, up_acc, up_car, up_car_comp, up_date]
                        for i, val in enumerate(updated_row): sheet1.update_cell(target_res.index[0] + 2, i + 1, val)
                        st.session_state[f"edit_{search_name}"] = False; st.rerun()
        else:
            st.error(f"'{search_name}'님은 미등록 고객입니다.")
            if st.button("➕ 신규 등록하러 가기"): st.session_state.temp_name = search_name; st.session_state.menu = "➕ 고객 신규등록"; st.rerun()

elif st.session_state.menu == "➕ 고객 신규등록":
    st.title("➕ 신규 고객 등록")
    pre_name = st.session_state.get("temp_name", "")
    with st.form("reg_form"):
        r1, r2 = st.columns(2)
        with r1:
            r_name = st.text_input("이름", value=pre_name); r_jumin = st.text_input("주민번호 (- 포함)")
            r_phone = st.text_input("연락처"); r_addr = st.text_input("주소"); r_job = st.text_input("직업")
        with r2:
            r_acc = st.text_input("계좌번호"); r_car = st.text_input("차량번호"); r_car_comp = st.text_input("자동차보험회사"); r_date = st.date_input("가입일자")
        if st.form_submit_button("✅ 고객 등록"):
            if r_name:
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, r_acc, r_car, r_car_comp, r_date.strftime("%Y-%m-%d")])
                st.session_state.temp_name = ""; st.session_state.menu = "🔍 고객 조회 및 수정"; st.rerun()

elif st.session_state.menu == "📄 보유계약 입력":
    st.title("📄 보유계약 리스트 수동 입력")
    selected_cust = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else ["등록된 고객 없음"])
    if selected_cust != "선택":
        with st.form("contract_form"):
            c_date = st.text_input("가입날짜 (2026.01.10)"); c_comp = st.text_input("보험회사"); c_prod = st.text_input("상품명"); c_price = st.text_input("금액")
            if st.form_submit_button("🚀 보장분석 시트로 전송"):
                is_dup = not db_contract[(db_contract['계약자'] == selected_cust) & (db_contract['가입날짜'] == c_date) & (db_contract['보험회사'] == c_comp) & (db_contract['상품명'] == c_prod)].empty
                if not is_dup:
                    sheet2.append_row([selected_cust, c_date, c_comp, c_prod, c_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                    st.success("보장분석시트에 등록되었습니다."); st.rerun()
                else: st.warning("이미 등록된 계약입니다.")

elif st.session_state.menu == "💰 실적 입력 및 분석":
    st.title("💰 실적 관리 및 자동 연동")
    tab_in, tab_an = st.tabs(["✍️ 신규 실적 입력", "📈 성과 분석"])
    with tab_in:
        with st.form("perf_form"):
            p_name = st.selectbox("계약자 선택", db_cust['이름'].unique().tolist() if not db_cust.empty else ["고객없음"])
            p_date = st.date_input("가입날짜(체결일)", today)
            p_comp = st.text_input("보험회사"); p_prod = st.text_input("상품명"); p_price = st.text_input("금액 (숫자만)")
            if st.form_submit_button("🚀 실적 등록 및 보장분석 반영"):
                if p_name != "고객없음" and p_price:
                    p_date_str = p_date.strftime("%Y.%m.%d")
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet3.append_row([p_name, p_date_str, p_comp, p_prod, p_price, now_str])
                    is_dup = not db_contract[(db_contract['계약자'] == p_name) & (db_contract['가입날짜'] == p_date_str) & (db_contract['보험회사'] == p_comp) & (db_contract['상품명'] == p_prod)].empty
                    if not is_dup: sheet2.append_row([p_name, p_date_str, p_comp, p_prod, p_price, now_str])
                    st.success(f"✅ 실적 등록 완료!"); st.rerun()
    with tab_an:
        period = st.radio("기간 선택", ["주간 실적", "월간 실적", "연간 실적"], horizontal=True)
        if not db_perf.empty:
            if period == "주간 실적": filtered = db_perf[db_perf['가입날짜_dt'] >= (today - timedelta(days=today.weekday()))]
            elif period == "월간 실적": filtered = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
            else: filtered = db_perf[db_perf['가입날짜_dt'].dt.year == today.year]
            st.metric(f"누적 합계 ({period})", f"{filtered['금액_숫자'].sum():,}")
            st.dataframe(filtered[["계약자", "가입날짜", "보험회사", "상품명", "금액"]].reset_index(drop=True), use_container_width=True)

elif st.session_state.menu == "📂 CSV DB 일괄 업로드":
    st.title("📂 고객 DB 스마트 병합")
    up_file = st.file_uploader("CSV 선택", type=['csv'])
    if up_file:
        df = pd.read_csv(up_file).fillna(""); st.dataframe(df.head())
        csv_cols = ["선택 안 함"] + list(df.columns)
        mapping = {}
        target_h = ["이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
        cols = st.columns(3)
        for i, h in enumerate(target_h):
            with cols[i%3]: 
                def_idx = csv_cols.index(h) if h in csv_cols else 0
                if h == "연락처":
                    for syn in ["전화번호", "핸드폰"]:
                        if syn in csv_cols: def_idx = csv_cols.index(syn); break
                mapping[h] = st.selectbox(f"➡️ {h}", csv_cols, index=def_idx)
        if st.button("🚀 데이터 병합 전송"):
            new_data, up_cnt = [], 0
            for _, row in df.iterrows():
                n_val = str(row[mapping["이름"]]).strip()
                if not n_val: continue
                in_d = {k: str(row[mapping[k]]).strip() for k in target_h if mapping[k] != "선택 안 함"}
                exist = db_cust[db_cust['이름'] == n_val]
                if not exist.empty:
                    s_idx = exist.index[0] + 2
                    for k, v in in_d.items():
                        if str(exist.iloc[0].get(k, "")) in ["", "-", "None", "nan"] and v:
                            sheet1.update_cell(s_idx, target_h.index(k)+2, v); up_cnt += 1
                else: new_data.append([datetime.now().strftime("%Y-%m-%d")] + [in_d.get(k, "") for k in target_h])
            if new_data: sheet1.append_rows(new_data)
            st.success(f"신규 {len(new_data)}명 등록, {up_cnt}건 정보 보완 완료!")

# (7) SMS 단체 발송 (Cloud 전용)
elif st.session_state.menu == "📩 SMS 단체 발송 (Cloud)":
    st.title("📩 고객 맞춤형 단체 문자 발송 (SMS)")
    st.info("💡 모바일, 태블릿, 외부 PC 어디서든 클라우드를 통해 접속하여 즉시 문자를 발송할 수 있는 시스템입니다.")
    st.warning("※ 현재는 시뮬레이션 모드이며, 추후 알리고(Aligo) 등의 API Key를 등록하면 즉시 실전 발송이 가능합니다.")
    
    if db_cust.empty:
        st.error("등록된 고객 데이터가 없습니다.")
    else:
        valid_cust = db_cust[db_cust['연락처'].astype(str).str.len() > 8]
        
        st.subheader("1. 수신 대상 필터링")
        target_group = st.radio("문자 발송 대상을 선택하세요", ["직접 선택", "이번달 생일 고객", "전체 고객"], horizontal=True)
        
        selected_recipients = []
        if target_group == "전체 고객":
            selected_recipients = valid_cust['이름'].tolist()
            st.write(f"총 **{len(selected_recipients)}명**이 선택되었습니다.")
        elif target_group == "이번달 생일 고객":
            bday_cust = []
            for _, row in valid_cust.iterrows():
                jumin = str(row.get('주민번호', '')).strip()
                if len(jumin) >= 6 and jumin[2:4] == str(today.month).zfill(2):
                    bday_cust.append(row['이름'])
            selected_recipients = bday_cust
            st.write(f"이번 달 생일 고객은 총 **{len(selected_recipients)}명**입니다.")
        elif target_group == "직접 선택":
            selected_recipients = st.multiselect("수신할 고객을 다중 선택하세요", valid_cust['이름'].tolist())
            
        st.subheader("2. 문자 내용 (템플릿)")
        template = st.selectbox("빠른 템플릿 불러오기", ["직접 작성", "생일 축하 (LMS)", "안부 인사 (SMS)", "자동차보험 만기 알림 (LMS)"])
        
        default_msg = ""
        if template == "생일 축하 (LMS)":
            default_msg = "[배현우 FC]\n고객님, 생일을 진심으로 축하드립니다! 🎉\n항상 건강하시고 오늘 하루 행복 가득하시길 바랍니다.\n변함없이 든든한 보험 파트너가 되겠습니다."
        elif template == "안부 인사 (SMS)":
            default_msg = "[배현우 FC]\n고객님, 환절기 건강 유의하시고 평안한 한 주 보내시길 바랍니다! 궁금한 점 있으시면 언제든 연락주세요."
        elif template == "자동차보험 만기 알림 (LMS)":
            default_msg = "[배현우 FC]\n고객님, 자동차보험 만기가 다가오고 있습니다.\n올해도 가장 유리한 조건으로 갱신하실 수 있도록 꼼꼼히 비교하여 최적의 플랜을 준비해 두었습니다.\n편하신 시간에 연락 주시면 상세히 안내해 드리겠습니다!"
            
        message = st.text_area("메시지 내용 (90바이트 초과 시 자동으로 장문(LMS) 전환됩니다)", value=default_msg, height=150)
        
        st.markdown("---")
        if st.button("🚀 클라우드 SMS 자동 발송 시작", type="primary"):
            if not selected_recipients:
                st.error("수신할 고객을 1명 이상 선택해주세요.")
            elif not message:
                st.error("보낼 메시지를 입력해주세요.")
            else:
                with st.spinner("통신사 API 서버로 데이터를 전송하는 중입니다..."):
                    # 실제 발송 API 연동 시 이 부분에 requests.post 코드가 들어갑니다.
                    st.success(f"✅ {len(selected_recipients)}명의 고객에게 문자가 성공적으로 전송(예약)되었습니다!")
                    
                    with st.expander("📝 상세 발송 리포트 보기"):
                        report_data = []
                        for name in selected_recipients:
                            phone = valid_cust[valid_cust['이름'] == name].iloc[0]['연락처']
                            report_data.append({"고객명": name, "연락처": phone, "상태": "발송 성공"})
                        st.dataframe(pd.DataFrame(report_data), hide_index=True)
