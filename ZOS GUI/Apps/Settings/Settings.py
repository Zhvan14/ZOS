import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.textinput import TextInput
from kivy.network.urlrequest import UrlRequest

# Path to the settings file
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.txt")

class FileBrowserPopup(Popup):
    def __init__(self, on_select, **kwargs):
        super().__init__(**kwargs)
        self.on_select = on_select
        self.title = 'Select a Wallpaper'
        self.size_hint = (0.9, 0.9)

        main_layout = BoxLayout(orientation='vertical', spacing=10)
        
        self.filechooser = FileChooserListView(
            path='/storage/emulated/0/',
            filters=['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp'],
            multiselect=False
        )
        main_layout.add_widget(self.filechooser)
        
        button_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        
        select_button = Button(text='Select')
        select_button.bind(on_release=self.select_file)
        button_layout.add_widget(select_button)

        cancel_button = Button(text='Cancel')
        cancel_button.bind(on_release=self.dismiss)
        button_layout.add_widget(cancel_button)

        main_layout.add_widget(button_layout)
        self.content = main_layout
    
    def select_file(self, instance):
        selected = self.filechooser.selection
        if selected:
            self.on_select(selected[0])
            self.dismiss()

class SettingsApp(App):
    def build(self, app_args={}):
        self.settings = self.load_settings()
        
        layout = BoxLayout(orientation='vertical', spacing=20, padding=40)
        layout.add_widget(Label(text="Settings", font_size='24sp'))
        
        # City selection setting with TextInput
        city_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        city_box.add_widget(Label(text="Enter City for Weather:"))
        self.city_input = TextInput(
            text=self.settings.get('city', ''),
            size_hint=(0.7, 1),
            multiline=False
        )
        self.city_input.bind(on_text_validate=self.validate_city)
        city_box.add_widget(self.city_input)
        layout.add_widget(city_box)

        self.validation_status_label = Label(
            text="", 
            color=(1, 1, 1, 1), 
            size_hint_y=None, 
            height=30
        )
        layout.add_widget(self.validation_status_label)

        # Wallpaper setting
        wallpaper_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        wallpaper_box.add_widget(Label(text="Set Custom Wallpaper:"))
        
        wallpaper_buttons_box = BoxLayout(orientation='horizontal', spacing=10)
        
        self.wallpaper_path_label = Label(text=self.settings.get('custom_wallpaper_path', 'No custom wallpaper set.'), font_size='14sp', shorten=True, text_size=(Window.width * 0.3, None))
        wallpaper_buttons_box.add_widget(self.wallpaper_path_label)
        
        choose_btn = Button(text="Choose")
        choose_btn.bind(on_release=self.open_file_browser)
        wallpaper_buttons_box.add_widget(choose_btn)

        reset_btn = Button(text="Reset")
        reset_btn.bind(on_release=self.reset_wallpaper)
        wallpaper_buttons_box.add_widget(reset_btn)

        wallpaper_box.add_widget(wallpaper_buttons_box)
        
        layout.add_widget(wallpaper_box)
        
        # Save button
        save_button = Button(text="Save Settings", size_hint_y=None, height=50)
        save_button.bind(on_press=self.save_settings)
        layout.add_widget(save_button)

        return layout

    def load_settings(self):
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                for line in f.readlines():
                    try:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value
                    except ValueError:
                        pass
        return settings

    def validate_city(self, instance):
        city = instance.text.strip()
        if not city:
            self.validation_status_label.text = "Please enter a city."
            self.validation_status_label.color = (1, 0, 0, 1)
            self.city_input.focus = True
            return
        
        self.validation_status_label.text = "Checking city..."
        self.validation_status_label.color = (1, 1, 0, 1)
        
        # Replace spaces with hyphens to improve server recognition for multi-word cities
        formatted_city = city.replace(' ', '-')
        url = f"https://wttr.in/{formatted_city}?format=j1"

        UrlRequest(
            url, 
            on_success=self.on_city_valid, 
            on_failure=self.on_connection_failed, 
            on_error=self.on_city_not_found, 
            timeout=5
        )

    def on_city_valid(self, req, result):
        if not isinstance(result, dict) or 'current_condition' not in result:
            self.on_city_not_found(req, result)
        else:
            self.settings['city'] = self.city_input.text.strip()
            self.validation_status_label.text = "City is valid! Set successfully."
            self.validation_status_label.color = (0, 1, 0, 1)
            self.city_input.focus = True
            self.city_input.text = ''

    def on_connection_failed(self, req, result):
        self.validation_status_label.text = "Network connection failed. Try again."
        self.validation_status_label.color = (1, 0, 0, 1)
        self.city_input.focus = True
        self.city_input.text = ''

    def on_city_not_found(self, req, result):
        self.validation_status_label.text = "City not found."
        self.validation_status_label.color = (1, 0, 0, 1)
        self.city_input.focus = True
        self.city_input.text = ''

    def open_file_browser(self, instance):
        file_browser = FileBrowserPopup(on_select=self.on_file_selected)
        file_browser.open()
        self.city_input.focus = True

    def on_file_selected(self, filepath):
        self.settings['custom_wallpaper_path'] = filepath
        self.wallpaper_path_label.text = filepath

    def reset_wallpaper(self, instance):
        self.settings.pop('custom_wallpaper_path', None)
        self.wallpaper_path_label.text = 'No custom wallpaper set.'

    def save_settings(self, instance):
        with open(SETTINGS_FILE, 'w') as f:
            for key, value in self.settings.items():
                f.write(f"{key}={value}\n")
        
        status_label = Label(text="Settings saved!", color=(0,1,0,1))
        
        popup = Popup(title='Success', content=status_label, size_hint=(0.6, 0.2))
        popup.open()
        
        Clock.schedule_once(popup.dismiss, 1.5)
        Clock.schedule_once(lambda dt: setattr(self.city_input, 'focus', True), 1.6)

if __name__ == '__main__':
    SettingsApp().run()
