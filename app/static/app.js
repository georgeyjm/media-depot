/**
 * Media Depot - Frontend Application
 */

// ===== State =====
const state = {
    currentPage: 'home',
    drawerOpen: false,
    tasks: [], // { id, shareText, status, title, thumbnailPath, postId, createdAt }
    posts: {
        items: [],
        page: 1,
        hasMore: true,
        loading: false,
    },
    currentPost: null,
    currentMediaIndex: 0,
    pollingIntervals: {},
};

// ===== DOM Elements =====
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const elements = {
    // Navigation
    navItems: $$('.nav-item[data-page]'),
    settingsBtn: $('#settings-btn'),
    
    // Pages
    pageHome: $('#page-home'),
    pageLibrary: $('#page-library'),
    
    // Home
    shareInput: $('#share-input'),
    submitBtn: $('#submit-btn'),
    
    // Tasks Drawer
    tasksDrawer: $('#tasks-drawer'),
    tasksList: $('#tasks-list'),
    drawerToggle: $('#drawer-toggle'),
    closeDrawerBtn: $('#close-drawer-btn'),
    taskCount: $('#task-count'),
    
    // Library
    libraryContent: $('.library-content'),
    postsGrid: $('#posts-grid'),
    loadMoreBtn: $('#load-more-btn'),
    platformFilter: $('#platform-filter'),
    typeFilter: $('#type-filter'),
    searchInput: $('#search-input'),
    
    // Media Modal
    mediaModal: $('#media-modal'),
    modalClose: $('#modal-close'),
    mediaViewer: $('#media-viewer'),
    mediaInfo: $('#media-info'),
    mediaNav: $('#media-nav'),
    mediaPrev: $('#media-prev'),
    mediaNext: $('#media-next'),
    mediaCounter: $('#media-counter'),
    creatorAvatar: $('#creator-avatar'),
    creatorName: $('#creator-name'),
    postTitle: $('#post-title'),
    
    // Settings Modal
    settingsModal: $('#settings-modal'),
    settingsClose: $('#settings-close'),
    themeSelect: $('#theme-select'),
    
    // Thumbnail Preview
    thumbnailPreview: $('#thumbnail-preview'),
};

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initHomeInput();
    initDrawer();
    initLibrary();
    initModals();
    loadTasksFromStorage();
    
    // Handle initial page based on URL
    const path = window.location.pathname;
    if (path === '/library') {
        switchPage('library', false);
    }
    
    // Handle browser back/forward
    window.addEventListener('popstate', (e) => {
        const page = e.state?.page || 'home';
        switchPage(page, false);
    });
});

// ===== Theme =====
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    elements.themeSelect.value = savedTheme;
    
    elements.themeSelect.addEventListener('change', (e) => {
        const theme = e.target.value;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    });
}

// ===== Navigation =====
function initNavigation() {
    elements.navItems.forEach((item) => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

function switchPage(page, updateUrl = true) {
    state.currentPage = page;
    
    // Update nav items
    elements.navItems.forEach((item) => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // Update pages
    $$('.page').forEach((p) => p.classList.remove('active'));
    $(`#page-${page}`).classList.add('active');
    
    // Show/hide drawer toggle based on page
    if (page === 'home') {
        elements.drawerToggle.classList.remove('hidden');
    } else {
        elements.drawerToggle.classList.add('hidden');
        closeDrawer();
    }
    
    // Update URL
    if (updateUrl) {
        const url = page === 'home' ? '/' : `/${page}`;
        history.pushState({ page }, '', url);
    }
    
    // Load library data when switching to library page
    if (page === 'library' && state.posts.items.length === 0) {
        loadPosts(true);
        loadPlatforms();
    }
}

// ===== Home Input =====
function initHomeInput() {
    const { shareInput, submitBtn } = elements;
    
    // Auto-resize textarea
    shareInput.addEventListener('input', () => {
        shareInput.style.height = 'auto';
        shareInput.style.height = Math.min(shareInput.scrollHeight, 160) + 'px';
        
        // Enable/disable submit button
        submitBtn.disabled = !shareInput.value.trim();
    });
    
    // Submit on Enter (without Shift)
    shareInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!submitBtn.disabled) {
                handleSubmit();
            }
        }
    });
    
    submitBtn.addEventListener('click', handleSubmit);
}

