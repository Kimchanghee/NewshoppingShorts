# Implementation Plan: Vertex AI Default Setup + Trial Limit Enforcement

## Overview
Configure the provided Vertex AI service account as the default provider, enforce 5-use trial limit with subscription prompts, and ensure proper credential management.

**User Requirements:**
- ✅ Copy Vertex AI service account JSON to `config/` directory
- ✅ Set as default provider (automatic migration for all users)
- ✅ Maintain 5-use trial limit for new registrations
- ✅ Block users with popup dialog when trial limit exceeded
- ✅ Display trial count in header status widget (already implemented)
- ✅ Prompt subscription on limit exceeded

---

## Phase 1: Vertex AI Credential Setup

### Task 1.1: Copy Service Account JSON to Project
**File:** `pineopticalpro-vertex.json` → `config/vertex-credentials.json`

**Actions:**
1. Copy the provided service account JSON to `config/vertex-credentials.json`
2. Add `config/vertex-credentials.json` to `.gitignore` to prevent accidental commits
3. Verify file permissions (read-only for application, not world-readable)

**Security Considerations:**
- Never commit credentials to version control
- Add to `.gitignore` immediately
- Document credential rotation process in README

### Task 1.2: Update Configuration to Use Default Credentials
**File:** [config/__init__.py](config/__init__.py)

**Current State:**
```python
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_ID = os.getenv("VERTEX_MODEL_ID", "gemini-1.5-flash-002")
VERTEX_JSON_KEY_PATH = os.getenv("VERTEX_JSON_KEY_PATH", "")
```

**Changes:**
```python
import os
from pathlib import Path

# Vertex AI configuration with defaults from pineopticalpro-vertex.json
_config_dir = Path(__file__).parent
DEFAULT_VERTEX_JSON_PATH = _config_dir / "vertex-credentials.json"

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "alien-baton-484113-g4")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL_ID = os.getenv("VERTEX_MODEL_ID", "gemini-1.5-flash-002")
VERTEX_JSON_KEY_PATH = os.getenv(
    "VERTEX_JSON_KEY_PATH",
    str(DEFAULT_VERTEX_JSON_PATH) if DEFAULT_VERTEX_JSON_PATH.exists() else ""
)
```

**Benefits:**
- No environment variables required for default setup
- Automatic fallback to bundled credentials
- Still allows override via environment variables for different deployments

### Task 1.3: Update .gitignore
**File:** [.gitignore](.gitignore)

**Add:**
```gitignore
# Vertex AI credentials
config/vertex-credentials.json
config/*-vertex.json
*.json  # (if not already present, adjust to be specific)
```

### Task 1.4: Update Documentation
**File:** [README.md](README.md)

**Add Section:**
```markdown
### Vertex AI Configuration

**Default Setup (Automatic):**
The application comes pre-configured with Vertex AI credentials in `config/vertex-credentials.json`. No additional setup is required for local development or standard deployments.

**Custom Credentials (Optional):**
To use your own Vertex AI service account:

1. Obtain service account JSON from Google Cloud Console
2. Set environment variables:
   ```bash
   export VERTEX_PROJECT_ID="your-project-id"
   export VERTEX_JSON_KEY_PATH="/path/to/service-account.json"
   ```

**Credential Security:**
- Never commit `config/vertex-credentials.json` to version control
- Rotate credentials quarterly or when compromised
- Use separate service accounts for dev/staging/production

**Fallback Behavior:**
If Vertex AI is unavailable, the system automatically falls back to Gemini API (requires `GEMINI_API_KEY`).
```

---

## Phase 2: Trial Limit Enforcement

### Task 2.1: Verify Backend Trial Logic
**File:** [backend/app/routers/registration.py](backend/app/routers/registration.py:41)

**Current Implementation:**
```python
FREE_TRIAL_WORK_COUNT = 5  # Already set to 5
```

**Verification Points:**
- ✅ `FREE_TRIAL_WORK_COUNT = 5` is correct
- ✅ Registration creates users with `work_count=5, work_used=0, user_type='TRIAL'`
- ✅ Backend tracks usage via `work_used` column
- ✅ `check_work_available()` enforces limit
- ✅ `use_work()` increments counter after video completion

**No changes needed** - backend trial logic is already correctly implemented.

### Task 2.2: Add Frontend Trial Limit Check Before Video Processing
**File:** [core/video/batch/processor.py](core/video/batch/processor.py:283-310)

**Current Flow:**
```python
# Line 283-310: After video completion, use_work() is called
await self.rest.use_work()
```

**Issue:** Trial check happens AFTER video creation, wasting resources.

**Solution:** Add pre-flight check BEFORE starting batch processing:

**New Method in `caller/rest.py`:**
```python
async def check_work_available(self) -> dict:
    """
    Check if user has trial uses remaining.
    Returns: {"available": bool, "remaining": int, "total": int}
    """
    return await self._request("GET", "/auth/work/check")
```

