import os
import sys
import subprocess
import threading
import importlib.util
import datetime
import requests
import tarfile
import tempfile
import shutil
import hashlib
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.animation import Animation
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

# ---------------- Fonts ----------------
try:
    LabelBase.register(name='RobotoThin', fn_regular='Assets/Roboto-Thin.ttf')
except IOError:
    print("Roboto-Thin.ttf not found. Using default font.")

# ---------------- Image Button ----------------
class ImageButton(ButtonBehavior, Image):
    pass

# ---------------- Splash Screen ----------------
class SplashScreen(Screen):
    def __init__(self, duration, next_callback, **kwargs):
        super().__init__(**kwargs)
        self.next_callback = next_callback
        layout = FloatLayout()
        
        with layout.canvas.before:
            Color(0, 0, 0, 1)
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_bg_rect, pos=self._update_bg_rect)

        try:
            splash_image_source = 'Assets/icon.png'
            if not os.path.exists(splash_image_source):
                splash_image_source = 'atlas://data/images/defaulttheme/bad-image'
            self.splash_image = Image(source=splash_image_source, size_hint=(0.5, 0.5), pos_hint={'center_x': 0.5, 'center_y': 0.5}, allow_stretch=True, keep_ratio=True)
            layout.add_widget(self.splash_image)
        except Exception as e:
            error_label = Label(text=f"Error: Could not load 'icon.png'\nDetails: {e}", color=(1, 0, 0, 1))
            layout.add_widget(error_label)
        
        self.add_widget(layout)
        Clock.schedule_once(lambda dt: self.next_callback(), duration)

    def _update_bg_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

# ---------------- Login Screen ----------------
class LoginScreen(Screen):
    def __init__(self, zos_app_instance, **kwargs):
        super().__init__(**kwargs)
        self.zos_app = zos_app_instance
        self.unlock_callback = self.zos_app.login
        
        layout = FloatLayout()
        self.add_widget(layout)

        with layout.canvas.before:
            Color(0,0,0,0.3)
            self.rect = Rectangle(size=Window.size, pos=(0,0))
        layout.bind(size=self.update_rect, pos=self.update_rect)

        self.login_layout = BoxLayout(orientation='vertical', spacing=10, padding=40, size_hint=(1,0.4), pos_hint={'center_x':0.5,'top':0.8})
        layout.add_widget(self.login_layout)

        self.time_label = Label(text="", font_size='80sp', color=(0.5,1,0.5,1), font_name='RobotoThin')
        self.date_label = Label(text="", font_size='25sp', color=(0.5,0.8,1,1), font_name='RobotoThin')
        self.weather_label = Label(text="Weather...", font_size='20sp', color=(0.8,1,0.8,1), font_name='RobotoThin')
        self.login_layout.add_widget(self.time_label)
        self.login_layout.add_widget(self.date_label)
        self.login_layout.add_widget(self.weather_label)

        self.unlock_container = BoxLayout(orientation='vertical', spacing=10, size_hint=(0.8, None), height=100, pos_hint={'center_x': 0.5, 'y': 0.05})
        layout.add_widget(self.unlock_container)

        self.swipe_hint = Label(text="Swipe up to unlock", font_size='20sp', color=(1,1,1,1), font_name='RobotoThin')
        self.password_input = TextInput(hint_text="Enter password", password=True, multiline=False,
                                        size_hint=(1, None), height=40,
                                        background_color=(0.2, 0.2, 0.2, 1), foreground_color=(1, 1, 1, 1))
        self.password_input.bind(on_text_validate=self.check_password)
        
        self.use_password = 'password' in self.zos_app.settings
        
        if self.use_password:
            self.unlock_container.add_widget(self.password_input)
        else:
            self.unlock_container.add_widget(self.swipe_hint)
            self.add_animation()

        self.swipe_start_y = None
        self.weather_last_update = None
        Clock.schedule_interval(self.update_clock, 1)

    def on_enter(self):
        """Called when the screen becomes the current screen."""
        if self.use_password:
            self.password_input.focus = True

    def check_password(self, instance):
        entered_password = instance.text
        stored_hash = self.zos_app.settings.get('password')
        
        if stored_hash and hashlib.sha256(entered_password.encode()).hexdigest() == stored_hash:
            self.unlock_callback()
        else:
            self.password_input.text = ''
            self.password_input.hint_text = 'Incorrect password, try again'
            self.password_input.focus = True
            
    def add_animation(self):
        anim = Animation(color=(1, 1, 1, 0.4), duration=1) + \
               Animation(color=(1, 1, 1, 1), duration=1)
        anim.repeat = True
        anim.start(self.swipe_hint)

    def on_touch_down(self, touch):
        if not self.use_password:
            self.swipe_start_y = touch.y
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if not self.use_password and self.swipe_start_y is not None and (touch.y - self.swipe_start_y > 150):
            self.unlock_callback()
        return super().on_touch_up(touch)

    def update_clock(self, dt):
        now = datetime.datetime.now()
        self.time_label.text = now.strftime("%I:%M")
        self.date_label.text = now.strftime("%A, %B %d, %Y")
        
        city = self.zos_app.settings.get('city')

        if self.weather_last_update is None or (datetime.datetime.now()-self.weather_last_update).total_seconds()>600:
            self.weather_last_update = datetime.datetime.now()
            threading.Thread(target=self.fetch_weather, args=(city,)).start()

    def fetch_weather(self, city=None):
        if not city:
            city = "Erbil"
        
        try:
            weather_info = requests.get(f"https://wttr.in/{city}?format=%C+%t",timeout=3).text
            Clock.schedule_once(lambda dt: self.update_weather_label(weather_info))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.update_weather_label("Weather N/A"))
            
    def update_weather_label(self, text):
        self.weather_label.text = text

    def update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

