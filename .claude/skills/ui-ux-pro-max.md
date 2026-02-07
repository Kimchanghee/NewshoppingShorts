# UI/UX Pro Max Design Skill

## Overview
AI-powered design intelligence for professional UI/UX development across multiple platforms.

## Core Principles

### 1. Design System First
- Always start with a consistent design system
- Use design tokens for colors, typography, spacing
- Maintain visual hierarchy and consistency

### 2. User-Centric Design
- Prioritize user experience over aesthetics
- Ensure accessibility (WCAG 2.1 AA minimum)
- Design for all device sizes and contexts

### 3. Performance-Aware
- Optimize for fast load times
- Minimize visual complexity
- Use progressive enhancement

## Design Assets Library

### UI Styles (67 total)
- **Glassmorphism**: Frosted glass effects with blur and transparency
- **Claymorphism**: Soft, inflated 3D elements with subtle shadows
- **Minimalism**: Clean, simple, focused on essentials
- **Brutalism**: Raw, bold, intentionally unpolished
- **Neumorphism**: Soft UI with light/shadow to create depth
- **Bento Grid**: Card-based modular layouts
- **Dark Mode**: Optimized for low-light environments
- **AI-Native UI**: Modern gradients, depth, adaptive interfaces

### Color Palettes (96 industry-specific)

**Tech & SaaS**:
- Primary: `#2563EB` (Blue)
- Success: `#10B981` (Green)
- Warning: `#F59E0B` (Amber)
- Error: `#DC2626` (Red)
- Surface: `#FFFFFF` / `#1F2937` (Dark)
- Text: `#111827` / `#F9FAFB` (Dark)

**E-commerce**:
- Primary: `#E31639` (Shopping Red)
- Secondary: `#FF4D6A` (Accent)
- Success: `#059669` (Purchase Green)
- Surface: `#F9FAFB` (Light Gray)

**Finance**:
- Primary: `#1E40AF` (Trust Blue)
- Success: `#047857` (Profit Green)
- Warning: `#D97706` (Alert Orange)
- Surface: `#F3F4F6` (Neutral)

### Typography (57 font pairings)

**Modern SaaS**:
- Headings: `Inter` / `Pretendard` (bold, 600-800 weight)
- Body: `Inter` / `Pretendard` (regular, 400-500 weight)
- Code: `JetBrains Mono` / `Fira Code`

**E-commerce**:
- Headings: `Montserrat` / `Noto Sans KR` (bold)
- Body: `Open Sans` / `Noto Sans KR` (regular)

**Sizes Scale** (Tailwind-inspired):
- xs: 12px
- sm: 14px
- base: 16px
- lg: 18px
- xl: 20px
- 2xl: 24px
- 3xl: 30px

### Spacing System
- space-1: 4px
- space-2: 8px
- space-3: 12px
- space-4: 16px
- space-5: 20px
- space-6: 24px
- space-8: 32px
- space-10: 40px
- space-12: 48px
- space-16: 64px

### Border Radius
- sm: 4px (buttons, inputs)
- md: 8px (cards)
- lg: 12px (modals)
- xl: 16px (hero sections)
- full: 9999px (pills, avatars)

## UX Best Practices (99 rules)

### Navigation
1. Primary actions should be highly visible
2. Use consistent navigation patterns
3. Provide clear visual feedback for current location
4. Keep navigation hierarchy shallow (max 3 levels)

### Forms
5. Group related fields
6. Provide inline validation
7. Show clear error messages
8. Use appropriate input types
9. Disable submit until validation passes
10. Show loading states during submission

### Feedback
11. Show success confirmation after actions
12. Use toast notifications for non-critical alerts
13. Provide undo options for destructive actions
14. Show progress indicators for long operations

### Accessibility
15. Maintain 4.5:1 text contrast ratio minimum
16. Support keyboard navigation
17. Provide focus indicators
18. Use semantic HTML
19. Include ARIA labels where needed

### Performance
20. Lazy load images and heavy components
21. Show skeleton screens during loading
22. Optimize for mobile-first
23. Minimize animation duration (200-300ms)

## Anti-Patterns to Avoid

### Visual
- ❌ Low contrast text (below 4.5:1)
- ❌ Overuse of animations
- ❌ Inconsistent spacing
- ❌ Too many font families (max 2-3)
- ❌ Misaligned elements

### UX
- ❌ Unclear error messages
- ❌ No loading indicators
- ❌ Destructive actions without confirmation
- ❌ Hidden navigation
- ❌ Auto-playing media

