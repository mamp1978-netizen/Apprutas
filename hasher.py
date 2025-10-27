import streamlit_authenticator as stauth

# Contraseña que queremos usar (por ejemplo, 'testpassword')
password_to_hash = "testpassword"

# Generar el hash
hashed_password = stauth.Hasher([password_to_hash]).generate()

# Imprimir el hash para que puedas copiarlo
print("\n--- COPIA ESTE HASH ---\n")
print(hashed_password[0])
print("\n----------------------\n")
