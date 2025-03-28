from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
import cv2
import numpy as np
from datetime import datetime
import logging
import threading
from functools import partial
from db_config import DatabaseConfig
from collections import deque
from kivymd.app import MDApp


class SeguimientoAnguloScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_ui()
        self.cap = None
        self.ultima_captura_angulo = None
        self.tiempo_quieto = 0
        self.db = DatabaseConfig()
        self.usuario_id = None
        self.angulos_buffer = deque(maxlen=5)  # Aumentado para suavizado más efectivo
        self.frame_buffer = None
        self.frame_ready = False
        self.processing_lock = threading.Lock()
        self.frame_count = 0
        self.skip_frames = 1  # Procesar cada N frames
        self.available_cameras = []
        self.camera_dialog = None

        # Configurar logging para depuración
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

        # Mantener mismos parámetros de calibración para compatibilidad
        self.calibracion = {
            'fuchsia': {
                'lower': np.array([140, 50, 150]),
                'upper': np.array([160, 255, 255])
            },
            'yellow': {
                'lower': np.array([20, 100, 100]),
                'upper': np.array([30, 255, 255])
            }
        }

        # Usar el área mínima original para mantener sensibilidad
        self.min_area = 50
        # Mantener escala original inicialmente por compatibilidad
        self.resolution_scale = 1.0

        # Detectar cámaras disponibles para Windows
        self.detect_cameras()

    def detect_cameras(self):
        """Detecta cámaras disponibles en el sistema Windows"""
        self.available_cameras = []
        for i in range(10):  # Probar hasta 10 cámaras
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Usar DSHOW en Windows
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    self.available_cameras.append(i)
                cap.release()
            except Exception as e:
                pass  # Ignorar errores en la detección inicial

        logging.info(f"Cámaras disponibles: {self.available_cameras}")

        # Si solo hay una cámara, seleccionarla automáticamente para la próxima vez
        if len(self.available_cameras) == 1:
            self.camera_id = self.available_cameras[0]

    def setup_ui(self):
        """Configuración de la interfaz de usuario (adaptada para Windows)"""
        # Layout principal
        layout = MDBoxLayout(orientation='vertical')

        # Toolbar con botón de navegación
        toolbar = MDTopAppBar(
            title="Seguimiento de Ángulo",
            elevation=10,
            right_action_items=[["history", lambda x: self.go_to_history()]]
        )
        layout.add_widget(toolbar)

        # Contenedor principal
        main_container = MDBoxLayout(
            orientation='horizontal',
            padding=dp(10),
            spacing=dp(10)
        )

        # Panel izquierdo con la imagen
        imagen_container = MDCard(
            size_hint=(0.7, 1),
            elevation=2,
            padding=dp(8)
        )
        self.img_widget = Image(allow_stretch=True, keep_ratio=True)
        imagen_container.add_widget(self.img_widget)

        # Panel derecho con controles
        controles_container = MDBoxLayout(
            orientation='vertical',
            size_hint=(0.3, 1),
            spacing=dp(10),
            padding=dp(10)
        )

        # Añadir botón de selección de cámara para Windows
        self.btn_select_camera = MDRaisedButton(
            text="Seleccionar Cámara",
            on_release=self.show_camera_selection,
            size_hint=(1, None),
            height=dp(48)
        )

        # Botones y etiquetas
        self.btn_toggle = MDRaisedButton(
            text="Iniciar Seguimiento",
            on_release=self.toggle_seguimiento,
            size_hint=(1, None),
            height=dp(48)
        )

        self.btn_captura = MDRaisedButton(
            text="Capturar",
            on_release=self.capturar_manual,
            disabled=True,
            size_hint=(1, None),
            height=dp(48)
        )

        self.btn_history = MDRaisedButton(
            text="Ver Historial",
            on_release=lambda x: self.go_to_history(),
            size_hint=(1, None),
            height=dp(48)
        )

        self.lbl_angulo = MDLabel(
            text="Ángulo: 0.0°",
            size_hint=(1, None),
            height=dp(30)
        )

        self.lbl_estado = MDLabel(
            text="Estado: Inactivo",
            size_hint=(1, None),
            height=dp(30)
        )

        # Agregar widgets al contenedor de controles
        controles_container.add_widget(self.btn_select_camera)  # Nuevo botón para Windows
        controles_container.add_widget(self.btn_toggle)
        controles_container.add_widget(self.btn_captura)
        controles_container.add_widget(self.btn_history)
        controles_container.add_widget(self.lbl_angulo)
        controles_container.add_widget(self.lbl_estado)

        # Agregar contenedores al layout principal
        main_container.add_widget(imagen_container)
        main_container.add_widget(controles_container)
        layout.add_widget(main_container)

        self.add_widget(layout)

    def show_camera_selection(self, *args):
        """Muestra un diálogo para seleccionar la cámara (específico para Windows)"""
        if self.cap:
            self.detener_seguimiento()

        # Intentar directamente con la primera cámara (normalmente la 0)
        try:
            # Vamos a intentar directamente usar la cámara 0, que es la más común
            self.select_camera(0)
            return
        except Exception as e:
            logging.error(f"Error al intentar usar cámara 0 automáticamente: {str(e)}")
            # Si falla, continuamos con el método normal de detección

        # Verificamos las cámaras realmente disponibles
        self.available_cameras = []
        for i in range(3):  # Limitar a 3 cámaras para evitar falsos positivos
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Usar DSHOW en Windows
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    self.available_cameras.append(i)
                cap.release()
            except Exception as e:
                logging.error(f"Error al verificar cámara {i}: {str(e)}")

        logging.info(f"Cámaras realmente disponibles: {self.available_cameras}")

        if not self.available_cameras:
            dialog = MDDialog(
                title="No se detectaron cámaras",
                text="No se detectaron cámaras disponibles en el sistema.",
                buttons=[
                    MDFlatButton(
                        text="Aceptar",
                        on_release=self.dismiss_dialog
                    )
                ]
            )
            self.camera_dialog = dialog
            dialog.open()
            return

        # Si solo hay una cámara, la seleccionamos automáticamente sin mostrar diálogo
        if len(self.available_cameras) == 1:
            self.select_camera(self.available_cameras[0])
            return

        # Si hay múltiples cámaras, mostramos diálogo de selección
        buttons = []

        # Creamos botones regulares en lugar de flatbuttons
        for cam_id in self.available_cameras:
            button = MDFlatButton(
                text=f"Cámara {cam_id}",
                on_release=self.create_camera_callback(cam_id)
            )
            buttons.append(button)

        dialog = MDDialog(
            title="Seleccionar Cámara",
            text="Elija la cámara que desea utilizar:",
            buttons=buttons
        )
        self.camera_dialog = dialog
        dialog.open()

    def dismiss_dialog(self, *args):
        """Método seguro para cerrar diálogos"""
        if hasattr(self, 'camera_dialog') and self.camera_dialog:
            try:
                self.camera_dialog.dismiss()
            except:
                pass
            self.camera_dialog = None

    def create_camera_callback(self, camera_id):
        """Crea un callback seguro para la selección de cámara"""

        def callback(instance):
            self.select_camera_and_dismiss_dialog(camera_id)

        return callback

    def select_camera_and_dismiss_dialog(self, camera_id):
        """Selecciona la cámara y cierra el diálogo"""
        # Cerrar primero el diálogo
        self.dismiss_dialog()

        # Luego seleccionar la cámara
        try:
            self.select_camera(camera_id)
        except Exception as e:
            logging.error(f"Error al seleccionar cámara: {str(e)}")
            self.show_message_dialog("Error", f"No se pudo seleccionar la cámara: {str(e)}")

    def select_camera(self, camera_id):
        """Selecciona la cámara especificada"""
        try:
            if self.cap:
                self.cap.release()

            # En Windows, es mejor especificar el backend DirectShow
            self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)

            # Configuración específica para asegurar que la cámara funcione
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            # Verificar que realmente obtenemos frames
            ret, frame = self.cap.read()
            if not ret or frame is None or frame.size == 0:
                raise Exception("No se pudo obtener imagen de la cámara")

            # Guardar el ID de la cámara para futuras referencias
            self.camera_id = camera_id
            logging.info(f"Cámara {camera_id} seleccionada correctamente")

            # Iniciar el seguimiento automáticamente después de seleccionar
            self.iniciar_seguimiento_con_camara()

        except Exception as e:
            logging.error(f"Error al seleccionar cámara {camera_id}: {str(e)}")
            self.show_message_dialog("Error",
                                     f"No se pudo iniciar la cámara {camera_id}. {str(e)}")

    def iniciar_seguimiento_con_camara(self):
        """Inicia el seguimiento usando la cámara ya seleccionada"""
        try:
            # Verificar que la cámara está abierta y funcionando
            if not self.cap or not self.cap.isOpened():
                raise Exception("La cámara no está abierta")

            # Leer un frame para probar si la cámara funciona
            ret, test_frame = self.cap.read()
            if not ret or test_frame is None:
                raise Exception("La cámara no devuelve frames")

            logging.info(f"Frame de prueba obtenido: {test_frame.shape}")

            # Actualizar UI
            self.btn_toggle.text = "Detener Seguimiento"
            self.btn_toggle.md_bg_color = (0.7, 0.2, 0.2, 1)
            self.btn_captura.disabled = False
            self.lbl_estado.text = "Estado: Activo"

            # Iniciar hilo de captura
            self.frame_ready = False
            self.frame_buffer = None
            self.capture_thread = threading.Thread(target=self.capturar_frames)
            self.capture_thread.daemon = True
            self.capture_thread.start()

            # Programar actualización de UI a 30 FPS para Windows
            Clock.schedule_interval(self.actualizar_ui, 1.0 / 30.0)
            logging.info("Seguimiento iniciado exitosamente")
        except Exception as e:
            logging.error(f"Error al iniciar seguimiento: {str(e)}")
            self.lbl_estado.text = f"Error: {str(e)}"
            self.show_message_dialog("Error", f"Error al iniciar seguimiento: {str(e)}")

    def toggle_seguimiento(self, *args):
        if not self.cap:
            self.iniciar_seguimiento()
        else:
            self.detener_seguimiento()

    def iniciar_seguimiento(self):
        """Inicia el proceso de seguimiento con selección de cámara"""
        # Si no hay una cámara seleccionada previamente, mostrar selección
        if not hasattr(self, 'camera_id'):
            # Verificar si tenemos una sola cámara disponible
            if len(self.available_cameras) == 1:
                self.select_camera(self.available_cameras[0])
                return
            else:
                # Si hay múltiples cámaras o ninguna, mostrar diálogo
                self.show_camera_selection()
        else:
            # Si ya hay una cámara seleccionada, intentar usarla
            try:
                if self.cap:
                    self.cap.release()

                self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    # Si falla, volver a mostrar la selección
                    self.show_camera_selection()
                    return

                self.iniciar_seguimiento_con_camara()
            except Exception as e:
                logging.error(f"Error reiniciando cámara: {str(e)}")
                # Si hay error, volver a mostrar selección
                self.show_camera_selection()

    def detener_seguimiento(self):
        if self.cap:
            Clock.unschedule(self.actualizar_ui)
            self.cap.release()
            self.cap = None
            self.btn_toggle.text = "Iniciar Seguimiento"
            self.btn_toggle.md_bg_color = (0.2, 0.7, 0.2, 1)
            self.btn_captura.disabled = True
            self.lbl_estado.text = "Estado: Inactivo"
            self.img_widget.texture = None
            self.frame_ready = False

    def capturar_frames(self):
        """Hilo dedicado a capturar frames de la cámara"""
        logging.info("Iniciando hilo de captura de frames")

        # Asegurarse de que la cámara está configurada correctamente
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()

                if not ret or frame is None or frame.size == 0:
                    logging.warning("No se pudo capturar frame válido")
                    # Pequeña pausa para evitar consumo excesivo de CPU
                    import time
                    time.sleep(0.1)
                    continue

                # Voltear frame horizontalmente para que sea como un espejo
                frame = cv2.flip(frame, 1)

                # Reducir resolución para procesamiento más rápido si es necesario
                if self.resolution_scale != 1.0:
                    h, w = frame.shape[:2]
                    new_h, new_w = int(h * self.resolution_scale), int(w * self.resolution_scale)
                    frame = cv2.resize(frame, (new_w, new_h))

                with self.processing_lock:
                    self.frame_buffer = frame.copy()
                    self.frame_ready = True

                # Pequeña pausa para evitar consumo excesivo de CPU
                import time
                time.sleep(0.01)
            except Exception as e:
                logging.error(f"Error en hilo de captura: {str(e)}")
                import time
                time.sleep(0.1)

    def actualizar_ui(self, dt):
        """Actualiza la UI con el frame procesado"""
        if not self.cap or not self.cap.isOpened():
            return False

        # Comprobamos si hay un frame disponible en el buffer
        if not self.frame_ready or self.frame_buffer is None:
            # Si no hay frame en el buffer, intentamos capturar uno directamente
            ret, frame = self.cap.read()
            if not ret or frame is None:
                # Si no se puede capturar, log e intentar en la próxima iteración
                logging.warning("No se pudo capturar frame al actualizar UI")
                return True  # Seguir intentando

            # Voltear el frame horizontalmente
            frame = cv2.flip(frame, 1)
        else:
            # Tomamos el frame del buffer con seguridad
            with self.processing_lock:
                if self.frame_buffer is None:
                    return True  # Seguir intentando
                frame = self.frame_buffer.copy()
                self.frame_ready = False

        try:
            # Verificar que el frame es válido antes de procesarlo
            if frame.size == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
                logging.warning("Frame inválido (vacío o de tamaño cero)")
                return True

            # Procesar frame para análisis de ángulo
            angulo, frame_procesado, tiene_todos_puntos = self.procesar_frame(frame)

            # Mostrar el frame procesado en la UI
            if frame_procesado is not None and frame_procesado.size > 0:
                buf = cv2.flip(frame_procesado, 0).tobytes()
                texture = Texture.create(size=(frame_procesado.shape[1], frame_procesado.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                self.img_widget.texture = texture
            else:
                logging.warning("Frame procesado inválido")

            # Actualizar la etiqueta de ángulo con diseño profesional
            if tiene_todos_puntos:
                self.lbl_angulo.text = f"Ángulo: {angulo:.1f}°"
                # Cambiar color a verde para indicar medición válida
                self.lbl_angulo.theme_text_color = "Custom"
                self.lbl_angulo.text_color = (0, 0.8, 0, 1)  # Verde
            else:
                # Si no tenemos todos los puntos, mostrar mensaje amigable
                self.lbl_angulo.text = "Buscando puntos..."
                self.lbl_angulo.theme_text_color = "Custom"
                self.lbl_angulo.text_color = (0.9, 0.5, 0, 1)  # Naranja

            # Lógica de captura automática solo si tenemos todos los puntos
            if tiene_todos_puntos and self.ultima_captura_angulo is not None:
                diferencia = abs(angulo - self.ultima_captura_angulo)
                if diferencia < 2:
                    self.tiempo_quieto += dt * 1000
                    if self.tiempo_quieto >= 1500:
                        # Solo guardar si tenemos todos los puntos
                        Clock.schedule_once(partial(self.guardar_medicion_segura, frame, angulo), 0)
                        self.tiempo_quieto = 0
                else:
                    self.tiempo_quieto = 0

                # Actualizar el último ángulo capturado solo si tenemos puntos válidos
                self.ultima_captura_angulo = angulo
            elif not tiene_todos_puntos:
                # Reset del tiempo quieto si perdemos puntos
                self.tiempo_quieto = 0

            return True
        except Exception as e:
            logging.error(f"Error en actualizar_ui: {str(e)}")
            # Si falla el procesamiento, intentar mostrar al menos el frame original
            try:
                if frame is not None and frame.size > 0:
                    buf = cv2.flip(frame, 0).tobytes()
                    texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                    texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                    self.img_widget.texture = texture
            except Exception as inner_e:
                logging.error(f"Error adicional al mostrar frame original: {str(inner_e)}")

            return True  # Seguir intentando

    def procesar_frame(self, frame):
        """Procesa el frame para detectar marcadores y calcular ángulo"""
        # Hacer una copia para no modificar el original
        frame_procesado = frame.copy()

        # Convertir a HSV (más eficiente para detección de color)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Ampliar el rango de detección para el color amarillo para facilitar la detección
        yellow_lower = np.array([15, 70, 70])  # Valores más permisivos
        yellow_upper = np.array([35, 255, 255])

        # Crear máscaras
        mask_fuchsia = cv2.inRange(hsv, self.calibracion['fuchsia']['lower'],
                                   self.calibracion['fuchsia']['upper'])
        mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)

        # Detectar marcadores
        punto_fuchsia = self.encontrar_centroide_valido(mask_fuchsia, 'fuchsia')
        puntos_yellow = self.encontrar_centroides_yellow(mask_yellow)

        # Calcular ángulo si se detectaron todos los puntos necesarios
        angulo = 0

        # Verificar si tenemos todos los puntos necesarios
        tiene_todos_puntos = punto_fuchsia and len(puntos_yellow) >= 2

        # Dibujar puntos y líneas (siempre dibujar lo que se detecte)
        if punto_fuchsia:
            cv2.circle(frame_procesado, punto_fuchsia, 7, (255, 0, 255), -1)

        # Dibujar puntos amarillos
        for i, punto in enumerate(puntos_yellow):
            cv2.circle(frame_procesado, punto, 7, (0, 255, 255), -1)

            # Dibujar líneas desde el punto fucsia a cada punto amarillo (si existe el punto fucsia)
            if punto_fuchsia:
                cv2.line(frame_procesado, punto_fuchsia, punto, (255, 255, 255), 2)

        # Dibujar línea entre puntos amarillos si hay al menos 2
        if len(puntos_yellow) >= 2:
            cv2.line(frame_procesado, puntos_yellow[0], puntos_yellow[1], (0, 165, 255), 2)

        # Calcular y mostrar ángulo si tenemos todos los puntos
        if tiene_todos_puntos:
            angulo = self.calcular_angulo(punto_fuchsia, puntos_yellow[0], puntos_yellow[1])
            angulo = self.suavizar_angulo(angulo)
            self.dibujar_indicadores(frame_procesado, punto_fuchsia, puntos_yellow, angulo)

        # Añadir overlay de estado en la esquina inferior
        alto, ancho = frame_procesado.shape[:2]
        overlay = frame_procesado.copy()

        if tiene_todos_puntos:
            # Rectángulo verde semitransparente
            cv2.rectangle(overlay, (10, alto - 50), (200, alto - 10), (0, 100, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame_procesado, 0.3, 0, frame_procesado)
            cv2.putText(frame_procesado, "LISTO", (35, alto - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            # Rectángulo naranja semitransparente (menos agresivo que rojo)
            cv2.rectangle(overlay, (10, alto - 50), (280, alto - 10), (0, 128, 255), -1)
            cv2.addWeighted(overlay, 0.7, frame_procesado, 0.3, 0, frame_procesado)
            cv2.putText(frame_procesado, "DETECTANDO...", (25, alto - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        return angulo, frame_procesado, tiene_todos_puntos

    def encontrar_centroide_valido(self, mask, color):
        """Encuentra el centroide del contorno más grande de un color específico"""
        # Usar los mismos parámetros del código original
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [c for c in contours if cv2.contourArea(c) > self.min_area]

        if not valid_contours:
            return None

        mejor_contorno = max(valid_contours, key=cv2.contourArea)
        M = cv2.moments(mejor_contorno)

        if M["m00"] == 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)

    def encontrar_centroides_yellow(self, mask):
        """Encuentra los centroides de los dos contornos amarillos más grandes"""
        # Usar exactamente la misma lógica del código original
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [c for c in contours if cv2.contourArea(c) > self.min_area]

        if len(valid_contours) < 2:
            return []

        valid_contours.sort(key=cv2.contourArea, reverse=True)
        centroides = []

        for contour in valid_contours[:2]:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                centroides.append((cx, cy))

        return centroides

    def calcular_angulo(self, punto_fuchsia, punto_yellow1, punto_yellow2):
        v1 = np.array([punto_yellow1[0] - punto_fuchsia[0],
                       punto_yellow1[1] - punto_fuchsia[1]])
        v2 = np.array([punto_yellow2[0] - punto_fuchsia[0],
                       punto_yellow2[1] - punto_fuchsia[1]])

        dot_product = np.dot(v1, v2)
        norms = np.linalg.norm(v1) * np.linalg.norm(v2)

        if norms == 0:
            return 0

        cos_angle = dot_product / norms
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))

        return angle

    def suavizar_angulo(self, angulo):
        """Suaviza el ángulo para reducir fluctuaciones usando una media móvil"""
        # Usar el mismo método de suavizado del código original
        self.angulos_buffer.append(angulo)
        return np.mean(self.angulos_buffer)

    def dibujar_indicadores(self, frame, punto_fuchsia, puntos_yellow, angulo):
        """Dibuja los indicadores visuales en el frame"""
        # Las líneas principales ya se dibujan en el método procesar_frame

        # Mostrar el ángulo con un diseño profesional
        # Crear un óvalo semitransparente alrededor del texto del ángulo
        texto_angulo = f"{angulo:.1f}°"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.9
        thickness = 2

        # Obtener dimensiones del texto
        (text_width, text_height), _ = cv2.getTextSize(texto_angulo, font, font_scale, thickness)

        # Posición del texto cerca del punto fucsia (pivote)
        text_x = punto_fuchsia[0] - text_width // 2
        text_y = punto_fuchsia[1] - 25

        # Crear óvalo de fondo
        padding = 10
        overlay = frame.copy()
        cv2.ellipse(overlay,
                    (text_x + text_width // 2, text_y),
                    (text_width // 2 + padding, text_height + padding),
                    0, 0, 360, (30, 30, 30), -1)

        # Aplicar transparencia
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Dibujar texto
        cv2.putText(frame, texto_angulo,
                    (text_x, text_y + text_height // 2),
                    font, font_scale, (255, 255, 255), thickness)

        # Dibujar arco para visualizar el ángulo con estilo profesional
        # Calcular vectores normalizados
        v1 = np.array([puntos_yellow[0][0] - punto_fuchsia[0],
                       puntos_yellow[0][1] - punto_fuchsia[1]])
        v2 = np.array([puntos_yellow[1][0] - punto_fuchsia[0],
                       puntos_yellow[1][1] - punto_fuchsia[1]])

        length1 = np.linalg.norm(v1)
        length2 = np.linalg.norm(v2)

        if length1 > 0 and length2 > 0:
            # Radio del arco proporcional a las longitudes de los vectores
            radius = min(40, int(min(length1, length2) / 4))

            # Normalizar vectores para dibujar arco
            v1_norm = v1 / length1
            v2_norm = v2 / length2

            # Calcular ángulos para el arco
            angle1 = np.degrees(np.arctan2(v1_norm[1], v1_norm[0]))
            angle2 = np.degrees(np.arctan2(v2_norm[1], v2_norm[0]))

            # Asegurar que dibujamos el arco más pequeño
            if abs(angle1 - angle2) > 180:
                if angle1 < angle2:
                    angle1 += 360
                else:
                    angle2 += 360

            # Dibujar arco con gradiente de color
            start_angle = min(angle1, angle2)
            end_angle = max(angle1, angle2)

            # Usar colores que combinen con los marcadores
            cv2.ellipse(frame, punto_fuchsia, (radius, radius),
                        0, start_angle, end_angle, (120, 120, 255), 3)

            # Añadir pequeñas marcas en los extremos del arco
            mark_length = 8
            angle1_rad = np.radians(angle1)
            angle2_rad = np.radians(angle2)

            # Puntos para las marcas
            mark1_start = (
                int(punto_fuchsia[0] + (radius - mark_length) * np.cos(angle1_rad)),
                int(punto_fuchsia[1] + (radius - mark_length) * np.sin(angle1_rad))
            )
            mark1_end = (
                int(punto_fuchsia[0] + (radius + mark_length) * np.cos(angle1_rad)),
                int(punto_fuchsia[1] + (radius + mark_length) * np.sin(angle1_rad))
            )

            mark2_start = (
                int(punto_fuchsia[0] + (radius - mark_length) * np.cos(angle2_rad)),
                int(punto_fuchsia[1] + (radius - mark_length) * np.sin(angle2_rad))
            )
            mark2_end = (
                int(punto_fuchsia[0] + (radius + mark_length) * np.cos(angle2_rad)),
                int(punto_fuchsia[1] + (radius + mark_length) * np.sin(angle2_rad))
            )

            # Dibujar las marcas
            cv2.line(frame, mark1_start, mark1_end, (100, 100, 255), 2)
            cv2.line(frame, mark2_start, mark2_end, (100, 100, 255), 2)

    def capturar_manual(self, *args):
        """Captura manual del ángulo actual"""
        if not self.cap or not self.cap.isOpened():
            return

        if self.frame_buffer is not None:
            with self.processing_lock:
                frame = self.frame_buffer.copy()

            # Procesar frame para verificar que tenemos todos los puntos
            angulo, _, tiene_todos_puntos = self.procesar_frame(frame)

            # Solo guardar si tenemos todos los puntos necesarios
            if tiene_todos_puntos:
                self.guardar_medicion(frame, angulo)
            else:
                # Informar al usuario que faltan puntos
                self.lbl_estado.text = "Error: Faltan puntos"
                Clock.schedule_once(lambda dt: self.resetear_estado(), 2)

    def guardar_medicion_segura(self, frame, angulo, *args):
        """Versión segura para ser llamada desde Clock.schedule_once"""
        self.guardar_medicion(frame, angulo)

    def guardar_medicion(self, frame, angulo):
        try:
            if self.usuario_id:
                statistics = {
                    "tiempo_quieto": self.tiempo_quieto,
                    "angulos_previos": list(self.angulos_buffer),
                    "modo_captura": "automático" if self.tiempo_quieto >= 1500 else "manual"
                }

                # Iniciar en hilo separado para no bloquear la UI
                threading.Thread(
                    target=self.db.save_angle_measurement,
                    args=(self.usuario_id, angulo, frame, statistics)
                ).start()

                self.lbl_estado.text = "¡Medición guardada!"
                Clock.schedule_once(lambda dt: self.resetear_estado(), 2)
            else:
                self.lbl_estado.text = "Error: Usuario no establecido"
                self.show_message_dialog("Error", "Usuario no establecido. Por favor, inicie sesión nuevamente.")
        except Exception as e:
            logging.error(f"Error al guardar medición: {str(e)}")
            self.lbl_estado.text = "Error al guardar"
            self.show_message_dialog("Error", f"No se pudo guardar la medición: {str(e)}")

    def resetear_estado(self):
        self.lbl_estado.text = "Estado: Activo" if self.cap else "Estado: Inactivo"

    def set_usuario_id(self, usuario_id):
        self.usuario_id = usuario_id

    def go_to_history(self):
        app = MDApp.get_running_app()
        history_screen = app.root.get_screen('historial')
        if hasattr(history_screen, 'set_previous_screen'):
            history_screen.set_previous_screen('seguimiento')
        app.root.current = 'historial'

    def show_message_dialog(self, title, message):
        """Muestra un diálogo simple con un mensaje"""
        dialog = MDDialog(
            title=title,
            text=message,
            buttons=[
                MDFlatButton(
                    text="Aceptar",
                    on_release=self.dismiss_message_dialog
                )
            ]
        )
        self.message_dialog = dialog
        dialog.open()

    def dismiss_message_dialog(self, *args):
        """Cierra el diálogo de mensaje"""
        if hasattr(self, 'message_dialog') and self.message_dialog:
            try:
                self.message_dialog.dismiss()
            except:
                pass
            self.message_dialog = None