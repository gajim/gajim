import gtk, syncmenu


open_item = None
copy_item = None


def menu_item_activate_cb(item, user_data):
	print "Item activated: %s" % user_data

	#g_object_get (G_OBJECT (copy_item),
	#            "visible", &visible,
	#            "sensitive", &sensitive,
	#            NULL)

	#if (item == open_item) {
	#gtk_widget_set_sensitive (copy_item, !sensitive)
	#/*g_object_set (G_OBJECT (copy_item), "visible", !visible, NULL)*/


def test_setup_menu():
	global open_item, copy_item
	menubar = gtk.MenuBar()

	item = gtk.MenuItem("File")
	menubar.append(item)
	menu = gtk.Menu()
	item.set_submenu(menu)
	item = gtk.MenuItem("Open")
	open_item = item
	item.connect("activate", menu_item_activate_cb, "open")
	menu.append(item)
	item = gtk.MenuItem("Quit")
	item.connect("activate", menu_item_activate_cb, "quit")
	menu.append(item)

	item = gtk.MenuItem("Edit")

	menubar.append(item)
	menu = gtk.Menu()
	item.set_submenu(menu)
	item = gtk.MenuItem("Copy")
	copy_item = item
	item.connect("activate", menu_item_activate_cb, "copy")
	menu.append(item)
	item = gtk.MenuItem("Paste")
	item.connect("activate", menu_item_activate_cb, "paste")
	menu.append(item)

	item = gtk.MenuItem("Help")
	menubar.append(item)
	menu = gtk.Menu()
	item.set_submenu(menu)
	item = gtk.MenuItem("About")
	item.connect("activate", menu_item_activate_cb, "about")
	menu.append(item)

	return menubar


window = gtk.Window(gtk.WINDOW_TOPLEVEL)
window.set_default_size(400, 300)
window.connect("destroy", gtk.main_quit, None)

vbox = gtk.VBox(False, 0)
window.add(vbox)

menubar = test_setup_menu()
vbox.pack_start(menubar, False, True, 0)
vbox.pack_start(gtk.Label("Some window content here"), True, True, 0)

window.show_all()
menubar.hide()

syncmenu.takeover_menu(menubar)

gtk.main()

# vim: se ts=3:
