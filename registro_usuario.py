# registro_usuario.py updates
from kivy.uix.screenmanager import Screen
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.app import MDApp
import sqlite3
import hashlib
import logging
from db_config import DatabaseConfig
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

class RegistroUsuarioScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self.setup_logging()
        # Establecer el tamaño mínimo solo para desktop
        if platform not in ('android', 'ios'):
            Window.minimum_width = dp(400)
            Window.minimum_height = dp(600)

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='app.log'
        )

    def mostrar_snackbar(self, mensaje, color=(0.2, 0.8, 0.2, 1)):
        SnackbarUtils.show_message(mensaje, bg_color=color)

    def mostrar_dialogo(self, titulo, texto):
        if not self.dialog:
            self.dialog = MDDialog(
                title=titulo,
                text=texto,
                buttons=[
                    MDFlatButton(
                        text="ENTENDIDO",
                        theme_text_color="Primary",
                        on_release=lambda x: self.dialog.dismiss()
                    )
                ],
                radius=[20, 7, 20, 7]
            )
        self.dialog.open()

    def mostrar_registro(self):
        self.manager.transition.direction = 'left'
        self.manager.current = 'registro'

    def iniciar_sesion(self):
        cedula = self.ids.login_cedula.text.strip()
        password = self.ids.login_password.text

        if not cedula or not password:
            self.mostrar_dialogo(
                "Campos Requeridos",
                "Por favor completa todos los campos para continuar."
            )
            return

        try:
            conn = sqlite3.connect(DatabaseConfig.db_path)
            cursor = conn.cursor()

            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            cursor.execute(
                'SELECT nombre, apellido FROM usuarios WHERE cedula = ? AND password = ?',
                (cedula, hashed_password)
            )
            usuario = cursor.fetchone()

            if usuario:
                nombre_completo = f"{usuario[0]} {usuario[1]}"
                self.mostrar_snackbar(
                    f"¡Bienvenido {nombre_completo}!",
                    color=MDApp.get_running_app().theme_cls.primary_color
                )
                # Aquí agregarías la navegación a tu pantalla principal
            else:
                self.mostrar_dialogo(
                    "Error de Acceso",
                    "Las credenciales ingresadas no son correctas. Por favor verifica e intenta nuevamente."
                )

        except sqlite3.Error as e:
            logging.error(f"Error en la base de datos: {e}")
            self.mostrar_dialogo(
                "Error",
                "Ocurrió un error al intentar iniciar sesión. Por favor intenta nuevamente."
            )
        finally:
            conn.close()


class RegistroScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None

    def volver_login(self):
        self.manager.transition.direction = 'right'
        self.manager.current = 'login'

    def limpiar_campos(self):
        self.ids.register_cedula.text = ""
        self.ids.register_nombre.text = ""
        self.ids.register_apellido.text = ""
        self.ids.register_password.text = ""

    def mostrar_snackbar(self, mensaje, color=(0.2, 0.8, 0.2, 1)):
        SnackbarUtils.show_message(mensaje, bg_color=color)
    def registrar_usuario(self):
        cedula = self.ids.register_cedula.text.strip()
        nombre = self.ids.register_nombre.text.strip()
        apellido = self.ids.register_apellido.text.strip()
        password = self.ids.register_password.text

        if not all([cedula, nombre, apellido, password]):
            self.mostrar_dialogo(
                "Campos Incompletos",
                "Por favor completa todos los campos para continuar con el registro."
            )
            return

        try:
            conn = sqlite3.connect(DatabaseConfig.db_path)
            cursor = conn.cursor()

            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            cursor.execute('''
                INSERT INTO usuarios (cedula, nombre, apellido, password)
                VALUES (?, ?, ?, ?)
            ''', (cedula, nombre, apellido, hashed_password))

            conn.commit()

            self.mostrar_snackbar(
                "¡Registro exitoso! Redirigiendo al login...",
                color=(0.2, 0.8, 0.2, 1)
            )

            self.limpiar_campos()
            Clock.schedule_once(lambda dt: self.volver_login(), 2)

        except sqlite3.IntegrityError:
            self.mostrar_dialogo(
                "Usuario Existente",
                "La cédula ingresada ya está registrada en el sistema."
            )
        except sqlite3.Error as e:
            logging.error(f"Error en la base de datos: {e}")
            self.mostrar_dialogo(
                "Error",
                "Ocurrió un error al intentar registrar el usuario."
            )
        finally:
            conn.close()

    def mostrar_dialogo(self, titulo, texto):
        if not self.dialog:
            self.dialog = MDDialog(
                title=titulo,
                text=texto,
                buttons=[
                    MDFlatButton(
                        text="ENTENDIDO",
                        theme_text_color="Primary",
                        on_release=lambda x: self.dialog.dismiss()
                    )
                ],
                radius=[20, 7, 20, 7]
            )
        else:
            self.dialog.title = titulo
            self.dialog.text = texto
        self.dialog.open()