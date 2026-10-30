document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.login-password-toggle, .register-password-toggle').forEach(function (button) {
    button.addEventListener('click', function () {
      const targetId = button.dataset.target || button.dataset.toggle;
      const input = (targetId && document.getElementById(targetId))
        || button.closest('.login-password, .sirkula-register-password')?.querySelector('input');
      if (!input) return;

      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(visible));
      button.setAttribute('aria-label', visible ? 'Sembunyikan password' : 'Tampilkan password');
      const icon = button.querySelector('.password-toggle-icon');
      if (icon) icon.src = visible ? button.dataset.eyeOpen : button.dataset.eyeClosed;
    });
  });

  document.querySelectorAll('[data-toast]').forEach(function (toast) {
    let timeout;
    const dismiss = function () {
      window.clearTimeout(timeout);
      toast.classList.add('is-leaving');
      window.setTimeout(function () { toast.remove(); }, 200);
    };

    toast.querySelector('[data-dismiss-message]')?.addEventListener('click', dismiss);
    timeout = window.setTimeout(dismiss, 1800);
  });

  document.querySelectorAll('[data-avatar-input]').forEach(function (input) {
    const preview = document.querySelector('[data-avatar-preview]');
    const fallback = document.querySelector('[data-avatar-fallback]');
    const error = document.querySelector('[data-avatar-error]');
    const originalPreview = preview && preview.getAttribute('src');
    let previewUrl;

    input.addEventListener('change', function () {
      const file = input.files && input.files[0];
      if (error) {
        error.textContent = '';
        error.hidden = true;
      }
      if (!file) return;

      if (!file.type.startsWith('image/') || file.size > 2 * 1024 * 1024) {
        if (error) {
          error.textContent = file.size > 2 * 1024 * 1024
            ? 'Ukuran foto maksimal 2 MB.'
            : 'Pilih file gambar yang valid.';
          error.hidden = false;
        }
        input.value = '';
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = undefined;
        if (preview) {
          preview.src = originalPreview || '';
          preview.hidden = !originalPreview;
        }
        if (fallback) fallback.hidden = Boolean(originalPreview);
        return;
      }

      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(file);
      if (preview) {
        preview.src = previewUrl;
        preview.hidden = false;
      }
      if (fallback) fallback.hidden = true;
    });
  });
});
