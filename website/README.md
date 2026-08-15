# SSMaker Website

SSMaker의 공식 랜딩·공지·문의 웹사이트 원본입니다. 이 디렉터리는
`Kimchanghee/NewshoppingShorts` 저장소와 Vercel 프로젝트가 직접 소유하며,
외부 사이트 빌더나 퍼블리싱 서비스 없이 로컬 및 CI에서 빌드됩니다.

## Local development

```bash
npm ci
npm run dev
```

## Verification

```bash
npm test
npm run build
```

Vercel은 저장소 루트의 `vercel.json`에 따라 `website/dist`를 정적 사이트로
배포하고, 기존 Python API 요청은 `api/index.py`로 전달합니다.
