from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivy.properties import ListProperty, DictProperty, NumericProperty
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.uix.widget import Widget
from db_config import DatabaseConfig
import logging


class AnimatedLabel(MDLabel):
    slide_height = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0
        self.height = 0
        self._original_height = dp(30)

    def slide_in(self):
        anim = Animation(opacity=1, height=self._original_height, duration=0.3)
        anim.start(self)

    def slide_out(self):
        anim = Animation(opacity=0, height=0, duration=0.3)
        anim.start(self)


class OpcionBoton(MDRaisedButton):
    def __init__(self, numero, **kwargs):
        super().__init__(**kwargs)
        self.text = str(numero)
        self.size_hint = (None, None)
        self.size = (dp(40), dp(40))
        self.md_bg_color = [0.9, 0.9, 0.9, 1]
        self.text_color = [0, 0, 0, 0.87]
        self.selected = False
        self.valor = numero

    def on_release(self):
        if hasattr(self, 'parent') and hasattr(self.parent, 'parent'):
            card = self.parent.parent
            if isinstance(card, PreguntaCard):
                # Actualizar el estilo de todos los botones
                for boton in card.botones:
                    boton.selected = False
                    boton.md_bg_color = [0.9, 0.9, 0.9, 1]
                    boton.text_color = [0, 0, 0, 0.87]

                # Actualizar el estilo del botón seleccionado
                self.selected = True
                self.md_bg_color = [0.61, 0.15, 0.69, 1]
                self.text_color = [1, 1, 1, 1]

                # Llamar a la función de selección con el valor correcto
                card.seleccionar_opcion(self.valor, card.callback)
