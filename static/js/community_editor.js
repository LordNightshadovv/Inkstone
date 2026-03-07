/**
 * Community Editor - WYSIWYG editing for Our Community cards
 * Properly implements Quill.js by creating dynamic instances on contenteditable fields
 */

// Brand colors for the color picker
const BRAND_COLORS = [
    '#365B4C', // Deep green
    '#3A7467', // Mid green
    '#4E8C76', // Light green
    '#7BAF9E', // Mint
    '#C94C4C', // Accent red
    '#000000', // Black
    '#FFFFFF'  // White
];

// Track active Quill instances
let activeQuillInstances = new Map(); // Map of element -> Quill instance
let currentEditingElement = null;

/**
 * Initialize Quill editor on a contenteditable field
 */
function initializeQuillOnField(field) {
    // If already has a Quill instance, just focus it
    if (activeQuillInstances.has(field)) {
        const quill = activeQuillInstances.get(field);
        quill.focus();
        return quill;
    }
    
    // Store original HTML content
    const originalContent = field.innerHTML;
    
    // Remove contenteditable attribute (Quill will manage editing)
    field.removeAttribute('contenteditable');
    
    // Determine toolbar configuration based on field type
    const isTitle = field.classList.contains('card-title');
    const toolbarConfig = isTitle ? [
        ['bold', 'italic', 'underline'],
        [{ 'color': BRAND_COLORS }],
        ['clean']
    ] : [
        [{ 'header': [1, 2, 3, false] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ 'color': BRAND_COLORS }],
        [{ 'background': [] }],
        [{ 'size': ['small', false, 'large', 'huge'] }],
        [{ 'align': [] }],
        ['clean']
    ];
    
    // Initialize Quill on this field
    const quill = new Quill(field, {
        theme: 'snow',
        modules: {
            toolbar: toolbarConfig
        },
        placeholder: isTitle ? 'Enter title...' : 'Enter description...'
    });
    
    // Load the original content
    quill.root.innerHTML = originalContent;
    
    // Store the instance
    activeQuillInstances.set(field, quill);
    currentEditingElement = field;
    
    // Focus the editor
    quill.focus();
    
    // Handle blur - save content and optionally destroy instance
    quill.on('selection-change', function(range, oldRange, source) {
        if (range === null && oldRange !== null) {
            // Lost focus
            setTimeout(() => {
                // Check if focus moved to another card field
                const activeElement = document.activeElement;
                const isMovingToAnotherField = activeElement && 
                    (activeElement.classList.contains('card-title') || 
                     activeElement.classList.contains('card-body') ||
                     activeElement.closest('.ql-toolbar'));
                
                if (!isMovingToAnotherField) {
                    // Save and cleanup
                    saveAndCleanupQuill(field, quill);
                }
            }, 200);
        }
    });
    
    return quill;
}

/**
 * Save Quill content back to the field and cleanup
 */
function saveAndCleanupQuill(field, quill) {
    if (!quill || !activeQuillInstances.has(field)) {
        return;
    }
    
    // Save the content
    const content = quill.root.innerHTML;
    
    // Remove Quill instance
    const toolbar = field.parentElement.querySelector('.ql-toolbar');
    if (toolbar) {
        toolbar.remove();
    }
    
    // Restore the field as contenteditable
    field.innerHTML = content;
    field.setAttribute('contenteditable', 'true');
    
    // Remove from tracking
    activeQuillInstances.delete(field);
    
    if (currentEditingElement === field) {
        currentEditingElement = null;
    }
}

/**
 * Cleanup all Quill instances
 */
function cleanupAllQuillInstances() {
    activeQuillInstances.forEach((quill, field) => {
        saveAndCleanupQuill(field, quill);
    });
}

/**
 * Add new card via AJAX
 */
