from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, NetworkTimeout
from datetime import datetime
import gridfs
import cv2
import logging
import certifi
from functools import wraps
import time
import os
import platform
import tempfile

# Crear directorio de datos para la aplicación
app_data_dir = os.path.join(os.path.expanduser('~'), 'KinesofobiaAppData')
if not os.path.exists(app_data_dir):
    os.makedirs(app_data_dir)

def retry_connection(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        continue
            raise last_error

        return wrapper

    return decorator


class DatabaseConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConfig, cls).__new__(cls)
            cls._instance.initialized = False
            cls._instance.offline_mode = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return

        try:
            # Verificar conectividad de red antes de intentar conectar
            self.check_connectivity()

            # Asegurarse de que certifi puede encontrar los certificados
            self.ensure_certificates()

            # Crear instancia de cliente MongoDB
            logging.info("Iniciando conexión a MongoDB...")
            self.client = MongoClient(
                "mongodb+srv://kinesiophobiadb:Kinesiophobiadb@kinesiophobiadb.iep8p.mongodb.net/?retryWrites=true&w=majority&appName=Kinesiophobiadb",
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                maxPoolSize=1,
                minPoolSize=1,
                maxIdleTimeMS=30000,
                waitQueueTimeoutMS=10000,
                retryWrites=True,
                retryReads=True,
                connect=True
            )

            # Verificar conexión con timeout mayor
            logging.info("Verificando conexión...")
            self.client.admin.command('ping', serverSelectionTimeoutMS=10000)

            self.db = self.client['kinesiophobia']
            self.fs = gridfs.GridFS(self.db)
            self.initialized = True
            self.offline_mode = False
            logging.info("Conexión a MongoDB establecida exitosamente")

        except NetworkTimeout:
            logging.warning("Timeout al conectar a MongoDB - entrando en modo offline")
            self.handle_offline_mode()
        except Exception as e:
            logging.error(f"Error inicializando conexión a MongoDB: {str(e)}")
            self.handle_offline_mode()

    def check_connectivity(self):
        """Verifica si hay conectividad de red"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            logging.info("Conectividad de red verificada")
            return True
        except OSError:
            logging.warning("No hay conectividad de red")
            return False

    def ensure_certificates(self):
        """Asegura que los certificados estén disponibles"""
        try:
            cert_path = certifi.where()
            logging.info(f"Ruta de certificados: {cert_path}")

            # Verificar si el archivo existe
            if not os.path.exists(cert_path):
                logging.warning(f"Archivo de certificados no encontrado en {cert_path}")

                # Registrar información para diagnóstico
                debug_log_path = os.path.join(app_data_dir, "cert_debug.log")
                with open(debug_log_path, "w") as f:
                    f.write(f"Ruta original: {cert_path}\n")
                    f.write(f"Verificando certificados...\n")

                    # Listar archivos en directorio Python
                    import sys
                    python_path = os.path.dirname(sys.executable)
                    f.write(f"Python path: {python_path}\n")

                    # Listar algunos directorios comunes
                    dirs_to_check = [
                        python_path,
                        os.path.join(python_path, "certifi"),
                        os.path.join(os.path.dirname(__file__)),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "certifi"))
                    ]

                    for directory in dirs_to_check:
                        f.write(f"Verificando {directory}:\n")
                        if os.path.exists(directory):
                            f.write(f"  - Existe\n")
                            try:
                                files = os.listdir(directory)
                                f.write(f"  - Archivos: {files}\n")
                            except:
                                f.write("  - No se pueden listar archivos\n")
                        else:
                            f.write(f"  - No existe\n")
        except Exception as e:
            logging.error(f"Error al verificar certificados: {e}")

    def handle_offline_mode(self):
        """Configura el modo sin conexión"""
        self.offline_mode = True
        self.initialized = True
        logging.warning("Entrando en modo offline - algunas funciones estarán limitadas")

    @retry_connection()
    def save_user(self, cedula, nombre, apellido, hashed_password):
        """Guarda un nuevo usuario en la base de datos"""
        if self.offline_mode:
            # En modo offline, simulamos un ID para desarrollo
            import uuid
            dummy_id = str(uuid.uuid4())
            logging.warning(f"Modo offline: Simulando registro de usuario con ID: {dummy_id}")
            return {"insertedId": dummy_id}

        try:
            users = self.db.users
            existing_user = users.find_one({"cedula": cedula})
            if existing_user:
                raise Exception("Usuario ya existe")

            user_data = {
                "cedula": cedula,
                "nombre": nombre,
                "apellido": apellido,
                "password": hashed_password,
                "created_at": datetime.utcnow()
            }
            result = users.insert_one(user_data)
            return result
        except Exception as e:
            logging.error(f"Error guardando usuario: {str(e)}")
            raise

    @retry_connection()
    def verify_user(self, cedula, hashed_password):
        """Verifica las credenciales del usuario"""
        if self.offline_mode:
            # En modo offline, permitimos cualquier credencial para desarrollo
            import uuid
            logging.warning("Modo offline: Verificación simulada de usuario")
            return {
                "_id": str(uuid.uuid4()),
                "cedula": cedula,
                "nombre": "Usuario",
                "apellido": "Desarrollo",
                "created_at": datetime.utcnow()
            }

        try:
            users = self.db.users
            user = users.find_one({"cedula": cedula, "password": hashed_password})
            return user
        except Exception as e:
            logging.error(f"Error verificando usuario: {str(e)}")
            raise

    @retry_connection()
    def save_angle_measurement(self, user_id, angle, frame, statistics=None):
        """
        Guarda una medición de ángulo con su imagen y estadísticas
        """
        if self.offline_mode:
            # En modo offline, simular guardado de medición para desarrollo
            import uuid
            dummy_id = str(uuid.uuid4())

            # Guardar imagen en directorio local
            debug_dir = os.path.join(app_data_dir, 'images')
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)

            filename = f"angle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(os.path.join(debug_dir, filename), frame)

            logging.warning(f"Modo offline: Simulando guardado de medición con ID: {dummy_id}")
            return {"insertedId": dummy_id}

        try:
            # Comprimir imagen antes de guardar
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            image_bytes = buffer.tobytes()

            # Generar nombre de archivo con timestamp actual
            current_timestamp = datetime.utcnow()
            file_id = self.fs.put(
                image_bytes,
                filename=f"angle_{current_timestamp.strftime('%Y%m%d_%H%M%S')}.jpg",
                content_type='image/jpeg'
            )

            measurements = self.db.angle_measurements
            measurement_data = {
                "user_id": user_id,
                "angle": angle,
                "image_id": file_id,
                "timestamp": current_timestamp,
                "statistics": statistics if statistics else {}
            }
            result = measurements.insert_one(measurement_data)
            return result
        except Exception as e:
            logging.error(f"Error guardando medición: {str(e)}")
            raise

    @retry_connection()
    def save_questionnaire_result(self, user_id, responses, total_score, level, description):
        """Guarda los resultados del cuestionario TSK-11"""
        if self.offline_mode:
            # En modo offline, simular guardado de resultados para desarrollo
            import uuid
            dummy_id = str(uuid.uuid4())

            logging.warning(f"Modo offline: Simulando guardado de cuestionario con ID: {dummy_id}")
            return {"insertedId": dummy_id}

        try:
            questionnaire_results = self.db.questionnaire_results
            result_data = {
                "user_id": user_id,
                "responses": responses,
                "total_score": total_score,
                "level": level,
                "description": description,
                "timestamp": datetime.utcnow()
            }
            result = questionnaire_results.insert_one(result_data)
            return result
        except Exception as e:
            logging.error(f"Error guardando resultados del cuestionario: {str(e)}")
            raise

    @retry_connection()
    def get_user_measurements(self, user_id, limit=50):
        """Obtiene las últimas mediciones de un usuario"""
        if self.offline_mode:
            # En modo offline, devolver datos de prueba para desarrollo
            logging.warning("Modo offline: Devolviendo mediciones simuladas")

            # Generar datos simulados
            mock_data = []
            for i in range(5):
                timestamp = datetime.now()
                timestamp = timestamp.replace(day=timestamp.day - i)

                mock_data.append({
                    "_id": f"mock_id_{i}",
                    "user_id": user_id,
                    "angle": 45.0 + i * 5,
                    "image_id": f"mock_image_{i}",
                    "timestamp": timestamp,
                    "statistics": {
                        "tiempo_quieto": 1500,
                        "angulos_previos": [44.0, 44.5, 45.0],
                        "modo_captura": "automático"
                    }
                })

            return mock_data

        try:
            measurements = self.db.angle_measurements
            return list(measurements.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit))
        except Exception as e:
            logging.error(f"Error obteniendo mediciones: {str(e)}")
            return []

    @retry_connection()
    def get_user_questionnaire_results(self, user_id, limit=10):
        """Obtiene los últimos resultados de cuestionarios de un usuario"""
        if self.offline_mode:
            # En modo offline, devolver datos de prueba para desarrollo
            logging.warning("Modo offline: Devolviendo resultados de cuestionario simulados")

            # Generar datos simulados
            mock_data = []
            for i in range(3):
                timestamp = datetime.now()
                timestamp = timestamp.replace(day=timestamp.day - i * 7)  # Cada 7 días

                mock_data.append({
                    "_id": f"mock_id_{i}",
                    "user_id": user_id,
                    "responses": {
                        "0": 2, "1": 3, "2": 1, "3": 4, "4": 2,
                        "5": 3, "6": 2, "7": 1, "8": 2, "9": 3, "10": 2
                    },
                    "total_score": 25,
                    "level": "Nivel moderado de kinesofobia",
                    "description": "Los resultados sugieren un nivel moderado de miedo al movimiento. Se recomienda consultar con un profesional de la salud.",
                    "timestamp": timestamp
                })

            return mock_data

        try:
            results = self.db.questionnaire_results
            return list(results.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit))
        except Exception as e:
            logging.error(f"Error obteniendo resultados de cuestionarios: {str(e)}")
            return []

    def close(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'client') and not self.offline_mode:
            try:
                self.client.close()
                logging.info("Conexión a MongoDB cerrada")
            except Exception as e:
                logging.error(f"Error al cerrar conexión a MongoDB: {e}")

    def __del__(self):
        self.close()