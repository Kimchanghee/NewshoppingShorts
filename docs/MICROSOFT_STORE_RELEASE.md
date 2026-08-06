# Microsoft Store 무료 서명 배포

SSMaker는 기존 GitHub/Inno Setup 배포와 Microsoft Store/MSIX 배포를 함께 지원합니다.
Store용 MSIX는 Partner Center 인증을 통과하면 Microsoft가 무료로 다시 서명합니다.

## 최초 1회 준비

1. [Microsoft Store 개발자 계정](https://storedeveloper.microsoft.com/)을 만듭니다.
2. Partner Center에서 앱 이름 `SSMaker`를 예약합니다.
3. 앱의 **Product identity** 화면에서 다음 값을 복사합니다.
   - `Package/Identity/Name`
   - `Package/Identity/Publisher`
   - `Package/Properties/PublisherDisplayName`

이 값은 임의로 만들면 Store 제출이 거부됩니다. Partner Center에 표시된 문자열을 그대로 사용해야 합니다.

## Store 패키지 만들기

1. GitHub 저장소의 **Actions** 탭을 엽니다.
2. **Build Microsoft Store MSIX**를 선택하고 **Run workflow**를 누릅니다.
3. Product identity의 세 값을 입력합니다.
4. 성공한 작업의 `SSMaker-Microsoft-Store-MSIX` 아티팩트를 내려받습니다.
5. Partner Center의 새 제출에 `.msix`를 업로드합니다.

워크플로는 인증서/PFX 없이 PyInstaller 페이로드와 MSIX를 생성합니다. 업로드된 패키지는 Store 인증 후 Microsoft 인증서로 서명됩니다.

## 호환성 정책

- GitHub에서 배포하는 기존 EXE는 기존 설치 및 자동 업데이트 방식을 유지합니다.
- Microsoft Store 버전에서는 EXE 설치 프로그램 기반 자체 업데이트를 실행하지 않습니다. 업데이트는 Store가 담당합니다.
- Store 버전의 자동 실행은 MSIX 시작 작업으로 등록되며 Windows **설정 > 앱 > 시작 프로그램**에서 관리합니다.
- 기존 EXE 설치에서 남은 HKCU 시작프로그램 항목은 Store 버전이 처음 실행될 때 제거해 중복 실행을 방지합니다.
- Store 패키지 버전은 `주.부.패치.0` 형식을 사용합니다. 마지막 숫자는 Microsoft Store용으로 예약됩니다.

## 로컬 구조 검증

이미 `dist/ssmaker`가 생성돼 있다면 인증서나 Windows SDK 없이 매니페스트, 로고와 파일 매핑을 검사할 수 있습니다.

```powershell
./scripts/build_msix.ps1 -AllowDevelopmentIdentity -ValidateOnly
```

개발 ID로 만든 패키지는 Store 제출용이 아닙니다. 실제 제출에는 반드시 Partner Center Product identity를 사용합니다.
