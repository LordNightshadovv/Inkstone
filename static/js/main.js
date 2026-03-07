// 墨石 Inkstone - Revolutionary Interactive System
// Eastern Philosophy meets Western Innovation

class InkstoneInteractive {
    constructor() {
        this.particles = [];
        this.maxParticles = 50;
        this.isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.init();
    }

    init() {
        this.setupScrollEffects();
        this.setupParticleSystem();
        this.setupMagneticEffects();
        this.setupIntersectionObserver();
        this.setupNavigation();
    }

    // Zen-inspired scroll effects
    setupScrollEffects() {
        let lastScrollY = window.scrollY;
        let ticking = false;

        const updateScroll = () => {
            const currentScrollY = window.scrollY;
            const navbar = document.querySelector('.navbar');
            
            if (navbar) {
                // Subtle navbar behavior
                if (currentScrollY > 100) {
                    navbar.style.background = 'rgba(12, 12, 12, 0.95)';
                    navbar.style.backdropFilter = 'blur(20px) saturate(180%)';
                } else {
                    navbar.style.background = 'rgba(248, 249, 250, 0.03)';
                    navbar.style.backdropFilter = 'blur(20px) saturate(180%)';
                }
            }

            // Parallax effect for hero visual
            const heroVisual = document.querySelector('.hero-visual');
            if (heroVisual && currentScrollY < window.innerHeight) {
                const parallaxSpeed = currentScrollY * 0.5;
                heroVisual.style.transform = `translateY(${parallaxSpeed}px)`;
            }

            lastScrollY = currentScrollY;
            ticking = false;
        };

        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(updateScroll);
                ticking = true;
            }
        });
    }

    // Subtle particle system
    setupParticleSystem() {
        if (this.isReducedMotion) return;

        // Mouse trail particles (very subtle)
        document.addEventListener('mousemove', (e) => {
            if (Math.random() > 0.98) {
                this.createParticle(e.clientX, e.clientY);
            }
        });

        // Click effects
        document.addEventListener('click', (e) => {
            if (e.target.matches('.cta-button, .read-more, .nav-links a')) {
                this.createRipple(e.clientX, e.clientY);
            }
        });
    }

    createParticle(x, y) {
        if (this.particles.length >= this.maxParticles) return;

        const particle = document.createElement('div');
        const colors = ['rgba(29, 209, 161, 0.6)', 'rgba(200, 16, 46, 0.6)', 'rgba(204, 153, 0, 0.6)'];
        const color = colors[Math.floor(Math.random() * colors.length)];

        particle.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: 2px;
            height: 2px;
            background: ${color};
            border-radius: 50%;
            pointer-events: none;
            z-index: 9999;
            animation: particleFloat 2s ease-out forwards;
        `;

        document.body.appendChild(particle);
        this.particles.push(particle);

        setTimeout(() => {
            if (particle.parentNode) {
                particle.remove();
            }
            this.particles = this.particles.filter(p => p !== particle);
        }, 2000);
    }

    createRipple(x, y) {
        const ripple = document.createElement('div');
        ripple.style.cssText = `
            position: fixed;
            left: ${x - 25}px;
            top: ${y - 25}px;
            width: 50px;
            height: 50px;
            border: 2px solid rgba(29, 209, 161, 0.5);
            border-radius: 50%;
            pointer-events: none;
            z-index: 9999;
            animation: rippleExpand 0.6s ease-out forwards;
        `;

        document.body.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    }

    // Magnetic effects for interactive elements
    setupMagneticEffects() {
        const magneticElements = document.querySelectorAll('.cta-button, .media-item, .nav-links a');
        
        magneticElements.forEach(element => {
            element.addEventListener('mouseenter', function() {
                if (!this.isReducedMotion) {
                    this.style.transition = 'transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
                }
            });

            element.addEventListener('mousemove', (e) => {
                if (this.isReducedMotion) return;

                const rect = element.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;

                const distance = Math.sqrt(x * x + y * y);
                const maxDistance = 100;

                if (distance < maxDistance) {
                    const force = (maxDistance - distance) / maxDistance;
                    const moveX = x * force * 0.2;
                    const moveY = y * force * 0.2;

                    element.style.transform = `translate(${moveX}px, ${moveY}px)`;
                }
            });

            element.addEventListener('mouseleave', function() {
                this.style.transform = 'translate(0, 0)';
            });
        });
    }

    // Intersection Observer for scroll animations
    setupIntersectionObserver() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);

        // Observe media items
        document.querySelectorAll('.media-item').forEach((item, index) => {
            item.style.opacity = '0';
            item.style.transform = 'translateY(30px)';
            item.style.transition = `all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94) ${index * 0.1}s`;
            observer.observe(item);
        });

        // Observe section titles
        document.querySelectorAll('.section-title').forEach(title => {
            title.style.opacity = '0';
            title.style.transform = 'translateY(20px)';
            title.style.transition = 'all 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
            observer.observe(title);
        });
    }

    // Enhanced navigation
    setupNavigation() {
        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });

        // Active nav link highlighting
        const navLinks = document.querySelectorAll('.nav-links a');
        const currentPath = window.location.pathname;
        
        navLinks.forEach(link => {
            if (link.getAttribute('href') === currentPath) {
                link.classList.add('active');
            }
        });
    }
}

// Utility functions
const utils = {
    // Debounce function for performance
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Throttle function for scroll events
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // Check if element is in viewport
    isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
};

// Form enhancements
class FormEnhancer {
    constructor() {
        this.setupFormValidation();
        this.setupFormAnimations();
    }

    setupFormValidation() {
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            
            inputs.forEach(input => {
                // Real-time validation
                input.addEventListener('blur', () => {
                    this.validateField(input);
                });

                // Enhanced focus states
                input.addEventListener('focus', () => {
                    input.parentElement.classList.add('focused');
                });

                input.addEventListener('blur', () => {
                    if (!input.value) {
                        input.parentElement.classList.remove('focused');
                    }
                });
            });

            // Form submission enhancement
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });
        });
    }

    validateField(field) {
        const value = field.value.trim();
        const fieldContainer = field.parentElement;
        
        // Remove existing validation classes
        fieldContainer.classList.remove('valid', 'invalid');
        
        // Basic validation
        if (field.required && !value) {
            fieldContainer.classList.add('invalid');
            return false;
        }

        // Email validation
        if (field.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                fieldContainer.classList.add('invalid');
                return false;
            }
        }

        fieldContainer.classList.add('valid');
        return true;
    }

    validateForm(form) {
        const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
        let isValid = true;

        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    setupFormAnimations() {
        // Animated labels
        document.querySelectorAll('.form-group').forEach(group => {
            const input = group.querySelector('input, textarea');
            const label = group.querySelector('label');

            if (input && label) {
                // Check if field has value on load
                if (input.value) {
                    group.classList.add('has-value');
                }

                input.addEventListener('input', () => {
                    if (input.value) {
                        group.classList.add('has-value');
                    } else {
                        group.classList.remove('has-value');
                    }
                });
            }
        });
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize main interactive system
    new InkstoneInteractive();
    
    // Initialize form enhancements
    new FormEnhancer();

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes particleFloat {
            0% {
                opacity: 1;
                transform: scale(1) translateY(0);
            }
            100% {
                opacity: 0;
                transform: scale(0) translateY(-60px);
            }
        }

        @keyframes rippleExpand {
            0% {
                transform: scale(0);
                opacity: 1;
            }
            100% {
                transform: scale(2);
                opacity: 0;
            }
        }

        .animate-in {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }

        .nav-links a.active {
            color: var(--cyber-teal) !important;
            background: rgba(29, 209, 161, 0.1);
        }

        .form-group.focused label,
        .form-group.has-value label {
            transform: translateY(-20px) scale(0.85);
            color: var(--cyber-teal);
        }

        .form-group.valid input,
        .form-group.valid textarea {
            border-color: var(--cyber-teal);
        }

        .form-group.invalid input,
        .form-group.invalid textarea {
            border-color: var(--fire-vermillion);
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
    `;
    document.head.appendChild(style);
});

