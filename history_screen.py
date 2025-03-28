from kivymd.uix.screen import MDScreen
from kivymd.uix.list import MDList, ThreeLineAvatarListItem, ImageLeftWidget
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivy.clock import Clock
from datetime import datetime
import io
import gridfs
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.tab import MDTabs, MDTabsBase
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.toolbar import MDTopAppBar
import logging
from kivy.core.image import Image as CoreImage
from kivy.uix.image import AsyncImage
import cv2
import numpy as np
from bson import ObjectId
from kivy.metrics import dp
from kivy.cache import Cache

# Configurar caché para las imágenes
Cache.register('history_images', limit=10)


class Tab(MDFloatLayout, MDTabsBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll = ScrollView()
        self.list_view = MDList()
        self.scroll.add_widget(self.list_view)
        self.add_widget(self.scroll)


class HistoryScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None
        self.usuario_id = None
        self.previous_screen = 'seguimiento'
        self.image_dialog = None
        self.setup_ui()

    def set_previous_screen(self, screen_name):
        """Establece la pantalla anterior para la navegación"""
        self.previous_screen = screen_name
        logging.info(f"Pantalla anterior establecida: {screen_name}")

    def setup_ui(self):
        """Configurar la interfaz de usuario con tabs y toolbar"""
        # Layout principal
        self.layout = MDBoxLayout(orientation='vertical')

        # Toolbar con botón de regreso
        self.toolbar = MDTopAppBar(
            title="Historial",
            elevation=10,
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            pos_hint={"top": 1}
        )

        # Obtener la instancia de la app para acceder a theme_cls
        app = MDApp.get_running_app()

        # Crear tabs
        self.tabs = MDTabs(
            allow_stretch=False,
            background_color=app.theme_cls.primary_color,
            text_color_normal=(1, 1, 1, 0.5),
            text_color_active=(1, 1, 1, 1)
        )

        # Crear tab de mediciones
        self.measurements_tab = Tab(
            title="Mediciones"
        )

        # Crear tab de cuestionarios
        self.questionnaire_tab = Tab(
            title="Cuestionarios"
        )

        # Añadir tabs
        self.tabs.add_widget(self.measurements_tab)
        self.tabs.add_widget(self.questionnaire_tab)

        # Añadir widgets al layout principal
        self.layout.add_widget(self.toolbar)
        self.layout.add_widget(self.tabs)

        # Añadir layout a la pantalla
        self.add_widget(self.layout)

    def go_back(self):
        """Regresa a la pantalla anterior"""
        app = MDApp.get_running_app()
        app.root.current = self.previous_screen

    def create_measurement_item(self, measurement):
        """Crea un item de lista para una medición con imagen y estadísticas"""
        try:
            # Formatear la fecha
            timestamp = measurement.get('timestamp')
            date_str = timestamp.strftime("%d/%m/%Y %H:%M") if timestamp else "Fecha no disponible"

            # Formatear el ángulo
            angle = measurement.get('angle', 0)

            # Obtener y formatear estadísticas
            statistics = measurement.get('statistics', {})
            stats_text = ""
            if statistics:
                modo = statistics.get('modo_captura', 'N/A')
                tiempo_quieto = statistics.get('tiempo_quieto', 0) / 1000.0  # Convertir a segundos
                angulos_previos = statistics.get('angulos_previos', [])
                variacion = np.std(angulos_previos) if angulos_previos else 0

                stats_text = (
                    f"Modo: {modo} | "
                    f"Tiempo quieto: {tiempo_quieto:.1f}s | "
                    f"Variación: {variacion:.2f}°"
                )

            # Crear el item de lista con estadísticas
            list_item = ThreeLineAvatarListItem(
                text=f"Fecha: {date_str}",
                secondary_text=f"Ángulo medido: {angle:.1f}°",
                tertiary_text=stats_text if stats_text else "Toque para ver imagen ampliada"
            )

            # Procesar la imagen si existe
            if 'image_id' in measurement:
                image_id = str(measurement['image_id'])

                # Verificar si la imagen está en caché
                cached_image = Cache.get('history_images', image_id)

                if cached_image is None:
                    try:
                        # Obtener imagen de GridFS
                        grid_fs = gridfs.GridFS(self.db.db)
                        image_data = grid_fs.get(measurement['image_id']).read()

                        # Convertir bytes a numpy array
                        nparr = np.frombuffer(image_data, np.uint8)
                        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        # Redimensionar la imagen para la miniatura
                        height, width = img_np.shape[:2]
                        max_size = 100
                        if height > width:
                            new_height = max_size
                            new_width = int(width * (max_size / height))
                        else:
                            new_width = max_size
                            new_height = int(height * (max_size / width))

                        img_np = cv2.resize(img_np, (new_width, new_height))
                        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

                        # Convertir a formato que Kivy puede usar
                        buf = io.BytesIO(cv2.imencode('.png', img_rgb)[1].tobytes())
                        core_image = CoreImage(buf, ext='png')

                        # Guardar en caché
                        Cache.append('history_images', image_id, {
                            'texture': core_image.texture,
                            'image_data': image_data,
                            'statistics': statistics
                        })

                    except Exception as img_error:
                        logging.error(f"Error procesando imagen: {img_error}")
                        return list_item

                # Obtener imagen y estadísticas de caché
                cached_data = Cache.get('history_images', image_id)

                # Crear y añadir widget de imagen
                image_widget = ImageLeftWidget()
                image_widget.texture = cached_data['texture']
                list_item.add_widget(image_widget)

                # Bind para mostrar imagen ampliada con estadísticas
                list_item.bind(
                    on_release=lambda x, data=cached_data['image_data'],
                                      a=angle, s=cached_data['statistics']:
                    self.show_image_dialog(data, a, s)
                )

            return list_item

        except Exception as e:
            logging.error(f"Error creando item de medición: {e}")
            return None

    def show_image_dialog(self, image_data, angle, statistics=None):
        """Muestra un diálogo con la imagen ampliada y estadísticas"""
        try:
            content = MDBoxLayout(
                orientation='vertical',
                spacing=dp(10),
                size_hint_y=None,
                height=dp(500)
            )

            # Convertir bytes a imagen
            nparr = np.frombuffer(image_data, np.uint8)
            img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

            # Redimensionar manteniendo la relación de aspecto
            max_size = 400
            height, width = img_rgb.shape[:2]
            if height > width:
                new_height = max_size
                new_width = int(width * (max_size / height))
            else:
                new_width = max_size
                new_height = int(height * (max_size / width))

            img_resized = cv2.resize(img_rgb, (new_width, new_height))

            # Convertir a formato que Kivy puede usar
            buf = io.BytesIO(cv2.imencode('.png', img_resized)[1].tobytes())
            image = CoreImage(buf, ext='png')

            # Crear y añadir el widget de imagen
            img_widget = AsyncImage(
                texture=image.texture,
                size_hint=(None, None),
                size=(new_width, new_height)
            )
            content.add_widget(img_widget)

            # Añadir estadísticas si existen
            if statistics:
                stats_text = f"""
Modo de captura: {statistics.get('modo_captura', 'N/A')}
Tiempo quieto: {statistics.get('tiempo_quieto', 0) / 1000.0:.1f} segundos
Variación de ángulos: {np.std(statistics.get('angulos_previos', [])):.2f}°
"""
                from kivymd.uix.label import MDLabel
                stats_label = MDLabel(
                    text=stats_text,
                    size_hint_y=None,
                    height=dp(80)
                )
                content.add_widget(stats_label)

            # Cerrar diálogo anterior si existe
            if self.image_dialog:
                self.image_dialog.dismiss()

            # Crear y mostrar nuevo diálogo
            self.image_dialog = MDDialog(
                title=f"Ángulo medido: {angle:.1f}°",
                type="custom",
                content_cls=content,
                buttons=[
                    MDFlatButton(
                        text="CERRAR",
                        on_release=lambda x: self.image_dialog.dismiss()
                    )
                ]
            )
            self.image_dialog.open()

        except Exception as e:
            logging.error(f"Error mostrando diálogo de imagen: {e}")
            if self.image_dialog:
                self.image_dialog.dismiss()

    def set_usuario_id(self, usuario_id):
        """Set the user ID for the screen"""
        self.usuario_id = usuario_id
        logging.info(f"Usuario ID establecido en HistoryScreen: {usuario_id}")

    def on_enter(self):
        """Se llama cuando la pantalla se muestra"""
        app = MDApp.get_running_app()
        self.db = app.db

        if not self.usuario_id:
            logging.error("No hay ID de usuario establecido en HistoryScreen")
            return

        # Convertir string ID a ObjectId si es necesario
        if isinstance(self.usuario_id, str):
            self.usuario_id = ObjectId(self.usuario_id)

        # Cargar datos
        Clock.schedule_once(lambda dt: self.load_measurements())
        Clock.schedule_once(lambda dt: self.load_questionnaires())

    def load_measurements(self):
        """Carga las mediciones del usuario desde la base de datos"""
        try:
            # Limpiar lista actual
            self.measurements_tab.list_view.clear_widgets()

            # Obtener mediciones
            measurements = self.db.get_user_measurements(self.usuario_id)

            if not measurements:
                list_item = ThreeLineAvatarListItem(
                    text="No hay mediciones disponibles",
                    secondary_text="Realice una medición de ángulo",
                    tertiary_text="Las mediciones aparecerán aquí"
                )
                self.measurements_tab.list_view.add_widget(list_item)
                return

            # Añadir cada medición a la lista
            for measurement in measurements:
                list_item = self.create_measurement_item(measurement)
                if list_item:
                    self.measurements_tab.list_view.add_widget(list_item)

        except Exception as e:
            logging.error(f"Error loading measurements: {e}")
            list_item = ThreeLineAvatarListItem(
                text="Error al cargar mediciones",
                secondary_text="Por favor, intente más tarde",
                tertiary_text=str(e)
            )
            self.measurements_tab.list_view.add_widget(list_item)

    def load_questionnaires(self):
        """Carga los resultados de cuestionarios del usuario"""
        try:
            self.questionnaire_tab.list_view.clear_widgets()
            questionnaires = self.db.get_user_questionnaire_results(self.usuario_id)

            if not questionnaires:
                list_item = ThreeLineAvatarListItem(
                    text="No hay cuestionarios completados",
                    secondary_text="Complete el cuestionario TSK-11",
                    tertiary_text="Los resultados aparecerán aquí"
                )
                self.questionnaire_tab.list_view.add_widget(list_item)
                return

            # Ordenar cuestionarios por fecha, más reciente primero
            questionnaires = sorted(
                questionnaires,
                key=lambda x: x.get('timestamp', datetime.min),
                reverse=True
            )

            for questionnaire in questionnaires:
                timestamp = questionnaire.get('timestamp')
                date_str = timestamp.strftime("%d/%m/%Y %H:%M") if timestamp else "Fecha no disponible"

                total_score = questionnaire.get('total_score', 0)
                level = questionnaire.get('level', 'No disponible')

                list_item = ThreeLineAvatarListItem(
                    text=f"Fecha: {date_str}",
                    secondary_text=f"Puntuación total: {total_score}",
                    tertiary_text=f"Nivel: {level}"
                )
                self.questionnaire_tab.list_view.add_widget(list_item)

        except Exception as e:
            logging.error(f"Error loading questionnaires: {e}")
            list_item = ThreeLineAvatarListItem(
                text="Error al cargar cuestionarios",
                secondary_text="Por favor, intente más tarde",
                tertiary_text=str(e)
            )
            self.questionnaire_tab.list_view.add_widget(list_item)

