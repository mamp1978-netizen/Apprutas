import streamlit as st
print("DEBUG: main_desarrollo.py — RAMA DESARROLLO")   # <- debería verse en logs Cloud
from tab_profesional_ui import mostrar_profesional

def main():
    st.set_page_config(page_title="Apprutas (Pruebas)", layout="centered")
    mostrar_profesional()

if __name__ == "__main__":
    main()
