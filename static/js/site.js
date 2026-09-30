// Site-wide behaviour. Loaded on every page (see templates/base.html).
(function () {
  'use strict';

  // --- Header: menu button (narrow screens) and language switcher -----------
  var nav = document.getElementById('site-nav');
  if (nav) {
    var toggle = nav.querySelector('.nav-toggle');
    var langMenu = nav.querySelector('details.lang-switch');

    var setMenu = function (open) {
      nav.classList.toggle('menu-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    };

    toggle.addEventListener('click', function () {
      langMenu.removeAttribute('open');
      setMenu(!nav.classList.contains('menu-open'));
    });
    langMenu.addEventListener('toggle', function () {
      if (langMenu.open) setMenu(false);
    });

    // Close menus when clicking elsewhere or pressing Escape.
    document.addEventListener('click', function (event) {
      if (!nav.contains(event.target)) {
        setMenu(false);
        langMenu.removeAttribute('open');
      } else if (!langMenu.contains(event.target)) {
        langMenu.removeAttribute('open');
      }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        setMenu(false);
        langMenu.removeAttribute('open');
      }
    });
  }

  // --- Forms ------------------------------------------------------------------
  // <select data-autosubmit> submits its form as soon as the choice changes.
  document.addEventListener('change', function (event) {
    if (event.target.matches('select[data-autosubmit]')) {
      event.target.form.submit();
    }
  });

  // <form data-confirm="Question?"> asks before submitting.
  document.addEventListener('submit', function (event) {
    var message = event.target.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // <button data-copy="input-id" data-copied-label="Copied"> copies the input's value.
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-copy]');
    if (!button) return;
    var input = document.getElementById(button.getAttribute('data-copy'));
    var done = function () {
      var original = button.textContent;
      button.textContent = button.getAttribute('data-copied-label') || original;
      setTimeout(function () { button.textContent = original; }, 2000);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(input.value).then(done);
    } else {
      input.select();  // fallback: select the text so it can be copied manually
    }
  });

  // --- Guidebook: expand and collapse steps -----------------------------------
  document.addEventListener('click', function (event) {
    var header = event.target.closest('.gb-step-header');
    if (header) {
      header.parentElement.classList.toggle('open');
    }
  });
})();