### Technical
- ❌ Inline styles (use design system)
- ❌ Fixed pixel values (use rem/em)
- ❌ Missing alt text for images
- ❌ Non-responsive layouts

## Design System Generator Workflow

### 1. Analysis Phase
```
Input: Project requirements (industry, platform, features)
Output: Design direction recommendation
```

### 2. Pattern Selection
- Hero-Centric: Landing pages, marketing sites
- Dashboard: Admin panels, analytics
- Form-Heavy: Checkout, registration
- Content-First: Blogs, documentation
- Social Proof: Reviews, testimonials

### 3. Style Classification
- **Minimalist**: Clean, focused, high performance
- **Modern Gradient**: Vibrant, energetic, consumer-facing
- **Professional**: Trustworthy, corporate, B2B
- **Playful**: Fun, casual, consumer apps

### 4. Component Library
Based on selected style, generate:
- Buttons (primary, secondary, ghost)
- Forms (inputs, selects, checkboxes)
- Cards (content, pricing, feature)
- Navigation (header, sidebar, tabs)
- Feedback (alerts, toasts, modals)

### 5. Pre-Delivery Checklist
- [ ] Color contrast meets WCAG AA
- [ ] Typography scale is consistent
- [ ] Spacing follows system
- [ ] Components are reusable
- [ ] Responsive breakpoints defined
- [ ] Dark mode variant provided (if needed)
- [ ] Loading states included
- [ ] Error states included
- [ ] Accessibility tested

## Technology Stack Support

### Web
- **React/Next.js**: Use shadcn/ui components + Tailwind
- **Vue/Nuxt**: Use Nuxt UI + Tailwind
- **Svelte**: Use Skeleton UI + Tailwind
- **PyQt6**: Use design system tokens with QSS

### Mobile
- **SwiftUI**: Use SwiftUI built-in design system
- **Jetpack Compose**: Material 3 design tokens
- **React Native**: React Native Paper
- **Flutter**: Material 3 or custom theme

## Implementation Guide

### 1. Setup Design System
```python
# For PyQt6
class DesignSystem:
    colors = {
        "primary": "#2563EB",
        "surface": "#FFFFFF",
        "text_primary": "#111827",
        # ...
    }

    spacing = {
        "space_4": 16,
        "space_6": 24,
        # ...
    }
```

### 2. Apply Consistently
```python
# Use design tokens everywhere
btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {ds.colors.primary};
        color: {ds.colors.text_on_primary};
        padding: {ds.spacing.space_3}px {ds.spacing.space_5}px;
        border-radius: {ds.radius.md}px;
    }}
""")
```

### 3. Document Patterns
Create a `DESIGN.md` file documenting:
- Color palette with usage guidelines
- Typography scale with examples
- Component patterns with code snippets
- Common layouts with wireframes

## Industry-Specific Guidelines

### E-commerce
- **Primary Action**: Always red/brand color for "Buy" buttons
- **Trust Signals**: Show reviews, security badges prominently
- **Product Cards**: High-quality images, clear pricing, quick actions
- **Checkout**: Progress indicator, minimal form fields

### SaaS
- **Onboarding**: Step-by-step guided tours
- **Dashboard**: Data visualization, quick actions, status cards
- **Settings**: Organized tabs, clear labels, inline help
- **Pricing**: Feature comparison table, highlighted "Popular" plan

### Finance
- **Security**: Visual indicators of security (locks, shields)
- **Data Visualization**: Clear charts with annotations
- **Actions**: Two-step confirmation for transfers
- **Trust**: Professional, minimal, high contrast

## Maintenance

### Design System Persistence
```
project/
├── design-system/
│   ├── MASTER.md          # Global design rules
│   ├── pages/
│   │   ├── home.md        # Page-specific overrides
│   │   ├── dashboard.md
│   │   └── settings.md
│   └── components/
│       ├── buttons.md
│       ├── forms.md
│       └── cards.md
```

### Version Control
- Tag design system updates in git
- Document breaking changes
- Provide migration guides
- Keep changelog updated

## Resources

- **Google Fonts**: https://fonts.google.com
- **Color Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Tailwind CSS**: https://tailwindcss.com/docs
- **Material Design**: https://m3.material.io/
- **shadcn/ui**: https://ui.shadcn.com/

---

**Remember**: Good design is invisible. The user should accomplish their goals without noticing the interface.
