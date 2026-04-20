import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# --- [보안 설정] ---
ACCESS_PASSWORD = "123456" 
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

# 보험 뉴스 스크래핑
def get_insurance_news():
    try:
        url = "https://search.naver.com/search.naver?where=news&query=보험&sm=tab_pge&sort=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".news_tit")
        return [{"title": item['title'], "link": item['href']} for item in news_items[:5]]
    except:
        return []

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 보안 접속")
    pwd_input = st.text_input("접속 비밀번호 6자리를 입력하세요.", type="password")
    if st.button("접속하기"):
        if pwd_input == ACCESS_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else: st.error("❌ 비밀번호 오류")
    st.stop()

# --- 사이드바 메뉴 ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("이동할 메뉴", ["🏠 홈", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식", "💬 고객문자발송(안내)"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v7.5")

sheet = get_gsheet()
all_values = sheet.get_all_values() if sheet else []
db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
db = db.fillna("")

if menu == "🏠 홈":
    st.subheader("🏠 메인 대시보드")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(f"현재 등록된 총 고객은 **{len(db)}명**입니다.")
        st.markdown("### 📰 실시간 보험 뉴스")
        news = get_insurance_news()
        if news:
            for n in news:
                st.markdown(f"• [{n['title']}]({n['link']})")
        else: st.write("뉴스를 불러올 수 없습니다.")

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    page_size = 30
    total_records = len(db)
    total_pages = max(1, (total_records // page_size) + (1 if total_records % page_size > 0 else 0))
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * page_size
    st.table(db[['날짜', '이름', '연락처', '주소', '자동차만기일']].iloc[start_idx : start_idx + page_size])

    st.markdown("---")
    cols = st.columns(min(total_pages, 20)) 
    for i in range(1, total_pages + 1):
        if i <= len(cols):
            if cols[i-1].button(str(i), key=f"p_{i}"):
                st.session_state.current_page = i
                st.rerun()

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_search = st.text_input("고객 성함 입력")
    if name_search:
        res = db[db['이름'].str.contains(name_search)]
        if not res.empty:
            for _, row in res.iterrows():
                with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**주민번호:** {row['주민번호']}\n\n**주소:** {row['주소']}")
                    with c2:
                        if row['차량번호']:
                            st.success(f"**차량:** {row['차량번호']} ({row['보험사']})\n\n**만기:** {row['자동차만기일']}")
                        else: st.info("차량 정보 없음")
                    
                    st.markdown("---")
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.subheader("📋 보유계약현황")
                        ana = memo.split("[보장분석]")[-1]
                        items = [i.strip() for i in ana.split('|') if i.strip()]
                        t_list = []
                        for it in items:
                            p = it.split('/')
                            if len(p) >= 2:
                                t_list.append({"보험사": p[0], "상품명": p[1], "료": p[2] if len(p)>2 else "-", "일": p[3] if len(p)>3 else "-"})
                        if t_list: st.table(pd.DataFrame(t_list))
                        st.info(f"**특이사항:** {memo.split('[보장분석]')[0].strip()}")
                    else: st.info(f"**특이사항:** {memo}")
        else: st.warning("검색 결과가 없습니다.")

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 간편 등록")
    quick = st.text_input("한 줄 등록 (이름, 주민, 연락처, 주소)", placeholder="이흥식, 560310-1673932, 010-9646-4275, 대구 동구...")
    if st.button("🚀 즉시 등록") and quick:
        try:
            d = [i.strip() for i in quick.split(',')]
            new_row = [datetime.now().strftime("%Y-%m-%d"), d[0], d[1] if len(d)>1 else "", d[2] if len(d)>2 else "", d[3] if len(d)>3 else "", "", "", d[0]] + [""]*7
            sheet.append_row(new_row); st.success(f"{d[0]}님 등록 완료!"); st.rerun()
        except: st.error("형식 오류")

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    v_in = st.text_input("양식: 이름, 차량번호, 보험사, 만기일")
    if st.button("✅ 업데이트"):
        ps = [x.strip() for x in v_in.split(',')]
        if len(ps) >= 4:
            idx = db.index[db['이름'] == ps[0]].tolist()
            if idx:
                sheet.update_cell(idx[-1]+2, 13, ps[1]); sheet.update_cell(idx[-1]+2, 14, ps[2]); sheet.update_cell(idx[-1]+2, 15, ps[3])
                st.success("완료"); st.rerun()

elif menu == "📄 보장분석리스트 입력":
    st.subheader("📄 보장분석 리스트 입력")
    target = st.selectbox("고객 선택", ["선택"] + db['이름'].unique().tolist())
    u_in = st.text_area("보장분석 결과 복사/붙여넣기")
    if st.button("🚀 반영"):
        if target != "선택" and u_in:
            m_idx = db.index[db['이름'] == target].tolist()[-1]
            old = db.iloc[m_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
            sheet.update_cell(m_idx + 2, 7, f"{old} | [보장분석] {u_in}")
            st.success("반영 완료!"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 주요 보험사 청구 양식 링크")
    st.markdown("- [삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html) / [DB손보](https://www.idbins.com/FWCRRE1001.do) / [현대해상](https://www.hi.co.kr/service/claim/guide/form.do)")

elif menu == "💬 고객문자발송(안내)":
    st.subheader("💬 문자 발송 시스템 가이드")
    st.info("알리고 API 연동이 필요합니다. 연동 시 자동 만기 안내가 가능합니다.")
