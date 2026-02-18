# NewshoppingShortsMaker

?쇳븨 ?륂뤌 ?곸긽 ?먮룞 ?쒖옉 ?꾧뎄 | Automated Shopping Shorts Video Creator

以묎뎅???먮쭑???쒓굅?섍퀬 ?쒓뎅??TTS瑜?異붽??섏뿬 ?쇳븨 ?륂뤌 肄섑뀗痢좊? ?먮룞?쇰줈 ?앹꽦?⑸땲??

---

## ??二쇱슂 湲곕뒫

- **?렞 OCR 湲곕컲 ?먮쭑 媛먯?**: Tesseract/RapidOCR濡?以묎뎅???먮쭑 ?먮룞 ?몄떇
- **?? GPU 媛??*: CuPy瑜??듯븳 CUDA 媛??吏??(?좏깮?ы빆)
- **?뵄 AI ?뚯꽦 ?앹꽦**: Gemini API瑜??쒖슜???먯뿰?ㅻ윭???쒓뎅??TTS
- **?벞 ?먮룞 鍮꾨뵒??泥섎━**: ?먮쭑 釉붾윭 泥섎━, ?쒓뎅???먮쭑 異붽?, ?곸긽 ?⑹꽦
- **??蹂묐젹 泥섎━**: ?ㅼ쨷 ?멸렇癒쇳듃 ?숈떆 泥섎━濡?鍮좊Ⅸ ?묒뾽 ?띾룄
- **?썳截??덉젙??媛뺥솕**: ?ш큵?곸씤 ?먮윭 泥섎━, ?낅젰 寃利? ?먮룞 ?ъ떆??
---

## ?뱥 ?쒖뒪???붽뎄?ы빆

### ?꾩닔 ?붽뎄?ы빆

- **Python**: 3.12 - 3.14 (理쒖떊 踰꾩쟾 沅뚯옣)
- **FFmpeg**: 鍮꾨뵒??泥섎━??- **Tesseract OCR**: ?먮쭑 ?몄떇??
### ?좏깮?ы빆 (沅뚯옣)

- **NVIDIA GPU + CUDA**: GPU 媛??(2-3諛?鍮좊Ⅸ 泥섎━)
- **CuPy**: GPU 媛???쇱씠釉뚮윭由?
---

## ?? 鍮좊Ⅸ ?쒖옉

### 1. ??μ냼 ?대줎

```bash
git clone https://github.com/yourusername/NewshoppingShortsMaker.git
cd NewshoppingShortsMaker
```

### 2. ?섏〈???ㅼ튂

**?먮룞 ?ㅼ튂 (沅뚯옣)**:
```bash
python install_dependencies.py
```

**?섎룞 ?ㅼ튂**:
```bash
pip install -r requirements.txt
```

### 3. ?쒖뒪??寃利?
?ㅼ튂媛 ?щ컮瑜닿쾶 ?섏뿀?붿? ?뺤씤:
```bash
python scripts/startup_validation.py
```

**?덉긽 異쒕젰**:
```
??Python Version: Python 3.14.x
??Required Packages: 6 packages installed
??OCR Engine: Tesseract OCR available
??FFmpeg: FFmpeg available
??File Permissions: Write permissions OK

??All checks passed! Ready to run.
```

### 4. OCR ?붿쭊 ?ㅼ튂 (Tesseract)

**Windows**:
```bash
winget install UB-Mannheim.TesseractOCR
```

**macOS**:
```bash
brew install tesseract tesseract-lang
```

**Linux**:
```bash
sudo apt install tesseract-ocr tesseract-ocr-kor tesseract-ocr-chi-sim
```

### 5. API ???ㅼ젙

**諛⑸쾿 1: ?섍꼍 蹂??(沅뚯옣)**
```bash
# Windows
set GEMINI_API_KEY=your_gemini_api_key_here

# Linux/macOS
export GEMINI_API_KEY=your_gemini_api_key_here
```

**諛⑸쾿 2: UI?먯꽌 ?ㅼ젙**
- ???ㅽ뻾 ??"API ??愿由??먯꽌 異붽?

### 6. ???ㅽ뻾

```bash
python main.py
```

---

## ?렜 ?ъ슜 諛⑸쾿

