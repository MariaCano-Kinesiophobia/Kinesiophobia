from kivymd.app import MDApp
from history_screen import HistoryScreen
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.utils import platform
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDIconButton, MDFlatButton
from kivy.clock import Clock
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy.uix.screenmanager import SlideTransition, NoTransition
import hashlib
import logging
import sys
import os
import kivy
import kivymd
from datetime import datetime
from kivy.properties import ObjectProperty, BooleanProperty
from db_config import DatabaseConfig
from cuestionario import Cuestionario
from seguimiento_angulo import SeguimientoAnguloScreen
from threading import Thread
from functools import partial
from kivy.config import Config
from kivy.metrics import dp
from kivy.factory import Factory
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout


# Función para manejar rutas de recursos en PyInstaller
def resource_path(relative_path):
    """Obtiene la ruta absoluta a un recurso, sea en desarrollo o en un ejecutable"""
    try:
        # PyInstaller crea una carpeta temporal y almacena la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Configurar la ruta de registros para que funcione en entorno de PyInstaller
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys, '_MEIPASS'):
    APP_DIR = sys._MEIPASS
LOG_DIR = os.path.join(os.path.expanduser('~'), 'KinesofobiaApp')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

# Configurar tamaño de ventana para Windows
# Estas configuraciones no afectan a dispositivos móviles si se ejecuta allí
Config.set('graphics', 'width', '1024')
Config.set('graphics', 'height', '768')
Config.set('graphics', 'resizable', '1')
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

# Configuración del registro de actividad
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Establecer el color de fondo de la ventana
Window.clearcolor = (1, 1, 1, 1)  # Fondo blanco

# Cargar el KV file inmediatamente
kv_file = resource_path('main.kv')
Builder.load_file(kv_file)


class CustomToggleButton(MDIconButton):
    is_selected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_text_color = "Custom"
        self.text_color = self.theme_cls.primary_color
        self.md_bg_color = [0, 0, 0, 0]
        self.size_hint = (None, None)
        self.size = ("48dp", "48dp")
        self.ripple_scale = 1.5

    def on_release(self):
        self.is_selected = not self.is_selected
        if self.is_selected:
            self.md_bg_color = self.theme_cls.primary_color
            self.text_color = [1, 1, 1, 1]
        else:
            self.md_bg_color = [0, 0, 0, 0]
            self.text_color = self.theme_cls.primary_color


class SplashScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None
        # Programar la carga del logo
        Clock.schedule_once(self.set_logo_path, 0)

    def set_logo_path(self, dt):
        """Establece la ruta correcta del logo"""
        if hasattr(self, 'ids') and hasattr(self.ids, 'logo_image'):
            self.ids.logo_image.source = resource_path('assets/logo.png')
            logging.info(f"Ruta del logo en SplashScreen: {self.ids.logo_image.source}")

    def on_enter(self):
        # Iniciar la carga de la aplicación directamente sin verificar permisos
        self.start_loading()

    def start_loading(self):
        logging.info("Iniciando carga de la aplicación...")
        Clock.schedule_once(lambda dt: Thread(target=self.connect_db).start(), 1)

    def connect_db(self):
        try:
            # Importar certifi al principio para asegurar que esté disponible
            import certifi
            # Establecer explícitamente la ruta del certificado
            os.environ['SSL_CERT_FILE'] = certifi.where()

            logging.info("Conectando a la base de datos...")
            self.db = DatabaseConfig()
            # Agregar un tiempo de espera más largo
            Clock.schedule_once(self.on_connection_complete, 10)  # Aumentar a 10 segundos
        except Exception as e:
            import traceback
            error_msg = f"Error de conexión: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)

            # Guardar error en archivo local para diagnóstico
            error_log_path = os.path.join(LOG_DIR, "db_error.log")
            with open(error_log_path, "w") as f:
                f.write(error_msg)

            # Esperar un poco antes de mostrar el error
            Clock.schedule_once(lambda dt: self.show_connection_error(str(e)), 1)

    def on_connection_complete(self, *args):
        logging.info("Conexión a la base de datos completada")
        # Almacenar la conexión a la base de datos en la instancia de la aplicación
        app = MDApp.get_running_app()
        app.db = self.db

        # Transición a la pantalla de inicio de sesión
        self.manager.transition = NoTransition()
        self.manager.current = 'login'

    def show_connection_error(self, error_msg, *args):
        logging.error(f"Mostrando error de conexión: {error_msg}")
        MDApp.get_running_app().show_alert(
            "Error de Conexión",
            f"No se pudo conectar a la base de datos: {error_msg}"
        )


class LoginScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize database reference as None
        self.db = None
        # Programar la configuración del campo de contraseña después de que la UI esté lista
        Clock.schedule_once(self.setup_password_field, 0)
        # Programar la carga del logo
        Clock.schedule_once(self.set_logo_path, 0)

    def set_logo_path(self, dt):
        """Establece la ruta correcta del logo"""
        if hasattr(self, 'ids') and hasattr(self.ids, 'logo_image'):
            self.ids.logo_image.source = resource_path('assets/logo.png')
            logging.info(f"Ruta del logo en LoginScreen: {self.ids.logo_image.source}")

    def setup_password_field(self, dt):
        # Asegurarse de que ids esté disponible
        if hasattr(self, 'ids') and hasattr(self.ids, 'password'):
            # Configurar el campo de contraseña
            password_field = self.ids.password
            password_field.password = True
            password_field.icon_right = "eye-off"

            # Configurar la funcionalidad del icono de contraseña
            def on_password_icon_press():
                password_field.password = not password_field.password
                password_field.icon_right = "eye" if not password_field.password else "eye-off"

            # Vincular el manejador de eventos
            password_field.bind(on_icon_right_press=lambda x: on_password_icon_press())

    def on_enter(self):
        # Get database instance from the running app when screen is entered
        app = MDApp.get_running_app()
        self.db = app.db

    def verify_credentials(self):
        if not self.db:
            self.show_error_message("Error de conexión a la base de datos.")
            return

        cedula = self.ids.username.text.strip()
        password = self.ids.password.text

        if not cedula or not password:
            self.show_error_message("Por favor completa todos los campos.")
            return

        try:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            user = self.db.verify_user(cedula, hashed_password)

            if user:
                app = MDApp.get_running_app()
                app.usuario_id = user['_id']

                # Configurar el ID de usuario en todas las pantallas relevantes
                cuestionario_screen = self.manager.get_screen('cuestionario')
                seguimiento_screen = self.manager.get_screen('seguimiento')
                history_screen = self.manager.get_screen('historial')

                cuestionario_screen.set_usuario_id(user['_id'])
                seguimiento_screen.set_usuario_id(user['_id'])
                history_screen.set_usuario_id(user['_id'])

                nombre_completo = f"{user['nombre']} {user['apellido']}"
                self.show_success_message(f"¡Bienvenido {nombre_completo}!")
                self.manager.transition = NoTransition()
                self.manager.current = 'cuestionario'
            else:
                self.show_error_message("Credenciales incorrectas. Por favor, intenta de nuevo.")

        except Exception as e:
            logging.error(f"Error en la base de datos: {e}")
            self.show_error_message("Ocurrió un error al iniciar sesión. Por favor, intenta de nuevo.")

    def show_error_message(self, message):
        dialog = MDDialog(
            title="Error",
            text=message,
            buttons=[
                MDFlatButton(
                    text="Cerrar",
                    theme_text_color="Custom",
                    text_color=MDApp.get_running_app().theme_cls.primary_color,
                    on_release=lambda *args: dialog.dismiss()
                )
            ]
        )
        dialog.open()

    def show_success_message(self, message):
        dialog = MDDialog(
            title="Éxito",
            text=message,
            buttons=[
                MDFlatButton(
                    text="OK",
                    theme_text_color="Custom",
                    text_color=MDApp.get_running_app().theme_cls.primary_color,
                    on_release=lambda *args: dialog.dismiss()
                )
            ]
        )
        dialog.open()


class RegistroScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = DatabaseConfig()
        Clock.schedule_once(self.setup_password_field)

    def setup_password_field(self, dt):
        # Asegurarse de que ids esté disponible
        if hasattr(self, 'ids') and hasattr(self.ids, 'register_password'):
            # Configurar el campo de contraseña
            password_field = self.ids.register_password
            password_field.password = True
            password_field.icon_right = "eye-off"

            # Configurar la funcionalidad del icono de contraseña
            def on_password_icon_press():
                password_field.password = not password_field.password
                password_field.icon_right = "eye" if not password_field.password else "eye-off"

            # Vincular el manejador de eventos
            password_field.bind(on_icon_right_press=lambda x: on_password_icon_press())

    def registrar_usuario(self):
        cedula = self.ids.register_cedula.text.strip()
        nombre = self.ids.register_nombre.text.strip()
        apellido = self.ids.register_apellido.text.strip()
        password = self.ids.register_password.text

        if not all([cedula, nombre, apellido, password]):
            self.show_error_message("Por favor completa todos los campos.")
            return

        try:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            # Verificar si el usuario ya existe
            existing_user = self.db.verify_user(cedula, hashed_password)
            if existing_user:
                self.show_error_message("La cédula ingresada ya está registrada.")
                return

            # Registrar nuevo usuario
            self.db.save_user(cedula, nombre, apellido, hashed_password)

            self.show_success_message("¡Registro exitoso! Redirigiendo al login...")
            Clock.schedule_once(lambda dt: self.volver_login(), 2)

        except Exception as e:
            logging.error(f"Error en la base de datos: {e}")
            self.show_error_message("Ocurrió un error al registrar el usuario.")

    def show_error_message(self, message):
        dialog = MDDialog(
            title="Error",
            text=message,
            buttons=[
                MDFlatButton(
                    text="Cerrar",
                    theme_text_color="Custom",
                    text_color=MDApp.get_running_app().theme_cls.primary_color,
                    on_release=lambda *args: dialog.dismiss()
                )
            ]
        )
        dialog.open()

    def show_success_message(self, message):
        dialog = MDDialog(
            title="Éxito",
            text=message,
            buttons=[
                MDFlatButton(
                    text="OK",
                    theme_text_color="Custom",
                    text_color=MDApp.get_running_app().theme_cls.primary_color,
                    on_release=lambda *args: dialog.dismiss()
                )
            ]
        )
        dialog.open()

    def volver_login(self):
        self.manager.current = 'login'


class MainApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.usuario_id = None
        self.theme_cls.primary_palette = "Purple"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Light"

        # Registrar el inicio de la aplicación
        logging.info("Aplicación inicializada")

    def build(self):
        sm = MDScreenManager(transition=SlideTransition())
        screens = {
            'splash': SplashScreen(name='splash'),
            'login': LoginScreen(name='login'),
            'registro': RegistroScreen(name='registro'),
            'cuestionario': Cuestionario(name='cuestionario'),
            'seguimiento': SeguimientoAnguloScreen(name='seguimiento'),
            'historial': HistoryScreen(name='historial')
        }

        for screen in screens.values():
            sm.add_widget(screen)

        sm.current = 'splash'
        return sm

    def on_start(self):
        """Se llama cuando la aplicación inicia"""
        # Programar la corrección de rutas de recursos
        Clock.schedule_once(self._fix_image_paths, 1)

    def _fix_image_paths(self, dt):
        """Busca y corrige las rutas de imágenes en todos los widgets"""

        # Recorrer toda la jerarquía de widgets
        def fix_paths(widget):
            # Corregir path de imagen si es un widget Image o tiene source
            if hasattr(widget, 'source') and isinstance(widget.source, str):
                if 'assets/' in widget.source:
                    old_source = widget.source
                    widget.source = resource_path(widget.source)
                    logging.info(f"Ruta de imagen corregida: {old_source} -> {widget.source}")

            # Buscar recursivamente en todos los hijos
            if hasattr(widget, 'children'):
                for child in widget.children:
                    fix_paths(child)

        # Comenzar el recorrido desde la raíz
        fix_paths(self.root)

    def show_alert(self, title, text):
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(
                    text="OK",
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=lambda *args: dialog.dismiss()
                )
            ]
        )
        dialog.open()

    def on_stop(self):
        if hasattr(self, 'db'):
            self.db.client.close()
        logging.info("Aplicación cerrada correctamente")

    def cambiar_tema(self):
        self.theme_cls.theme_style = (
            "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        )

    def handle_error(self, error_msg):
        logging.error(error_msg)
        self.show_alert("Error", error_msg)

    def logout(self):
        self.usuario_id = None
        self.root.current = 'login'


def main():
    MainApp().run()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.critical(f"Error crítico en la aplicación: {e}")
        # Guardar error crítico en una ubicación accesible incluso en PyInstaller
        error_log_path = os.path.join(LOG_DIR, "critical_error.log")
        with open(error_log_path, "w") as f:
            import traceback

            f.write(f"Error crítico: {str(e)}\n{traceback.format_exc()}")
        raise