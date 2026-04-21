import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET
import time

# --- [매크로 전용 라이브러리 (설치 필수: pip install pyautogui pyperclip)] ---
try:
    import pyautogui
    import pyperclip
    MACRO_AVAILABLE = True
except ImportError:
    MACRO_AVAILABLE = False

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

# (1~6 메뉴 생략 - v55.0과 완전히 동일하게 유지됨. 스크롤 압박을 줄이기 위해 카톡 발송 메뉴 로직만 집중해서 보여드립니다. 실제 파일에는 기존 코드를 그대로 두시면 됩니다.)
# -------------------------------------------------------------------------------------------------------------------------------------------

# (7) SMS & 카톡 자동 발송 (매크로 탑재)
if st.session_state.menu == "📩 SMS & 카톡 자동 발송":
    st.title("📩 알림톡 & 카카오톡 무료 자동 발송")
    
    tab_sms, tab_kakao = st.tabs(["📱 유료 SMS 발송 (API)", "💬 무료 PC카톡 매크로 발송"])
    
    # [탭 1: 기존 SMS]
    with tab_sms:
        st.info("외부 문자 대행사(Aligo 등)의 API를 연결하여 발송하는 유료 기능입니다. (현재 시뮬레이션)")
        # ... (이전 v55.0의 문자 발송 로직과 동일) ...
        st.write("카카오톡 무료 발송은 옆의 [무료 PC카톡 매크로 발송] 탭을 눌러주세요.")

    # [탭 2: 신규 PC 카톡 매크로]
    with tab_kakao:
        if not MACRO_AVAILABLE:
            st.error("⚠️ 매크로 모듈이 설치되지 않았습니다. 명령 프롬프트에서 `pip install pyautogui pyperclip`을 실행해주세요.")
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
            
            # 발송 버튼
            st.markdown("---")
            if st.button("🚀 PC 카톡 자동 발송 시작 (위험: 마우스 손 떼기!)", type="primary"):
                if not selected_k_recipients:
                    st.error("수신자를 선택하세요.")
                elif not k_msg:
                    st.error("메시지를 입력하세요.")
                else:
                    msg_placeholder = st.empty()
                    msg_placeholder.info("⏳ 5초 뒤 매크로가 시작됩니다. 열려있는 PC 카카오톡 창을 한 번 클릭해 활성화해주세요!")
                    time.sleep(5) # 사용자가 카톡 창을 클릭할 시간 5초 부여
                    
                    success_cnt = 0
                    for name in selected_k_recipients:
                        msg_placeholder.warning(f"🤖 [{name}]님에게 카톡을 전송하는 중...")
                        
                        try:
                            # 1. 카카오톡 '친구 찾기' 단축키 (Ctrl + F)
                            pyautogui.hotkey('ctrl', 'f')
                            time.sleep(1)
                            
                            # 2. 이름 복사 및 검색창에 붙여넣기
                            pyperclip.copy(name)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(1.5) # 검색 로딩 대기
                            
                            # 3. 검색된 친구 채팅방 열기 (Enter)
                            pyautogui.press('enter')
                            time.sleep(1.5) # 채팅방 열리는 시간 대기
                            
                            # 4. 메시지 복사 및 붙여넣기
                            pyperclip.copy(k_msg)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(1)
                            
                            # 5. 전송 (Enter)
                            pyautogui.press('enter')
                            time.sleep(1)
                            
                            # 6. 채팅방 닫기 (ESC)
                            pyautogui.press('esc')
                            time.sleep(1)
                            
                            success_cnt += 1
                        except Exception as e:
                            st.error(f"{name}님 전송 실패: {e}")
                            break # 에러 나면 즉시 매크로 중단
                            
                    msg_placeholder.success(f"🎉 총 {success_cnt}명에게 카카오톡 자동 발송이 완료되었습니다. 이제 마우스를 잡으셔도 됩니다.")