// Modal System for Post Previews
class ModalSystem {
    constructor() {
        this.currentModal = null;
        this.setupModalTriggers();
    }

    setupModalTriggers() {
        // Setup click listeners for all article panels in voices gallery
        document.addEventListener('click', (e) => {
            const articlePanel = e.target.closest('.media-item[data-post-id]');
            if (articlePanel) {
                e.preventDefault();
                const postId = articlePanel.dataset.postId;
                this.openPostModal(postId);
            }
        });

        // Setup escape key to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentModal) {
                this.closeModal();
            }
        });
    }

    async openPostModal(postId) {
        try {
            // Fetch post data from API
            const response = await fetch(`/api/post/${postId}`);
            if (!response.ok) {
                throw new Error('Post not found');
            }
            
            const postData = await response.json();
            
            // Determine modal type based on post content
            if (postData.youtube_url) {
                this.showVideoModal(postData);
            } else if (postData.gallery_template === 'slideshow') {
                this.showSlideshowModal(postData);
            } else if (postData.gallery_template === 'waterfall') {
                this.showWaterfallModal(postData);
            } else {
                this.showTextModal(postData);
            }
        } catch (error) {
            console.error('Error loading post:', error);
            this.showErrorModal();
        }
    }

    showVideoModal(postData) {
        const videoId = this.extractYouTubeId(postData.youtube_url);
        const modalHTML = `
            <div class="modal-overlay" onclick="modalSystem.closeModal()">
                <div class="modal-container video-modal" onclick="event.stopPropagation()">
                    <button class="modal-close" onclick="modalSystem.closeModal()">×</button>
                    <div class="modal-header">
                        <h2>${postData.title}</h2>
                        <p class="modal-author">by ${postData.author}</p>
                    </div>
                    <div class="modal-content">
                        <div class="video-container">
                            <iframe src="https://www.youtube.com/embed/${videoId}" 
                                    frameborder="0" 
                                    allowfullscreen>
                            </iframe>
                        </div>
                        <div class="modal-text">
                            <p class="modal-abstract">${postData.abstract}</p>
                            ${postData.text_content ? `<div class="modal-body">${postData.text_content}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.displayModal(modalHTML);
    }

    showSlideshowModal(postData) {
        const pictures = postData.pictures || [];
        
        if (pictures.length === 0) {
            // If no pictures, show text modal instead
            this.showTextModal(postData);
            return;
        }
        
        const slidesHTML = pictures.map((pic, index) => `
            <div class="slide ${index === 0 ? 'active' : ''}" data-slide="${index}">
                <img src="${pic.url}" alt="${pic.filename}" loading="lazy">
            </div>
        `).join('');

        const dotsHTML = pictures.map((_, index) => `
            <button class="slide-dot ${index === 0 ? 'active' : ''}" 
                    onclick="modalSystem.goToSlide(${index})"></button>
        `).join('');

        const modalHTML = `
            <div class="modal-overlay" onclick="modalSystem.closeModal()">
                <div class="modal-container slideshow-modal" onclick="event.stopPropagation()">
                    <button class="modal-close" onclick="modalSystem.closeModal()">×</button>
                    <div class="modal-header">
                        <h2>${postData.title}</h2>
                        <p class="modal-author">by ${postData.author}</p>
                    </div>
                    <div class="modal-content">
                        <div class="slideshow-container">
                            <div class="slides-wrapper">
                                ${slidesHTML}
                            </div>
                            ${pictures.length > 1 ? `
                                <button class="slide-nav prev" onclick="modalSystem.prevSlide()">‹</button>
                                <button class="slide-nav next" onclick="modalSystem.nextSlide()">›</button>
                                <div class="slide-dots">
                                    ${dotsHTML}
                                </div>
                            ` : ''}
                        </div>
                        <div class="modal-text">
                            <p class="modal-abstract">${postData.abstract}</p>
                            ${postData.text_content ? `<div class="modal-body">${postData.text_content}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.displayModal(modalHTML);
        this.currentSlide = 0;
        this.totalSlides = pictures.length;
    }

    showWaterfallModal(postData) {
        const pictures = postData.pictures || [];
        
        if (pictures.length === 0) {
            // If no pictures, show text modal instead
            this.showTextModal(postData);
            return;
        }
        
        const imagesHTML = pictures.map(pic => `
            <div class="waterfall-item">
                <img src="${pic.url}" alt="${pic.filename}" loading="lazy">
            </div>
        `).join('');

        const modalHTML = `
            <div class="modal-overlay" onclick="modalSystem.closeModal()">
                <div class="modal-container waterfall-modal" onclick="event.stopPropagation()">
                    <button class="modal-close" onclick="modalSystem.closeModal()">×</button>
                    <div class="modal-header">
                        <h2>${postData.title}</h2>
                        <p class="modal-author">by ${postData.author}</p>
                    </div>
                    <div class="modal-content">
                        <div class="modal-text">
                            <p class="modal-abstract">${postData.abstract}</p>
                            ${postData.text_content ? `<div class="modal-body">${postData.text_content}</div>` : ''}
                        </div>
                        <div class="waterfall-gallery">
                            ${imagesHTML}
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.displayModal(modalHTML);
    }

    showTextModal(postData) {
        const modalHTML = `
            <div class="modal-overlay" onclick="modalSystem.closeModal()">
                <div class="modal-container text-modal" onclick="event.stopPropagation()">
                    <button class="modal-close" onclick="modalSystem.closeModal()">×</button>
                    <div class="modal-header">
                        <h2>${postData.title}</h2>
                        <p class="modal-author">by ${postData.author}</p>
                    </div>
                    <div class="modal-content">
                        <div class="modal-text">
                            <p class="modal-abstract">${postData.abstract}</p>
                            ${postData.text_content ? `<div class="modal-body">${postData.text_content}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.displayModal(modalHTML);
    }

    showErrorModal() {
        const modalHTML = `
            <div class="modal-overlay" onclick="modalSystem.closeModal()">
                <div class="modal-container error-modal" onclick="event.stopPropagation()">
                    <button class="modal-close" onclick="modalSystem.closeModal()">×</button>
                    <div class="modal-content">
                        <h2>Content Not Available</h2>
                        <p>Sorry, this content could not be loaded at the moment.</p>
                    </div>
                </div>
            </div>
        `;
        this.displayModal(modalHTML);
    }

    displayModal(html) {
        // Remove existing modal
        this.closeModal();
        
        // Create and show new modal
        const modalElement = document.createElement('div');
        modalElement.className = 'modal-system';
        modalElement.innerHTML = html;
        
        document.body.appendChild(modalElement);
        document.body.style.overflow = 'hidden';
        
        this.currentModal = modalElement;
        
        // Animate in
        requestAnimationFrame(() => {
            modalElement.classList.add('active');
        });
    }

    closeModal() {
        if (this.currentModal) {
            this.currentModal.classList.remove('active');
            document.body.style.overflow = 'auto';
            
            setTimeout(() => {
                if (this.currentModal && this.currentModal.parentNode) {
                    this.currentModal.remove();
                }
                this.currentModal = null;
            }, 300);
        }
    }

    // Slideshow navigation methods
    goToSlide(index) {
        if (!this.currentModal) return;
        
        const slides = this.currentModal.querySelectorAll('.slide');
        const dots = this.currentModal.querySelectorAll('.slide-dot');
        
        // Remove active class from all
        slides.forEach(slide => slide.classList.remove('active'));
        dots.forEach(dot => dot.classList.remove('active'));
        
        // Add active class to current
        if (slides[index]) slides[index].classList.add('active');
        if (dots[index]) dots[index].classList.add('active');
        
        this.currentSlide = index;
    }

    nextSlide() {
        const nextIndex = (this.currentSlide + 1) % this.totalSlides;
        this.goToSlide(nextIndex);
    }

    prevSlide() {
        const prevIndex = (this.currentSlide - 1 + this.totalSlides) % this.totalSlides;
        this.goToSlide(prevIndex);
    }

    extractYouTubeId(url) {
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }
}

// Initialize modal system
let modalSystem;
document.addEventListener('DOMContentLoaded', () => {
    modalSystem = new ModalSystem();
});

// Export for potential external use
window.InkstoneInteractive = InkstoneInteractive;
window.FormEnhancer = FormEnhancer;
window.ModalSystem = ModalSystem;
window.utils = utils;

// Our Story Section - Expand/Collapse Functionality
window.expandOurStory = function() {
    const section = document.querySelector('.our-story-section');
    console.log('expandOurStory called', section); // Debug log
    if (section) {
        console.log('Before:', section.classList); // Debug log
        section.classList.remove('collapsed');
        section.classList.add('expanded');
        console.log('After:', section.classList); // Debug log
        
        // Smooth scroll to the expanded content
        setTimeout(() => {
            section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    } else {
        console.error('Section not found!');
    }
};
