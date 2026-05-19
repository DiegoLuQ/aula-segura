from database import engine, SessionLocal
import models
from auth import get_password_hash

def seed():
    db = SessionLocal()
    
    # 1. Crear Roles
    lawyer_rol = db.query(models.Rol).filter(models.Rol.rol == "lawyer").first()
    if not lawyer_rol:
        lawyer_rol = models.Rol(rol="lawyer")
        db.add(lawyer_rol)
    
    viewer_rol = db.query(models.Rol).filter(models.Rol.rol == "viewer").first()
    if not viewer_rol:
        viewer_rol = models.Rol(rol="viewer")
        db.add(viewer_rol)

    super_viewer_rol = db.query(models.Rol).filter(models.Rol.rol == "super_viewer").first()
    if not super_viewer_rol:
        super_viewer_rol = models.Rol(rol="super_viewer")
        db.add(super_viewer_rol)

    admin_rol = db.query(models.Rol).filter(models.Rol.rol == "admin").first()
    if not admin_rol:
        admin_rol = models.Rol(rol="admin")
        db.add(admin_rol)
    
    db.commit()
    db.refresh(lawyer_rol)
    db.refresh(viewer_rol)
    db.refresh(super_viewer_rol)
    db.refresh(admin_rol)
    
    # 2. Crear Colegios
    colegio1 = db.query(models.Colegio).filter(models.Colegio.nombre == "Colegio Macaya").first()
    if not colegio1:
        colegio1 = models.Colegio(nombre="Colegio Macaya")
        db.add(colegio1)
    
    colegio2 = db.query(models.Colegio).filter(models.Colegio.nombre == "Diego Portales").first()
    if not colegio2:
        colegio2 = models.Colegio(nombre="Diego Portales")
        db.add(colegio2)
    
    db.commit()
    db.refresh(colegio1)
    db.refresh(colegio2)
    
    # 3. Crear Usuarios
    # Lawyer
    admin = db.query(models.Usuario).filter(models.Usuario.nombre == "lawyer_user").first()
    if not admin:
        admin = models.Usuario(
            nombre="lawyer_user",
            clave=get_password_hash("lawyer123"),
            id_rol=lawyer_rol.id,
            id_colegio=colegio1.id
        )
        db.add(admin)
    
    # Viewer
    viewer = db.query(models.Usuario).filter(models.Usuario.nombre == "viewer_user").first()
    if not viewer:
        viewer = models.Usuario(
            nombre="viewer_user",
            clave=get_password_hash("viewer123"),
            id_rol=viewer_rol.id,
            id_colegio=colegio1.id
        )
        db.add(viewer)

    # Super Viewer
        super_user = models.Usuario(
            nombre="super_user",
            clave=get_password_hash("super123"),
            id_rol=super_viewer_rol.id,
            id_colegio=colegio1.id
        )
        db.add(super_user)

    # Admin User
    admin_user = db.query(models.Usuario).filter(models.Usuario.nombre == "admin_user").first()
    if not admin_user:
        admin_user = models.Usuario(
            nombre="admin_user",
            clave=get_password_hash("admin123"),
            id_rol=admin_rol.id,
            id_colegio=colegio1.id
        )
        db.add(admin_user)
    
    db.commit()
    print("Seed completado: \nLawyer: lawyer_user / lawyer123 \nViewer: viewer_user / viewer123 \nSuper Viewer: super_user / super123 \nAdmin: admin_user / admin123")

if __name__ == "__main__":
    seed()