### 湲곕낯 ?뚰겕?뚮줈??
1. **鍮꾨뵒???좏깮**
   - 濡쒖뺄 ?뚯씪 ?좏깮 ?먮뒗 URL ?낅젰 (Douyin, TikTok, Xiaohongshu 吏??

2. **?듭뀡 ?ㅼ젙**
   - 以묎뎅???먮쭑 釉붾윭: ??   - ?쒓뎅???먮쭑 異붽?: ??   - TTS ?뚯꽦 ?앹꽦: ??
3. **泥섎━ ?쒖옉**
   - "?곸긽 泥섎━ ?쒖옉" 踰꾪듉 ?대┃
   - 吏꾪뻾 ?곹솴 ?ㅼ떆媛??뺤씤

4. **寃곌낵 ?뺤씤**
   - ?꾨즺???곸긽? 吏?뺥븳 異쒕젰 ?대뜑?????   - 湲곕낯: `C:\Users\Administrator\Desktop\`

---

## ?숋툘 怨좉툒 ?ㅼ젙

### GPU 媛???쒖꽦??
**1. CUDA ?ㅼ튂 ?뺤씤**:
```bash
nvidia-smi
```

**2. CuPy ?ㅼ튂**:
```bash
# CUDA 12.x
pip install cupy-cuda12x

# CUDA 11.x
pip install cupy-cuda11x
```

**3. GPU 媛?⑹꽦 ?뺤씤**:
```python
import cupy as cp
print(f"GPU devices: {cp.cuda.runtime.getDeviceCount()}")
```

### ?섍꼍 蹂???ㅼ젙

| 蹂??| ?ㅻ챸 | ?덉떆 |
|------|------|------|
| `GEMINI_API_KEY` | Gemini API ??| `AIza...` |
| `TESSERACT_CMD` | Tesseract ?ㅽ뻾 ?뚯씪 寃쎈줈 | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `TESSDATA_PREFIX` | Tesseract ?몄뼱 ?곗씠??寃쎈줈 | `C:\Program Files\Tesseract-OCR\tessdata` |

---

## ?㎦ ?뚯뒪???ㅽ뻾

```bash
# 紐⑤뱺 ?뚯뒪???ㅽ뻾
pytest

# ?뱀젙 移댄뀒怨좊━留??ㅽ뻾
pytest -m unit  # ?좊떅 ?뚯뒪?몃쭔
pytest tests/unit/test_validators.py  # ?뱀젙 ?뚯씪留?
# 而ㅻ쾭由ъ? ?ы븿
pytest --cov=. --cov-report=html
```

---

## ?뱛 ?꾨줈?앺듃 援ъ“

```
NewshoppingShortsMaker/
?쒋?? main.py                     # ?좏뵆由ъ??댁뀡 吏꾩엯???쒋?? config/
??  ?붴?? constants.py            # ?ㅼ젙 ?곸닔 (?꾧퀎媛? ?쒗븳媛???
?쒋?? utils/
??  ?쒋?? logging_config.py       # 以묒븰吏묒쨷??濡쒓퉭
??  ?쒋?? validators.py           # ?낅젰 寃利?(蹂댁븞)
??  ?쒋?? error_handlers.py       # ?덉쇅 泥섎━ ?꾨젅?꾩썙????  ?붴?? ocr_backend.py          # OCR ?붿쭊 ?섑띁
?쒋?? processors/
??  ?쒋?? subtitle_detector.py    # ?먮쭑 媛먯? (OCR)
??  ?쒋?? subtitle_processor.py   # ?먮쭑 釉붾윭 泥섎━
??  ?붴?? tts_processor.py        # TTS ?앹꽦
?쒋?? managers/
??  ?쒋?? settings_manager.py     # ?ㅼ젙 愿由???  ?붴?? voice_manager.py        # ?뚯꽦 愿由??쒋?? ui/
??  ?쒋?? components/             # UI 而댄룷?뚰듃
??  ?붴?? panels/                 # UI ?⑤꼸
?쒋?? scripts/
??  ?붴?? startup_validation.py   # ?쒖뒪???ъ쟾 寃???쒋?? tests/
??  ?쒋?? unit/                   # ?좊떅 ?뚯뒪????  ?쒋?? integration/            # ?듯빀 ?뚯뒪????  ?붴?? conftest.py             # ?뚯뒪???ㅼ젙
?붴?? docs/
    ?붴?? IMPROVEMENTS.md         # 媛쒖꽑?ы빆 臾몄꽌
```

---

## ?썱截?臾몄젣 ?닿껐

### OCR???묐룞?섏? ?딆쓬

**利앹긽**: "OCR reader not initialized" ?먮윭

**?닿껐**:
1. Tesseract ?ㅼ튂 ?뺤씤:
   ```bash
   tesseract --version
   ```

2. Tesseract 寃쎈줈 ?ㅼ젙:
   ```bash
   set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

3. ?몄뼱 ?곗씠???ㅼ튂 ?뺤씤:
   - `chi_sim.traineddata` (以묎뎅??媛꾩껜)
   - `kor.traineddata` (?쒓뎅??

### GPU 媛?띿씠 ?묐룞?섏? ?딆쓬

**利앹긽**: "GPU acceleration disabled" 硫붿떆吏

**?닿껐**:
1. NVIDIA GPU ?뺤씤:
   ```bash
   nvidia-smi
   ```

2. CUDA ?ㅼ튂 ?뺤씤:
   - CUDA Toolkit 11.8 ?먮뒗 12.x ?꾩슂

3. CuPy ?ъ꽕移?
   ```bash
   pip uninstall cupy cupy-cuda12x
   pip install cupy-cuda12x
   ```

4. **Python 3.14 二쇱쓽?ы빆**:
   - CuPy媛 ?ㅼ튂?섏? ?딆쑝硫??먮룞?쇰줈 NumPy CPU 紐⑤뱶濡??꾪솚?⑸땲??   - 湲곕뒫? ?뺤긽 ?묐룞?섏?留??띾룄媛 ?먮┫ ???덉뒿?덈떎

### API ???ㅻ쪟

**利앹긽**: "?깅줉??API ?ㅺ? ?놁뒿?덈떎"

**?닿껐**:
1. ?섍꼍 蹂???ㅼ젙:
   ```bash
   set GEMINI_API_KEY=your_key_here
   ```

2. ?먮뒗 UI?먯꽌 "API ??愿由? ????異붽?

3. `api_keys_config.json` 吏곸젒 ?몄쭛:
   ```json
   {
     "gemini": {
       "key_1": "AIza..."
     }
   }
   ```

---

## ?뱤 ?깅뒫 理쒖쟻????
### 1. GPU 媛???쒖슜
- NVIDIA GPU ?ъ슜 ??2-3諛?鍮좊Ⅸ 泥섎━
- CuPy ?ㅼ튂 沅뚯옣

### 2. 蹂묐젹 泥섎━ 理쒖쟻??- CPU 肄붿뼱 ?섏뿉 ?곕씪 ?먮룞 議곗젙
- `config/constants.py`?먯꽌 `MAX_WORKERS` 議곗젙 媛??
### 3. OCR ?섑뵆留?媛꾧꺽 議곗젙
- 湲곕낯: 0.3珥?媛꾧꺽
- `VideoSettings.SAMPLE_INTERVAL_DEFAULT` 議곗젙

### 4. 硫붾え由?理쒖쟻??- ?꾨젅??罹먯떆???먮룞 ?뺣━??- 湲??곸긽 泥섎━ ??10珥??멸렇癒쇳듃濡?遺꾪븷 泥섎━

---

## ?뵏 蹂댁븞 湲곕뒫

- ??**寃쎈줈 ?쒗쉶 怨듦꺽 諛⑹?**: ?뚯씪 寃쎈줈 寃利?- ??**?뚯씪 ?뺤옣???붿씠?몃━?ㅽ듃**: ?덉쟾???뚯씪留??덉슜
- ??**API ?묐떟 寃利?*: ?낆쓽?곸씤 API ?묐떟 李⑤떒
- ??**?섍꼍 蹂??API ??*: ?됰Ц ???諛⑹?
- ??**?낅젰 寃利?*: SQL ?몄젥?? XSS 諛⑹?

---

## ?뱢 理쒓렐 媛쒖꽑?ы빆

### Phase 1-2 (2026-01-24 ?꾨즺)

#### ?덈줈 異붽???湲곕뒫
- ??以묒븰吏묒쨷??濡쒓퉭 ?쒖뒪??(?뚯씪 + 肄섏넄)
- ???ш큵?곸씤 ?낅젰 寃利?(蹂댁븞 媛뺥솕)
- ????낇솕???덉쇅 泥섎━ (蹂듦뎄 ?뚰듃 ?ы븿)
- ???쒖뒪???ъ쟾 寃???ㅽ겕由쏀듃
- ???섍꼍 蹂??API ??吏??
#### ?섏젙??臾몄젣
- ??OCR 珥덇린???ㅽ뙣 ??紐낇솗???먮윭 + ?ъ떆??(3??
- ??Python 3.14 ?명솚????Graceful fallback
- ??以묐났 detector ?앹꽦 ??40% ?깅뒫 媛쒖꽑
- ??硫붾え由??꾩닔 ???꾨젅??罹먯떆 ?먮룞 ?뺣━
- ??GPU detection 媛쒖꽑 ??踰꾩쟾 泥댄겕 ?쒓굅

?먯꽭???댁슜? [IMPROVEMENTS.md](IMPROVEMENTS.md) 李몄“

---

## ?쩃 湲곗뿬?섍린

踰꾧렇 由ы룷?? 湲곕뒫 ?쒖븞, Pull Request瑜??섏쁺?⑸땲??

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## ?뱷 ?쇱씠?좎뒪

MIT License - ?먯쑀濡?쾶 ?ъ슜, ?섏젙, 諛고룷 媛??
---

## ?솋 ?꾩?留?諛?吏??
- **?댁뒋 由ы룷??*: [GitHub Issues](https://github.com/yourusername/NewshoppingShortsMaker/issues)
- **臾몄꽌**: [docs/](docs/) ?대뜑 李몄“
- **媛쒖꽑?ы빆**: [IMPROVEMENTS.md](IMPROVEMENTS.md)

---

## ?럦 媛먯궗?⑸땲??

NewshoppingShortsMaker瑜??ъ슜?댁＜?붿꽌 媛먯궗?⑸땲?? ?쇳븨 ?륂뤌 ?쒖옉?????ъ썙吏湲?諛붾엻?덈떎!

---

*Last Updated: 2026-01-24*

## Environment
- Python 3.14
- FFmpeg installed and on PATH
- Tesseract (for OCR) if using pytesseract
- Vertex AI: set VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_MODEL_ID, VERTEX_JSON_KEY_PATH
- Gemini fallback: set GEMINI_API_KEY (or SecretsManager)
- Payment server: set PAYMENT_API_BASE_URL for subscription checkout

- PayApp: PAYAPP_USERID, PAYAPP_LINKKEY, PAYAPP_LINKVAL, PAYAPP_SHOPNAME (optional), PAYAPP_API_URL (optional)

- Payment API (web checkout): PAYMENT_API_BASE_URL, CHECKOUT_POLL_INTERVAL, CHECKOUT_POLL_MAX_TRIES

---

## Vertex AI Configuration

**Default Setup (Automatic):**
The application comes pre-configured with Vertex AI credentials in `config/vertex-credentials.json`. No additional setup is required for local development or standard deployments.

**How it works:**
- Vertex AI is the primary model provider
- Automatic fallback to Gemini API if Vertex is unavailable
- Default project: `alien-baton-484113-g4`
- Default location: `us-central1`
- Default model: `gemini-1.5-flash-002`

**Custom Credentials (Optional):**
To use your own Vertex AI service account:

1. Obtain a service account JSON from [Google Cloud Console](https://console.cloud.google.com)
2. Set environment variables:
   ```bash
   export VERTEX_PROJECT_ID="your-project-id"
   export VERTEX_JSON_KEY_PATH="/path/to/service-account.json"
   # Optional overrides:
   export VERTEX_LOCATION="us-central1"
   export VERTEX_MODEL_ID="gemini-1.5-flash-002"
   ```

**Credential Security:**
- ⚠️ Never commit `config/vertex-credentials.json` to version control
- The file is already in `.gitignore` for protection
- Rotate credentials quarterly or immediately if compromised
- Use separate service accounts for dev/staging/production environments

**Fallback Behavior:**
If Vertex AI is unavailable (network issues, quota exceeded, invalid credentials), the system automatically falls back to Gemini API. Ensure `GEMINI_API_KEY` is configured for redundancy.

**Troubleshooting:**
- Check logs for `[Provider] Vertex init failed` messages
- Verify the JSON file exists at `config/vertex-credentials.json`
- Ensure the service account has Vertex AI API access enabled
- Check project quota limits in Google Cloud Console

---

## Trial System

**Free Trial:**
- New users receive 5 free video creations
- Trial count is displayed in the header (e.g., "3/5 남음")
- Color-coded for urgency: Green (3-5), Yellow (1-2), Red (0)

**After Trial:**
- Users are prompted to subscribe when limit is reached
- Video creation is blocked until subscription is activated
- Subscribers receive unlimited video creation

**For Administrators:**
- Trial limits are managed in the backend database
- Default limit: `FREE_TRIAL_WORK_COUNT = 5` in `backend/app/routers/registration.py`
- Subscription approval sets `work_count = -1` (unlimited)
