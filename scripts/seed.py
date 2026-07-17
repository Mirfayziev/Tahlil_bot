"""
Boshlang'ich ma'lumotlarni yaratish: super admin, bo'limlar, xizmat kategoriyalari.

Ishga tushirish:
    python scripts/seed.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import User, RoleEnum, Department, ServiceCategory, Priority

app = create_app()

DEFAULT_DEPARTMENTS = [
    ("Elektr-texnik xizmat bo'limi", "Elektr va santexnika bo'yicha xizmatlar"),
    ("IT va aloqa bo'limi", "Internet, kompyuter va tarmoq xizmatlari"),
    ("Xo'jalik bo'limi", "Mebel va umumiy xo'jalik ishlari"),
]

DEFAULT_CATEGORIES = [
    ("Elektr ta'miri", "orta", 24, "Elektr-texnik xizmat bo'limi"),
    ("Santexnika", "yuqori", 12, "Elektr-texnik xizmat bo'limi"),
    ("Internet", "yuqori", 8, "IT va aloqa bo'limi"),
    ("Kompyuter", "orta", 24, "IT va aloqa bo'limi"),
    ("Konditsioner", "orta", 24, "Elektr-texnik xizmat bo'limi"),
    ("Mebel", "past", 72, "Xo'jalik bo'limi"),
    ("Xo'jalik ishlari", "past", 48, "Xo'jalik bo'limi"),
    ("Boshqa", "orta", 24, None),
]

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(full_name="Bosh Administrator", username="admin", role=RoleEnum.SUPER_ADMIN)
        admin.set_password("admin12345")
        db.session.add(admin)
        print("✔ Super admin yaratildi: login=admin, parol=admin12345 (birinchi kirishdan so'ng o'zgartiring!)")

    dept_by_name = {}
    if not Department.query.first():
        for name, description in DEFAULT_DEPARTMENTS:
            dep = Department(name=name, description=description)
            db.session.add(dep)
            dept_by_name[name] = dep
        db.session.flush()
        print(f"✔ {len(DEFAULT_DEPARTMENTS)} ta bo'lim yaratildi")
    else:
        for d in Department.query.all():
            dept_by_name[d.name] = d

    if not ServiceCategory.query.first():
        for name, priority, sla, dept_name in DEFAULT_CATEGORIES:
            db.session.add(ServiceCategory(
                name_uz=name, default_priority=Priority(priority), default_sla_hours=sla,
                department_id=dept_by_name[dept_name].id if dept_name and dept_name in dept_by_name else None,
            ))
        print(f"✔ {len(DEFAULT_CATEGORIES)} ta kategoriya yaratildi (bo'limlarga bog'langan holda)")

    db.session.commit()
    print("Baza tayyor.")