# ---------------- Setup Screen ----------------
class SetupScreen(Screen):
    def __init__(self, zos_app_instance, **kwargs):
        super().__init__(**kwargs)
        self.zos_app = zos_app_instance
        
        layout = BoxLayout(orientation='vertical', spacing=20, padding=40)
        layout.add_widget(Label(text="Welcome to ZOS!\nLet's get you set up.", font_size='24sp', halign='center', valign='middle'))
        
        city_box = BoxLayout(orientation='vertical', size_hint_y=None, height=100)
        city_box.add_widget(Label(text="Enter City for Weather:", size_hint_y=None, height=40))
        self.city_input = TextInput(hint_text="e.g., London or New York", multiline=False, size_hint_y=None, height=40, background_color=(0.2,0.2,0.2,1), foreground_color=(1,1,1,1))
        self.city_input.bind(on_text_validate=self.check_city)
        self.city_input.focus = True
        city_box.add_widget(self.city_input)
        self.city_status_label = Label(text="", size_hint_y=None, height=20, color=(1,1,1,1))
        city_box.add_widget(self.city_status_label)
        layout.add_widget(city_box)

        password_box = BoxLayout(orientation='vertical', size_hint_y=None, height=100)
        password_box.add_widget(Label(text="Create Password (optional):", size_hint_y=None, height=40))
        self.password_input = TextInput(hint_text="Leave blank to use swipe", password=True, multiline=False, size_hint_y=None, height=40, background_color=(0.2,0.2,0.2,1), foreground_color=(1,1,1,1))
        password_box.add_widget(self.password_input)
        layout.add_widget(password_box)
        
        save_button = Button(text="Save and Continue", size_hint_y=None, height=50)
        save_button.bind(on_press=self.save_setup)
        layout.add_widget(save_button)
        self.add_widget(layout)

    def check_city(self, instance):
        city = self.city_input.text.strip().replace(' ', '-')
        if not city:
            self.city_status_label.text = ""
            return
            
        def fetch_thread():
            try:
                response = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=5)
                is_valid = "Unknown location" not in response.text
                Clock.schedule_once(lambda dt: self.update_status(is_valid))
            except Exception:
                Clock.schedule_once(lambda dt: self.update_status(False))

        threading.Thread(target=fetch_thread).start()
    
    def update_status(self, is_valid):
        if is_valid:
            self.city_status_label.text = "City is valid."
            self.city_status_label.color = (0, 1, 0, 1)
        else:
            self.city_status_label.text = "City invalid or not supported."
            self.city_status_label.color = (1, 0, 0, 1)

    def save_setup(self, instance):
        city = self.city_input.text.strip().replace(' ', '-')
        password = self.password_input.text.strip()
        
        if self.city_status_label.text == "City invalid or not supported.":
            return

        settings = {}
        if city:
            settings['city'] = city
        
        if password:
            settings['password'] = hashlib.sha256(password.encode()).hexdigest()
        
        self.zos_app.settings = settings
        self.zos_app.save_settings()
        self.zos_app.on_setup_complete()

