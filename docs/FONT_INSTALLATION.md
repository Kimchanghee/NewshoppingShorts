# Font Installation Guide

## Required Fonts for Enhanced UI/UX

The new "Content Creator's Studio" design system uses distinctive, professional fonts:

### 1. Outfit (Headlines & Titles)
- **Style**: Geometric, modern, confident
- **Weights needed**: Regular (400), Semi-Bold (600), Bold (700), Extra-Bold (800)
- **Download**: [Google Fonts - Outfit](https://fonts.google.com/specimen/Outfit)

### 2. Manrope (Body Text)
- **Style**: Friendly, readable, professional
- **Weights needed**: Regular (400), Medium (500), Semi-Bold (600), Bold (700)
- **Download**: [Google Fonts - Manrope](https://fonts.google.com/specimen/Manrope)

### 3. JetBrains Mono (Code/Technical)
- **Style**: Monospace for technical elements
- **Weights needed**: Regular (400), Bold (700)
- **Download**: [JetBrains Mono](https://www.jetbrains.com/lp/mono/)

---

## Installation Instructions

### Windows

1. **Download fonts** from the links above
2. Extract the `.ttf` or `.otf` files
3. **Install all font weights**:
   - Right-click each font file
   - Select "Install for all users"
   - Or copy files to `C:\Windows\Fonts\`

### macOS

1. **Download fonts** from the links above
2. Extract the font files
3. **Install**:
   - Double-click each `.ttf`/`.otf` file
   - Click "Install Font" in Font Book
   - Or copy to `~/Library/Fonts/` or `/Library/Fonts/`

### Linux

1. **Download fonts**
2. Extract font files
3. **Install**:
   ```bash
   mkdir -p ~/.fonts
   cp *.ttf ~/.fonts/
   fc-cache -fv
   ```

---

## Verification

After installing fonts, restart the application. You can verify fonts are loaded by checking:

```python
from PyQt6.QtGui import QFontDatabase

db = QFontDatabase()
print("Outfit available:", "Outfit" in db.families())
print("Manrope available:", "Manrope" in db.families())
print("JetBrains Mono available:", "JetBrains Mono" in db.families())
```

---

## Fallback Strategy

If custom fonts are not installed, the application will fall back to:
- **Primary**: Pretendard (Korean) → Malgun Gothic
- **System**: -apple-system (macOS) → BlinkMacSystemFont (Chrome) → System sans-serif

However, for the best visual experience, **install all three fonts**. The distinctive typography is a key part of the new design identity.

---

## Quick Install Script (Windows PowerShell)

```powershell
# Download and install fonts automatically
# Run as Administrator

$outfitUrl = "https://fonts.google.com/download?family=Outfit"
$manropeUrl = "https://fonts.google.com/download?family=Manrope"

# Download
Invoke-WebRequest -Uri $outfitUrl -OutFile "$env:TEMP\Outfit.zip"
Invoke-WebRequest -Uri $manropeUrl -OutFile "$env:TEMP\Manrope.zip"

# Extract and install
Expand-Archive "$env:TEMP\Outfit.zip" -DestinationPath "$env:TEMP\Outfit"
Expand-Archive "$env:TEMP\Manrope.zip" -DestinationPath "$env:TEMP\Manrope"

# Copy to Fonts directory
Copy-Item "$env:TEMP\Outfit\*.ttf" "C:\Windows\Fonts\"
Copy-Item "$env:TEMP\Manrope\*.ttf" "C:\Windows\Fonts\"

Write-Host "Fonts installed successfully! Please restart the application."
```

---

## License

Both **Outfit** and **Manrope** are licensed under the **SIL Open Font License (OFL)**, which allows free use in both personal and commercial projects.
