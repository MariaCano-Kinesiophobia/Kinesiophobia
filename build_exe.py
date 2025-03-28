"""
Script para crear un ejecutable de Windows con PyInstaller para KinesofobiaApp
Con fix para problemas de codificación y manejo correcto de dependencias
"""
import os
import sys
import shutil
import subprocess
import glob
import codecs
import certifi
cert_path = certifi.where()

# Obtener todos los archivos Python y KV de la aplicación
def get_all_app_files():
    """Obtener todos los archivos Python y KV de la aplicación"""
    python_files = glob.glob("*.py")
    kv_files = glob.glob("*.kv")

    # Eliminar este script de la lista para evitar incluirlo en la aplicación
    if "build_exe.py" in python_files:
        python_files.remove("build_exe.py")

    all_files = python_files + kv_files
    print(f"Archivos de la aplicación encontrados: {all_files}")
    return all_files


def check_encoding_issues():
    """Verificar y corregir problemas de codificación en archivos de código"""
    print("🔍 Verificando problemas de codificación en archivos...")

    # Lista de archivos Python a verificar
    python_files = glob.glob("*.py") + glob.glob("*.kv")

    for file_path in python_files:
        print(f"  Verificando: {file_path}")
        try:
            # Intentar leer como UTF-8
            with codecs.open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f"    ⚠️ Detectado problema de codificación en: {file_path}")
            try:
                # Leer como Latin-1 (que puede leer cualquier byte)
                with codecs.open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()

                # Guardar como UTF-8 con BOM para asegurar que Windows lo interprete correctamente
                with codecs.open(file_path + ".utf8", 'w', encoding='utf-8-sig') as f:
                    f.write(content)

                # Renombrar archivo
                os.remove(file_path)
                os.rename(file_path + ".utf8", file_path)
                print(f"    ✅ Archivo convertido a UTF-8: {file_path}")
            except Exception as e:
                print(f"    ❌ Error al convertir archivo: {str(e)}")

    print("✅ Verificación de codificación completada")


def clean_directories():
    """Limpiar directorios de compilaciones previas"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 Limpiando directorio: {dir_name}")
            shutil.rmtree(dir_name)

    # Eliminar archivos .spec existentes
    for spec_file in glob.glob("*.spec"):
        print(f"🧹 Eliminando archivo spec: {spec_file}")
        os.remove(spec_file)

    # Crear directorios necesarios
    for dir_name in ['build', 'dist']:
        os.makedirs(dir_name, exist_ok=True)


def create_runtime_hook():
    """Crear runtime hook con codificación UTF-8 y manejo de recursos"""
    hook_content = """
# -*- coding: utf-8 -*-
import os
import sys

# Función para manejar rutas de recursos
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Configurar codificación por defecto a UTF-8
import locale
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass

# Configurar la codificación de archivos a UTF-8 solo si no es None
import io
if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Agregar el directorio de la aplicación a la ruta de búsqueda de DLLs
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(os.path.dirname(sys.executable))

# Fix para asegurarse que Kivy puede encontrar sus dependencias
os.environ['KIVY_NO_CONSOLELOG'] = '1'

