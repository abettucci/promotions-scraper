"""
Dashboard web para visualizar promociones
Ejecutar con: streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from database import Database
import config

# Configuración de la página
st.set_page_config(
    page_title="Promociones Bancarias - Argentina",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos custom
st.markdown("""
<style>
    .promo-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .promo-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .promo-discount {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2ca02c;
        margin: 0.5rem 0;
    }
    .promo-bank {
        background: #ff7f0e;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 5px;
        display: inline-block;
        font-weight: bold;
    }
    .promo-terms {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
        font-style: italic;
    }
    .stat-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_database():
    """Obtiene instancia de base de datos (cached)"""
    return Database()

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_promotions(supermarket=None):
    """Carga promociones de la base de datos"""
    db = get_database()
    return db.get_active_promotions(supermarket)

@st.cache_data(ttl=300)
def load_stats():
    """Carga estadísticas de supermercados"""
    db = get_database()
    return db.get_supermarket_stats()

def main():
    # Header
    st.title("🛒 Promociones Bancarias - Supermercados Argentina")
    st.markdown("*Actualizado automáticamente todos los días*")
    st.markdown("---")
    
    # Sidebar - Filtros
    st.sidebar.title("🔍 Filtros")
    
    # Cargar datos
    try:
        all_promotions = load_promotions()
        stats = load_stats()
    except Exception as e:
        st.error(f"❌ Error cargando datos: {e}")
        st.info("💡 Ejecuta primero: `python scraper.py`")
        return
    
    if not all_promotions:
        st.warning("⚠️ No hay promociones en la base de datos")
        st.info("Ejecuta el scraper primero: `python scraper.py`")
        return
    
    # Convertir a DataFrame
    df = pd.DataFrame(all_promotions)
    
    # Filtro por supermercado
    supermarkets = ["Todos"] + sorted(df['supermarket_name'].unique().tolist())
    selected_supermarket = st.sidebar.selectbox(
        "Supermercado",
        supermarkets
    )
    
    # Filtro por banco
    banks = ["Todos"] + sorted([b for b in df['bank'].unique() if b])
    selected_bank = st.sidebar.selectbox(
        "Banco",
        banks
    )
    
    # Filtro por búsqueda
    search_term = st.sidebar.text_input("🔎 Buscar en título")
    
    # Aplicar filtros
    filtered_df = df.copy()
    
    if selected_supermarket != "Todos":
        filtered_df = filtered_df[filtered_df['supermarket_name'] == selected_supermarket]
    
    if selected_bank != "Todos":
        filtered_df = filtered_df[filtered_df['bank'] == selected_bank]
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['title'].str.contains(search_term, case=False, na=False)
        ]
    
    # Ordenar por fecha de scraping
    filtered_df = filtered_df.sort_values('scraped_at', ascending=False)
    
    # Estadísticas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{len(filtered_df)}</div>
            <div>Promociones Activas</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        unique_banks = filtered_df['bank'].nunique()
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{unique_banks}</div>
            <div>Bancos</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        unique_supermarkets = filtered_df['supermarket_name'].nunique()
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{unique_supermarkets}</div>
            <div>Supermercados</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        with_terms = filtered_df['requirements'].apply(lambda x: len(x) > 0 if x else False).sum()
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{with_terms}</div>
            <div>Con Requisitos</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📋 Promociones", "📊 Estadísticas", "ℹ️ Información"])
    
    # TAB 1: Lista de Promociones
    with tab1:
        st.subheader(f"📋 {len(filtered_df)} Promociones Encontradas")
        
        if len(filtered_df) == 0:
            st.info("No se encontraron promociones con los filtros seleccionados")
        else:
            for idx, row in filtered_df.iterrows():
                with st.container():
                    col_a, col_b = st.columns([3, 1])
                    
                    with col_a:
                        # Título y supermercado
                        st.markdown(f"### 🏪 {row['supermarket_name']}")
                        st.markdown(f"<div class='promo-title'>{row['title']}</div>", unsafe_allow_html=True)
                        
                        # Descuento
                        if row['discount']:
                            st.markdown(f"<div class='promo-discount'>💰 {row['discount']}</div>", unsafe_allow_html=True)
                        
                        # Banco/Billetera
                        if row['bank']:
                            st.markdown(f"<span class='promo-bank'>🏦 {row['bank']}</span>", unsafe_allow_html=True)
                        elif row['wallet']:
                            st.markdown(f"<span class='promo-bank'>💳 {row['wallet']}</span>", unsafe_allow_html=True)
                        
                        # Fechas
                        if row['valid_until']:
                            st.caption(f"⏰ Válido hasta: {row['valid_until']}")
                    
                    with col_b:
                        if row['image_url']:
                            try:
                                st.image(row['image_url'], use_container_width=True)
                            except:
                                pass
                    
                    # Términos y condiciones
                    if row['exclusions'] or row['requirements']:
                        with st.expander("📄 Términos y Condiciones"):
                            if row['requirements']:
                                st.markdown("**✅ Requisitos:**")
                                for req in row['requirements']:
                                    st.markdown(f"- {req}")
                            
                            if row['exclusions']:
                                st.markdown("**❌ Exclusiones:**")
                                for exc in row['exclusions']:
                                    st.markdown(f"- {exc}")
                            
                            if row['max_discount']:
                                st.markdown(f"**💵 Tope de descuento:** {row['max_discount']}")
                            
                            if row['min_purchase']:
                                st.markdown(f"**🛒 Compra mínima:** {row['min_purchase']}")
                            
                            if row['terms_raw']:
                                st.markdown("**📝 Texto original:**")
                                st.caption(row['terms_raw'])
                    
                    st.markdown("---")
    
    # TAB 2: Estadísticas
    with tab2:
        st.subheader("📊 Estadísticas y Análisis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de promociones por supermercado
            st.markdown("#### Promociones por Supermercado")
            promo_by_super = df.groupby('supermarket_name').size().reset_index(name='count')
            promo_by_super = promo_by_super.sort_values('count', ascending=True)
            
            fig = px.bar(
                promo_by_super,
                x='count',
                y='supermarket_name',
                orientation='h',
                labels={'count': 'Cantidad', 'supermarket_name': 'Supermercado'},
                color='count',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Gráfico de promociones por banco
            st.markdown("#### Top 10 Bancos")
            banks_df = df[df['bank'].notna() & (df['bank'] != '')]
            if len(banks_df) > 0:
                promo_by_bank = banks_df.groupby('bank').size().reset_index(name='count')
                promo_by_bank = promo_by_bank.sort_values('count', ascending=False).head(10)
                
                fig = px.pie(
                    promo_by_bank,
                    values='count',
                    names='bank',
                    hole=0.4
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de bancos disponibles")
        
        # Tabla de estadísticas
        st.markdown("#### 📈 Estadísticas Detalladas")
        stats_df = pd.DataFrame(stats)
        if not stats_df.empty:
            stats_df['last_scraped'] = pd.to_datetime(stats_df['last_scraped'])
            stats_df['last_scraped'] = stats_df['last_scraped'].dt.strftime('%Y-%m-%d %H:%M')
            
            st.dataframe(
                stats_df,
                column_config={
                    "name": "Supermercado",
                    "active_promotions": "Promociones Activas",
                    "last_scraped": "Última Actualización",
                    "scrape_count": "Veces Scrapeado"
                },
                hide_index=True,
                use_container_width=True
            )
    
    # TAB 3: Información
    with tab3:
        st.subheader("ℹ️ Acerca del Proyecto")
        
        st.markdown("""
        ### 🛒 Scraper de Promociones Bancarias
        
        Este sistema automatiza la recolección de promociones bancarias de supermercados argentinos.
        
        **Características:**
        - ✅ Scraping automático diario
        - ✅ Extracción de términos y condiciones
        - ✅ Detección de requisitos y exclusiones
        - ✅ Base de datos SQLite
        - ✅ Dashboard interactivo
        
        **Supermercados incluidos:**
        """)
        
        for key, data in config.SUPERMARKETS.items():
            status = "✅" if data.get('enabled', True) else "❌"
            st.markdown(f"{status} **{data['name']}** - `{data['url']}`")
        
        st.markdown("""
        ---
        ### 🚀 Cómo Usar
        
        **1. Ejecutar el scraper:**
        ```bash
        python scraper.py
        ```
        
        **2. Ver el dashboard:**
        ```bash
        streamlit run dashboard.py
        ```
        
        **3. Programar ejecución automática:**
        ```bash
        # Agregar a crontab (Linux/Mac)
        0 9 * * * cd /path/to/promo-scraper && python scraper.py
        ```
        
        ---
        ### 📊 Base de Datos
        
        - **Ubicación:** `{}`
        - **Tipo:** SQLite
        - **Tablas:** supermarkets, promotions, terms_conditions, scrape_history
        
        """.format(config.DATABASE_PATH))
        
        # Botón para recargar datos
        if st.button("🔄 Recargar Datos"):
            st.cache_data.clear()
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>"
        "Creado con ❤️ para Argentina 🇦🇷 | "
        "Última actualización: " + datetime.now().strftime('%Y-%m-%d %H:%M') +
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

