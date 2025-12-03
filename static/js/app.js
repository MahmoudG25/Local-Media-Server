// app.js - Enhanced functionality for Local Media Server

(function () {
  'use strict';

  // ============ IMAGE VIEWER / LIGHTBOX ============
  
  class ImageViewer {
    constructor() {
      this.currentIndex = 0;
      this.images = [];
      this.modal = null;
      this.init();
    }

    init() {
      // Create modal structure
      this.createModal();
      // Bind image clicks
      this.bindImageClicks();
      // Keyboard navigation
      document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    createModal() {
      this.modal = document.createElement('div');
      this.modal.className = 'image-modal';
      this.modal.innerHTML = `
        <div class="image-modal-overlay"></div>
        <div class="image-modal-content">
          <button class="image-modal-close" aria-label="Close">&times;</button>
          <button class="image-modal-prev" aria-label="Previous">‹</button>
          <button class="image-modal-next" aria-label="Next">›</button>
          <img src="" alt="Image preview" class="image-modal-img">
          <div class="image-modal-info"></div>
        </div>
      `;
      document.body.appendChild(this.modal);

      // Event listeners
      this.modal.querySelector('.image-modal-close').addEventListener('click', () => this.close());
      this.modal.querySelector('.image-modal-prev').addEventListener('click', () => this.navigate(-1));
      this.modal.querySelector('.image-modal-next').addEventListener('click', () => this.navigate(1));
      this.modal.querySelector('.image-modal-overlay').addEventListener('click', () => this.close());
    }

    bindImageClicks() {
      // Find all image file cards and convert "View" buttons to open in modal
      document.addEventListener('click', (e) => {
        const imageLink = e.target.closest('a[href*="/download/"]');
        if (imageLink) {
          const fileCard = imageLink.closest('.file-card');
          if (fileCard && fileCard.querySelector('.file-icon')?.textContent.includes('🖼️')) {
            e.preventDefault();
            this.open(imageLink.href, fileCard);
          }
        }
      });
    }

    open(imageUrl, fileCard) {
      // Collect all images in the current view
      this.images = Array.from(document.querySelectorAll('.file-card'))
        .filter(card => card.querySelector('.file-icon')?.textContent.includes('🖼️'))
        .map(card => {
          const link = card.querySelector('a[href*="/download/"]');
          const name = card.querySelector('.file-name')?.textContent || '';
          const meta = card.querySelector('.file-meta')?.textContent || '';
          return {
            url: link?.href || '',
            name: name,
            meta: meta,
            card: card
          };
        });

      this.currentIndex = this.images.findIndex(img => img.url === imageUrl);
      if (this.currentIndex === -1) this.currentIndex = 0;

      this.show();
    }

    show() {
      if (this.images.length === 0) return;

      const current = this.images[this.currentIndex];
      const img = this.modal.querySelector('.image-modal-img');
      const info = this.modal.querySelector('.image-modal-info');

      img.src = current.url;
      info.innerHTML = `
        <div class="image-modal-name">${current.name}</div>
        <div class="image-modal-meta">${current.meta}</div>
        <div class="image-modal-counter">${this.currentIndex + 1} / ${this.images.length}</div>
      `;

      // Show/hide navigation buttons
      const prevBtn = this.modal.querySelector('.image-modal-prev');
      const nextBtn = this.modal.querySelector('.image-modal-next');
      prevBtn.style.display = this.images.length > 1 ? 'flex' : 'none';
      nextBtn.style.display = this.images.length > 1 ? 'flex' : 'none';

      this.modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    navigate(direction) {
      if (this.images.length <= 1) return;
      this.currentIndex = (this.currentIndex + direction + this.images.length) % this.images.length;
      this.show();
    }

    close() {
      this.modal.classList.remove('active');
      document.body.style.overflow = '';
    }

    handleKeyboard(e) {
      if (!this.modal.classList.contains('active')) return;
      
      switch(e.key) {
        case 'Escape':
          this.close();
          break;
        case 'ArrowLeft':
          this.navigate(-1);
          break;
        case 'ArrowRight':
          this.navigate(1);
          break;
      }
    }
  }

  // ============ VIDEO WAKE LOCK ============
  
  class VideoWakeLock {
    constructor() {
      this.wakeLock = null;
      this.isSupported = 'wakeLock' in navigator;
      this.init();
    }

    init() {
      // Find all video elements and attach event listeners
      const videos = document.querySelectorAll('video');
      videos.forEach(video => this.attachToVideo(video));

      // Handle visibility change (release lock when tab hidden)
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          this.release();
        } else {
          // Re-request if video is still playing
          const video = document.querySelector('video');
          if (video && !video.paused) {
            this.request();
          }
        }
      });
    }

    attachToVideo(video) {
      video.addEventListener('play', () => this.request());
      video.addEventListener('pause', () => this.release());
      video.addEventListener('ended', () => this.release());
    }

    async request() {
      if (!this.isSupported) {
        console.log('Wake Lock API not supported');
        return;
      }

      try {
        this.wakeLock = await navigator.wakeLock.request('screen');
        console.log('Screen wake lock active');

        this.wakeLock.addEventListener('release', () => {
          console.log('Screen wake lock released');
        });
      } catch (err) {
        console.error(`${err.name}, ${err.message}`);
      }
    }

    async release() {
      if (this.wakeLock) {
        try {
          await this.wakeLock.release();
          this.wakeLock = null;
        } catch (err) {
          console.error(`Failed to release wake lock: ${err}`);
        }
      }
    }
  }

  // ============ INITIALIZATION ============
  
  document.addEventListener('DOMContentLoaded', () => {
    // Initialize image viewer
    new ImageViewer();

    // Initialize video wake lock
    new VideoWakeLock();

    // Show wake lock support status (optional, can be removed)
    const video = document.querySelector('video');
    if (video && !('wakeLock' in navigator)) {
      console.log('💤 Wake Lock API not supported. Screen may sleep during playback.');
    }
  });

})();