async function handleSubmit() {
    const { shareInput, submitBtn } = elements;
    const inputText = shareInput.value.trim();
    
    if (!inputText) return;
    
    // Split by newlines and filter empty lines
    const lines = inputText.split('\n').map(line => line.trim()).filter(line => line.length > 0 && /https?:\/\//.test(line));
    
    if (lines.length === 0) return;
    
    submitBtn.disabled = true;
    
    let hasSuccess = false;
    let hasError = false;
    
    // Submit each line as a separate task
    for (const shareText of lines) {
        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ share: shareText }),
            });
            
            if (!response.ok) {
                console.error('Submit error for line:', shareText, `HTTP ${response.status}`);
                hasError = true;
                continue;
            }
            
            const data = await response.json();
            
            // if (data.error) {
            //     console.error('Submit error for line:', shareText, data.error);
            //     hasError = true;
            //     continue;
            // }
            
            // Create task entry
            const task = {
                id: data.id,
                shareText: shareText,
                status: data.status,
                title: null,
                thumbnailPath: null,
                postId: null,
                createdAt: new Date().toISOString(),
            };
            
            addTask(task);
            hasSuccess = true;
            
            // Start polling for this task
            startPolling(task.id);
            
        } catch (err) {
            console.error('Submit error for line:', shareText, err);
            hasError = true;
        }
    }
    
    if (hasSuccess) {
        openDrawer();
        // Clear input
        shareInput.value = '';
        shareInput.style.height = 'auto';
    }
    
    if (hasError && !hasSuccess) {
        showNotification('Failed to submit. Please try again.', 'error');
    } else if (hasError && hasSuccess) {
        showNotification('Some links failed to submit', 'error');
    }
    
    submitBtn.disabled = true;
}

// ===== Tasks Drawer =====
function initDrawer() {
    elements.drawerToggle.addEventListener('click', toggleDrawer);
    elements.closeDrawerBtn.addEventListener('click', closeDrawer);
}

function toggleDrawer() {
    if (state.drawerOpen) {
        closeDrawer();
    } else {
        openDrawer();
    }
}

function openDrawer() {
    state.drawerOpen = true;
    elements.tasksDrawer.classList.add('open');
    elements.drawerToggle.classList.add('hidden');
    
    if (state.currentPage === 'home') {
        document.querySelector('.main-content').classList.add('drawer-open');
    }
}

function closeDrawer() {
    state.drawerOpen = false;
    elements.tasksDrawer.classList.remove('open');
    
    if (state.currentPage === 'home') {
        elements.drawerToggle.classList.remove('hidden');
    }
    
    document.querySelector('.main-content').classList.remove('drawer-open');
}

function addTask(task) {
    // Add to beginning of array
    state.tasks.unshift(task);
    saveTasksToStorage();
    renderTasks();
    updateTaskCount();
}

function updateTask(taskId, updates) {
    const task = state.tasks.find((t) => t.id === taskId);
    if (task) {
        Object.assign(task, updates);
        saveTasksToStorage();
        renderTasks();
    }
}

function renderTasks() {
    const { tasksList } = elements;
    
    if (state.tasks.length === 0) {
        tasksList.innerHTML = `
            <div class="posts-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                    <line x1="9" y1="9" x2="9.01" y2="9"/>
                    <line x1="15" y1="9" x2="15.01" y2="9"/>
                </svg>
                <p>No recent tasks</p>
            </div>
        `;
        return;
    }
    
    tasksList.innerHTML = state.tasks.map((task) => `
        <div class="task-item ${task.status}" 
             data-task-id="${task.id}" 
             data-post-id="${task.postId || ''}"
             data-thumbnail="${task.thumbnailPath || ''}">
            <div class="task-header">
                <div class="task-status ${task.status}">
                    ${getStatusIcon(task.status)}
                </div>
                <div class="task-content">
                    ${task.title ? `<div class="task-title">${escapeHtml(task.title)}</div>` : ''}
                    <div class="task-text">${escapeHtml(task.shareText)}</div>
                    <div class="task-time">${formatTime(task.createdAt)}</div>
                </div>
            </div>
        </div>
    `).join('');
    
    // Add click handlers
    tasksList.querySelectorAll('.task-item').forEach((item) => {
        const postId = item.dataset.postId;
        const isCompleted = item.classList.contains('completed');
        
        if (postId && postId !== '' && isCompleted) {
            item.style.cursor = 'pointer';
            item.addEventListener('click', () => openPostModal(parseInt(postId)));
            
            // Hover thumbnail preview
            const thumbnail = item.dataset.thumbnail;
            if (thumbnail && thumbnail !== '') {
                item.addEventListener('mouseenter', (e) => showThumbnailPreview(thumbnail, e));
                item.addEventListener('mousemove', (e) => moveThumbnailPreview(e));
                item.addEventListener('mouseleave', hideThumbnailPreview);
            }
        }
    });
}