class PreguntaCard(MDCard):
    def __init__(self, pregunta, numero, callback, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(180)
        self.padding = dp(16)
        self.spacing = dp(10)
        self.elevation = 1
        self.radius = [dp(10)]
        self.md_bg_color = [1, 1, 1, 1]
        self.pregunta_numero = numero
        self.callback = callback

        pregunta_label = MDLabel(
            text=pregunta,
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(60),
            font_style="Body1"
        )
        self.add_widget(pregunta_label)

        self.escala_label = AnimatedLabel(
            text="Totalmente en desacuerdo                     Totalmente de acuerdo",
            theme_text_color="Hint",
            size_hint_y=None,
            font_size="12sp"
        )
        self.add_widget(self.escala_label)

        botones_layout = MDBoxLayout(
            spacing=dp(10),
            size_hint_y=None,
            height=dp(50),
            padding=[dp(20), 0, dp(20), 0]
        )

        self.botones = []
        for i in range(1, 5):
            boton = OpcionBoton(i)
            self.botones.append(boton)
            botones_layout.add_widget(boton)

        self.add_widget(botones_layout)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.escala_label.slide_in()
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            self.escala_label.slide_out()
        return super().on_touch_up(touch)

    def seleccionar_opcion(self, valor, callback):
        if callback:
            callback(self.pregunta_numero, valor)
        self.escala_label.slide_out()
class Cuestionario(MDScreen):
    respuestas = DictProperty({})
    preguntas = ListProperty([
        "Tengo miedo de lesionarme si hago ejercicio físico.",
        "Si me dejara vencer por el dolor, el dolor aumentaría.",
        "Mi cuerpo me está diciendo que tengo algo serio.",
        "La gente no se toma mi condición médica con suficiente seriedad.",
        "Mi accidente/problema ha puesto a mi cuerpo en riesgo para el resto de mi vida.",
        "El dolor siempre significa que me he lesionado algo.",
        "Tengo miedo de lesionarme accidentalmente.",
        "La forma más segura de evitar que aumente mi dolor es simplemente ser cuidadoso y no hacer movimientos innecesarios.",
        "No tendría tanto dolor si no estuviera pasando algo potencialmente peligroso en mi cuerpo.",
        "No puedo hacer todo lo que la gente normal hace porque me podría lesionar con facilidad.",
        "Nadie debería hacer ejercicio cuando tiene dolor."
    ])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = DatabaseConfig()
        self.usuario_id = None
        Clock.schedule_once(self.crear_interfaz)
        Window.keyboard_anim_args = {'d': .2, 't': 'in_out_expo'}
        Window.softinput_mode = "below_target"
        self.disable_back_button()

    def set_usuario_id(self, usuario_id):
        """Establece el ID del usuario actual"""
        self.usuario_id = usuario_id
        logging.info(f"ID de usuario establecido en Cuestionario: {usuario_id}")
    def disable_back_button(self):
        Window.bind(on_keyboard=self.on_keyboard)

    def on_keyboard(self, window, key, *args):
        if key == 27:  # Código del botón de retroceso
            return True  # Previene la acción por defecto
        return False

    def crear_interfaz(self, *args):
        layout = self.ids.preguntas_layout
        layout.clear_widgets()
        layout.spacing = dp(16)
        layout.padding = dp(16)

        # Título del cuestionario
        titulo = MDLabel(
            text="Por favor, indique su grado de acuerdo con cada afirmación:",
            theme_text_color="Primary",
            font_style="H6",
            size_hint_y=None,
            height=dp(50),
            halign="center"
        )
        layout.add_widget(titulo)

        # Subtítulo con instrucciones
        subtitulo = MDLabel(
            text="1: Totalmente en desacuerdo | 4: Totalmente de acuerdo",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(30),
            halign="center"
        )
        layout.add_widget(subtitulo)

        # Crear cards para cada pregunta
        for i, pregunta in enumerate(self.preguntas):
            pregunta_card = PreguntaCard(
                f"{i + 1}. {pregunta}",
                i,
                self.on_seleccion,
                padding=[dp(8), dp(8)]
            )
            layout.add_widget(pregunta_card)

    def on_seleccion(self, pregunta, opcion):
        """Callback para cuando se selecciona una opción"""
        self.respuestas[pregunta] = opcion
        logging.info(f"Pregunta {pregunta + 1} respondida con valor {opcion}")

    def enviar_respuestas(self, instance):
        """Procesa y guarda las respuestas del cuestionario"""
        if not self.usuario_id:
            logging.error("ID de usuario no establecido en Cuestionario")
            self.mostrar_dialogo(
                "Error",
                "No se pudo identificar al usuario. Por favor, cierre sesión e inicie sesión nuevamente."
            )
            return

        # Verificar que todas las preguntas tienen respuesta
        preguntas_respondidas = set(self.respuestas.keys())
        todas_las_preguntas = set(range(len(self.preguntas)))

        if preguntas_respondidas != todas_las_preguntas:
            preguntas_faltantes = todas_las_preguntas - preguntas_respondidas
            mensaje = f"Por favor, responda la(s) pregunta(s): {', '.join(str(n + 1) for n in sorted(preguntas_faltantes))}"
            self.mostrar_dialogo(
                "Respuestas Incompletas",
                mensaje
            )
            return

        puntuacion_total = sum(self.respuestas.values())

        # Determinar el nivel y descripción
        if puntuacion_total <= 22:
            nivel = "Bajo nivel de kinesofobia"
            descripcion = "Los resultados sugieren que su miedo al movimiento es bajo. Esto es positivo para su recuperación."
        elif 23 <= puntuacion_total <= 33:
            nivel = "Nivel moderado de kinesofobia"
            descripcion = "Los resultados sugieren un nivel moderado de miedo al movimiento. Se recomienda consultar con un profesional de la salud."
        else:
            nivel = "Alto nivel de kinesofobia"
            descripcion = "Los resultados sugieren un alto nivel de miedo al movimiento. Es importante buscar ayuda profesional para manejar este temor."

        try:
            # Convert numeric keys to strings before saving
            respuestas_strings = {str(k): v for k, v in self.respuestas.items()}

            self.db.save_questionnaire_result(
                self.usuario_id,
                respuestas_strings,  # Use the converted dictionary
                puntuacion_total,
                nivel,
                descripcion
            )
            logging.info(f"Resultados del cuestionario guardados para usuario {self.usuario_id}")

            # Mostrar resultados al usuario
            self.mostrar_dialogo_resultados(
                puntuacion_total,
                nivel,
                descripcion
            )
        except Exception as e:
            logging.error(f"Error al guardar resultados del cuestionario: {str(e)}")
            self.mostrar_dialogo(
                "Error",
                "Ocurrió un error al guardar los resultados. Por favor, intente nuevamente."
            )

        # Mostrar resultados al usuario
        self.mostrar_dialogo_resultados(
            puntuacion_total,
            nivel,
            descripcion
        )

    def mostrar_dialogo(self, titulo, texto):
        """Muestra un diálogo genérico"""
        dialog = MDDialog(
            title=titulo,
            text=texto,
            buttons=[
                MDFlatButton(
                    text="Aceptar",
                    theme_text_color="Custom",
                    text_color=[0.61, 0.15, 0.69, 1],
                    on_release=lambda x: dialog.dismiss()
                )
            ]
        )
        dialog.open()

    def mostrar_dialogo_resultados(self, puntuacion_total, nivel, descripcion):
        """Muestra los resultados y cambia a la siguiente pantalla"""
        dialog = MDDialog(
            title="Resultados del Cuestionario TSK-11",
            text=f"Puntuación total: {puntuacion_total}\n\n{nivel}\n\n{descripcion}",
            buttons=[
                MDFlatButton(
                    text="Continuar",
                    theme_text_color="Custom",
                    text_color=[0.61, 0.15, 0.69, 1],
                    on_release=lambda x: self.continuar_a_seguimiento(x, dialog)
                )
            ]
        )
        dialog.open()

    def continuar_a_seguimiento(self, instance, dialog):
        """Cambia a la pantalla de seguimiento después de mostrar los resultados"""
        dialog.dismiss()
        seguimiento_screen = self.manager.get_screen('seguimiento')
        seguimiento_screen.set_usuario_id(self.usuario_id)
        self.manager.current = 'seguimiento'