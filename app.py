elif menu == "🏥 보험청구 양식":
    st.subheader("🏥 보험금 청구 가이드 및 전 보험사 링크")
    
    # 1. 고객 전송용 안내 문구 섹션
    with st.expander("📱 고객 전송용 서류 안내 문구 (복사하기)", expanded=True):
        st.info("아래 텍스트를 드래그해서 복사한 뒤 고객님께 문자로 보내세요.")
        guide_text = """[보험금 청구 서류 안내]

안녕하세요, 고객님! 요청하신 입원 및 수술 관련 청구 서류 안내드립니다. 

✅ 공통 필수 서류
1. 진료비 계산 영수증 (카드 영수증 X)
2. 진료비 세부내역서 (비급여 내역 포함 필수)

✅ 입원 시 추가
3. 입퇴원 확인서 (입원 기간 명시)
4. 진단서 (병명 및 질병분류코드 기재)

✅ 수술 시 추가
5. 수술 확인서 (수술명 및 수술 일자 명시)

💡 FC 배현우 가이드
* 서류 발급 시 '질병코드'가 누락되지 않았는지 꼭 확인해 주세요!
* 사진 촬영 시 서류의 네 모서리가 다 나오도록 찍어주시면 접수가 빠릅니다."""
        st.code(guide_text, language=None)

    st.markdown("---")
    
    # 2. 전 보험사 청구 링크 섹션 (메가 전용 팝업 리스트 반영)
    st.subheader("🔗 보험사별 온라인 청구 바로가기")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**[손해보험사]**")
        st.markdown("- [삼성화재](https://www.samsungfire.com/customer/claim/reward/reward_01.html)")
        st.markdown("- [현대해상](https://www.hi.co.kr/service/claim/guide/form.do)")
        st.markdown("- [DB손보](https://www.idbins.com/FWCRRE1001.do)")
        st.markdown("- [KB손보](https://www.kbinsure.co.kr/CG302010001.ec)")
        st.markdown("- [메리츠화재](https://www.meritzfire.com/compensation/guide/claim-guide.do)")
        st.markdown("- [한화손보](https://www.hwgeneralins.com/compensation/guide/form-download.do)")
        st.markdown("- [흥국화재](https://www.heungkukfire.co.kr/main/compensation/guide/compensationGuide.do)")
        st.markdown("- [롯데손보](https://www.lotteins.co.kr/web/CST/CLM/GLD/cstClmGld01.jsp)")
        st.markdown("- [MG손보](https://www.mggeneralins.com/main/compensation/guide/compensationGuide.do)")

    with c2:
        st.markdown("**[생명보험사 1]**")
        st.markdown("- [삼성생명](https://www.samsunglife.com/customer/claim/reward/reward_01.html)")
        st.markdown("- [한화생명](https://www.hanwhalife.com/static/service/customer/claim/reward/reward_01.html)")
        st.markdown("- [교보생명](https://www.kyobo.com/webdoc/customer/claim/reward/reward_01.html)")
        st.markdown("- [신한라이프](https://www.shinhanlife.co.kr/hp/cd/cd010101.do)")
        st.markdown("- [흥국생명](https://www.heungkuklife.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("- [동양생명](https://www.myangel.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("- [라이나생명](https://www.lina.co.kr/customer/claim/reward/reward_01.html)")
        st.markdown("- [AIA생명](https://www.aia.co.kr/ko/customer-service/claim/guide.html)")

    with c3:
        st.markdown("**[생명보험사 2 / 공제]**")
        st.markdown("- [미래에셋생명](https://life.miraeasset.com/customer/claim/reward/reward_01.html)")
        st.markdown("- [DB생명](https://www.idblife.com/customer/claim/reward/reward_01.html)")
        st.markdown("- [DGB생명](https://www.dgblife.co.kr/customer/claim/reward/reward_01.do)")
        st.markdown("- [KDB생명](https://www.kdblife.co.kr/customer/claim/reward/reward_01.do)")
        st.markdown("- [우체국보험](https://www.epostbank.go.kr/claim/reward/reward_01.html)")
        st.markdown("- [새마을금고](https://insu.kfcc.co.kr/customer/claim/guide.do)")
        st.markdown("- [수협공제](https://insu.suhyup-bank.com/customer/claim/guide.do)")
        st.markdown("- [신협공제](https://insu.cu.co.kr/customer/claim/guide.do)")
