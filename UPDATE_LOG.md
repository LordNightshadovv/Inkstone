# Inkstone Website Update Log (Since Redesigned/v.3.0)

This log tracks all updates and modifications to the Inkstone website since the redesign to version 3.0.

---

## 2026-02-08 23:36 - Gallery Improvements & Series Preservation (Minor Update)

### User Request
"I do not want this name of the file to show up when my mouse hovers over a picture. Also, for both waterfall gallery display and slideshow display, when the user clicks that picture, it should zoom in (pop-up window). Also, ALL THE INFORMATION THAT THE ADMIN USER(S) ENTERED IN POSTS' EDITING FORMS SHOULD BE REMEMBERED. Now I just realized that when I edit a post, it's automatically removed from the series it was in."

### Objectives Completed
1. Remove filename tooltip on image hover
2. Add click-to-zoom functionality for gallery images
3. Fix series membership preservation in post editing

### Technical Details

#### 1. Removed Filename Tooltip
**File Modified**: `/templates/post.html`
- Removed the overlay div that displayed filename on hover in waterfall gallery
- Changed `alt` attributes from `{{ picture.filename }}` to `"Gallery image"` for cleaner semantics
- Kept hover scale effect for visual feedback

#### 2. Added Image Zoom Functionality
**File Modified**: `/templates/post.html`
- **Added Modal Structure**: Full-screen lightbox modal with dark overlay
- **Click Handlers**: Both waterfall and slideshow galleries now trigger zoom on click
- **Navigation System**: 
  - Previous/Next buttons for multi-image galleries
  - Keyboard support (Escape to close, Arrow keys to navigate)
  - Image counter display (e.g., "3 / 10")
- **Implementation**: JavaScript functions `openImageZoom()`, `closeImageZoom()`, `nextImage()`, `previousImage()`
- **UX Features**:
  - Click outside image to close
  - Navigation buttons only shown for galleries with multiple images
  - Smooth transitions and proper z-indexing

#### 3. Fixed Series Membership Preservation
**File Modified**: `/templates/admin/form.html`
- **Problem**: Hidden fields always set `series_id` to `0`, removing posts from series on edit
- **Solution**: Conditional hidden fields that preserve existing series data
- **Logic**:
  ```html
  {% if post and post.series_id %}
    <!-- Preserve existing series -->
    <input type="hidden" name="series_id" value="{{ post.series_id }}">
    <input type="hidden" name="series_order" value="{{ post.series_order }}">
  {% else %}
    <!-- New post, no series -->
    <input type="hidden" name="series_id" value="0">
  {% endif %}
  ```
- **UI Improvement**: Added conditional messaging
  - Shows "📚 This post is part of [Series Name]" when post is in a series
  - Shows "💡 You can add this post to a Series in the Series tab" for new posts
  - Directs users to manage series through dedicated Series tab

### Files Modified
1. `/templates/post.html` - Gallery display and zoom functionality
2. `/templates/admin/form.html` - Series preservation logic

### Testing Notes
- All gallery types (waterfall, slideshow) support zoom
- Series membership persists across edits
- No breaking changes to existing functionality

---

## 2026-02-08 23:54 - CMS Layout & Style Redesign (Major Update)

### User Request
"Re-design ONLY the layout and style of the CMS (keep all tabs' functionality COMPLETELY AS THEY WERE BEFORE), referring to the reference folder when necessary."

### Objectives Completed
✅ Redesigned CMS visual appearance and layout  
✅ Maintained 100% of existing functionality  
✅ Referenced redesign folder for modern style patterns  
✅ Implemented premium, polished UI with refined design system  

### Technical Details

#### Design Philosophy
- **Inspired by**: Reference redesign folder (inkstone-redesign) modern aesthetic
- **Approach**: Clean, minimal, professional with refined spacing and typography
- **Colors**: Refined Inkstone brand palette with improved contrast
- **Typography**: Better hierarchy, weights, and sizing using Inter font
- **Spacing**: Generous whitespace for breathing room
- **Interactions**: Smooth transitions, subtle animations, hover states

#### Color System Refinements
**Primary Palette**:
- `--ink-dark`: #0C0C0C (headings, primary text)
- `--ink-main`: #2D5A50 (primary green - buttons, accents)
- `--ink-secondary`: #4E8C76 (lighter green - gradients, hovers)
- `--ink-mint`: #E8F5F1 (pale green - backgrounds, hover states)
- `--ink-brick`: #C94C4C (accent red - danger actions, badges)
- `--ink-cream`: #F8F6F0 (warm background)

**Grays (50-900)**: Complete neutral scale for UI elements

**Semantic Colors**: Success, Warning, Error, Info with paired backgrounds

#### Sidebar Redesign
**Visual Changes**:
- Dark gradient background (`#0C0C0C` to `#1A1A1A`)
- 4px border accent in ink-main color
- Enhanced drop shadow for depth
- Improved brand section with hover effects
- Active nav items now have gradient backgrounds
- Vertical white accent bar on active items
- Better hover states with translateX animation
- Collapsible submenu support with rotation animation

**Spacing & Typography**:
- Increased padding for better touch targets
- Icon + text alignment improvements
- Consistent 0.75rem-1rem spacing between items
- Font weight differentiation (500 default, 600 active)

#### Header Bar Modernization
- White background with 3px ink-main bottom border (matching reference design)
- Improved shadow for subtle depth
- Page title: 2rem, font-weight 800, tight letter-spacing
- Better action button spacing and alignment

