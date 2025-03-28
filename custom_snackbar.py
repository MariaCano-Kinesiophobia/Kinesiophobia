from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.button import MDButton

class SnackbarUtils:
    @staticmethod
    def show_message(mensaje, bg_color=None):
        if bg_color is None:
            bg_color = [0.2, 0.8, 0.2, 1]  # Verde por defecto

        snackbar = MDSnackbar(
            MDButton(
                text=mensaje,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                style="text",  # Esto hace que sea un botón plano
            ),
            y=10,
            pos_hint={"center_x": 0.5},
            size_hint_x=0.9,
            md_bg_color=bg_color,
            duration=2,
        )
        snackbar.open()