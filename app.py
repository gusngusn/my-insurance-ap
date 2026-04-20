import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# --- [접속 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# --- [보험매일 실시간 뉴스 스크래핑 함수] ---
def get_insurance_news():
    try:
        # 요청하신 보험매일 '종합/정책' 섹션 URL
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8' # 한글 깨짐 방지
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 보험매일 기사 제목 및 링크 추출 (사이트 구조 반영)
        news_list = soup.select(".list-titles a")
        
        results = []
        base_url = "https://www.insnews.co.kr"
        for item in news_list[:7]: # 최신 뉴스 7개
            title = item.get_text().strip()
            link = item.get('href')
            if link.startswith('/'): # 상대 경로일 경우 절대 경로로 변환
                link = base_url + link
            results.append({"title": title, "link": link})
        return results
    except Exception as e:
        return []

# --- [기본 환경 설정] ---
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
st.set_page_config(page_title="배현우 고객관리 시스템", layout="wide")

# --- [사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio(
        "이동할 메뉴를 선택하세요",
        ["🏠 홈", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식", "💬 고객문자발송(안내)"]
    )
    st.markdown("---")
    st.caption("배현우 FC 전용 시스템 v7.8")

# 데이터 로드
sheet = get_gsheet()
all_values = sheet.get_all_values() if sheet else []
db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
db = db.fillna("")

# --- [메뉴별 기능 구현] ---

if menu == "🏠 홈":
    st.subheader("🏠 메인 대시보드")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(f"현재 등록된 총 고객은 **{len(db)}명**입니다.")
        st.markdown("### 📰 보험매일 실시간 뉴스 (종합/정책)")
        news_list = get_insurance_news()
        if news_list:
            for n in news_list:
                st.markdown(f"• [{n['title']}]({n['link']})")
        else:
            st.warning("뉴스를 불러올 수 없습니다. 사이트 접근 권한이나 연결 상태를 확인하세요.")

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("검색할 고객 성함")
    if name_s:
        res = db[db['이름'].str.contains(name_s)]
        if not res.empty:
            for _, row in res.iterrows():
                with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**주민번호:** {row['주민번호']}\n\n**주소:** {row['주소']}")
                    with c2:
                        if row['차량번호']:
                            st.success(f"**차량:** {row['차량번호']} ({row['보험사']})\n\n**📅 자동차 만기:** {row['자동차만기일']}")
                    st.markdown("---")
                    memo = row['병력(특이사항)']
                    if "[보장분석]" in memo:
                        st.subheader("📋 보유계약현황")
                        ana = memo.split("[보장분석]")[-1]
                        raw = [i.strip() for i in ana.split('|') if i.strip()]
                        t_data = []
                        for it in raw:
                            p = it.split('/')
                            if len(p) >= 2:
                                t_data.append({"보험사": p[0], "상품명": p[1], "보험료": p[2] if len(p)>2 else "-", "가입일": p[3] if len(p)>3 else "-"})
                        if t_data: st.table(pd.DataFrame(t_data))
                        st.info(f"**💡 특이사항:** {memo.split('[보장분석]')[0].strip()}")
                    else: st.info(f"**💡 특이사항:** {memo}")

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 등록")
    quick = st.text_input("🚀 한 줄 간편 등록 (이름, 주민, 연락처, 주소)", placeholder="이흥식, 560310-1673932, 010-9646-4275, 대구 동구...")
    if st.button("즉시 등록") and quick:
        try:
            d = [i.strip() for i in quick.split(',')]
            new_row = [datetime.now().strftime("%Y-%m-%d"), d[0], d[1] if len(d)>1 else "", d[2] if len(d)>2 else "", d[3] if len(d)>3 else "", "", "", d[0]] + [""]*7
            sheet.append_row(new_row); st.success(f"{d[0]}님 등록 완료!"); st.rerun()
        except: st.error("데이터 형식을 확인해주세요.")

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트 (30명씩)")
    page_size = 30
    total_pages = max(1, (len(db) // page_size) + (1 if len(db) % page_size > 0 else 0))
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    
    start_idx = (st.session_state.current_page - 1) * page_size
    st.table(db[['날짜', '이름', '연락처', '주소', '자동차만기일']].iloc[start_idx : start_idx + page_size])
    
    st.write("페이지 이동:")
    cols = st.columns(20)
    for i in range(1, total_pages + 1):
        if cols[i-1].button(str(i), key=f"p_{i}"):
            st.session_state.current_page = i
            st.rerun()

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    v_in = st.text_input("양식: 이름, 차량번호, 보험사, 만기일")
    if st.button("✅ 데이터 반영"):
        ps = [x.strip() for x in v_in.split(',')]
        if len(ps) >= 4:
            idx = db.index[db['이름'] == ps[0]].tolist()
            if idx:
                r = idx[-1] + 2
                sheet.update_cell(r, 13, ps[1]); sheet.update_cell(r, 14, ps[2]); sheet.update_cell(r, 15, ps[3])
                st.success(f"{ps[0]}님 업데이트 완료!"); st.rerun()

elif menu == "📄 보장분석리스트 입력":
    st.subheader("📄 보장분석 리스트 입력")
    target = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
    u_in = st.text_area("보장분석 결과 (내용 붙여넣기)")
    if st.button("🚀 업데이트"):
        if target != "선택하세요" and u_in:
            m_idx = db.index[db['이름'] == target].tolist()[-1]
            old = db.iloc[m_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
            sheet.update_cell(m_idx + 2, 7, f"{old} | [보장분석] {u_in}")
            st.success("반영 완료!"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 주요 보험사 청구 양식 다운로드")
    st.markdown("- [삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html)\n- [DB손보](https://www.idbins.com/FWCRRE1001.do)\n- [현대해상](https://www.hi.co.kr/service/claim/guide/form.do)\n- [KB손보](https://www.kbinsure.co.kr/CG302010001.ec)")

elif menu == "💬 고객문자발송(안내)":
    st.subheader("💬 고객 문자 발송 안내")
    st.info("알리고(Aligo) API를 연동하면 이 화면에서 즉시 만기 안내 문자를 보낼 수 있습니다.")
