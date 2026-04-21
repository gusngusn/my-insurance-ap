import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- [1. 구글 시트 및 보안 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet(index=0):
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(index)
    except Exception as e:
        st.error(f"⚠️ 시트 연결 실패: {e}")
        return None

# --- [2. 보험 뉴스 스크래핑 함수] ---
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
            title = item.get_text().strip()
            link = "https://www.insnews.co.kr" + item.get('href') if item.get('href').startswith('/') else item.get('href')
            if title:
                results.append({"title": title, "link": link})
    except:
        pass
    return results

# --- [3. 데이터 로드 및 전처리] ---
st.set_page_config(page_title="배현우 성과관리 시스템", layout="wide")

sheet_cust = get_gsheet(0)  # 고객정보 시트
sheet_sales = get_gsheet(1) # 실적리스트 시트

# 고객 데이터 로드
cust_values = sheet_cust.get_all_values() if sheet_cust else []
EXPECTED_CUST_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]
if len(cust_values) > 1:
    db_cust = pd.DataFrame(cust_values[1:], columns=EXPECTED_CUST_HEADERS)
else:
    db_cust = pd.DataFrame(columns=EXPECTED_CUST_HEADERS)

# 실적 데이터 로드
sales_values = sheet_sales.get_all_values() if sheet_sales else []
sales_headers = ["날짜", "고객명", "생년월일", "상품명", "보험료"] # 생년월일 컬럼 추가
if len(sales_values) > 1:
    db_sales = pd.DataFrame(sales_values[1:], columns=sales_headers)
else:
    db_sales = pd.DataFrame(columns=sales_headers)

