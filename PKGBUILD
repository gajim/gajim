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

build() {
  cd $startdir/src/$pkgname-$pkgver

  echo "making trayicon..."
  make trayicon || return 1 #remove this if you have gnome-python-extras
  echo "done."
  
  echo "making idle detection..."
  make idle || return 1
  echo "done."

  echo "making translations..."
  make translation || return 1
  echo "done."

  make DESTDIR=$startdir/pkg install
}
md5sums=('03e95969c68ffdbe34f7a4173f8fd4db')
