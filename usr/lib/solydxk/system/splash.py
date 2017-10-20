#! /usr/bin/env python3
# ====================================================================
# Splash screen
#
# Initiate and start the Splash screen:
# from splash import Splash
# splash = Splash(title='Splash Screen')
#     Other arguments: width, height, font_size, font_color, background_color, background_image
#     width and height are ignored when background_image is used
# splash.start()
#
# When done:
# splash.destroy()
# ====================================================================

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk, Gdk
from threading import Thread
from os.path import exists


class Splash(Thread):
    def __init__(self, title, width=400, height=250, font_size=16, font_color='000000', background_color='ffffff', background_image=None):
        super(Splash, self).__init__()
        #Thread.__init__(self)
        self.font_size = font_size
        self.background_image = background_image
        self.width = width
        self.height = height
        self.title = title
        self.font_color = self.prep_hex_color(font_color)
        self.background_color_rgba = self.hex_to_rgba(background_color, True)
        self.parent = next((w for w in Gtk.Window.list_toplevels() if w.get_title()), None)

        # Window settings
        self.window = Gtk.Window(Gtk.WindowType.POPUP)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        #self.window.set_decorated(False)
        self.window.set_title(self.title)
        self.window.connect("destroy", Gtk.main_quit)
        self.window.connect("delete-event", Gtk.main_quit)
        # Set background color
        self.window.override_background_color(Gtk.StateType.NORMAL, self.background_color_rgba)
        # Set this window modal if a parent is found
        if self.parent is not None:
            self.window.set_modal(True)

        # Create overlay with a background image
        overlay = Gtk.Overlay()
        self.window.add(overlay)
        if exists(self.background_image):
            # Window will adjust to image size automatically
            bg = Gtk.Image.new_from_file(self.background_image)
            overlay.add(bg)
        else:
            # Set window dimensions
            self.window.set_default_size(self.width, self.height)

        # Add box with labels and a spinner
        # markup format: https://developer.gnome.org/pango/stable/PangoMarkupFormat.html
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(self.height / 4)
        # Add the box to a new overlay in the existing overlay
        overlay.add_overlay(box)
        lbl_title = Gtk.Label()
        lbl_title.set_markup('<span font="{}" foreground="#{}">{}</span>'.format(self.font_size, self.font_color, self.title))
        box.pack_start(lbl_title, False, False, 0)

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

        # Need to call Gtk.main to draw all widgets
        Gtk.main()

    def prep_hex_color(self, hex_color):
        hex_color = hex_color.strip('#')
        # Fill up with last character until length is 6 characters
        if len(hex_color) < 6:
            hex_color = hex_color.ljust(6, hex_color[-1])
        # Add alpha if it's not there
        hex_color = hex_color.ljust(8, 'f')
        return hex_color

    def hex_to_rgba(self, hex_color, as_gdk_rgba=False):
        hex_color = self.prep_hex_color(hex_color)
        # Create a list with rgba values from hex_color
        rgba = list(int(hex_color[i : i + 2], 16) for i in (0, 2 ,4, 6))
        if as_gdk_rgba:
            # Change values to float between 0 and 1 for Gdk.RGBA
            for i, val in enumerate(rgba):
                if val > 0:
                    rgba[i] = 1 / (255 / val)
            # Return the Gdk.RGBA object
            return Gdk.RGBA(rgba[0], rgba[1], rgba[2], rgba[3])
        return rgba

    def destroy(self):
        self.window.destroy()