# ---------------- ZOS App ----------------
class ZOSApp(App):
    def build(self):
        self.logged_in = False
        self.current_process = None
        self.apps_dir = "Apps"
        self.settings_dir = os.path.join(self.apps_dir, 'Settings')
        self.settings_file = os.path.join(self.settings_dir, "settings.txt")
        
        self.main_layout = FloatLayout()
        
        self.wallpaper = Image(allow_stretch=True, keep_ratio=False)
        self.main_layout.add_widget(self.wallpaper)
        
        self.overlay = FloatLayout()
        self.main_layout.add_widget(self.overlay)

        self.sm = ScreenManager(transition=FadeTransition())
        self.overlay.add_widget(self.sm)
        
        self.load_settings()

        # Check for first-time run before adding any screens
        if not os.path.exists(self.settings_file):
            print("Settings file not found. Showing setup screen.")
            self.setup_screen = SetupScreen(zos_app_instance=self, name='setup')
            self.sm.add_widget(self.setup_screen)
            self.sm.current = 'setup'
        else:
            print("Settings file found. Showing splash screen.")
            self.splash = SplashScreen(duration=3, next_callback=self.show_login, name='splash')
            self.login = LoginScreen(zos_app_instance=self, name='login')
            self.main = Screen(name='main')
            self.app_screen = Screen(name='app')

            self.sm.add_widget(self.splash)
            self.sm.add_widget(self.login)
            self.sm.add_widget(self.main)
            self.sm.add_widget(self.app_screen)

            self.setup_main_screen()
            self.setup_app_screen()
            
            self.sm.current = 'splash'

        self.sm.bind(current=self.on_screen_change)
        self.load_and_apply_wallpaper()
        
        return self.main_layout

    def on_setup_complete(self):
        print("Setup complete. Initializing main screens.")
        # We need to re-initialize the other screens after setup is done
        self.splash = SplashScreen(duration=3, next_callback=self.show_login, name='splash')
        self.login = LoginScreen(zos_app_instance=self, name='login')
        self.main = Screen(name='main')
        self.app_screen = Screen(name='app')
        
        # Clear existing screens to prevent duplicates
        self.sm.clear_widgets()
        self.sm.add_widget(self.splash)
        self.sm.add_widget(self.login)
        self.sm.add_widget(self.main)
        self.sm.add_widget(self.app_screen)

        self.setup_main_screen()
        self.setup_app_screen()

        self.sm.current = 'splash'
        self.load_and_apply_wallpaper()

    def load_and_apply_wallpaper(self):
        settings = self.load_settings()
        custom_wallpaper_path = settings.get('custom_wallpaper_path')
        
        if custom_wallpaper_path and os.path.exists(custom_wallpaper_path):
            wallpaper_source = custom_wallpaper_path
        else:
            wallpaper_source = 'Assets/wallpaper.jpg'
            
        try:
            self.wallpaper.source = wallpaper_source
        except Exception as e:
            print(f"Error: Could not load '{wallpaper_source}'\nDetails: {e}")
            self.wallpaper.source = 'atlas://data/images/defaulttheme/bad-image'
    
    def on_screen_change(self, instance, value):
        if value == 'main':
            self.load_and_apply_wallpaper()

    def load_settings(self):
        settings = {}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    for line in f.readlines():
                        try:
                            key, value = line.strip().split('=', 1)
                            settings[key] = value
                        except ValueError:
                            pass
            except IOError as e:
                print(f"Error loading settings: {e}")
                settings = {}
        self.settings = settings
        return self.settings

    def save_settings(self):
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
        try:
            with open(self.settings_file, 'w') as f:
                for key, value in self.settings.items():
                    f.write(f"{key}={value}\n")
        except IOError as e:
            print(f"Error saving settings: {e}")

    def show_login(self):
        self.sm.current = 'login'

    def login(self):
        self.logged_in = True
        self.sm.current = 'main'

    def setup_main_screen(self):
        layout = FloatLayout()

        self.app_grid = GridLayout(cols=3, spacing=60, padding=40, size_hint=(1,0.8), pos_hint={'center_x':0.5,'center_y':0.55})
        layout.add_widget(self.app_grid)

        self.main_label = Label(text="", font_size='20sp', color=(0.5,1,0.5,1), font_name='RobotoThin', size_hint=(1,0.1), pos_hint={'top':1})
        layout.add_widget(self.main_label)
        Clock.schedule_interval(self.update_main_time,1)

        logout_btn = Button(text="Logout", size_hint=(0.2,0.08), pos_hint={'right':1,'top':1}, background_color=(0.5,1,0.5,1), font_name='RobotoThin')
        logout_btn.bind(on_press=self.logout)
        layout.add_widget(logout_btn)

        self.main.add_widget(layout)
        self.load_apps_menu()

    def update_main_time(self, dt):
        now = datetime.datetime.now()
        date = now.strftime("%A, %B %d, %Y")
        time = now.strftime("%I:%M %p")
        self.main_label.text = f"{date} | {time}"

    def load_apps_menu(self):
        self.app_grid.clear_widgets()
        apps_list = []
        if os.path.isdir(self.apps_dir):
            for folder in sorted(os.listdir(self.apps_dir)):
                folder_path = os.path.join(self.apps_dir, folder)
                if os.path.isdir(folder_path) and folder.lower() not in ['gallery', 'settings']:
                    icon_path = os.path.join(folder_path,'icon.png')
                    if not os.path.exists(icon_path):
                        icon_path = 'Assets/icon.png'
                    for file in sorted(os.listdir(folder_path)):
                        if file.endswith((".py", ".zpkg")):
                            app_name = os.path.splitext(file)[0]
                            apps_list.append({'name': app_name, 'path': os.path.join(folder_path, file), 'icon': icon_path})
            
            settings_app = {'name': 'Settings', 'path': os.path.join(self.apps_dir, 'Settings', 'settings.py'), 'icon': os.path.join(self.apps_dir, 'Settings', 'icon.png')}
            apps_list.append(settings_app)

        for app in apps_list:
            box = BoxLayout(orientation='vertical', spacing=5, size_hint=(None,None), size=(120,150))
            icon = ImageButton(source=app['icon'], size_hint=(None,None), size=(100,100))
            icon.bind(on_press=lambda instance, path=app['path'], name=app['name']: self.run_app(path,name))
            label = Label(text=app['name'], font_size='16sp', halign='center', valign='middle', font_name='RobotoThin', size_hint=(1,None), height=30)
            box.add_widget(icon)
            box.add_widget(label)
            self.app_grid.add_widget(box)

    def setup_app_screen(self):
        layout = BoxLayout(orientation='vertical')
        back_btn = Button(text="Back", size_hint_y=None, height=50, background_color=(0.4,1,0.4,1), font_name='RobotoThin')
        back_btn.bind(on_press=self.go_back)
        layout.add_widget(back_btn)
        self.app_container = BoxLayout()
        layout.add_widget(self.app_container)
        self.app_screen.add_widget(layout)

    def go_back(self, instance):
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            self.current_process = None
        self.app_container.clear_widgets()
        self.sm.current = 'main'

    def logout(self, instance):
        self.logged_in = False
        self.sm.current = 'login'

    def run_app(self, path, name, app_args={}):
        self.app_container.clear_widgets()
        self.sm.current = 'app'

        if path.endswith('.zpkg'):
            try:
                temp_dir = tempfile.mkdtemp()
                
                with tarfile.open(path, "r") as tar:
                    tar.extractall(path=temp_dir)
                
                extracted_app_path = None
                
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.py'):
                            extracted_app_path = os.path.join(root, file)
                            break
                    if extracted_app_path:
                        break

                if extracted_app_path and os.path.exists(extracted_app_path):
                    with open(extracted_app_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if 'from kivy.app import App' in content or 'kivy.app import App' in content or 'App().run' in content:
                        self.run_kivy_app(extracted_app_path, app_args)
                    else:
                        self.run_cli_app(extracted_app_path)
                else:
                    raise FileNotFoundError("Could not find any .py file after extraction. The archive may be empty or improperly structured.")
                
                def cleanup_temp_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
                self.sm.bind(current=lambda instance, value: cleanup_temp_dir() if value == 'main' else None)

            except Exception as e:
                print(f"Failed to open .zpkg app: {e}", file=sys.stderr)
                self.app_container.add_widget(Label(text=f"Failed to open .zpkg app:\n{e}"))
                self.sm.current = 'main'
        
        else:
            try:
                if name.lower() == 'settings':
                    spec = importlib.util.spec_from_file_location("settings_app", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    app_class = module.SettingsApp
                    app_instance = app_class() 
                    widget = app_instance.build()
                    self.app_container.add_widget(widget)
                else:
                    with open(path,'r', encoding='utf-8') as f:
                        content = f.read()
                    if 'from kivy.app import App' in content or 'kivy.app import App' in content or 'App().run' in content:
                        self.run_kivy_app(path, app_args)
                    else:
                        self.run_cli_app(path)
            except Exception as e:
                print(f"Failed to open app: {e}", file=sys.stderr)
                self.app_container.add_widget(Label(text=f"Failed to open app:\n{e}"))
            
    def run_kivy_app(self, path, app_args={}):
        try:
            app_settings = self.load_settings()
            
            spec = importlib.util.spec_from_file_location("dynamic_app", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            app_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, App) and attr.__name__ != 'App':
                    app_class = attr
                    break
            if app_class:
                # This is the key change. We check if the app accepts the custom arguments.
                init_signature = app_class.__init__.__code__
                arg_names = init_signature.co_varnames[:init_signature.co_argcount]

                if 'zos_app_instance' in arg_names and 'settings' in arg_names:
                    # It's an S3 app or a custom app that expects our arguments.
                    app_instance = app_class(zos_app_instance=self, settings=app_settings, **app_args) 
                else:
                    # It's a regular Kivy app, don't pass the custom arguments.
                    app_instance = app_class(**app_args)

                widget = app_instance.build() 
                self.app_container.add_widget(widget)
                
                app_instance.bind(on_stop=lambda instance: self.load_apps_menu())

            else:
                self.app_container.add_widget(Label(text="Error: No App class found"))
        except Exception as e:
            print(f"Kivy app failed: {e}", file=sys.stderr)
            self.app_container.add_widget(Label(text=f"Kivy app failed:\n{e}"))
            
    def run_cli_app(self, path):
        output_scroll = ScrollView(size_hint=(1,0.9))
        output_label = Label(text="Starting...\n", size_hint_y=None, font_name='RobotoThin', halign='left', valign='top', text_size=(Window.width-50,None))
        output_label.bind(texture_size=lambda inst, val: setattr(inst,'height',inst.texture_size[1]))
        output_scroll.add_widget(output_label)
        self.app_container.add_widget(output_scroll)

        def run_thread():
            try:
                process = subprocess.Popen([sys.executable,path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.current_process = process
                for line in process.stdout:
                    Clock.schedule_once(lambda dt, t=line: output_label.__setattr__('text', output_label.text + t))
                for line in process.stderr:
                    Clock.schedule_once(lambda dt, t=line: output_label.__setattr__('text', output_label.text + "Error: " + t))
                process.wait()
            except Exception as e:
                Clock.schedule_once(lambda dt: output_label.__setattr__('text', output_label.text + f"Failed: {e}"))
            finally:
                self.current_process = None
                Clock.schedule_once(lambda dt: self.load_apps_menu())

        threading.Thread(target=run_thread).start()

if __name__ == '__main__':
    ZOSApp().run()