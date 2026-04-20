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

st.set_page_config(page_title="현우 통합 관리 v5.4", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v5.4")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if not all_values:
        sheet.insert_row(EXPECTED_HEADERS, 1)
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    else:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
        db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 - 끊긴 데이터 자동 필터링 로직
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            res = res.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} (주민번호: {row['주민번호']})", expanded=True):
                        st.markdown("### 📋 현재 최신 유지계약 리스트")
                        memo_raw = row.get('병력(특이사항)', '')
                        
                        if "[보장분석]" in memo_raw:
                            analysis_part = memo_raw.split("[보장분석]")[-1]
                            ins_items = [item.strip() for item in analysis_part.split('|') if item.strip()]
                            
                            table_data = []
                            for item in ins_items:
                                # [핵심] 미납, 해지 및 '보험회사' 등의 헤더 텍스트 차단
                                if any(k in item for k in ["미납", "해지", "실효", "보험회사", "상품명", "월 보험료"]): continue
                                
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    # 상품명 정제: 숫자 제거 및 짧게 끊긴 상품명(5자 미만) 차단
                                    name = re.sub(r'^\d+\s*', '', parts[1]).strip()
                                    name = re.sub(r'\(.*?\)|\[.*?\]', '', name).replace("무배당", "").strip()
                                    
                                    price = parts[2].strip() if len(parts) > 2 else "-"
                                    date = parts[3].strip() if len(parts) > 3 else "-"
                                    
                                    # [품질 관리] 정보가 온전한 것만 표에 추가
                                    if len(name) >= 5 and (price != "-" or date != "-"):
                                        table_data.append({
                                            "보험회사": parts[0].strip(),
                                            "상품명": name,
                                            "월 보험료": price if "원" in price else "-",
                                            "가입날짜": date if len(date) >= 8 else "-"
                                        })
                            
                            if table_data:
                                final_df = pd.DataFrame(table_data).drop_duplicates(subset=['상품명'], keep='first')
                                st.table(final_df)
                            else: st.info("유효한 최신 계약 정보가 없습니다.")
                        else: st.info("등록된 보장분석 데이터가 없습니다.")
                        
                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**연락처:** {row.get('연락처', '-')}")
                            st.write(f"**주소:** {row.get('주소', '-')}")
                        with c2:
                            st.write(f"**차량:** {row.get('차량번호', '미등록')} / **만기:** {row.get('자동차만기일', '-')}")
                            st.info(f"**💡 기타 특이사항:** {memo_raw.split('[보장분석]')[0].strip()}")
            else: st.info("검색 결과가 없습니다.")

    # [TAB 2] AI 등록 및 병합 (전체 코드 유지)
    with tab2:
        st.subheader("📝 텍스트로 정보 등록 및 업데이트")
        raw_text = st.text_area("이름, 연락처, 주민번호, 주소 등 입력", height=200)
        if st.button("🚀 데이터 반영"):
            name, phone, ssn, addr, memo = "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                else: memo += f"{line} "
            if name and phone:
                m_idx = db.index[(db['이름'] == name) & (db['연락처'] == phone)].tolist()
                if m_idx:
                    r_num = m_idx[-1] + 2
                    target = db.iloc[m_idx[-1]]
                    if not target['주민번호'] and ssn: sheet.update_cell(r_num, 3, ssn)
                    if not target['주소'] and addr: sheet.update_cell(r_num, 5, addr)
                    if memo:
                        base = target['병력(특이사항)'].split('[보장분석]')[0]
                        final = (base + " " + memo).strip()
                        if "[보장분석]" in target['병력(특이사항)']:
                            final += " | [보장분석]" + target['병력(특이사항)'].split('[보장분석]')[1]
                        sheet.update_cell(r_num, 7, final)
                    st.success(f"✅ {name}님 정보 업데이트 완료!"); st.rerun()
                else:
                    sheet.append_row([datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, "", memo.strip(), name, 0,0,0,0,"","",""])
                    st.success("신규 등록 완료!"); st.rerun()

    # [TAB 3] 자동차 보험 최신본 자동 교체 (전체 코드 유지)
    with tab3:
        st.subheader("🚘 자동차 보험 최신본 덮어쓰기")
        u_in = st.text_input("이름, 차량번호, 보험사, 만기일")
        if st.button("✅ 최신 정보로 교체"):
            p = [i.strip() for i in u_in.split(',')]
            if len(p) >= 4:
                idx = db.index[db['이름'] == p[0]].tolist()
                if idx:
                    r_n = idx[-1] + 2
                    sheet.update_cell(r_n, 13, p[1]); sheet.update_cell(r_n, 14, p[2]); sheet.update_cell(r_n, 15, p[3])
                    st.success("최신 자동차 보험 정보로 업데이트되었습니다."); st.rerun()

    # [TAB 4] 보장분석 PDF 최신본 자동 교체 (전체 코드 유지)
    with tab4:
        st.subheader("📄 보장분석 PDF 최신본 자동 교체")
        up_file = st.file_uploader("새로운 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        if up_file and target_u != "선택하세요":
            if st.button("🚀 기존 데이터 삭제 후 최신본 반영"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        text = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                    cos = ["삼성화재", "삼성생명", "DB손해", "현대해상", "KB손해", "메리츠", "한화손해", "흥국화재", "신한라이프", "교보생명", "라이나", "동양생명", "에이스손해"]
                    extracted = []
                    for line in text.split('\n'):
                        if any(k in line for k in ["미납", "해지", "실효"]): continue
                        co = next((c for c in cos if c in line), "")
                        if co and ("보험" in line or "공제" in line):
                            pr = re.search(r'\d{1,3}(?:,\d{3})*원', line)
                            dt = re.search(r'\d{4}[.\-/]\d{2}[.\-/]\d{2}', line)
                            nm = line.split(co)[-1].split('원')[0].split('20')[0].strip()
                            if len(nm) >= 5: # 끊긴 상품명 방지
                                extracted.append(f"{co}/{nm}/{pr.group() if pr else '-'}/{dt.group() if dt else '-'}")
                    if extracted:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted)))}"
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 기존 데이터 삭제 및 최신본 업데이트 완료!"); st.rerun()
                except Exception as e: st.error(f"오류: {e}")
