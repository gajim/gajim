# For ArchLinux #
#################

pkgname=gajim
pkgver=0.7
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
md5sums=('70d6b882c496ea7fbacc4222da49b125')
