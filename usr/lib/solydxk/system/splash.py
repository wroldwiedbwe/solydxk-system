#! /usr/bin/env python3

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk, Gdk
from threading import Thread
from os.path import exists

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('solydxk-system')


class Splash(Thread):
    def __init__(self, width=400, height=250, title=None, foreground_color=None, background_color=None, background_image=None, icon_name=None):
        super(Splash, self).__init__()
        #self.daemon = True
        
        # Set dimensions
        self.width = width
        self.height = height
        
        # Set title
        if title is None:
            title = ''
        self.title = title
        
        # Set foreground color
        if foreground_color is None:
            foreground_color = '000000'
        foreground_color = foreground_color.strip('#')
        if len(foreground_color) == 6:
            foreground_color += 'ff'
        self.foreground_color = foreground_color
        #print(">>> foreground_color = %s" % self.foreground_color)
        
        # Set background color
        if background_color is None:
            background_color = 'ffffff'
        background_color = background_color.strip('#')
        if len(background_color) == 6:
            background_color += 'ff'
        self.background_color = background_color
        #print(">>> background_color = %s" % self.background_color)
        self.background_color_rgba = tuple(int(self.background_color[i:i+2], 16) for i in (0, 2 ,4, 6))
        #print(">>> background_color_rgba = %s" % str(self.background_color_rgba))
        
        # Set background image
        self.background_image = background_image
        
        # Set icon
        self.icon_name = icon_name
        
        # Set window position and decoration
        self.window = Gtk.Window()
        self.window.set_default_size(self.width, self.height)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_decorated(False)
        if self.icon_name is not None:
            self.window.set_icon_name(self.icon_name)
        self.window.set_title(self.title)
        self.window.connect("destroy", Gtk.main_quit)
        
        # Set background color
        r = 0
        if self.background_color_rgba[0] > 0:
            r = 1 / (255 / self.background_color_rgba[0])
        g = 0
        if self.background_color_rgba[1] > 0:
            g = 1 / (255 / self.background_color_rgba[1])
        b = 0
        if self.background_color_rgba[2] > 0:
            b = 1 / (255 / self.background_color_rgba[2])
        a = 0
        if self.background_color_rgba[3] > 0:
            a = 1 / (255 / self.background_color_rgba[3])
        self.window.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(r, g, b, a))
                                                                             
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
        box.set_margin_bottom(60)
        # Add the box to a new overlay in the existing overlay
        overlay.add_overlay(box)
        #self.window.add(box)
        if self.title:
            lbl_title = Gtk.Label()
            lbl_title.set_markup('<span font="18" foreground="#{}">{}</span>'.format(self.foreground_color, self.title))
            box.pack_start(lbl_title, True, True, 0)
        lbl_loading = Gtk.Label()
        lbl_loading.set_markup('<span font="24" weight="bold" foreground="#{}">{}</span>'.format(self.foreground_color, _("Loading")))
        box.pack_start(lbl_loading, True, True, 0)
        
        # Adding a spinner crashes Gtk sometimes and prevents the main window to show:
        # Gdk-CRITICAL **: _gdk_frame_clock_freeze: assertion 'GDK_IS_FRAME_CLOCK (clock)' failed
        spinner = Gtk.Spinner()
        spinner.start()
        box.pack_start(spinner, True, True, 0)

    def run(self):
        # Show the splash screen without causing startup notification
        # https://developer.gnome.org/gtk3/stable/GtkWindow.html#gtk-window-set-auto-startup-notification
        self.window.set_auto_startup_notification(False)
        self.window.show_all()
        self.window.set_auto_startup_notification(True)
        
        # Ensure the splash is completely drawn before moving on
        # Somehow I need this before calling Gtk.main or else the main UI might not show up
        while Gtk.events_pending():
            Gtk.main_iteration()
        
        # This looks dirty but without it the window isn't drawn
        Gtk.main()
        
    def destroy(self):
        self.window.destroy()
