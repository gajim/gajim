# For ArchLinux #
#################

pkgname=gajim
pkgver=0.6.1
pkgrel=1
pkgdesc="Gajim is a GTK Jabber client"
url="http://www.gajim.org"
license="GPL"
depends=(pygtk)
source=($url/downloads/$pkgname-$pkgver.tar.bz2)
md5sums=(8175a3ccf93093f23865baebe4fa82f8)

build() {
  cd $startdir/src/$pkgname-$pkgver
  make || return 1
  make DESTDIR=$startdir/pkg install
}
