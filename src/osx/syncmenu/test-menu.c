#include <gtk/gtk.h>

#include "sync-menu.h"

GtkWidget *open_item;
GtkWidget *copy_item;

static void
menu_item_activate_cb (GtkWidget *item,
                       gpointer   user_data)
{
  gboolean visible;
  gboolean sensitive;

  g_print ("Item activated: %s\n", (gchar *) user_data);

  g_object_get (G_OBJECT (copy_item),
                "visible", &visible,
                "sensitive", &sensitive,
                NULL);

  if (item == open_item) {
    gtk_widget_set_sensitive (copy_item, !sensitive);
    /*g_object_set (G_OBJECT (copy_item), "visible", !visible, NULL);*/
  }
}

static GtkWidget *
test_setup_menu (void)
{
  GtkWidget *menubar;
  GtkWidget *menu;
  GtkWidget *item;
  
  menubar = gtk_menu_bar_new ();

  item = gtk_menu_item_new_with_label ("File");
  gtk_menu_shell_append (GTK_MENU_SHELL (menubar), item);
  menu = gtk_menu_new ();
  gtk_menu_item_set_submenu (GTK_MENU_ITEM (item), menu);
  item = gtk_menu_item_new_with_label ("Open");
  open_item = item;
  g_signal_connect (item, "activate", G_CALLBACK (menu_item_activate_cb), "open");
  gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);
  item = gtk_menu_item_new_with_label ("Quit");
  g_signal_connect (item, "activate", G_CALLBACK (menu_item_activate_cb), "quit");
  gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);

  item = gtk_menu_item_new_with_label ("Edit");

  gtk_menu_shell_append (GTK_MENU_SHELL (menubar), item);
  menu = gtk_menu_new ();
  gtk_menu_item_set_submenu (GTK_MENU_ITEM (item), menu);
  item = gtk_menu_item_new_with_label ("Copy");
  copy_item = item;
  g_signal_connect (item, "activate", G_CALLBACK (menu_item_activate_cb), "copy");
  gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);
  item = gtk_menu_item_new_with_label ("Paste");
  g_signal_connect (item, "activate", G_CALLBACK (menu_item_activate_cb), "paste");
  gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);

  item = gtk_menu_item_new_with_label ("Help");
  gtk_menu_shell_append (GTK_MENU_SHELL (menubar), item);
  menu = gtk_menu_new ();
  gtk_menu_item_set_submenu (GTK_MENU_ITEM (item), menu);
  item = gtk_menu_item_new_with_label ("About");
  g_signal_connect (item, "activate", G_CALLBACK (menu_item_activate_cb), "about");
  gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);

  return menubar;
}

int
main (int argc, char **argv)
{
  GtkWidget *window;
  GtkWidget *vbox;
  GtkWidget *menubar;

  gtk_init (&argc, &argv);

  window = gtk_window_new (GTK_WINDOW_TOPLEVEL);
  gtk_window_set_default_size (GTK_WINDOW (window), 400, 300);
  g_signal_connect (window, "destroy", G_CALLBACK (gtk_main_quit), NULL);

  vbox = gtk_vbox_new (FALSE, 0);
  gtk_container_add (GTK_CONTAINER (window), vbox);

  menubar = test_setup_menu ();
  gtk_box_pack_start (GTK_BOX (vbox), 
                      menubar,
                      FALSE, TRUE, 0);
  
  gtk_box_pack_start (GTK_BOX (vbox), 
                      gtk_label_new ("Some window content here"), 
                      TRUE, TRUE, 0);

  gtk_widget_show_all (window);

  gtk_widget_hide (menubar);

  sync_menu_takeover_menu (GTK_MENU_SHELL (menubar));

  gtk_main ();

  return 0;
}