function addNewCard() {
    // Cleanup any active editors first
    cleanupAllQuillInstances();
    
    fetch('/admin/website-text-edit/our-community/card', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            addCardToGrid(data.card);
        } else {
            alert('Error: ' + (data.error || 'Failed to create card'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error creating card');
    });
}

/**
 * Add card element to the grid
 */
function addCardToGrid(cardData) {
    const grid = document.getElementById('community-cards');
    const cardHtml = `
        <div class="community-card" data-card-id="${cardData.id}" draggable="true">
            <div class="card-header">
                <button type="button" class="card-delete" onclick="deleteCard(this)">×</button>
                <div class="drag-handle">⋮⋮</div>
            </div>
            <div class="card-title" contenteditable="true" data-field="title">${cardData.title_html}</div>
            <div class="card-separator"></div>
            <div class="card-body" contenteditable="true" data-field="body">${cardData.body_html}</div>
        </div>
    `;
    grid.insertAdjacentHTML('beforeend', cardHtml);
    
    // Add drag listeners to new card
    const newCard = grid.lastElementChild;
    initializeDragAndDrop(newCard);
    
    // Add click listeners for Quill initialization
    initializeFieldListeners(newCard);
}

/**
 * Delete card with confirmation
 */
function deleteCard(button) {
    if (!confirm('Delete this card? This action cannot be undone.')) return;
    
    const card = button.closest('.community-card');
    
    // Cleanup any Quill instances in this card
    const titleField = card.querySelector('.card-title');
    const bodyField = card.querySelector('.card-body');
    
    if (activeQuillInstances.has(titleField)) {
        const quill = activeQuillInstances.get(titleField);
        saveAndCleanupQuill(titleField, quill);
    }
    if (activeQuillInstances.has(bodyField)) {
        const quill = activeQuillInstances.get(bodyField);
        saveAndCleanupQuill(bodyField, quill);
    }
    
    // Visual feedback and remove
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
    card.remove();
}

/**
 * Save all cards to database
 */
function saveAllCards() {
    // Cleanup all Quill instances first to save content
    cleanupAllQuillInstances();
    
    const saveButton = document.getElementById('save-community');
    const originalText = saveButton.textContent;
    saveButton.textContent = 'Saving...';
    saveButton.disabled = true;
    
    const cards = [];
    document.querySelectorAll('.community-card').forEach((card, index) => {
        const cardId = card.dataset.cardId;
        const titleHtml = card.querySelector('.card-title').innerHTML;
        const bodyHtml = card.querySelector('.card-body').innerHTML;
        
        cards.push({
            id: cardId !== 'undefined' ? parseInt(cardId) : null,
            title_html: titleHtml,
            body_html: bodyHtml,
            display_order: index
        });
    });
    
    fetch('/admin/website-text-edit/our-community/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ cards: cards })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Changes saved successfully!');
            window.location.reload();
        } else {
            alert('Error: ' + (data.error || 'Failed to save changes'));
            saveButton.textContent = originalText;
            saveButton.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving changes');
        saveButton.textContent = originalText;
        saveButton.disabled = false;
    });
}

// Global variable for drag and drop
let draggedCard = null;

/**
 * Initialize drag and drop for a card
 */
function initializeDragAndDrop(card) {
    card.addEventListener('dragstart', function(e) {
        // Don't allow dragging while editing
        if (currentEditingElement && card.contains(currentEditingElement)) {
            e.preventDefault();
            return;
        }
        
        draggedCard = this;
        this.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', this.innerHTML);
    });
    
    card.addEventListener('dragend', function(e) {
        this.classList.remove('dragging');
        draggedCard = null;
    });
    
    card.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        
        // Visual feedback
        if (draggedCard && draggedCard !== this) {
            this.style.borderColor = 'var(--admin-primary)';
        }
    });
    
    card.addEventListener('dragleave', function(e) {
        this.style.borderColor = '';
    });
    
    card.addEventListener('drop', function(e) {
        e.preventDefault();
        this.style.borderColor = '';
        
        if (draggedCard && draggedCard !== this) {
            const grid = document.getElementById('community-cards');
            const allCards = Array.from(grid.children);
            const draggedIndex = allCards.indexOf(draggedCard);
            const targetIndex = allCards.indexOf(this);
            
            // Reorder cards in DOM
            if (draggedIndex < targetIndex) {
                this.parentNode.insertBefore(draggedCard, this.nextSibling);
            } else {
                this.parentNode.insertBefore(draggedCard, this);
            }
        }
    });
}

/**
 * Initialize click listeners for fields to create Quill instances
 */
function initializeFieldListeners(card) {
    const titleField = card.querySelector('.card-title');
    const bodyField = card.querySelector('.card-body');
    
    [titleField, bodyField].forEach(field => {
        field.addEventListener('click', function(e) {
            // Only initialize if not already a Quill instance
            if (!activeQuillInstances.has(this)) {
                // Cleanup other instances first
                cleanupAllQuillInstances();
                // Initialize Quill on this field
                initializeQuillOnField(this);
            }
        });
    });
}

/**
 * Initialize the community editor
 */
function initializeCommunityEditor() {
    // Initialize drag and drop for existing cards
    document.querySelectorAll('.community-card').forEach(card => {
        initializeDragAndDrop(card);
        initializeFieldListeners(card);
    });
    
    // Add card button
    const addButton = document.getElementById('add-card');
    if (addButton) {
        addButton.addEventListener('click', addNewCard);
    }
    
    // Save button
    const saveButton = document.getElementById('save-community');
    if (saveButton) {
        saveButton.addEventListener('click', saveAllCards);
    }
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        cleanupAllQuillInstances();
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCommunityEditor);
} else {
    initializeCommunityEditor();
}
