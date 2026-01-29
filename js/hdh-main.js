/**
 * ============================================================================
 * 匯東華官網 - 主要 JavaScript
 * ============================================================================
 * 版本：v1.0
 * 建立日期：2026-01-29
 * 依據：html-css-spec v1.1
 *
 * 功能：
 * - 導覽列互動（漢堡選單、子選單展開）
 * - 搜尋功能
 * - 捲動效果（Header 陰影、返回頂部）
 * - 課程輪播（基本實作）
 * ============================================================================
 */

(function() {
  'use strict';

  // 命名空間
  window.HDH = window.HDH || {};

  /**
   * DOM Ready
   */
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  /**
   * ========================================================================
   * 導覽列功能
   * ========================================================================
   */
  HDH.Nav = {
    init: function() {
      this.header = document.querySelector('.hdh-header');
      this.nav = document.querySelector('.hdh-nav');
      this.toggle = document.querySelector('.hdh-nav__toggle');
      this.mobileMenu = document.querySelector('.hdh-nav__mobile');

      if (!this.nav) return;

      this.bindEvents();
      this.initDesktopSubmenus();
      this.initMobileSubmenus();
    },

    bindEvents: function() {
      var self = this;

      // 漢堡選單切換
      if (this.toggle) {
        this.toggle.addEventListener('click', function(e) {
          e.preventDefault();
          self.toggleMobileMenu();
        });
      }

      // 點擊外部關閉選單
      document.addEventListener('click', function(e) {
        if (self.nav && self.nav.classList.contains('hdh-nav--open')) {
          if (!self.nav.contains(e.target) && !self.toggle.contains(e.target)) {
            self.closeMobileMenu();
          }
        }
      });

      // ESC 鍵關閉選單
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && self.nav.classList.contains('hdh-nav--open')) {
          self.closeMobileMenu();
          self.toggle.focus();
        }
      });
    },

    toggleMobileMenu: function() {
      var isOpen = this.nav.classList.toggle('hdh-nav--open');
      this.toggle.setAttribute('aria-expanded', isOpen);

      if (isOpen) {
        // 鎖定 body 捲動
        document.body.style.overflow = 'hidden';
        // Focus 第一個連結
        var firstLink = this.mobileMenu.querySelector('a');
        if (firstLink) firstLink.focus();
      } else {
        document.body.style.overflow = '';
      }
    },

    closeMobileMenu: function() {
      this.nav.classList.remove('hdh-nav--open');
      this.toggle.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    },

    initDesktopSubmenus: function() {
      var submenuItems = document.querySelectorAll('.hdh-nav__item--has-submenu');

      submenuItems.forEach(function(item) {
        var link = item.querySelector('.hdh-nav__link--has-submenu');
        var submenu = item.querySelector('.hdh-nav__submenu');

        if (!link || !submenu) return;

        // 設定初始 aria 屬性
        link.setAttribute('aria-expanded', 'false');
        link.setAttribute('aria-haspopup', 'true');

        // Hover 事件
        item.addEventListener('mouseenter', function() {
          link.setAttribute('aria-expanded', 'true');
        });

        item.addEventListener('mouseleave', function() {
          link.setAttribute('aria-expanded', 'false');
        });

        // 鍵盤導覽
        link.addEventListener('keydown', function(e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            var isExpanded = link.getAttribute('aria-expanded') === 'true';
            link.setAttribute('aria-expanded', !isExpanded);
          }

          if (e.key === 'ArrowDown') {
            e.preventDefault();
            var firstSubmenuLink = submenu.querySelector('a');
            if (firstSubmenuLink) firstSubmenuLink.focus();
          }
        });

        // 子選單鍵盤導覽
        var submenuLinks = submenu.querySelectorAll('a');
        submenuLinks.forEach(function(subLink, index) {
          subLink.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              var next = submenuLinks[index + 1] || submenuLinks[0];
              next.focus();
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault();
              var prev = submenuLinks[index - 1] || link;
              prev.focus();
            }
            if (e.key === 'Escape') {
              link.setAttribute('aria-expanded', 'false');
              link.focus();
            }
          });
        });
      });
    },

    initMobileSubmenus: function() {
      var mobileItems = document.querySelectorAll('.hdh-nav__mobile-item--has-submenu');

      mobileItems.forEach(function(item) {
        var toggleBtn = item.querySelector('.hdh-nav__mobile-toggle');
        var link = item.querySelector('.hdh-nav__mobile-link');

        if (toggleBtn) {
          toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            item.classList.toggle('hdh-nav__mobile-item--open');
          });
        }

        // 或者點擊連結也展開（如果是父選單）
        if (link && link.getAttribute('aria-haspopup') === 'true') {
          link.addEventListener('click', function(e) {
            e.preventDefault();
            item.classList.toggle('hdh-nav__mobile-item--open');
          });
        }
      });
    }
  };

  /**
   * ========================================================================
   * 搜尋功能
   * ========================================================================
   */
  HDH.Search = {
    init: function() {
      this.desktopInput = document.getElementById('search-input');
      this.desktopBtn = document.querySelector('.hdh-search__btn');
      this.mobileInput = document.querySelector('.hdh-nav__mobile-search-input');

      this.bindEvents();
    },

    bindEvents: function() {
      var self = this;

      // Desktop 搜尋
      if (this.desktopInput && this.desktopBtn) {
        this.desktopBtn.addEventListener('click', function(e) {
          e.preventDefault();
          self.performSearch(self.desktopInput.value);
        });

        this.desktopInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            self.performSearch(self.desktopInput.value);
          }
        });
      }

      // Mobile 搜尋
      if (this.mobileInput) {
        this.mobileInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            self.performSearch(self.mobileInput.value);
          }
        });
      }
    },

    performSearch: function(query) {
      query = query.trim();
      if (query) {
        // 使用 Google 站內搜尋
        var url = 'https://www.google.com/search?q=site:medatatw.com+' + encodeURIComponent(query);
        window.open(url, '_blank');
      }
    }
  };

  /**
   * ========================================================================
   * 捲動效果
   * ========================================================================
   */
  HDH.Scroll = {
    init: function() {
      this.header = document.querySelector('.hdh-header');
      this.backToTop = document.querySelector('.hdh-footer__back-to-top');
      this.scrollThreshold = 100;

      this.bindEvents();
    },

    bindEvents: function() {
      var self = this;
      var ticking = false;

      window.addEventListener('scroll', function() {
        if (!ticking) {
          window.requestAnimationFrame(function() {
            self.onScroll();
            ticking = false;
          });
          ticking = true;
        }
      });

      // 返回頂部按鈕
      if (this.backToTop) {
        this.backToTop.addEventListener('click', function(e) {
          e.preventDefault();
          self.scrollToTop();
        });
      }
    },

    onScroll: function() {
      var scrollY = window.scrollY || window.pageYOffset;

      // Header 陰影
      if (this.header) {
        if (scrollY > this.scrollThreshold) {
          this.header.classList.add('hdh-header--scrolled');
        } else {
          this.header.classList.remove('hdh-header--scrolled');
        }
      }

      // 返回頂部按鈕顯示
      if (this.backToTop) {
        if (scrollY > 300) {
          this.backToTop.classList.add('hdh-footer__back-to-top--visible');
        } else {
          this.backToTop.classList.remove('hdh-footer__back-to-top--visible');
        }
      }
    },

    scrollToTop: function() {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  };

  /**
   * ========================================================================
   * 課程輪播（基本實作，可搭配 Slick 使用）
   * ========================================================================
   */
  HDH.Carousel = {
    init: function() {
      // 如果使用 jQuery + Slick
      if (typeof jQuery !== 'undefined' && typeof jQuery.fn.slick !== 'undefined') {
        this.initSlick();
      }
    },

    initSlick: function() {
      var $ = jQuery;

      // 課程輪播
      if ($('.hdh-courses-carousel').length) {
        $('.hdh-courses-carousel').slick({
          dots: true,
          arrows: true,
          infinite: true,
          speed: 500,
          slidesToShow: 3,
          slidesToScroll: 1,
          autoplay: true,
          autoplaySpeed: 5000,
          pauseOnHover: true,
          responsive: [
            {
              breakpoint: 992,
              settings: {
                slidesToShow: 2
              }
            },
            {
              breakpoint: 576,
              settings: {
                slidesToShow: 1,
                arrows: false
              }
            }
          ]
        });
      }

      // Banner 輪播
      if ($('.hdh-banner-carousel').length) {
        $('.hdh-banner-carousel').slick({
          dots: true,
          arrows: false,
          infinite: true,
          speed: 500,
          slidesToShow: 1,
          slidesToScroll: 1,
          autoplay: true,
          autoplaySpeed: 4000,
          fade: true,
          cssEase: 'linear'
        });
      }
    }
  };

  /**
   * ========================================================================
   * 平滑滾動到錨點
   * ========================================================================
   */
  HDH.SmoothScroll = {
    init: function() {
      var links = document.querySelectorAll('a[href^="#"]');

      links.forEach(function(link) {
        link.addEventListener('click', function(e) {
          var targetId = this.getAttribute('href');
          if (targetId === '#' || targetId === '#!') return;

          var target = document.querySelector(targetId);
          if (target) {
            e.preventDefault();
            var headerHeight = document.querySelector('.hdh-header')?.offsetHeight || 0;
            var targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;

            window.scrollTo({
              top: targetPosition,
              behavior: 'smooth'
            });
          }
        });
      });
    }
  };

  /**
   * ========================================================================
   * Hero 區塊滾動提示
   * ========================================================================
   */
  HDH.Hero = {
    init: function() {
      var scrollHint = document.querySelector('.hdh-hero__scroll-hint');

      if (scrollHint) {
        scrollHint.addEventListener('click', function() {
          var nextSection = document.querySelector('.hdh-hero').nextElementSibling;
          if (nextSection) {
            var headerHeight = document.querySelector('.hdh-header')?.offsetHeight || 0;
            var targetPosition = nextSection.getBoundingClientRect().top + window.pageYOffset - headerHeight;

            window.scrollTo({
              top: targetPosition,
              behavior: 'smooth'
            });
          }
        });
      }
    }
  };

  /**
   * ========================================================================
   * 初始化
   * ========================================================================
   */
  HDH.init = function() {
    HDH.Nav.init();
    HDH.Search.init();
    HDH.Scroll.init();
    HDH.Carousel.init();
    HDH.SmoothScroll.init();
    HDH.Hero.init();

    console.log('[HDH] 匯東華官網 JavaScript 已初始化');
  };

  // DOM Ready 後初始化
  ready(function() {
    HDH.init();
  });

})();
