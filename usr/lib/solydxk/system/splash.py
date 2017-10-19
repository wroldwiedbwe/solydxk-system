#! /usr/bin/env python3

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk
from os.path import exists
from threading import Thread

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')


class Splash(Thread):
    def __init__(self, title=None, background_image=None, icon_name=None):
        super(Splash, self).__init__()
        self.daemon = True
        if title is None:
            title = ''
        self.title = title
        self.background_image = background_image
        self.icon_name = icon_name
        
        # Set position and decoration
        self.window = Gtk.Window()
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_decorated(False)
        if self.icon_name is not None:
            self.window.set_icon_name(self.icon_name)
        self.window.set_title(self.title)
        
        # Create overlay with a background image
        overlay = Gtk.Overlay()
        self.window.add(overlay)
        if exists(self.background_image):
            bg = Gtk.Image.new_from_file(self.background_image)
            overlay.add(bg)

        # Add box with labels and a spinner
        # markup format: https://developer.gnome.org/pango/stable/PangoMarkupFormat.html
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(30)
        box.set_margin_bottom(30)
        lbl_title = Gtk.Label()
        lbl_title.set_markup('<span font="18" foreground="#243e4b">{}</span>'.format(self.title))
        box.pack_start(lbl_title, True, True, 0)
        lbl_loading = Gtk.Label()
        lbl_loading.set_markup('<span font="24" weight="bold" foreground="#243e4b">{}...</span>'.format(_("Loading")))
        box.pack_start(lbl_loading, True, True, 0)
        spinner = Gtk.Spinner()
        spinner.start()
        box.pack_start(spinner, True, True, 0)
        
        # Add the box to a new overlay in the existing overlay
        overlay.add_overlay(box)

    def run(self):
        # Show the splash screen without causing startup notification
        # https://developer.gnome.org/gtk3/stable/GtkWindow.html#gtk-window-set-auto-startup-notification
        self.window.set_auto_startup_notification(False)
        self.window.show_all()
        self.window.set_auto_startup_notification(True)
        
        # This looks dirty but without it the window isn't drawn
        Gtk.main()
        
    def destroy(self):
        self.window.destroy()
        Gtk.main_quit()
