pkgname=mechanical-keyboard-debounce
pkgver=0.1.0
pkgrel=1
pkgdesc="Debounce filter for a specific evdev keyboard device using a virtual uinput keyboard"
arch=('any')
url="https://github.com/awsms/mechanical-keyboard-debounce"
license=('WTFPL')
depends=('python' 'python-evdev')
source=('debounce.py'
        'mechanical-keyboard-debounce.service')
sha256sums=('9343809163e14706da6bcaf63987cb4c3c7b1ec413b891b04e3095461aa066a6'
            'SKIP')

package() {
  install -Dm755 "${srcdir}/debounce.py" "${pkgdir}/usr/local/bin/debounce.py"
  install -Dm644 "${srcdir}/mechanical-keyboard-debounce.service" \
    "${pkgdir}/usr/lib/systemd/system/mechanical-keyboard-debounce.service"
}
