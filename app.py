import streamlit as st

st.set_page_config(page_title="AppRutas", layout="wide")

try:
    from photo_agent_app import main
    main()
except Exception as e:
    st.error(f"Ocurrió un error al iniciar la aplicación: {e}")
    import traceback
    st.code(traceback.format_exc())
