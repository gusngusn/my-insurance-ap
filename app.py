import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET
import time
import subprocess
import sys

# --- [매크로 전용 라이브러리 자동 설치 로직] ---
try:
    import pyautogui
    import pyperclip
    MACRO_AVAILABLE = True
except ImportError:
    MACRO_AVAILABLE = False
    st.warning("⚙️ 매크로 부품이 다른 경로에 설치되어 있어, 앱 내부에서 자기 방으로 자동 복사(설치)를 진행합니다. (약 10~30초 소요)")
    try:
        # 앱이 실행 중인 정확한 파이썬 경로(sys.executable)를 찾아 그곳에 직접 설치합니다.
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui", "pyperclip"])
        st.success("✅ 매크로 부품 자동 설치가 완료되었습니다! 키보드의 [F5] 키를 눌러 화면을 새로고침 해주세요.")
    except Exception as e:
        st.error(f"자동 설치 실패. 권한 문제일 수 있습니다: {e}")

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

# --- [3. 데이터 로드] ---
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
    menu_options = ["📊 메인 대시보드", "🔍 고객 조회 및 수정", "➕ 고객 신규등록", "📄 보유계약 입력", "💰 실적 입력 및 분석", "📂 CSV DB 일괄 업로드", "📩 SMS & 카톡 자동 발송"]
    current_idx = menu_options.index(st.session_state.menu) if st.session_state.menu in menu_options else 0
    st.session_state.menu = st.radio("메뉴 이동", menu_options, index=current_idx)

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [5. 메뉴별 기능 상세 구현] ---

# (1) 메인 대시보드
if st.session_state.menu == "📊 메인 대시보드":
    st.title("🚀 배현우 FC 성과 대시보드")
    if not db_perf.empty:
        this_month_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
        m_count = len(this_month_df)
        m_total = this_month_df['금액_숫자'].sum()
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

# (2) 고객 조회 및 수정
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
                st.subheader("📋 보유계약 현황 (보장분석시트)")
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

# (3) 고객 신규등록
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

# (4) 보유계약 입력
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

# (5) 실적 입력 및 분석
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

# (6) CSV DB 일괄 업로드
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

# (7) SMS & 카톡 자동 발송
elif st.session_state.menu == "📩 SMS & 카톡 자동 발송":
    st.title("📩 알림톡 & 카카오톡 무료 자동 발송")
    tab_sms, tab_kakao = st.tabs(["📱 유료 SMS 발송 (API)", "💬 무료 PC카톡 매크로 발송"])
    
    with tab_sms:
        st.info("외부 문자 대행사(Aligo 등)의 API를 연결하여 발송하는 유료 기능입니다.")
        st.write("카카오톡 무료 발송은 옆의 [무료 PC카톡 매크로 발송] 탭을 눌러주세요.")

    with tab_kakao:
        if not MACRO_AVAILABLE:
            st.error("⚠️ 매크로 모듈이 아직 설치 중이거나 설치에 실패했습니다. 코드를 다시 실행해주세요.")
        else:
            st.warning("🚨 [주의사항] 매크로가 시작되면 **절대 마우스와 키보드를 만지지 마세요!** 화면이 혼자 움직입니다.")
            st.markdown("""
            **💡 PC 카톡 발송 준비 체크리스트**
            1. 현재 PC에 **카카오톡이 켜져 있고 로그인** 되어 있어야 합니다.
            2. 카카오톡 창을 화면에 한 번 띄워두세요. (최소화 금지)
            3. 고객 DB의 '이름'과 내 카카오톡 친구 목록에 저장된 '이름'이 완벽히 똑같아야 합니다.
            """)
            
            valid_cust = db_cust[db_cust['연락처'].astype(str).str.len() > 8]
            
            st.subheader("1. 카톡을 보낼 대상 선택")
            target_group = st.radio("카톡 발송 대상을 선택하세요", ["직접 선택", "이번달 생일 고객"], key="k_radio")
            
            selected_k_recipients = []
            if target_group == "이번달 생일 고객":
                bday_cust = []
                for _, row in valid_cust.iterrows():
                    jumin = str(row.get('주민번호', '')).strip()
                    if len(jumin) >= 6 and jumin[2:4] == str(today.month).zfill(2):
                        bday_cust.append(row['이름'])
                selected_k_recipients = bday_cust
                st.write(f"이번 달 생일 고객: **{len(selected_k_recipients)}명**")
            elif target_group == "직접 선택":
                selected_k_recipients = st.multiselect("수신 고객 선택", valid_cust['이름'].tolist(), key="k_multi")

            st.subheader("2. 카톡 내용 작성")
            k_msg = st.text_area("보낼 카톡 메시지를 입력하세요", value="[배현우 FC]\n고객님, 환절기 감기 조심하세요! 😊", height=150)
            
            if st.button("🚀 PC 카톡 자동 발송 시작 (위험: 마우스 손 떼기!)", type="primary"):
                if not selected_k_recipients: st.error("수신자를 선택하세요.")
                elif not k_msg: st.error("메시지를 입력하세요.")
                else:
                    msg_placeholder = st.empty()
                    msg_placeholder.info("⏳ 5초 뒤 매크로가 시작됩니다. 열려있는 PC 카카오톡 창을 한 번 클릭해 활성화해주세요!")
                    time.sleep(5) 
                    
                    success_cnt = 0
                    for name in selected_k_recipients:
                        msg_placeholder.warning(f"🤖 [{name}]님에게 카톡을 전송하는 중...")
                        try:
                            pyautogui.hotkey('ctrl', 'f')
                            time.sleep(1)
                            pyperclip.copy(name)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(1.5)
                            pyautogui.press('enter')
                            time.sleep(1.5)
                            pyperclip.copy(k_msg)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(1)
                            pyautogui.press('enter')
                            time.sleep(1)
                            pyautogui.press('esc')
                            time.sleep(1)
                            success_cnt += 1
                        except Exception as e:
                            st.error(f"{name}님 전송 실패: {e}")
                            break
                    msg_placeholder.success(f"🎉 총 {success_cnt}명에게 카카오톡 자동 발송이 완료되었습니다. 이제 마우스를 잡으셔도 됩니다.")
