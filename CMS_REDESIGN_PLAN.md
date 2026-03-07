# CMS Redesign Implementation Plan

## Overview
Redesign the entire CMS interface based on the reference design in `/Users/vold/inkstone-magazine-redesign-for-reference (4)/` while maintaining ALL existing functionality.

## Reference Design Key Features
1. **Sidebar**: Dark jade (`#134e4a`) with "inkstone. CMS" branding
2. **Dashboard**: Clean table-based post list with search/filter
3. **Editor**: Modern block-based content editor with sidebar settings  
4. **Theme**: Clean, minimal, modern with proper spacing and shadows
5. **Colors**: Uses ink-main (#0d9488), ink-dark (#134e4a), ink-brick (#b91c1c)

## Phase 1: Core Infrastructure
### Step 1.1: Update `admin_style.css`
- Replace all styles with modern design system
- Implement utility classes matching Tailwind approach
- Add animations and transitions
- Create component-specific styles

### Step 1.2: Update `admin/base.html`
- Implement new dark sidebar design
- Add proper navigation structure
- Include "inkstone. CMS" branding
- Add "View Site" and "Logout" buttons in footer

## Phase 2: Dashboard & List Views
### Step 2.1: Update `admin/dashboard.html`
- Create stats cards grid
- Add "Recent Activity" section
- Add "Quick Draft" widget (optional)
- Modernize layout

### Step 2.2: Update `admin/list.html` (All Posts)
- Implement table-based post list
- Add search bar and filters toolbar
- Add action buttons (Edit, Delete, Preview)
- Maintain existing post details sidebar functionality

### Step 2.3: Update List Views
- `admin/theme_list.html` - Grid-based card layout
- `admin/series_list.html` - Table layout
- `admin/protagonist_list.html` - Table or card layout
- `admin/keyword_list.html` - Table layout

## Phase 3: Forms (CRITICAL - Preserve ALL Functionality)
### Step 3.1: Post Editor (`admin/form.html`)
**Must Preserve:**
- All form fields (title, abstract, authors, editors, translators, keywords, etc.)
- Dynamic field addition (add/remove authors, etc.)
-Autocomplete for keywords and protagonists
- Image gallery upload with drag-and-drop
- Video URL support
- Template selection
- Publication date fields
- Theme and series assignment
- Featured post toggle

**New Design:**
- Cleaner layout with better spacing
- Modern input styling
- Better visual hierarchy
- Sidebar for settings (optional)

### Step 3.2: Theme Form (`admin/theme_form.html`)
**Must Preserve:**
- All fields (name, description, color, background, icon, etc.)
- Post assignment functionality
- Theme preview functionality
- All JavaScript interactions

### Step 3.3: Series Form (`admin/series_form.html`)
**Must Preserve:**
- All fields
- Post ordering/assignment
- All existing functionality

### Step 3.4: Protagonist Form (`admin/protagonist_form.html`)
**Must Preserve:**
- All fields (name, role, location, bio, etc.)
- Post association
- Search functionality
- All existing functionality

### Step 3.5: Keyword Form (`admin/keyword_form.html`)
**Must Preserve:**
- All fields
- Usage count display
- Post search functionality
- All existing functionality

## Phase 4: Special Pages
### Step 4.1: `admin/slogan_backgrounds.html`
- Modern card grid layout
- Upload functionality preserved
- Active badge styling

### Step 4.2: Login Page `admin/login.html`
- Modern, clean login form
- Proper branding

## Phase 5: Testing & Refinement
- Test all forms end-to-end
- Verify data persistence
- Check all JavaScript functionality
- Test responsive design
- Browser compatibility

## Implementation Order
1. CSS foundation (`admin_style.css`)
2. Base template (`admin/base.html`)
3. Dashboard (`admin/dashboard.html`)
4. Post list (`admin/list.html`)
5. Post editor (`admin/form.html`) - CAREFULLY
6. Other list views
7. Other forms
8. Special pages
9. Testing and bug fixes

## Critical Success Factors
- ✅ NO functionality loss
- ✅ All JavaScript preserved
- ✅ All form fields preserved  
- ✅ All database operations work
- ✅ Modern, clean design
- ✅ Consistent with reference design