# Configurar la ruta de los certificados SSL
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
"""

    with codecs.open("runtime_hook.py", "w", encoding='utf-8-sig') as f:
        f.write(hook_content)

    print("✅ Runtime hook creado")


def run_pyinstaller():
    """Ejecutar PyInstaller para crear el ejecutable"""
    print("🚀 Ejecutando PyInstaller...")

    app_name = "KinesofobiaApp"

    # Crear runtime hook personalizado
    create_runtime_hook()

    # Obtener todos los archivos de la aplicación
    app_files = get_all_app_files()

    # Crear la lista de argumentos para PyInstaller
    pyinstaller_args = [
        'main.py',
        f'--name={app_name}',
        '--windowed',  # Sin consola para la versión final
        '--onefile',  # Un solo archivo ejecutable
    ]

    # Si existe el icono, usarlo
    if os.path.exists('assets/logo.ico'):
        pyinstaller_args.append('--icon=assets/logo.ico')
    elif os.path.exists('assets/logo.png'):
        pyinstaller_args.append('--icon=assets/logo.png')

    # Agregar todos los archivos Python y KV
    for file in app_files:
        if file != "main.py":  # main.py ya se incluye como punto de entrada
            pyinstaller_args.append(f'--add-data={file};.')

    # Agregar carpetas de recursos
    pyinstaller_args.extend([
        '--add-data=assets;assets',  # Agregar carpeta de recursos
        f'--add-data={cert_path};certifi',  # Incluir certificados
        '--runtime-hook=runtime_hook.py',  # Hook para arreglar problemas
    ])

    # Agregar imports ocultos manualmente en lugar de usar collect-all
    hidden_imports = [
        'kivy',
        'kivy.core.window',
        'kivy.core.text',
        'kivy.core.audio',
        'kivy.core.image',
        'kivy.core.video',
        'kivy.core.clipboard',
        'kivy.core.camera',
        'kivy.core.gl',
        'kivy.graphics',
        'kivy.graphics.context_instructions',
        'kivy.graphics.compiler',
        'kivy.graphics.fbo',
        'kivy.graphics.instructions',
        'kivy.graphics.opengl',
        'kivy.graphics.shader',
        'kivy.graphics.stencil_instructions',
        'kivy.graphics.texture',
        'kivy.graphics.transformation',
        'kivy.graphics.vertex',
        'kivy.graphics.vertex_instructions',
        'kivy.factory_registers',
        'kivy.input.providers',
        'kivy.input.providers.mouse',
        'kivy.input.providers.tuio',
        'kivymd',
        'kivymd.uix',
        'kivymd.uix.button',
        'kivymd.uix.dialog',
        'kivymd.uix.screen',
        'kivymd.uix.screenmanager',
        'kivymd.uix.textfield',
        'kivymd.uix.boxlayout',
        'pymongo',
        'pymongo.mongo_client',
        'pymongo.collection',
        'pymongo.cursor',
        'pymongo.database',
        'pymongo.pool',
        'pymongo.results',
        'cv2',
        'numpy',
        'gridfs',
        'certifi',
        'urllib3',
        'bson',
        'bson.binary',
        'dns',
        'dns.resolver',
    ]

    for imp in hidden_imports:
        pyinstaller_args.append(f'--hidden-import={imp}')

    # Opciones adicionales
    pyinstaller_args.extend([
        '--log-level=DEBUG',  # Maximizar información de depuración
        '--clean',  # Limpiar caché
        '--noconfirm',  # No preguntar para sobrescribir
    ])

    # Ejecutar PyInstaller con codificación explícita en el entorno
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'

    try:
        print("Ejecutando PyInstaller con los siguientes argumentos:")
        print(" ".join([sys.executable, "-m", "PyInstaller"] + pyinstaller_args))

        # Usar subprocess con configuración de codificación
        process = subprocess.Popen(
            [sys.executable, "-m", "PyInstaller"] + pyinstaller_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            universal_newlines=True,
            encoding='utf-8'
        )

        # Mostrar salida en tiempo real
        stdout, stderr = process.communicate()

        # Mostrar salida
        if stdout:
            print("Salida estándar:")
            print(stdout)

        if stderr:
            print("Errores:")
            print(stderr)

        if process.returncode != 0:
            print(f"❌ Error al ejecutar PyInstaller (código: {process.returncode})")
            return False

        print("✅ PyInstaller completado exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error al ejecutar PyInstaller: {str(e)}")
        return False


def main():
    print("🔨 Iniciando construcción del ejecutable de KinesofobiaApp...")

    # Verificar y corregir problemas de codificación
    check_encoding_issues()

    # Limpiar directorios
    clean_directories()

    # Ejecutar PyInstaller
    if not run_pyinstaller():
        return 1

    print("\n✨ Construcción del ejecutable completada exitosamente!")
    print(f"📂 El ejecutable se encuentra en: dist/KinesofobiaApp.exe")

    return 0


if __name__ == "__main__":
    sys.exit(main())