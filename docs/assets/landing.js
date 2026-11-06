const root = document.documentElement
const arabic = root.lang === 'ar'
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')
const themeButton = document.querySelector('.theme-toggle')
const themeColor = document.querySelector('meta[name="theme-color"]')

function updateTheme() {
  const dark = root.dataset.theme === 'dark'
  themeButton?.setAttribute('aria-pressed', String(dark))
  themeButton?.setAttribute('aria-label', arabic ? (dark ? 'تفعيل المظهر الفاتح' : 'تفعيل المظهر الداكن') : (dark ? 'Activate light theme' : 'Activate dark theme'))
  themeColor?.setAttribute('content', dark ? '#101713' : '#f3f0e8')
}

updateTheme()
themeButton?.addEventListener('click', () => {
  root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark'
  try { localStorage.setItem('rtl-admin-theme', root.dataset.theme) } catch {}
  updateTheme()
})

const viewerCopy = {
  en: {
    en: ['English · LTR', 'Navigation left · filters right'],
    ar: ['Arabic · RTL', 'Navigation right · filters left'],
  },
  ar: {
    en: ['الإنجليزية · LTR', 'تنقّل يسار · مرشحات يمين'],
    ar: ['العربية · RTL', 'تنقّل يمين · مرشحات يسار'],
  },
}

document.querySelectorAll('[data-admin-viewer]').forEach((viewer) => {
  const image = viewer.querySelector('[data-admin-image]')
  const buttons = [...viewer.querySelectorAll('[data-view]')]
  const label = viewer.querySelector('[data-view-label]')
  const detail = viewer.querySelector('[data-view-detail]')
  let current = viewer.dataset.default || 'en'
  let switchTimer
  let autoplayTimer
  let stopped = false

  function render(language, animate = true) {
    if (!image || language === current && image.src === image.dataset[`src${language.toUpperCase()}`]) return
    current = language
    buttons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.view === language)))
    const apply = () => {
      image.src = language === 'ar' ? image.dataset.srcAr : image.dataset.srcEn
      image.alt = language === 'ar' ? image.dataset.altAr : image.dataset.altEn
      const copy = viewerCopy[arabic ? 'ar' : 'en'][language]
      if (label) label.textContent = copy[0]
      if (detail) detail.textContent = copy[1]
      viewer.classList.remove('is-switching')
    }
    clearTimeout(switchTimer)
    if (animate && !reducedMotion.matches) {
      viewer.classList.add('is-switching')
      switchTimer = setTimeout(apply, 140)
    } else {
      apply()
    }
  }

  function stopAutoplay() {
    stopped = true
    clearInterval(autoplayTimer)
  }

  buttons.forEach((button) => button.addEventListener('click', () => {
    stopAutoplay()
    render(button.dataset.view)
  }))

  const initial = current
  current = ''
  render(initial, false)

  if (viewer.dataset.autoplay === 'true' && !reducedMotion.matches) {
    autoplayTimer = setInterval(() => {
      if (!stopped && !document.hidden) render(current === 'en' ? 'ar' : 'en')
    }, 6500)
    viewer.addEventListener('pointerenter', () => clearInterval(autoplayTimer))
    viewer.addEventListener('pointerleave', () => {
      if (stopped) return
      clearInterval(autoplayTimer)
      autoplayTimer = setInterval(() => {
        if (!document.hidden) render(current === 'en' ? 'ar' : 'en')
      }, 6500)
    })
    viewer.addEventListener('focusin', stopAutoplay)
  }

  const preload = () => {
    const other = new Image()
    other.src = initial === 'ar' ? image.dataset.srcEn : image.dataset.srcAr
  }
  if ('requestIdleCallback' in window) requestIdleCallback(preload, { timeout: 2500 })
  else setTimeout(preload, 1200)
})

const copyStatus = document.querySelector('.copy-status')
let copyTimer

document.querySelectorAll('[data-copy-target]').forEach((button) => {
  button.addEventListener('click', async () => {
    const code = document.getElementById(button.dataset.copyTarget)
    if (!code) return
    const text = code.textContent.replace(/^\$\s*/, '')
    const label = button.querySelector('span')
    clearTimeout(copyTimer)
    try {
      await navigator.clipboard.writeText(text)
      if (label) label.textContent = arabic ? 'تم النسخ' : 'Copied'
      if (copyStatus) copyStatus.textContent = arabic ? 'نُسخت الشيفرة إلى الحافظة.' : 'Code copied to clipboard.'
      copyTimer = setTimeout(() => {
        if (label) label.textContent = arabic ? 'نسخ' : 'Copy'
        if (copyStatus) copyStatus.textContent = ''
      }, 2400)
    } catch {
      const range = document.createRange()
      range.selectNodeContents(code)
      const selection = window.getSelection()
      selection.removeAllRanges()
      selection.addRange(range)
      code.focus()
      if (copyStatus) copyStatus.textContent = arabic ? 'حدّد الشيفرة وانسخها يدويًا.' : 'Select and copy the code manually.'
    }
  })
})

const menu = document.querySelector('.mobile-menu')
menu?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => menu.removeAttribute('open')))
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') menu?.removeAttribute('open')
})
document.addEventListener('pointerdown', (event) => {
  if (menu?.open && !menu.contains(event.target)) menu.removeAttribute('open')
})