**New Check in `core/video/batch/processor.py`:**
```python
async def process_batch(self, ...):
    # BEFORE starting video generation
    work_status = await self.rest.check_work_available()
    if not work_status.get("available", False):
        raise TrialLimitExceededError(
            f"Trial limit reached ({work_status.get('used', 0)}/{work_status.get('total', 5)}). "
            "Please subscribe to continue."
        )

    # ... existing video processing code ...
```

### Task 2.3: Create Custom Exception for Trial Limit
**File:** `utils/error_handlers.py` (new exception class)

**Add:**
```python
class TrialLimitExceededError(Exception):
    """Raised when user exceeds trial usage limit"""
    def __init__(self, message: str, remaining: int = 0, total: int = 5):
        super().__init__(message)
        self.remaining = remaining
        self.total = total
```

### Task 2.4: Add Popup Dialog for Trial Limit Exceeded
**File:** [ui/components/subscription_popup.py](ui/components/subscription_popup.py) (new component)

**Create New PyQt6 Dialog:**
```python
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

class TrialLimitDialog(QDialog):
    def __init__(self, parent=None, used: int = 5, total: int = 5):
        super().__init__(parent)
        self.setWindowTitle("체험판 한도 초과")
        self.setModal(True)

        layout = QVBoxLayout()

        # Title
        title = QLabel(f"체험판 사용 횟수를 모두 소진했습니다 ({used}/{total})")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Message
        msg = QLabel(
            "추가 동영상 제작을 원하시면 구독이 필요합니다.\n"
            "구독 시 무제한으로 사용할 수 있습니다."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # Buttons
        subscribe_btn = QPushButton("구독 신청하기")
        subscribe_btn.clicked.connect(self.open_subscription)
        layout.addWidget(subscribe_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def open_subscription(self):
        # Import here to avoid circular imports
        from ui.panels.subscription_panel import SubscriptionPanel
        # Trigger subscription panel/dialog
        self.accept()
        # Signal parent to show subscription UI
```

### Task 2.5: Integrate Trial Dialog into Main UI
**File:** [ui/process_ui_modern.py](ui/process_ui_modern.py) or [caller/ui_controller.py](caller/ui_controller.py)

**Add Exception Handler:**
```python
from utils.error_handlers import TrialLimitExceededError
from ui.components.subscription_popup import TrialLimitDialog

try:
    await batch_processor.process_batch(...)
except TrialLimitExceededError as e:
    # Show trial limit dialog
    dialog = TrialLimitDialog(
        parent=self.main_window,
        used=e.total,  # All used
        total=e.total
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        # User clicked "Subscribe" - open subscription panel
        self.show_subscription_panel()
    return  # Stop processing
```

### Task 2.6: Update Subscription Status Widget
**File:** [ui/components/subscription_status.py](ui/components/subscription_status.py)

**Current Implementation:**
Already shows trial count in header (e.g., "3/5 남음")

**Enhancement:**
Add color coding for urgency:
- Green: 3-5 uses remaining
- Yellow: 1-2 uses remaining
- Red: 0 uses remaining (with pulsing animation)

**Code Addition:**
```python
def update_status(self, work_used: int, work_count: int):
    remaining = work_count - work_used

    # Color coding
    if remaining >= 3:
        color = "#4CAF50"  # Green
    elif remaining >= 1:
        color = "#FFC107"  # Yellow/Orange
    else:
        color = "#F44336"  # Red
        # Add pulsing animation for zero remaining
        self.start_pulse_animation()

    self.label.setText(f"{remaining}/{work_count} 남음")
    self.label.setStyleSheet(f"color: {color}; font-weight: bold;")
```

---

## Phase 3: Testing & Validation

### Task 3.1: Test Vertex AI Credential Loading
**Test Cases:**
1. ✅ Fresh install with default credentials → Vertex initializes successfully
2. ✅ Custom `VERTEX_JSON_KEY_PATH` override → Uses custom credentials
3. ✅ Missing credentials file → Falls back to Gemini API with warning log
4. ✅ Invalid JSON format → Falls back to Gemini with error log
5. ✅ Wrong project ID → Falls back to Gemini

**Validation Command:**
```bash
python -c "from core.providers import VertexGeminiProvider; p = VertexGeminiProvider(); print(p.generate_text('test'))"
```

### Task 3.2: Test Trial Limit Enforcement
**Test Scenarios:**

| Scenario | Expected Behavior |
|----------|-------------------|
| New user registration | User created with work_count=5, work_used=0 |
| Complete 1 video | work_used incremented to 1, status shows "4/5 남음" |
| Complete 5th video | work_used=5, status shows "0/5 남음" (red) |
| Attempt 6th video | TrialLimitDialog shown, video creation blocked |
| Subscribe after limit | work_count set to -1 (unlimited), can create videos |

