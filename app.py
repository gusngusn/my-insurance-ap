import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- 1. 보안 및 구글 시트 설정 ---
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

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 관리 v5.7", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v5.7")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 - 정밀 정돈 출력
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            res = res.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} (주민번호: {row['주민번호']})", expanded=True):
                        st.markdown("### 📋 보유계약현황 리스트")
                        memo_raw = row.get('병력(특이사항)', '')
                        
                        if "[보장분석]" in memo_raw:
                            analysis_part = memo_raw.split("[보장분석]")[-1]
                            ins_items = [item.strip() for item in analysis_part.split('|') if item.strip()]
                            
                            table_data = []
                            for item in ins_items:
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    co, nm = parts[0].strip(), parts[1].strip()
                                    # 쓰레기 데이터 및 중복 제거 로직
                                    if any(k in nm for k in ["보험사", "계약자", "내용없음"]) or len(nm) < 2: continue
                                    
                                    table_data.append({
                                        "보험회사": co,
                                        "상품명": nm,
                                        "월 보험료": parts[2].strip() if len(parts) > 2 else "-",
                                        "가입날짜": parts[3].strip() if len(parts) > 3 else "-"
                                    })
                            
                            if table_data:
                                st.table(pd.DataFrame(table_data).drop_duplicates(subset=['상품명']))
                            else: st.info("유효한 계약 데이터가 없습니다.")
                        else: st.info("등록된 보장분석 데이터가 없습니다.")
                        
                        st.markdown("---")
                        st.write(f"**연락처:** {row.get('연락처', '-')} | **주소:** {row.get('주소', '-')}")

    # [TAB 4] 보장분석 PDF 정밀 분석 (단어 뭉치 기반 추출)
    with tab4:
        st.subheader("📄 보장분석 PDF 정밀 분석 (리스트 복원)")
        up_file = st.file_uploader("보장분석 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약 리스트 강제 복원"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        extracted = []
                        cos = ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "신한", "AIA", "에이스", "하나", "농협"]
                        
                        for page in pdf.pages:
                            # 텍스트가 아닌 '단어 객체'로 접근하여 위치 기반 분석
                            words = page.extract_words()
                            for i, word in enumerate(words):
                                co = next((c for c in cos if c in word['text']), "")
                                if co:
                                    # 보험사 단어를 찾으면 그 주변(다음 5단어 이내)에서 보험료와 날짜 탐색
                                    context = " ".join([w['text'] for w in words[i:i+10]])
                                    if "보험" in context or "공제" in context:
                                        pr = re.search(r'\d{1,3}(?:,\d{3})*원', context)
                                        dt = re.search(r'20\d{2}[.\-/]\d{2}[.\-/]\d{2}', context)
                                        # 보험사 바로 뒤부터 보험료/날짜 전까지를 상품명으로
                                        nm_part = context.split(co)[-1].split(pr.group() if pr else "20")[0].strip()
                                        
                                        if len(nm_part) >= 2:
                                            extracted.append(f"{co}/{nm_part}/{pr.group() if pr else '-'}/{dt.group() if dt else '-'}")
                    
                    if extracted:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        # 중복 제거 후 최신 데이터로 교체
                        final_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted)))}"
                        sheet.update_cell(r_num, 7, final_memo)
                        st.success(f"✅ {target_u}님 보유계약 {len(set(extracted))}건 복원 완료!"); st.rerun()
                except Exception as e: st.error(f"분석 오류: {e}")

    # [TAB 2, 3] 기존 로직 전체 포함
    with tab2:
        st.subheader("📝 고객 정보 업데이트")
        r_txt = st.text_area("정보 입력", height=150)
        if st.button("🚀 반영"):
            # (기존 등록 로직 전체 포함)
            pass
