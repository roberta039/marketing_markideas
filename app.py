import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
import tempfile
import os

# --- 1. Configurare Pagină ---
st.set_page_config(
    page_title="Marketing Portfolio Optimizer (Vision)",
    page_icon="👁️",
    layout="wide"
)

# --- 2. Gestionare Secrete ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ Cheile API lipsesc! Configurează secrets.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcții Helper ---

@st.cache_data(ttl=3600)
def get_available_gemini_models():
    """Returnează modelele care suportă imagini/fișiere."""
    models_list = []
    try:
        for m in genai.list_models():
            # Căutăm modele 'gemini' care suportă generare de conținut
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                models_list.append(m.name)
        models_list.sort(reverse=True)
        return models_list
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(uploaded_file, mime_type="application/pdf"):
    """Încarcă fișierul pe Google AI pentru analiză vizuală."""
    try:
        # 1. Salvăm fișierul temporar pe disk (Streamlit îl ține în RAM)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        # 2. Îl încărcăm pe serverele Google
        file_ref = genai.upload_file(tmp_file_path, mime_type=mime_type)
        
        # 3. Ștergem fișierul local temporar
        os.remove(tmp_file_path)
        
        return file_ref
    except Exception as e:
        st.error(f"Eroare la upload către Google: {e}")
        return None

def search_internet(query):
    """Căutare Tavily."""
    try:
        response = tavily_client.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
        context = ""
        if 'answer' in response:
            context += f"Tavily Summary: {response['answer']}\n"
        for res in response.get('results', []):
            context += f"- {res['content']} ({res['url']})\n"
        return context
    except Exception as e:
        return f"Eroare search: {e}"

# --- 4. Interfață ---

st.title("👁️ Asistent Marketing (Cu Viziune)")
st.markdown("Acest AI **vede** imaginile din catalog (culori, design, layout) și le compară cu trendurile de pe net.")

with st.sidebar:
    st.header("⚙️ Configurare")
    
    # Selector Model
    models = get_available_gemini_models()
    selected_model = st.selectbox("Alege Model:", models, index=0, format_func=lambda x: x.replace("models/", "").upper())
    
    st.divider()
    st.header("📂 Catalog")
    uploaded_file = st.file_uploader("Încarcă Catalog PDF", type=['pdf'])
    
    if st.button("Reset Chat"):
        st.session_state.messages = []
        # Opțional: Poți șterge și referința la fișier dacă vrei
        st.rerun()

# --- 5. Logică Principală ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare Fișier (Upload o singură dată la Google)
if uploaded_file:
    # Verificăm dacă fișierul curent este diferit de cel procesat anterior
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        with st.spinner("📤 Trimit catalogul către 'ochii' AI-ului (Google Vision)..."):
            google_file_ref = upload_to_gemini(uploaded_file)
            
            if google_file_ref:
                st.session_state.gemini_file = google_file_ref
                st.session_state.current_file_name = uploaded_file.name
                st.success("✅ Catalog încărcat! AI-ul vede acum imaginile și textul.")
            else:
                st.error("Nu s-a putut procesa fișierul.")

# Chat UI
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Ex: Arată designul pixurilor de la pag 5 demodat?"):
    
    if "gemini_file" not in st.session_state:
        st.error("Încarcă catalogul PDF mai întâi.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            loader = st.empty()
            with st.spinner("Analizez vizual și caut pe net..."):
                
                # 1. Căutare net
                web_data = search_internet(prompt)
                
                # 2. Configurare Prompt Multimodal
                # Îi trimitem LISTA: [Prompt Text, Obiectul Fișier PDF]
                input_content = [
                    f"""Ești un expert în design de produs și marketing.
                    Analizează fișierul PDF atașat (text ȘI imagini).
                    
                    CONTEXT DIN INTERNET:
                    {web_data}
                    
                    ÎNTREBARE UTILIZATOR:
                    {prompt}
                    
                    INSTRUCȚIUNI:
                    - Te rog să te uiți la imaginile produselor.
                    - Comentează despre estetică, culori și design în raport cu trendurile actuale.
                    - Dacă întrebarea e despre o pagină anume, uită-te la acea pagină.
                    """,
                    st.session_state.gemini_file
                ]
                
                try:
                    model = genai.GenerativeModel(selected_model)
                    response = model.generate_content(input_content, stream=True)
                    
                    full_text = ""
                    for chunk in response:
                        if chunk.text:
                            full_text += chunk.text
                            loader.markdown(full_text + "▌")
                    loader.markdown(full_text)
                    st.session_state.messages.append({"role": "assistant", "content": full_text})
                    
                except Exception as e:
                    loader.error(f"Eroare: {e}")