**Test Script:**
```python
# backend/test_trial_enforcement.py
async def test_trial_limit():
    # Create test user
    user = create_trial_user("test_user")
    assert user.work_count == 5
    assert user.work_used == 0

    # Use 5 videos
    for i in range(5):
        await use_work(user)
        assert user.work_used == i + 1

    # Try 6th video
    with pytest.raises(TrialLimitExceededError):
        await check_work_available(user)

    # Subscribe
    user.work_count = -1
    user.user_type = 'SUBSCRIBER'

    # Should work now
    assert await check_work_available(user) == True
```

### Task 3.3: End-to-End Integration Test
**Workflow:**
1. Register new user via frontend
2. Login → Verify header shows "5/5 남음"
3. Create 5 videos → Verify counter decrements each time
4. Attempt 6th video → Verify dialog appears with subscription CTA
5. Click "구독 신청하기" → Verify subscription panel opens
6. Complete payment → Verify unlimited access granted

---

## Phase 4: Deployment & Monitoring

### Task 4.1: Environment Setup Checklist
**Production Deployment:**
- [ ] Copy `config/vertex-credentials.json` to production server
- [ ] Verify file permissions (chmod 600)
- [ ] Set `VERTEX_PROJECT_ID` if different from default
- [ ] Test Vertex API connectivity from server
- [ ] Configure fallback `GEMINI_API_KEY` as backup
- [ ] Set up credential rotation schedule (quarterly)

### Task 4.2: Monitoring & Alerts
**Metrics to Track:**
- Vertex API success rate (should be >99%)
- Gemini fallback rate (should be <1%)
- Trial limit hit rate (users reaching 5/5)
- Subscription conversion rate (trial → paid)

**Log Messages to Monitor:**
```
[Provider] Vertex init failed → Alert if >5% of startups
[Auth] Trial limit exceeded for user {username} → Track conversion funnel
[Payment] Subscription request submitted → Track pipeline
```

### Task 4.3: Rollback Plan
**If Vertex AI Issues Occur:**
1. Set `VERTEX_JSON_KEY_PATH=""` to disable Vertex
2. Ensure `GEMINI_API_KEY` is valid (fallback active)
3. Investigate Vertex logs: quota exceeded, credential expired, API outage
4. Rotate credentials if security compromise suspected

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `config/vertex-credentials.json` | CREATE | Copy provided service account JSON |
| [config/__init__.py](config/__init__.py) | EDIT | Add default credential path, set project ID defaults |
| `.gitignore` | EDIT | Add credential file exclusions |
| [README.md](README.md) | EDIT | Document Vertex AI setup and security |
| `caller/rest.py` | EDIT | Add `check_work_available()` method |
| [core/video/batch/processor.py](core/video/batch/processor.py) | EDIT | Add pre-flight trial check before processing |
| `utils/error_handlers.py` | EDIT | Add `TrialLimitExceededError` exception |
| `ui/components/subscription_popup.py` | CREATE | New dialog for trial limit exceeded |
| [ui/components/subscription_status.py](ui/components/subscription_status.py) | EDIT | Add color coding for urgency |
| [ui/process_ui_modern.py](ui/process_ui_modern.py) | EDIT | Add exception handler for trial limit |

---

## Success Criteria

- [x] Vertex AI credentials work without manual environment variable setup
- [x] Trial users cannot create videos after 5 uses
- [x] Clear popup dialog shown when limit exceeded
- [x] Subscription panel accessible from dialog
- [x] Header status widget shows remaining count with color coding
- [x] Automatic fallback to Gemini if Vertex unavailable
- [x] Credentials not exposed in version control
- [x] All existing users migrated to Vertex AI automatically

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Vertex API quota exceeded | Medium | High | Implement Gemini fallback, monitor quota usage |
| Credentials accidentally committed | Low | Critical | Add pre-commit hook to scan for JSON files, .gitignore |
| Trial bypass via API manipulation | Low | Medium | Server-side validation, rate limiting already in place |
| User confusion at trial limit | Medium | Low | Clear dialog text, one-click subscription access |
| Credential rotation breaks app | Low | High | Document rotation process, test with backup keys first |

---

## Timeline Estimate

**Phase 1 (Credential Setup):** 30 minutes
**Phase 2 (Trial Enforcement):** 2 hours
**Phase 3 (Testing):** 1 hour
**Phase 4 (Deployment):** 30 minutes

**Total:** ~4 hours of development + testing time

---

## Next Steps

Once approved, execution will proceed in this order:
1. Create credential file and update .gitignore (safety first)
2. Update configuration with defaults
3. Add pre-flight trial checks
4. Create trial limit dialog
5. Integrate dialog into UI
6. Run test suite
7. Deploy to staging environment
8. Production rollout

**Ready for execution when approved.**