db_sales['보험료'] = pd.to_numeric(db_sales['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
db_sales['날짜_dt'] = pd.to_datetime(db_sales['날짜'], errors='coerce')

# --- [4. 사이드바 메뉴 구성] ---
with st.sidebar:
    st.header("📋 메뉴 리스트")
    menu = st.radio(
        "이동할 메뉴를 선택하세요",
        ["🏠 홈", "📊 실적 관리", "🔍 고객조회/수정", "✍️ 고객정보 신규등록", "📑 고객리스트", "🚘 자동차증권 업데이트", "📄 보장분석리스트 입력", "🏥 보험청구 양식"]
    )
    st.markdown("---")
    st.caption("배현우 FC 전용 시스템 v11.0")

# --- [5. 메뉴별 상세 기능 구현] ---

if menu == "🏠 홈":
    st.title("🛡️ 배현우 FC 성과 대시보드")
    curr_m, curr_y = datetime.now().month, datetime.now().year
    this_m_data = db_sales[(db_sales['날짜_dt'].dt.month == curr_m) & (db_sales['날짜_dt'].dt.year == curr_y)]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 이번 달 보험료 합계", f"{int(this_m_data['보험료'].sum()):,}원")
    m2.metric("📈 이번 달 체결 건수", f"{len(this_m_data)}건")
    m3.metric("🏆 올해 누적 실적", f"{int(db_sales[db_sales['날짜_dt'].dt.year == curr_y]['보험료'].sum()):,}원")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🎂 이번 달 생일 고객")
        this_month_str = datetime.now().strftime("%m")
        birth_cust = db_cust[db_cust['주민번호'].str.slice(2, 4) == this_month_str]
        if not birth_cust.empty:
            for _, r in birth_cust.iterrows(): st.write(f"🎈 **{r['이름']}** ({r['주민번호'][:6]}) - {r['연락처']}")
        else: st.write("이번 달 생일인 고객이 없습니다.")
    with col_b:
        st.subheader("🚘 자동차보험 만기 임박 (30일내)")
        today, in_30_days, exp_count = datetime.now(), datetime.now() + timedelta(days=30), 0
        for _, r in db_cust.iterrows():
            m_str = r['자동차만기일'].replace('.', '-').strip()
            try:
                m_dt = datetime.strptime(m_str, "%Y-%m-%d")
                if today <= m_dt <= in_30_days:
                    st.warning(f"⚠️ **{r['이름']}** : {r['자동차만기일']} ({r['차량번호']})")
                    exp_count += 1
            except: pass
        if exp_count == 0: st.write("30일 이내 만기 고객이 없습니다.")

    st.markdown("---")
    st.markdown("### 📰 실시간 보험 뉴스")
    news = get_insurance_news()
    for n in news: st.markdown(f"• [{n['title']}]({n['link']})")

elif menu == "📊 실적 관리":
    st.subheader("📊 실적 입력 및 자동 보장 연동")
    with st.expander("➕ 새 실적 입력하기 (저장 시 고객 보장리스트 자동 반영)", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: in_date = st.date_input("계약날짜", datetime.now())
        with c2: in_name = st.text_input("고객명")
        with c3: in_birth = st.text_input("생년월일(6자리)", placeholder="830608")
        with c4: in_prod = st.text_input("회사/상품명")
        with c5: in_price = st.text_input("보험료")
        
        if st.button("🚀 실적 저장 및 보장 연동"):
            if in_name and in_birth and in_prod and in_price:
                clean_price = re.sub(r'[^0-9]', '', in_price)
                # 1. 실적 시트 저장
                sheet_sales.append_row([str(in_date), in_name, in_birth, in_prod, clean_price])
                
                # 2. 고객 시트 자동 연동 (이름 + 주민번호 앞자리 매칭)
                match_idx = db_cust[(db_cust['이름'] == in_name) & (db_cust['주민번호'].str.startswith(in_birth))].index.tolist()
                if match_idx:
                    row_idx = match_idx[-1] + 2
                    old_memo = db_cust.iloc[match_idx[-1]]['병력(특이사항)']
                    new_entry = f"{in_prod}/{clean_price}/{in_date}"
                    
                    if "[보장분석]" in old_memo:
                        updated_memo = f"{old_memo} | {new_entry}"
                    else:
                        updated_memo = f"{old_memo.strip()} | [보장분석] {new_entry}" if old_memo.strip() else f"[보장분석] {new_entry}"
                    
                    sheet_cust.update_cell(row_idx, 7, updated_memo)
                    st.success(f"✅ {in_name}님 실적 저장 및 고객 보장리스트 업데이트 완료!")
                else:
                    st.info(f"✅ 실적은 저장되었으나, 고객 리스트에 일치하는 정보(이름/생년월일)가 없어 보장 연동은 생략되었습니다.")
                st.rerun()
            else: st.warning("모든 항목을 채워주세요.")

    st.markdown("---")
    if not db_sales.empty:
        db_sales['년월'] = db_sales['날짜_dt'].dt.strftime('%Y-%m')
        sel_m = st.selectbox("월별 실적 확인", sorted(db_sales['년월'].unique().tolist(), reverse=True))
        st.dataframe(db_sales[db_sales['년월'] == sel_m][["날짜", "고객명", "생년월일", "상품명", "보험료"]], use_container_width=True)

elif menu == "🔍 고객조회/수정":
    st.subheader("🔍 고객 상세 조회")
    s_name = st.text_input("고객 성함")
    if s_name:
        res = db_cust[db_cust['이름'].str.contains(s_name)]
        for _, row in res.iterrows():
            with st.expander(f"👤 {row['이름']} ({row['연락처']})", expanded=True):
                c1, c2 = st.columns(2)
                with c1: st.write(f"**주민:** {row['주민번호']}\n\n**주소:** {row['주소']}")
                with c2: 
                    if row['차량번호']: st.success(f"**차량:** {row['차량번호']} ({row['보험사']})\n\n**만기:** {row['자동차만기일']}")
                memo = row['병력(특이사항)']
                if "[보장분석]" in memo:
                    parts = memo.split("[보장분석]")
                    st.table(pd.DataFrame([{"보험사/상품": i.split('/')[0], "료": i.split('/')[1], "일": i.split('/')[2]} for i in parts[-1].split('|') if '/' in i]))
                    st.info(f"**특이사항:** {parts[0]}")
                else: st.info(f"**특이사항:** {memo}")

elif menu == "✍️ 고객정보 신규등록":
    st.subheader("✍️ 신규 고객 등록")
    q_in = st.text_input("이름, 주민번호(앞6자리-뒤7자리), 연락처, 주소")
    if st.button("즉시 등록") and q_in:
        d = [i.strip() for i in q_in.split(',')]
        sheet_cust.append_row([datetime.now().strftime("%Y-%m-%d"), d[0], d[1], d[2], d[3], "", "", d[0], "", "", "", "", "", "", ""])
        st.success("등록 완료!"); st.rerun()

elif menu == "📑 고객리스트":
    st.subheader("📑 전체 고객 리스트")
    p_size = 30
    t_pages = max(1, (len(db_cust) // p_size) + (1 if len(db_cust) % p_size > 0 else 0))
    if 'p_num' not in st.session_state: st.session_state.p_num = 1
    start_i = (st.session_state.p_num - 1) * p_size
    st.table(db_cust[['날짜', '이름', '주민번호', '연락처', '주소', '자동차만기일']].iloc[start_i : start_i + p_size])
    cols = st.columns(20)
    for i in range(1, t_pages + 1):
        if cols[i-1].button(str(i)): st.session_state.p_num = i; st.rerun()

elif menu == "🚘 자동차증권 업데이트":
    st.subheader("🚘 자동차 정보 업데이트")
    up_in = st.text_input("이름, 차량번호, 보험사, 만기일")
    if st.button("✅ 반영"):
        p = [x.strip() for x in up_in.split(',')]
        idx = db_cust.index[db_cust['이름'] == p[0]].tolist()
        if idx:
            sheet_cust.update_cell(idx[-1]+2, 13, p[1]); sheet_cust.update_cell(idx[-1]+2, 14, p[2]); sheet_cust.update_cell(idx[-1]+2, 15, p[3])
            st.success("반영 완료!"); st.rerun()

elif menu == "📄 보장분석리스트 입력":
    st.subheader("📄 수동 보장분석 입력")
    sel_name = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist())
    ana_in = st.text_area("보험사/상품명/료/일 | ...")
    if st.button("🚀 반영"):
        if sel_name != "선택" and ana_in:
            m_idx = db_cust.index[db_cust['이름'] == sel_name].tolist()[-1]
            old = db_cust.iloc[m_idx]['병력(특이사항)'].split('[보장분석]')[0].strip()
            sheet_cust.update_cell(m_idx + 2, 7, f"{old} | [보장분석] {ana_in}")
            st.success("반영 완료!"); st.rerun()

elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 전 보험사 청구 링크")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**[손보]**\n[메리츠](https://www.meritzfire.com/compensation/guide/claim-guide.do) [삼성](https://www.samsungfire.com/customer/claim/reward/reward_01.html) [현대](https://www.hi.co.kr/service/claim/guide/form.do) [KB](https://www.kbinsure.co.kr/CG302010001.ec) [DB](https://www.idbins.com/FWCRRE1001.do)")
    with c2:
        st.markdown("**[생보]**\n[삼성](https://www.samsunglife.com/customer/claim/reward/reward_01.html) [한화](https://www.hanwhalife.com/static/service/customer/claim/reward/reward_01.html) [교보](https://www.kyobo.com/webdoc/customer/claim/reward/reward_01.html) [라이나](https://www.lina.co.kr/customer/claim/reward/reward_01.html)")
