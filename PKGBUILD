pkgname=mechanical-keyboard-debounce
pkgver=0.1.1
pkgrel=1
pkgdesc="Debounce filter for a specific evdev keyboard device using a virtual uinput keyboard"
arch=('any')
url="https://github.com/awsms/mechanical-keyboard-debounce"
license=('WTFPL')
depends=('python' 'python-evdev')
source=('debounce.py'
        'mechanical-keyboard-debounce.service')
sha256sums=('4fc3891ec58297fc70e3b61f5f8e005e8af6456121cb862a20a80cf82e789a5d'
            'SKIP')

package() {
  install -Dm755 "${srcdir}/debounce.py" "${pkgdir}/usr/local/bin/debounce.py"
  install -Dm644 "${srcdir}/mechanical-keyboard-debounce.service" \
    "${pkgdir}/usr/lib/systemd/system/mechanical-keyboard-debounce.service"
}
