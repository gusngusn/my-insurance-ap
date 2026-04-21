import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [접속 및 시트 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(index)
    except: return None

# --- [보험매일 뉴스 스크래핑 보강] ---
def get_insurance_news():
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        url = "https://www.insnews.co.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_items = soup.select(".list-titles a")
        for item in news_items[:5]:
            results.append({"title": item.get_text().strip(), "link": "https://www.insnews.co.kr" + item.get('href') if item.get('href').startswith('/') else item.get('href')})
    except: pass
    return results

# --- [데이터 로드] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")

sheet_cust = get_gsheet(0)
sheet_sales = get_gsheet(1)

cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS) if len(cust_values) > 1 else pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "상품명", "보험료"]
db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers) if len(sales_values) > 1 else pd.DataFrame(columns=sales_headers)
db_sales['보험료'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# --- [사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio("메뉴 선택", ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"])
    st.markdown("---")
    st.caption("배현우 FC 전용 v9.0")

# --- [메뉴별 기능 구현] ---
if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'], errors='coerce')
    curr_m, curr_y = datetime.now().month, datetime.now().year
    this_m_data = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 이번 달 보험료 합계", f"{int(this_m_data['보험료'].sum()):,}원")
    m2.metric("📈 이번 달 체결 건수", f"{len(this_m_data)}건")
    m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료'].sum()):,}원")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎂 이번 달 생일 고객")
        this_month_str = datetime.now().strftime("%m")
        birth_cust = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_month_str]
        if not birth_cust.empty:
            for _, r in birth_cust.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {r['연락처']}")
        else: st.write("생일인 고객이 없습니다.")
    with c2:
        st.subheader("🚘 자동차보험 만기 (30일내)")
        today, count = datetime.now(), 0
        for _, r in db_cust.iterrows():
            m_str = r['자동차만기일'].replace('.', '-').strip()
            if m_str:
                try:
                    m_dt = datetime.strptime(m_str, "%Y-%m-%d")
                    if today <= m_dt <= today + timedelta(days=30):
                        st.warning(f"⚠️ **{r['이름']}** : {r['자동차만기일']} ({r['차량번호']})")
                        count += 1
                except: pass
        if count == 0: st.write("만기 임박 고객이 없습니다.")

    st.markdown("---")
    st.markdown("### 📰 실시간 보험 뉴스")
    news = get_insurance_news()
    for n in news: st.markdown(f"• [{n['title']}]({n['link']})")

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 등록 및 현황")
    s_input = st.text_area("실적 내용 입력 (예: 1/13 배현우 삼성생명 치아보험 25,230)")
    if st.button("🚀 실적 기록") and s_input:
        try:
            parts = [p.strip() for p in re.split(r'[\s/]+', s_input.replace('\n', ' ')) if p.strip()]
            date_match = re.search(r'(\d{1,2}/\d{1,2})', s_input)
            date_val = f"{datetime.now().year}-{date_match.group(1).replace('/', '-')}" if date_match else datetime.now().strftime("%Y-%m-%d")
            price_val = re.sub(r'[^0-9]', '', parts[-1])
            name_val = parts[1] if len(parts) > 1 else "미정"
            prod_val = " ".join(parts[2:-1])
            sheet_sales.append_row([date_val, name_val, prod_val, price_val])
            st.success("등록 완료!"); st.rerun()
        except: st.error("입력 형식을 확인해주세요.")
    st.dataframe(db_sales.sort_values(by="날짜", ascending=False), use_container_width=True)

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    name_s = st.text_input("고객 성함")
    if name_s:
        res = db_cust[db_cust['이름'].str.contains(name_s)]
        for _, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                c1, c2 = st.columns(2)
                with c1: st.write(f"**주민:** {row['주민번호']}\n\n**주소:** {row['주소']}")
                with c2: 
                    if row['차량번호']: st.success(f"**차량:** {row['차량번호']} ({row['보험사']})\n\n**만기:** {row['자동차만기일']}")
                memo = row['병력(특이사항)']
                if "[보장분석]" in memo:
                    ana = memo.split("[보장분석]")[-1]
                    raw = [i.strip() for i in ana.split('|') if i.strip()]
                    t_data = [{"보험사": p.split('/')[0], "상품명": p.split('/')[1], "료": p.split('/')[2] if len(p.split('/'))>2 else "-"} for p in raw if len(p.split('/'))>=2]
                    st.table(pd.DataFrame(t_data))
                    st.info(f"**특이사항:** {memo.split('[보장분석]')[0]}")
                else: st.info(f"**특이사항:** {memo}")

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 등록")
    quick = st.text_input("한 줄 등록 (이름, 주민, 연락처, 주소)")
    if st.button("즉시 등록") and quick:
        d = [i.strip() for i in quick.split(',')]
        new_row = [datetime.now().strftime("%Y-%m-%d"), d[0], d[1] if len(d)>1 else "", d[2] if len(d)>2 else "", d[3] if len(d)>3 else "", "", "", d[0]] + [""]*7
        sheet_cust.append_row(new_row); st.success("등록 완료!"); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트 (30명씩)")
    page_size = 30
    total_pages = max(1, (len(db_cust) // page_size) + (1 if len(db_cust) % page_size > 0 else 0))
    if 'curr_p' not in st.session_state: st.session_state.curr_p = 1
    start = (st.session_state.curr_p - 1) * page_size
    st.table(db_cust[['날짜', '이름', '연락처', '주소', '자동차만기일']].iloc[start : start + page_size])
    cols = st.columns(20)
    for i in range(1, total_pages + 1):
        if cols[i-1].button(str(i)): st.session_state.curr_p = i; st.rerun()

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    v_in = st.text_input("이름, 차량번호, 보험사, 만기일")
    if st.button("반영"):
        p = [x.strip() for x in v_in.split(',')]
        idx = db_cust.index[db_cust['이름'] == p[0]].tolist()
        if idx:
            sheet_cust.update_cell(idx[-1]+2, 13, p[1]); sheet_cust.update_cell(idx[-1]+2, 14, p[2]); sheet_cust.update_cell(idx[-1]+2, 15, p[3])
            st.success("완료"); st.rerun()

elif menu == "📄 보장분석리스트 입력":
    st.subheader("📄 보장분석 리스트 입력")
    target = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    u_in = st.text_area("내용 입력")
    if st.button("업데이트"):
        if target != "선택" and u_in:
            m_idx = db_cust.index[db_cust['이름'] == target].tolist()[-1]
            old = db_cust.iloc[m_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
            sheet_cust.update_cell(m_idx + 2, 7, f"{old} | [보장분석] {u_in}")
            st.success("완료"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 전 보험사 보험금 청구 양식")
    st.info("💡 링크를 클릭하면 공식 홈페이지 청구 양식 다운로드 페이지로 이동합니다.")
    
    # 1. 손해보험사 (가나다순)
    st.markdown("#### [손해보험사]")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("[메리츠화재](https://www.meritzfire.com/compensation/guide/claim-guide.do)")
        st.markdown("[한화손해보험](https://www.hwgeneralins.com/compensation/guide/form-download.do)")
        st.markdown("[롯데손해보험](https://www.lotteins.co.kr/web/CST/CLM/GLD/cstClmGld01.jsp)")
        st.markdown("[MG손해보험](https://www.mggeneralins.com/compensation/guide/form-download.do)")
    with c2:
        st.markdown("[흥국화재](https://www.heungkukfire.co.kr/main/compensation/guide/compensationGuide.do)")
        st.markdown("[삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html)")
        st.markdown("[현대해상](https://www.hi.co.kr/service/claim/guide/form.do)")
        st.markdown("[KB손해보험](https://www.kbinsure.co.kr/CG302010001.ec)")
    with c3:
        st.markdown("[DB손해보험](https://www.idbins.com/FWCRRE1001.do)")
        st.markdown("[AXA손해보험](https://www.axa.co.kr/main/compensation/common/fileDownload.do)")
        st.markdown("[하나손해보험](https://www.hanainsure.co.kr/compensation/guide/form)")
        st.markdown("[캐롯손해보험](https://www.carrotins.com/claim/guide/form)")

    # 2. 생명보험사 (가나다순)
    st.markdown("---")
    st.markdown("#### [생명보험사]")
    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown("[한화생명](https://www.hanwhalife.com/static/service/customer/claim/reward/reward_01.html)")
        st.markdown("[ABL생명](https://www.abllife.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[삼성생명](https://www.samsunglife.com/customer/claim/reward/reward_01.html)")
        st.markdown("[흥국생명](https://www.heungkuklife.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[교보생명](https://www.kyobo.com/webdoc/customer/claim/reward/reward_01.html)")
        st.markdown("[DGB생명](https://www.dgblife.co.kr/customer/claim/reward/reward_01.html)")
    with c5:
        st.markdown("[KDB생명](https://www.kdblife.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[DB생명](https://www.idblife.com/customer/claim/reward/reward_01.html)")
        st.markdown("[동양생명](https://www.myangel.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[메트라이프](https://www.metlife.co.kr/customer-service/claim/guide/)")
        st.markdown("[라이나생명](https://www.lina.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[AIA생명](https://www.aia.co.kr/ko/customer-service/claim/guide.html)")
    with c6:
        st.markdown("[푸본현대생명](https://www.fubonhyundai.com/customer/claim/reward/reward_01.html)")
        st.markdown("[신한라이프](https://www.shinhanlife.co.kr/hp/cd/cd010101.do)")
        st.markdown("[미래에셋생명](https://life.miraeasset.com/customer/claim/reward/reward_01.html)")
        st.markdown("[교보라이프플래닛](https://www.lifeplanet.co.kr/customer/claim/guide.dev)")
        st.markdown("[아이엠라이프](https://www.imlife.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("[우체국보험](https://www.epostbank.go.kr/claim/reward/reward_01.html)")