function getStatusIcon(status) {
    const icons = {
        pending: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
        </svg>`,
        processing: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>`,
        completed: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>`,
        failed: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>`,
    };
    return icons[status] || icons.pending;
}

function updateTaskCount() {
    const activeCount = state.tasks.filter((t) => t.status === 'pending' || t.status === 'processing').length;
    const { taskCount } = elements;
    
    if (activeCount > 0) {
        taskCount.textContent = activeCount;
        taskCount.style.display = 'flex';
    } else {
        taskCount.style.display = 'none';
    }
}

// ===== Task Polling =====
function startPolling(taskId) {
    if (state.pollingIntervals[taskId]) return;
    
    state.pollingIntervals[taskId] = setInterval(() => pollTask(taskId), 1000);
}

function stopPolling(taskId) {
    if (state.pollingIntervals[taskId]) {
        clearInterval(state.pollingIntervals[taskId]);
        delete state.pollingIntervals[taskId];
    }
}

async function pollTask(taskId) {
    try {
        const response = await fetch(`/api/download/${taskId}`);
        if (!response.ok) {
            stopPolling(taskId);
            return;
        }
        
        const data = await response.json();
        const task = state.tasks.find((t) => t.id === taskId);
        
        if (!task) {
            stopPolling(taskId);
            return;
        }
        
        // Update task with new data
        const updates = {
            status: data.status,
        };
        
        // If we have a post_id, fetch post details for title and thumbnail
        if (data.post_id && !task.postId) {
            updates.postId = data.post_id;
            fetchPostDetails(taskId, data.post_id);
        }
        
        updateTask(taskId, updates);
        updateTaskCount();
        
        // Stop polling if completed or failed
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'canceled') {
            stopPolling(taskId);
        }
        
    } catch (err) {
        console.error('Polling error:', err);
    }
}

async function fetchPostDetails(taskId, postId) {
    try {
        const response = await fetch(`/api/posts/${postId}`);
        if (!response.ok) return;
        
        const post = await response.json();
        updateTask(taskId, {
            title: post.title,
            thumbnailPath: post.thumbnail_path,
        });
    } catch (err) {
        console.error('Fetch post details error:', err);
    }
}

// ===== Library =====
function initLibrary() {
    elements.loadMoreBtn.addEventListener('click', () => loadPosts(false));
    
    // Filters
    elements.platformFilter.addEventListener('change', () => loadPosts(true));
    elements.typeFilter.addEventListener('change', () => loadPosts(true));
    
    // Debounced search
    let searchTimeout;
    elements.searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => loadPosts(true), 300);
    });
    
    // Infinite scroll
    if (elements.libraryContent) {
        elements.libraryContent.addEventListener('scroll', handleLibraryScroll);
    }
}

function handleLibraryScroll() {
    const container = elements.libraryContent;
    if (!container) return;
    
    // Check if we're near the bottom (within 300px)
    const { scrollTop, scrollHeight, clientHeight } = container;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    
    if (distanceFromBottom < 300 && !state.posts.loading && state.posts.hasMore) {
        loadPosts(false);
    }
}

async function loadPlatforms() {
    try {
        const response = await fetch('/api/platforms');
        const platforms = await response.json();
        
        const { platformFilter } = elements;
        platformFilter.innerHTML = '<option value="">All Platforms</option>';
        platforms.forEach((p) => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = p.name.charAt(0).toUpperCase() + p.name.slice(1);
            platformFilter.appendChild(opt);
        });
    } catch (err) {
        console.error('Load platforms error:', err);
    }
}

