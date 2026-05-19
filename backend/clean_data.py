import os
import sys
import shutil
import argparse
from sqlalchemy import text
from database import engine

# Definicion de colores para la consola (Estetica Premium)
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_ENDC = "\033[0m"
COLOR_BOLD = "\033[1m"

def print_banner():
    banner = f"""
{COLOR_WARNING}{COLOR_BOLD}======================================================================
                  SISTEMA AULA SEGURA - SCRIPT DE LIMPIEZA
======================================================================{COLOR_ENDC}
Este script eliminara permanentemente la informacion operacional del sistema:
- Estudiantes e historiales de procesos
- Documentos asociados a estudiantes (PDFs, descargos, actas)
- Otras Medidas registradas
- Documentos asociados a otras medidas

{COLOR_GREEN}{COLOR_BOLD}SE CONSERVARA UNICAMENTE:{COLOR_ENDC}
- Roles (lawyer, viewer, admin, etc.)
- Colegios / Establecimientos
- Usuarios del sistema (claves y asignaciones)
- Estructura y migraciones de la base de datos (Alembic)
======================================================================
"""
    print(banner)

def clear_database_tables():
    tables_to_clear = [
        "pro_aula_segura_documentos_otras_medidas",
        "pro_aula_segura_documentos",
        "pro_aula_segura_otras_medidas",
        "pro_aula_segura_estudiantes"
    ]
    
    print(f"\n{COLOR_BLUE}[1/2] Conectando a la base de datos y limpiando tablas...{COLOR_ENDC}")
    
    try:
        with engine.connect() as connection:
            # Desactivar restricciones de llaves foraneas temporalmente
            # para poder usar TRUNCATE, lo cual reinicia los contadores AUTO_INCREMENT.
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            print(f"  {COLOR_GREEN}[OK]{COLOR_ENDC} Restricciones de llaves foraneas desactivadas temporalmente.")
            
            for table in tables_to_clear:
                try:
                    # Truncar tabla
                    connection.execute(text(f"TRUNCATE TABLE {table};"))
                    print(f"  {COLOR_GREEN}[OK]{COLOR_ENDC} Tabla '{table}' vaciada con exito (AUTO_INCREMENT reiniciado).")
                except Exception as e:
                    print(f"  {COLOR_FAIL}[ERROR]{COLOR_ENDC} Error al vaciar la tabla '{table}': {e}")
            
            # Reactivar restricciones de llaves foraneas
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            print(f"  {COLOR_GREEN}[OK]{COLOR_ENDC} Restricciones de llaves foraneas reactivadas.")
            
            # Confirmar cambios
            connection.commit()
            print(f"\n{COLOR_GREEN}{COLOR_BOLD}Base de datos limpiada exitosamente!{COLOR_ENDC}")
            
    except Exception as e:
        print(f"\n{COLOR_FAIL}{COLOR_BOLD}Error critico en la base de datos: {e}{COLOR_ENDC}")
        sys.exit(1)

def clear_uploads_folder():
    print(f"\n{COLOR_BLUE}[2/2] Limpiando archivos fisicos en la carpeta 'uploads'...{COLOR_ENDC}")
    
    # Obtener la ruta de la carpeta uploads
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    
    if not os.path.exists(uploads_dir):
        print(f"  {COLOR_WARNING}[AVISO]{COLOR_ENDC} La carpeta de subidas '{uploads_dir}' no existe. Creandola...")
        os.makedirs(uploads_dir)
        return
        
    files_deleted = 0
    errors = 0
    
    # Recorrer y eliminar contenido
    for item_name in os.listdir(uploads_dir):
        item_path = os.path.join(uploads_dir, item_name)
        # Evitar borrar archivos de sistema o .gitkeep si existiera
        if item_name.startswith("."):
            continue
            
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
                files_deleted += 1
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                files_deleted += 1
        except Exception as e:
            print(f"  {COLOR_FAIL}[ERROR]{COLOR_ENDC} No se pudo eliminar '{item_name}': {e}")
            errors += 1
            
    print(f"  {COLOR_GREEN}[OK]{COLOR_ENDC} Archivos eliminados en uploads: {files_deleted}")
    if errors > 0:
        print(f"  {COLOR_WARNING}[AVISO]{COLOR_ENDC} Hubo {errors} errores al intentar borrar algunos archivos.")
    else:
        print(f"  {COLOR_GREEN}[OK]{COLOR_ENDC} La carpeta de subidas esta completamente vacia y limpia.")

def main():
    parser = argparse.ArgumentParser(description="Script de limpieza para Aula Segura.")
    parser.add_argument(
        "--force", "-f", 
        action="store_true", 
        help="Ejecuta la limpieza sin solicitar confirmacion manual (modo automatico)."
    )
    args = parser.parse_args()
    
    print_banner()
    
    if not args.force:
        # Confirmacion interactiva de seguridad
        print(f"{COLOR_WARNING}{COLOR_BOLD}ADVERTENCIA!{COLOR_ENDC} Esta accion no se puede deshacer.")
        confirm = input(f"Escriba {COLOR_BOLD}'si'{COLOR_ENDC} o {COLOR_BOLD}'yes'{COLOR_ENDC} para confirmar la limpieza completa: ").strip().lower()
        
        if confirm not in ["si", "yes"]:
            print(f"\n{COLOR_FAIL}Operacion cancelada por el usuario.{COLOR_ENDC}")
            sys.exit(0)
            
    print(f"\n{COLOR_WARNING}{COLOR_BOLD}Iniciando limpieza completa...{COLOR_ENDC}")
    clear_database_tables()
    clear_uploads_folder()
    
    print(f"\n{COLOR_GREEN}{COLOR_BOLD}======================================================================{COLOR_ENDC}")
    print(f"{COLOR_GREEN}{COLOR_BOLD}          PROCESO DE LIMPIEZA FINALIZADO CON EXITO{COLOR_ENDC}")
    print(f"{COLOR_GREEN}{COLOR_BOLD}======================================================================{COLOR_ENDC}\n")

if __name__ == "__main__":
    main()
