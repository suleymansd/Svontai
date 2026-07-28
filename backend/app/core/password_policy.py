"""Central password policy used by every credential creation flow."""

COMMON_PASSWORDS = {
    "123456789012",
    "qwerty123456!",
    "svontai12345!",
}


def validate_password_strength(password: str) -> str:
    value = password or ""
    if len(value) < 12:
        raise ValueError("Şifre en az 12 karakter olmalıdır")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Şifre en fazla 72 bayt olabilir")
    if any(character.isspace() for character in value):
        raise ValueError("Şifre boşluk içeremez")
    if not any(character.islower() for character in value):
        raise ValueError("Şifre en az bir küçük harf içermelidir")
    if not any(character.isupper() for character in value):
        raise ValueError("Şifre en az bir büyük harf içermelidir")
    if not any(character.isdigit() for character in value):
        raise ValueError("Şifre en az bir rakam içermelidir")
    if not any(not character.isalnum() for character in value):
        raise ValueError("Şifre en az bir özel karakter içermelidir")
    if value.casefold() in COMMON_PASSWORDS:
        raise ValueError("Bu şifre yaygın olduğu için kullanılamaz")
    return value