async function loadPosts(reset = false) {
    if (state.posts.loading) return;
    
    if (reset) {
        state.posts.page = 1;
        state.posts.items = [];
        state.posts.hasMore = true;
    }
    
    if (!state.posts.hasMore) return;
    
    state.posts.loading = true;
    
    try {
        const params = new URLSearchParams({
            page: state.posts.page.toString(),
            per_page: '24',
        });
        
        const platform = elements.platformFilter.value;
        const postType = elements.typeFilter.value;
        const search = elements.searchInput.value.trim();
        
        if (platform) params.append('platform', platform);
        if (postType) params.append('post_type', postType);
        if (search) params.append('search', search);
        
        const response = await fetch(`/api/posts?${params}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Load posts error response:', errorText);
            showNotification('Failed to load posts', 'error');
            return;
        }
        
        const data = await response.json();
        
        state.posts.items = reset ? data.posts : [...state.posts.items, ...data.posts];
        state.posts.hasMore = data.has_more;
        state.posts.page++;
        
        renderPosts();
        
    } catch (err) {
        console.error('Load posts error:', err);
        showNotification('Failed to load posts', 'error');
    } finally {
        state.posts.loading = false;
    }
}

function renderPosts() {
    const { postsGrid, loadMoreBtn } = elements;
    
    if (state.posts.items.length === 0) {
        postsGrid.innerHTML = `
            <div class="posts-empty" style="grid-column: 1 / -1;">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
                <p>No posts yet</p>
            </div>
        `;
        loadMoreBtn.style.display = 'none';
        return;
    }
    
    postsGrid.innerHTML = state.posts.items.map((post) => `
        <div class="post-card" data-post-id="${post.id}">
            <img class="post-thumbnail" 
                 src="${post.thumbnail_path ? `/media/${post.thumbnail_path}` : ''}" 
                 alt="${escapeHtml(post.title || 'Post')}"
                 loading="lazy"
                 onerror="this.style.display='none'">
            <div class="post-info">
                <div class="post-card-title">${escapeHtml(post.title || 'Untitled')}</div>
                <div class="post-meta">
                    <span class="platform-badge">${post.platform.name}</span>
                    <span>@${escapeHtml(post.creator.username || post.creator.display_name || 'Unknown')}</span>
                </div>
            </div>
        </div>
    `).join('');
    
    // Add click handlers
    postsGrid.querySelectorAll('.post-card').forEach((card) => {
        card.addEventListener('click', () => {
            const postId = parseInt(card.dataset.postId);
            openPostModal(postId);
        });
    });
    
    loadMoreBtn.style.display = state.posts.hasMore ? 'block' : 'none';
}

// ===== Modals =====
function initModals() {
    // Media modal - close on background click
    elements.modalClose.addEventListener('click', closeMediaModal);
    
    // Close when clicking on the modal overlay or modal content background
    // but not on interactive elements inside
    const mediaModalContent = elements.mediaModal.querySelector('.media-modal-content');
    mediaModalContent.addEventListener('click', (e) => {
        // Close if clicking directly on the modal content background (not on children like media, buttons, info)
        if (e.target === mediaModalContent) {
            closeMediaModal();
        }
    });
    elements.mediaModal.addEventListener('click', (e) => {
        if (e.target === elements.mediaModal) closeMediaModal();
    });
    
    elements.mediaPrev.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateMedia(-1);
    });
    elements.mediaNext.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateMedia(1);
    });
    
    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (!elements.mediaModal.classList.contains('active')) return;
        
        if (e.key === 'Escape') closeMediaModal();
        if (e.key === 'ArrowLeft') navigateMedia(-1);
        if (e.key === 'ArrowRight') navigateMedia(1);
    });
    
    // Settings modal
    elements.settingsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openSettingsModal();
    });
    elements.settingsClose.addEventListener('click', closeSettingsModal);
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) closeSettingsModal();
    });
}

async function openPostModal(postId) {
    try {
        const response = await fetch(`/api/posts/${postId}`);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Open post modal error response:', response.status, errorText);
            throw new Error(`Post not found (${response.status})`);
        }
        
        const post = await response.json();
        state.currentPost = post;
        state.currentMediaIndex = 0;
        
        // Update modal info
        elements.creatorName.textContent = post.creator.display_name || post.creator.username || 'Unknown';
        elements.postTitle.textContent = post.title || '';
        
        if (post.creator.profile_pic_path) {
            elements.creatorAvatar.src = `/media/${post.creator.profile_pic_path}`;
            elements.creatorAvatar.style.display = 'block';
        } else {
            elements.creatorAvatar.style.display = 'none';
        }
        
        // Show navigation if multiple media
        if (post.media_items && post.media_items.length > 1) {
            elements.mediaNav.style.display = 'flex';
        } else {
            elements.mediaNav.style.display = 'none';
        }
        
        renderCurrentMedia();
        elements.mediaModal.classList.add('active');
        document.body.style.overflow = 'hidden';
        
    } catch (err) {
        console.error('Open post modal error:', err);
        showNotification('Failed to load post', 'error');
    }
}

function renderCurrentMedia() {
    const post = state.currentPost;
    if (!post || !post.media_items || post.media_items.length === 0) {
        elements.mediaViewer.innerHTML = '<p style="color: var(--text-muted);">No media available</p>';
        return;
    }

    const mediaItem = post.media_items[state.currentMediaIndex];
    if (!mediaItem || !mediaItem.file_path) {
        elements.mediaViewer.innerHTML = '<p style="color: var(--text-muted);">Media not found</p>';
        return;
    }

    const mediaPath = `/media/${mediaItem.file_path}`;

    if (mediaItem.media_type === 'video') {
        elements.mediaViewer.innerHTML = `
            <video src="${mediaPath}" controls autoplay playsinline></video>
        `;
    } else {
        elements.mediaViewer.innerHTML = `
            <img src="${mediaPath}" alt="${escapeHtml(post.title || 'Media')}">
        `;
    }

    // Update counter
    elements.mediaCounter.textContent = `${state.currentMediaIndex + 1} / ${post.media_items.length}`;

    // Update nav buttons
    elements.mediaPrev.disabled = state.currentMediaIndex === 0;
    elements.mediaNext.disabled = state.currentMediaIndex === post.media_items.length - 1;
}

function navigateMedia(direction) {
    if (!state.currentPost) return;
    
    const newIndex = state.currentMediaIndex + direction;
    if (newIndex < 0 || newIndex >= state.currentPost.media_items.length) return;
    
    state.currentMediaIndex = newIndex;
    renderCurrentMedia();
}

function closeMediaModal() {
    elements.mediaModal.classList.remove('active');
    document.body.style.overflow = '';
    
    // Pause any playing video
    const video = elements.mediaViewer.querySelector('video');
    if (video) video.pause();
    
    state.currentPost = null;
}

function openSettingsModal() {
    elements.settingsModal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeSettingsModal() {
    elements.settingsModal.classList.remove('active');
    document.body.style.overflow = '';
}

// ===== Thumbnail Preview =====
function showThumbnailPreview(path, e) {
    const preview = elements.thumbnailPreview;
    preview.querySelector('img').src = `/media/${path}`;
    preview.classList.add('visible');
    moveThumbnailPreview(e);
}

function moveThumbnailPreview(e) {
    const preview = elements.thumbnailPreview;
    const previewHeight = 220; // Approximate max height including margin
    const previewWidth = 180;  // Approximate width including margin
    const margin = 20;
    
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    
    let x = e.clientX;
    let y;
    let transformY;
    
    // Check if thumbnail would go above viewport when positioned above cursor
    if (e.clientY - margin - previewHeight < 0) {
        // Position below cursor
        y = e.clientY + margin;
        transformY = '0%';
    } else {
        // Position above cursor (default)
        y = e.clientY - margin;
        transformY = '-100%';
    }
    
    // Check horizontal bounds
    let transformX = '-50%';
    if (x - previewWidth / 2 < 0) {
        x = margin;
        transformX = '0%';
    } else if (x + previewWidth / 2 > viewportWidth) {
        x = viewportWidth - margin;
        transformX = '-100%';
    }
    
    preview.style.left = x + 'px';
    preview.style.top = y + 'px';
    preview.style.transform = `translate(${transformX}, ${transformY})`;
}

function hideThumbnailPreview() {
    elements.thumbnailPreview.classList.remove('visible');
}

// ===== Storage =====
function saveTasksToStorage() {
    // Only keep last 50 tasks
    const tasksToSave = state.tasks.slice(0, 50);
    localStorage.setItem('tasks', JSON.stringify(tasksToSave));
}

function loadTasksFromStorage() {
    try {
        const saved = localStorage.getItem('tasks');
        if (saved) {
            state.tasks = JSON.parse(saved);
            renderTasks();
            updateTaskCount();
            
            // Resume polling for active tasks
            state.tasks.forEach((task) => {
                if (task.status === 'pending' || task.status === 'processing') {
                    startPolling(task.id);
                }
            });
        }
    } catch (err) {
        console.error('Load tasks error:', err);
    }
}

// ===== Utilities =====
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    
    return date.toLocaleDateString();
}

function showNotification(message, type = 'info') {
    // Simple notification - could be enhanced with a toast library
    console.log(`[${type.toUpperCase()}]`, message);
    
    // Create a simple toast
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'error' ? 'var(--error)' : 'var(--bg-elevated)'};
        color: ${type === 'error' ? 'white' : 'var(--text-primary)'};
        padding: 12px 24px;
        border-radius: var(--radius-md);
        font-size: 0.9rem;
        z-index: 2000;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        animation: fadeIn 0.2s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.2s ease';
        setTimeout(() => toast.remove(), 200);
    }, 3000);
}

