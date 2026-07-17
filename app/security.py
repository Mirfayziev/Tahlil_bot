"""Xavfsizlik bilan bog'liq yordamchi funksiyalar (TZ v2, bo'lim 1: Xavfsizlik)."""
import re


def validate_password_strength(password: str, min_length: int = 8) -> list[str]:
    """Parol siyosatiga mos kelmasa, xatoliklar ro'yxatini qaytaradi (bo'sh — parol yaroqli)."""
    errors = []
    if not password or len(password) < min_length:
        errors.append(f"Parol kamida {min_length} ta belgidan iborat bo'lishi kerak.")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("Parolda kamida bitta katta harf bo'lishi kerak.")
    if not re.search(r"[a-z]", password or ""):
        errors.append("Parolda kamida bitta kichik harf bo'lishi kerak.")
    if not re.search(r"\d", password or ""):
        errors.append("Parolda kamida bitta raqam bo'lishi kerak.")
    return errors