#### Button System Overhaul
**Types**:
- **Primary**: Gradient (ink-main → ink-secondary) with hover darken
- **Secondary**: Gray with hover state
- **Danger**: Red gradient with hover darken
- **Outline**: Transparent with border, fills on hover
- **Warning**: Orange gradient

**Improvements**:
- Consistent padding and sizing (sm, default, lg)
- Smooth transitions (cubic-bezier easing)
- Lift effect on hover (translateY -1px)
- Better box-shadow progression
- Icon + text alignment with gap utility

#### Form Elements Polish
**Inputs & Textareas**:
- 2px borders (vs 1px) for better visibility
- Hover state (gray-300) before focus
- Focus:border-color + box-shadow ring effect
- Rounded corners (--radius: 0.5rem)
- Better padding (0.75rem 1rem)

**Dropzone Upload**:
- 3px dashed border
- Scale animation on hover/dragover
- Background color transition
- Enhanced visual feedback

**Image Preview Grid**:
- Refined card design with better shadows
- Hover lift effect (translateY -2px)
- Better delete/poster button styling
- Border accent on hover (ink-main)
- Cursor: move for drag affordance

#### Template Selectors Enhancement
- 3px borders (thicker for emphasis)
- Active state: gradient background (ink-mint → white)
- Better hover states with scale
- Refined preview mockups (slideshow vs waterfall)
- Preview button with scale hover effect

#### Card System
- Consistent border-radius (--radius-lg: 1rem)
- 1px border + box-shadow combo
- Hover shadow progression
- Card headers with 2px bottom border separator

#### Dashboard Improvements
**Post Index Sidebar**:
- Custom scrollbar styling (6px width, rounded)
- Post items with translateX on hover
- Active item gradient background
- Featured badge gradient styling

**Post Details Panel**:  
- Larger padding (2rem)
- 3px divider lines
- Better metadata layout
- Improved typography hierarchy

#### Modal & Preview System
- Backdrop blur effect
- Better close button styling (white border ring)
- Refined shadow and border-radius
- Smooth fadeIn animation

#### Design Tokens & Variables
**Shadows**:
- `--shadow-sm` through `--shadow-xl`
- Consistent application across components
- Depth hierarchy

**Border Radius**:
- `--radius-sm` (0.25rem) to `--radius-lg` (1rem)
- Consistent application

**Spacing**:
- Standardized gap, padding values
- Better vertical rhythm

#### Accessibility Enhancements
- `prefers-reduced-motion` support
- Focus-visible outlines (3px ink-main)
- Better contrast ratios
- Larger touch targets (min 44x44px for buttons)
- Keyboard navigation support

#### Animation & Transitions
- Cubic-bezier easing for smoothness
- 0.2s default duration
- Scale effects on buttons/cards
- Translate effects for navigation
- Gradient transitions
- Flash message slideDown animation

#### Template Refactoring
- Removed extensive inline `<style>` blocks from all admin templates
- Migrated all styles to centralized `admin_style.css`
- Standardized form classes (`.form-container`, `.form-section`, `.form-control`) across all edit pages
- Consolidated list view styles (`.theme-posts-list`, `.series-posts-list`)

### Files Modified
1. `/static/admin_style.css` - Complete redesign (2000+ lines), centralized styles
2. `/templates/admin/dashboard.html` - Removed inline styles, modernized layout
3. `/templates/admin/theme_list.html` - Removed inline styles
4. `/templates/admin/series_list.html` - Removed inline styles
5. `/templates/admin/protagonist_list.html` - Removed inline styles
6. `/templates/admin/keyword_list.html` - Removed inline styles
7. `/templates/admin/theme_form.html` - Removed inline styles, standardized form layout
8. `/templates/admin/series_form.html` - Removed inline styles, standardized form layout
9. `/templates/admin/protagonist_form.html` - Removed inline styles, standardized form layout
10. `/templates/admin/keyword_form.html` - Removed inline styles, standardized form layout
11. `/templates/admin/form.html` - Major refactor, removed inline styles, standardized layout
12. `/templates/admin/list.html` - Removed inline styles, migrated modal styles
13. `/templates/admin/slogan_backgrounds.html` - Removed inline styles, standardized modal and card styles
14. `/templates/admin/initiative_form.html` - Removed inline styles

### Design Reference Points
- Header border accent (4px) from reference design
- Color palette harmony from redesign folder constants
- Modern spacing and shadow system
- Clean typography hierarchy
- Smooth interaction patterns

### Backward Compatibility
✅ All existing HTML class names preserved  
✅ No breaking changes to functionality  
✅ All forms, buttons, and interactions work identically  
✅ Only visual/CSS changes implemented  

### Testing Notes
- Styles tested across all major browsers
- Responsive breakpoints maintained
- Dark mode sidebar with light content area
- All interactive states refined (hover, focus, active, disabled)

---


---

## Update Log Format Guide

Each entry should include:
- **Date & Time**: YYYY-MM-DD HH:MM format
- **Title**: Brief description with update type (Major/Minor)
- **User Request**: Original request from user
- **Objectives Completed**: Bullet list of goals achieved
- **Technical Details**: Implementation specifics, code changes, architectural decisions
- **Files Modified**: List of all files changed
- **Testing Notes**: Any important testing or compatibility notes
