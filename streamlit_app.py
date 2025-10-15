import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Arbitraje Dólar Oficial vs Crypto", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS PERSONALIZADOS (CSS) ---
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            width: 400px !important;
        }
        .big-metric {
            font-size: 2rem;
            font-weight: bold;
            text-align: center;
        }
        .profit-positive {
            color: #00ff00;
        }
        .profit-negative {
            color: #ff4444;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- EXCHANGES DISPONIBLES ---
EXCHANGES = [
    "binancep2p", "belo", "astropay", "bitso", "trubit", "binance",
    "tiendacrypto", "fiwind", "ripio", "buenbit", "bybit2p", "cryptomkt",
    "universalcoins", "letsbit", "ripioexchange", "pollux", "pluscrypto",
    "bybit", "dolarsop", "lemoncash", "huobi2p", "cocoscrypto", "saldo",
    "bitsoalpha", "satoshitango", "okex2p", "bitget2p", "eluter",
    "paydecep2p", "decrypto", "kriptonmarket", "kucoin2p", "inp2pbot2p",
    "airtm", "cocos", "paxfulp2p", "trubit2p", "wallbit", "cryptomktpro",
    "eldoradop2p", "takenos", "coinexp2p", "bingxp2p", "prex", "vibrant",
    "lemoncashp2p"
]

# --- CONSTANTES ---
COMISION_PORCENTAJE = 0.03  # 3%
COMISION_ENVIO_USDT = 1  # 1 USDT
VOLUMEN_MINIMO_DEFAULT = 100  # USD por defecto

# --- CACHING Y CARGA DE DATOS ---
@st.cache_data(ttl=60)  # Cache por 1 minuto
def get_dolar_oficial():
    """Obtiene la cotización del dólar oficial desde la API."""
    try:
        response = requests.get('https://dolarapi.com/v1/dolares/oficial', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al obtener dólar oficial: {e}")
        return None

@st.cache_data(ttl=60)  # Cache por 1 minuto
def get_dolar_mep():
    """Obtiene la cotización del dólar MEP desde la API."""
    try:
        response = requests.get('https://dolarapi.com/v1/dolares/bolsa', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error al obtener dólar MEP: {e}")
        return None

@st.cache_data(ttl=60)
def get_crypto_price(exchange, amount=0.1):
    """Obtiene el precio de USDT/ARS desde un exchange específico."""
    try:
        url = f"https://criptoya.com/api/{exchange}/USDT/ARS/{amount}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException:
        return None

def calcular_arbitraje(dolar_compra, crypto_venta, volumen_usd, comision_pct, comision_usdt):
    """
    Calcula el resultado de la operación de arbitraje.
    
    Flujo:
    1. Comprar USD en oficial con ARS
    2. Convertir USD a USDT (1:1)
    3. Vender USDT por ARS en exchange crypto
    4. Descontar comisiones
    """
    # Costo inicial en ARS para comprar USD oficiales
    costo_inicial_ars = volumen_usd * dolar_compra
    
    # USDT disponibles después de comisión de envío
    usdt_netos = volumen_usd - comision_usdt
    
    # Si después de la comisión no hay USDT suficientes
    if usdt_netos <= 0:
        return {
            'costo_inicial_ars': costo_inicial_ars,
            'usdt_netos': 0,
            'ingresos_brutos_ars': 0,
            'comision_ars': 0,
            'ingresos_netos_ars': 0,
            'ganancia_ars': -costo_inicial_ars,
            'ganancia_usd': -volumen_usd,
            'roi_porcentaje': -100,
            'viable': False
        }
    
    # Ingresos brutos por vender USDT
    ingresos_brutos_ars = usdt_netos * crypto_venta
    
    # Comisión del exchange (3% sobre el monto vendido)
    comision_ars = ingresos_brutos_ars * comision_pct
    
    # Ingresos netos después de comisión
    ingresos_netos_ars = ingresos_brutos_ars - comision_ars
    
    # Ganancia/Pérdida
    ganancia_ars = ingresos_netos_ars - costo_inicial_ars
    ganancia_usd = ganancia_ars / dolar_compra
    roi_porcentaje = (ganancia_ars / costo_inicial_ars) * 100 if costo_inicial_ars > 0 else 0
    
    return {
        'costo_inicial_ars': costo_inicial_ars,
        'usdt_netos': usdt_netos,
        'ingresos_brutos_ars': ingresos_brutos_ars,
        'comision_ars': comision_ars,
        'ingresos_netos_ars': ingresos_netos_ars,
        'ganancia_ars': ganancia_ars,
        'ganancia_usd': ganancia_usd,
        'roi_porcentaje': roi_porcentaje,
        'viable': ganancia_ars > 0
    }

def calcular_volumen_minimo(dolar_compra, crypto_venta, comision_pct, comision_usdt):
    """
    Calcula el volumen mínimo en USD necesario para que la operación sea rentable.
    
    La operación es rentable cuando: ingresos_netos_ars > costo_inicial_ars
    
    Fórmula:
    (V - C) * P * (1 - R) > V * D
    Donde:
    V = volumen en USD
    C = comisión fija en USDT
    P = precio crypto (ARS/USDT)
    R = comisión porcentual
    D = dólar compra
    
    Despejando V:
    V > (C * P * (1 - R)) / (P * (1 - R) - D)
    """
    denominador = crypto_venta * (1 - comision_pct) - dolar_compra
    
    if denominador <= 0:
        return float('inf')  # No hay volumen que haga rentable la operación
    
    volumen_min = (comision_usdt * crypto_venta * (1 - comision_pct)) / denominador
    
    return max(volumen_min, 0)

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Configuración")
    
    st.subheader("💰 Parámetros de Operación")
    volumen_usd = st.number_input(
        "Volumen a operar (USD)",
        min_value=1.0,
        value=VOLUMEN_MINIMO_DEFAULT,
        step=10.0,
        help="Cantidad de dólares oficiales a comprar"
    )
    
    st.markdown("---")
    st.subheader("📊 Comisiones")
    
    col1, col2 = st.columns(2)
    with col1:
        comision_pct = st.number_input(
            "Comisión %",
            min_value=0.0,
            max_value=100.0,
            value=COMISION_PORCENTAJE * 100,
            step=0.1,
            help="Comisión porcentual del exchange"
        ) / 100
    
    with col2:
        comision_usdt = st.number_input(
            "Comisión envío (USDT)",
            min_value=0.0,
            value=float(COMISION_ENVIO_USDT),
            step=0.1,
            help="Comisión fija por transferencia de USDT"
        )
    
    st.markdown("---")
    st.subheader("🔄 Exchanges a Consultar")
    
    seleccionar_todos = st.checkbox("Seleccionar todos", value=True)
    
    if seleccionar_todos:
        exchanges_seleccionados = EXCHANGES
    else:
        exchanges_seleccionados = st.multiselect(
            "Selecciona exchanges",
            options=EXCHANGES,
            default=["binancep2p", "ripio", "lemoncash", "buenbit"]
        )
    
    st.markdown("---")
    if st.button("🔄 Actualizar Datos", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- CUERPO PRINCIPAL ---
st.title("💱 Arbitraje Dólar Oficial/MEP vs Crypto")
st.markdown(
    """
    Esta herramienta analiza la oportunidad de arbitraje entre:
    - **Comprar** dólares en el mercado oficial
    - **Comprar** dólares MEP (Mercado Electrónico de Pagos)
    - **Vender** USDT en exchanges crypto
    
    Considera comisiones de transferencia y porcentuales para determinar la rentabilidad real.
    """
)

st.warning(
    """
    ⚠️ **IMPORTANTE - Dólar Matrimonio:**
    
    Una misma persona **NO puede operar dólar oficial y MEP simultáneamente** por restricciones del BCRA.
    
    La estrategia recomendada es **"Dólar Matrimonio"**: una persona compra dólar oficial y otra compra MEP, 
    luego intercambian entre sí para acceder a ambos mercados.
    
    📺 Para más información sobre esta estrategia, busca el video explicativo en el canal de YouTube 
    **"El Minero Sudaka"** donde se explica paso a paso cómo implementar el dólar matrimonio.
    """,
    icon="💑"
)

# --- OBTENER DATOS ---
with st.spinner('Obteniendo cotizaciones...'):
    # Dólar oficial
    dolar_data = get_dolar_oficial()
    
    # Dólar MEP
    mep_data = get_dolar_mep()
    
    if dolar_data is None and mep_data is None:
        st.error("No se pudo obtener ninguna cotización. Por favor, intenta nuevamente.")
        st.stop()
    
    # Extraer datos del dólar oficial
    if dolar_data:
        dolar_compra = dolar_data['compra']
        dolar_venta = dolar_data['venta']
        fecha_actualizacion_oficial = datetime.fromisoformat(dolar_data['fechaActualizacion'].replace('Z', '+00:00'))
    else:
        dolar_compra = None
        dolar_venta = None
        fecha_actualizacion_oficial = None
    
    # Extraer datos del MEP
    if mep_data:
        mep_compra = mep_data['compra']
        mep_venta = mep_data['venta']
        fecha_actualizacion_mep = datetime.fromisoformat(mep_data['fechaActualizacion'].replace('Z', '+00:00'))
    else:
        mep_compra = None
        mep_venta = None
        fecha_actualizacion_mep = None
    
    # Mostrar cotizaciones
    st.header("📌 Cotizaciones de Dólar")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💵 Dólar Oficial")
        if dolar_compra:
            subcol1, subcol2, subcol3 = st.columns(3)
            with subcol1:
                st.metric("Compra", f"${dolar_compra:,.2f}")
            with subcol2:
                st.metric("Venta", f"${dolar_venta:,.2f}")
            with subcol3:
                st.metric("🕐 Act.", fecha_actualizacion_oficial.strftime("%H:%M"))
        else:
            st.error("No disponible")
    
    with col2:
        st.subheader("📈 Dólar MEP")
        if mep_compra:
            subcol1, subcol2, subcol3 = st.columns(3)
            with subcol1:
                st.metric("Compra", f"${mep_compra:,.2f}")
            with subcol2:
                st.metric("Venta", f"${mep_venta:,.2f}")
            with subcol3:
                st.metric("🕐 Act.", fecha_actualizacion_mep.strftime("%H:%M"))
        else:
            st.error("No disponible")
    
    # Comparación entre oficial y MEP
    if dolar_compra and mep_compra:
        diferencia = mep_compra - dolar_compra
        diferencia_pct = (diferencia / dolar_compra) * 100
        st.info(f"📊 **Diferencia MEP vs Oficial:** ${diferencia:,.2f} ARS ({diferencia_pct:+.2f}%)")
    
    st.markdown("---")
    
    # Obtener precios crypto
    st.header("💎 Cotizaciones Crypto")
    
    if not exchanges_seleccionados:
        st.warning("Por favor, selecciona al menos un exchange en la barra lateral.")
        st.stop()
    
    resultados_oficial = []
    resultados_mep = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, exchange in enumerate(exchanges_seleccionados):
        status_text.text(f"Consultando {exchange}...")
        crypto_data = get_crypto_price(exchange)
        
        if crypto_data and 'totalBid' in crypto_data:
            crypto_venta = crypto_data['totalBid']  # Precio al que vendemos USDT
            
            # Calcular arbitraje con OFICIAL
            if dolar_compra:
                resultado_oficial = calcular_arbitraje(
                    dolar_compra, 
                    crypto_venta, 
                    volumen_usd,
                    comision_pct,
                    comision_usdt
                )
                
                vol_min_oficial = calcular_volumen_minimo(
                    dolar_compra,
                    crypto_venta,
                    comision_pct,
                    comision_usdt
                )
                
                resultados_oficial.append({
                    'Exchange': exchange.upper(),
                    'Precio USDT': crypto_venta,
                    'Spread vs Oficial (%)': ((crypto_venta - dolar_compra) / dolar_compra) * 100,
                    'Ganancia ARS': resultado_oficial['ganancia_ars'],
                    'Ganancia USD': resultado_oficial['ganancia_usd'],
                    'ROI (%)': resultado_oficial['roi_porcentaje'],
                    'Viable': resultado_oficial['viable'],
                    'Vol. Mínimo (USD)': vol_min_oficial,
                    'Detalles': resultado_oficial
                })
            
            # Calcular arbitraje con MEP
            if mep_compra:
                resultado_mep = calcular_arbitraje(
                    mep_compra, 
                    crypto_venta, 
                    volumen_usd,
                    comision_pct,
                    comision_usdt
                )
                
                vol_min_mep = calcular_volumen_minimo(
                    mep_compra,
                    crypto_venta,
                    comision_pct,
                    comision_usdt
                )
                
                resultados_mep.append({
                    'Exchange': exchange.upper(),
                    'Precio USDT': crypto_venta,
                    'Spread vs MEP (%)': ((crypto_venta - mep_compra) / mep_compra) * 100,
                    'Ganancia ARS': resultado_mep['ganancia_ars'],
                    'Ganancia USD': resultado_mep['ganancia_usd'],
                    'ROI (%)': resultado_mep['roi_porcentaje'],
                    'Viable': resultado_mep['viable'],
                    'Vol. Mínimo (USD)': vol_min_mep,
                    'Detalles': resultado_mep
                })
        
        progress_bar.progress((idx + 1) / len(exchanges_seleccionados))
    
    progress_bar.empty()
    status_text.empty()
    
    if not resultados_oficial and not resultados_mep:
        st.error("No se pudieron obtener cotizaciones de ningún exchange. Por favor, verifica tu conexión.")
        st.stop()
    
    # Crear DataFrames
    df_oficial = pd.DataFrame(resultados_oficial).sort_values('Ganancia ARS', ascending=False) if resultados_oficial else None
    df_mep = pd.DataFrame(resultados_mep).sort_values('Ganancia ARS', ascending=False) if resultados_mep else None
    
    # --- TABS PARA OFICIAL Y MEP ---
    if df_oficial is not None and df_mep is not None:
        tab1, tab2, tab3 = st.tabs(["🏆 Comparación", "💵 Dólar Oficial", "📈 Dólar MEP"])
    elif df_oficial is not None:
        tab1, tab2 = st.tabs(["💵 Dólar Oficial", "📊 Detalles"])
        tab3 = None
    elif df_mep is not None:
        tab1, tab2 = st.tabs(["📈 Dólar MEP", "📊 Detalles"])
        tab3 = None
    else:
        st.error("No hay datos disponibles")
        st.stop()
    
    # --- TAB COMPARACIÓN ---
    if df_oficial is not None and df_mep is not None:
        with tab1:
            st.header("🆚 ¿Qué conviene más: Oficial o MEP?")
            
            # Mejor oportunidad de cada uno
            mejor_oficial = df_oficial.iloc[0] if not df_oficial.empty else None
            mejor_mep = df_mep.iloc[0] if not df_mep.empty else None
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("💵 Mejor con Oficial")
                if mejor_oficial is not None and mejor_oficial['Viable']:
                    st.success(f"**{mejor_oficial['Exchange']}**")
                    st.metric("Ganancia", f"${mejor_oficial['Ganancia USD']:.2f} USD", f"{mejor_oficial['ROI (%)']:.2f}% ROI")
                    st.metric("En ARS", f"${mejor_oficial['Ganancia ARS']:,.2f}")
                else:
                    st.error("No hay oportunidades viables")
            
            with col2:
                st.subheader("📈 Mejor con MEP")
                if mejor_mep is not None and mejor_mep['Viable']:
                    st.success(f"**{mejor_mep['Exchange']}**")
                    st.metric("Ganancia", f"${mejor_mep['Ganancia USD']:.2f} USD", f"{mejor_mep['ROI (%)']:.2f}% ROI")
                    st.metric("En ARS", f"${mejor_mep['Ganancia ARS']:,.2f}")
                else:
                    st.error("No hay oportunidades viables")
            
            # Comparación directa
            st.markdown("---")
            st.subheader("📊 Comparación Top 5")
            
            # Tabla comparativa
            top_oficial = df_oficial[df_oficial['Viable']].head(5)
            top_mep = df_mep[df_mep['Viable']].head(5)
            
            if not top_oficial.empty or not top_mep.empty:
                # Gráfico comparativo
                fig_comp = go.Figure()
                
                if not top_oficial.empty:
                    fig_comp.add_trace(go.Bar(
                        name='Dólar Oficial',
                        x=top_oficial['Exchange'],
                        y=top_oficial['Ganancia USD'],
                        marker_color='lightblue',
                        text=[f"${val:.2f}" for val in top_oficial['Ganancia USD']],
                        textposition='outside'
                    ))
                
                if not top_mep.empty:
                    fig_comp.add_trace(go.Bar(
                        name='Dólar MEP',
                        x=top_mep['Exchange'],
                        y=top_mep['Ganancia USD'],
                        marker_color='lightgreen',
                        text=[f"${val:.2f}" for val in top_mep['Ganancia USD']],
                        textposition='outside'
                    ))
                
                fig_comp.update_layout(
                    template='plotly_dark',
                    title='Top 5 Exchanges: Oficial vs MEP',
                    xaxis_title='Exchange',
                    yaxis_title='Ganancia (USD)',
                    barmode='group',
                    height=500
                )
                
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Recomendación
                if mejor_oficial and mejor_mep:
                    if mejor_oficial['Ganancia USD'] > mejor_mep['Ganancia USD']:
                        diferencia = mejor_oficial['Ganancia USD'] - mejor_mep['Ganancia USD']
                        st.success(
                            f"✅ **Recomendación:** El dólar **OFICIAL** es más rentable por **${diferencia:.2f} USD** más de ganancia "
                            f"en el mejor exchange ({mejor_oficial['Exchange']})"
                        )
                    else:
                        diferencia = mejor_mep['Ganancia USD'] - mejor_oficial['Ganancia USD']
                        st.success(
                            f"✅ **Recomendación:** El dólar **MEP** es más rentable por **${diferencia:.2f} USD** más de ganancia "
                            f"en el mejor exchange ({mejor_mep['Exchange']})"
                        )
            else:
                st.warning("No hay oportunidades viables con el volumen actual para comparar.")
    
    # --- TAB OFICIAL ---
    if df_oficial is not None:
        with (tab2 if df_mep is not None else tab1):
            st.header("💵 Resultados con Dólar Oficial")
            
            mejores_oficial = df_oficial[df_oficial['Viable']].head(5)
            
            if mejores_oficial.empty:
                st.warning(
                    f"⚠️ **No hay oportunidades rentables con dólar oficial** (${volumen_usd:,.2f} USD)\n\n"
                    "Revisa los volúmenes mínimos en la tabla inferior."
                )
            else:
                st.subheader("🏆 Top 5 Oportunidades")
                for idx, row in mejores_oficial.iterrows():
                    with st.expander(
                        f"**{row['Exchange']}** - Ganancia: ${row['Ganancia ARS']:,.2f} ARS ({row['ROI (%)']:.2f}% ROI)", 
                        expanded=idx==mejores_oficial.index[0]
                    ):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Precio USDT", f"${row['Precio USDT']:,.2f}")
                        with col2:
                            st.metric("Ganancia ARS", f"${row['Ganancia ARS']:,.2f}")
                        with col3:
                            st.metric("Ganancia USD", f"${row['Ganancia USD']:.2f}")
                        with col4:
                            st.metric("ROI", f"{row['ROI (%)']:.2f}%")
                        
                        detalles = row['Detalles']
                        st.markdown(f"""
                        **Detalle de la Operación:**
                        1. 💵 **Comprar USD oficiales**: ${volumen_usd:,.2f} USD × ${dolar_compra:,.2f} = **${detalles['costo_inicial_ars']:,.2f} ARS**
                        2. 🔄 **Transferir a USDT**: ${volumen_usd:,.2f} USDT - ${comision_usdt} USDT (comisión) = **{detalles['usdt_netos']:.2f} USDT**
                        3. 💎 **Vender USDT**: {detalles['usdt_netos']:.2f} USDT × ${row['Precio USDT']:,.2f} = **${detalles['ingresos_brutos_ars']:,.2f} ARS**
                        4. 💸 **Comisión exchange** ({comision_pct*100:.1f}%): **${detalles['comision_ars']:,.2f} ARS**
                        5. ✅ **Ingresos netos**: **${detalles['ingresos_netos_ars']:,.2f} ARS**
                        6. 📊 **Resultado final**: **${detalles['ganancia_ars']:,.2f} ARS** (${detalles['ganancia_usd']:.2f} USD)
                        """)
            
            st.markdown("---")
            
            # Gráfico
            st.subheader("📊 Gráfico de Rentabilidad")
            df_plot_oficial = df_oficial.sort_values('Ganancia USD')
            colors_oficial = ['green' if viable else 'red' for viable in df_plot_oficial['Viable']]
            
            fig_oficial = go.Figure()
            fig_oficial.add_trace(go.Bar(
                x=df_plot_oficial['Ganancia USD'],
                y=df_plot_oficial['Exchange'],
                orientation='h',
                marker=dict(color=colors_oficial),
                text=[f"${val:.2f}" for val in df_plot_oficial['Ganancia USD']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Ganancia: $%{x:.2f} USD<br>ROI: %{customdata:.2f}%<extra></extra>',
                customdata=df_plot_oficial['ROI (%)']
            ))
            fig_oficial.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
            fig_oficial.update_layout(
                template='plotly_dark',
                title=f'Ganancia con Dólar Oficial (Volumen: ${volumen_usd:,.2f} USD)',
                xaxis_title='Ganancia (USD)',
                yaxis_title='Exchange',
                height=max(400, len(df_plot_oficial) * 30),
                showlegend=False
            )
            st.plotly_chart(fig_oficial, use_container_width=True)
            
            # Tabla
            st.subheader("📋 Tabla Completa")
            df_display_oficial = df_oficial[['Exchange', 'Precio USDT', 'Spread vs Oficial (%)', 
                                             'Ganancia ARS', 'Ganancia USD', 'ROI (%)', 
                                             'Vol. Mínimo (USD)', 'Viable']].copy()
            
            def highlight_viable(row):
                if row['Viable']:
                    return ['background-color: rgba(0, 255, 0, 0.1)'] * len(row)
                else:
                    return ['background-color: rgba(255, 0, 0, 0.1)'] * len(row)
            
            st.dataframe(
                df_display_oficial.style
                    .apply(highlight_viable, axis=1)
                    .format({
                        'Precio USDT': '${:,.2f}',
                        'Spread vs Oficial (%)': '{:.2f}%',
                        'Ganancia ARS': '${:,.2f}',
                        'Ganancia USD': '${:.2f}',
                        'ROI (%)': '{:.2f}%',
                        'Vol. Mínimo (USD)': '${:,.2f}'
                    }),
                use_container_width=True,
                height=400
            )
    
    # --- TAB MEP ---
    if df_mep is not None:
        with (tab3 if df_oficial is not None else tab1):
            st.header("📈 Resultados con Dólar MEP")
            
            mejores_mep = df_mep[df_mep['Viable']].head(5)
            
            if mejores_mep.empty:
                st.warning(
                    f"⚠️ **No hay oportunidades rentables con dólar MEP** (${volumen_usd:,.2f} USD)\n\n"
                    "Revisa los volúmenes mínimos en la tabla inferior."
                )
            else:
                st.subheader("🏆 Top 5 Oportunidades")
                for idx, row in mejores_mep.iterrows():
                    with st.expander(
                        f"**{row['Exchange']}** - Ganancia: ${row['Ganancia ARS']:,.2f} ARS ({row['ROI (%)']:.2f}% ROI)", 
                        expanded=idx==mejores_mep.index[0]
                    ):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Precio USDT", f"${row['Precio USDT']:,.2f}")
                        with col2:
                            st.metric("Ganancia ARS", f"${row['Ganancia ARS']:,.2f}")
                        with col3:
                            st.metric("Ganancia USD", f"${row['Ganancia USD']:.2f}")
                        with col4:
                            st.metric("ROI", f"{row['ROI (%)']:.2f}%")
                        
                        detalles = row['Detalles']
                        st.markdown(f"""
                        **Detalle de la Operación:**
                        1. 📈 **Comprar USD MEP**: ${volumen_usd:,.2f} USD × ${mep_compra:,.2f} = **${detalles['costo_inicial_ars']:,.2f} ARS**
                        2. 🔄 **Transferir a USDT**: ${volumen_usd:,.2f} USDT - ${comision_usdt} USDT (comisión) = **{detalles['usdt_netos']:.2f} USDT**
                        3. 💎 **Vender USDT**: {detalles['usdt_netos']:.2f} USDT × ${row['Precio USDT']:,.2f} = **${detalles['ingresos_brutos_ars']:,.2f} ARS**
                        4. 💸 **Comisión exchange** ({comision_pct*100:.1f}%): **${detalles['comision_ars']:,.2f} ARS**
                        5. ✅ **Ingresos netos**: **${detalles['ingresos_netos_ars']:,.2f} ARS**
                        6. 📊 **Resultado final**: **${detalles['ganancia_ars']:,.2f} ARS** (${detalles['ganancia_usd']:.2f} USD)
                        """)
            
            st.markdown("---")
            
            # Gráfico
            st.subheader("📊 Gráfico de Rentabilidad")
            df_plot_mep = df_mep.sort_values('Ganancia USD')
            colors_mep = ['green' if viable else 'red' for viable in df_plot_mep['Viable']]
            
            fig_mep = go.Figure()
            fig_mep.add_trace(go.Bar(
                x=df_plot_mep['Ganancia USD'],
                y=df_plot_mep['Exchange'],
                orientation='h',
                marker=dict(color=colors_mep),
                text=[f"${val:.2f}" for val in df_plot_mep['Ganancia USD']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Ganancia: $%{x:.2f} USD<br>ROI: %{customdata:.2f}%<extra></extra>',
                customdata=df_plot_mep['ROI (%)']
            ))
            fig_mep.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
            fig_mep.update_layout(
                template='plotly_dark',
                title=f'Ganancia con Dólar MEP (Volumen: ${volumen_usd:,.2f} USD)',
                xaxis_title='Ganancia (USD)',
                yaxis_title='Exchange',
                height=max(400, len(df_plot_mep) * 30),
                showlegend=False
            )
            st.plotly_chart(fig_mep, use_container_width=True)
            
            # Tabla
            st.subheader("📋 Tabla Completa")
            df_display_mep = df_mep[['Exchange', 'Precio USDT', 'Spread vs MEP (%)', 
                                     'Ganancia ARS', 'Ganancia USD', 'ROI (%)', 
                                     'Vol. Mínimo (USD)', 'Viable']].copy()
            
            st.dataframe(
                df_display_mep.style
                    .apply(highlight_viable, axis=1)
                    .format({
                        'Precio USDT': '${:,.2f}',
                        'Spread vs MEP (%)': '{:.2f}%',
                        'Ganancia ARS': '${:,.2f}',
                        'Ganancia USD': '${:.2f}',
                        'ROI (%)': '{:.2f}%',
                        'Vol. Mínimo (USD)': '${:,.2f}'
                    }),
                use_container_width=True,
                height=400
            )
    
    # --- INFORMACIÓN ADICIONAL ---
    st.markdown("---")
    st.header("💡 Información Importante")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(
            """
            **Cómo funciona:**
            1. Se compran dólares (Oficial o MEP)
            2. Se convierten a USDT (1:1)
            3. Se paga comisión de transferencia (${:.2f} USDT)
            4. Se venden USDT en el exchange crypto
            5. Se paga comisión del exchange ({:.1f}%)
            6. La diferencia es la ganancia/pérdida
            """.format(comision_usdt, comision_pct * 100)
        )
    
    with col2:
        st.warning(
            """
            **⚠️ Consideraciones:**
            - Los precios fluctúan constantemente
            - Límites de compra diaria de dólares oficiales
            - Verifica requisitos KYC de cada exchange
            - Esta es una simulación, no asesoramiento financiero
            - Revisa el volumen mínimo para rentabilidad
            - **No puedes operar oficial y MEP simultáneamente**
            """
        )
    
    # Estadísticas generales
    st.markdown("---")
    st.header("📈 Estadísticas Generales")
    
    if df_oficial is not None and df_mep is not None:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Exchanges Consultados", len(resultados_oficial))
        
        with col2:
            viables_oficial = len(df_oficial[df_oficial['Viable']])
            viables_mep = len(df_mep[df_mep['Viable']])
            st.metric("Viables Oficial", viables_oficial)
            st.metric("Viables MEP", viables_mep)
        
        with col3:
            mejor_roi_oficial = df_oficial['ROI (%)'].max()
            mejor_roi_mep = df_mep['ROI (%)'].max()
            st.metric("Mejor ROI Oficial", f"{mejor_roi_oficial:.2f}%")
            st.metric("Mejor ROI MEP", f"{mejor_roi_mep:.2f}%")
        
        with col4:
            vol_min_oficial = df_oficial[df_oficial['Vol. Mínimo (USD)'] < float('inf')]['Vol. Mínimo (USD)'].mean()
            vol_min_mep = df_mep[df_mep['Vol. Mínimo (USD)'] < float('inf')]['Vol. Mínimo (USD)'].mean()
            
            if pd.notna(vol_min_oficial):
                st.metric("Vol. Mín. Oficial", f"${vol_min_oficial:.2f}")
            if pd.notna(vol_min_mep):
                st.metric("Vol. Mín. MEP", f"${vol_min_mep:.2f}")
    
    elif df_oficial is not None:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Exchanges Consultados", len(resultados_oficial))
        with col2:
            viables = len(df_oficial[df_oficial['Viable']])
            st.metric("Oportunidades Viables", viables)
        with col3:
            mejor_roi = df_oficial['ROI (%)'].max()
            st.metric("Mejor ROI", f"{mejor_roi:.2f}%")
        with col4:
            vol_min_promedio = df_oficial[df_oficial['Vol. Mínimo (USD)'] < float('inf')]['Vol. Mínimo (USD)'].mean()
            if pd.notna(vol_min_promedio):
                st.metric("Vol. Mín. Promedio", f"${vol_min_promedio:.2f}")
            else:
                st.metric("Vol. Mín. Promedio", "N/A")
    
    elif df_mep is not None:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Exchanges Consultados", len(resultados_mep))
        with col2:
            viables = len(df_mep[df_mep['Viable']])
            st.metric("Oportunidades Viables", viables)
        with col3:
            mejor_roi = df_mep['ROI (%)'].max()
            st.metric("Mejor ROI", f"{mejor_roi:.2f}%")
        with col4:
            vol_min_promedio = df_mep[df_mep['Vol. Mínimo (USD)'] < float('inf')]['Vol. Mínimo (USD)'].mean()
            if pd.notna(vol_min_promedio):
                st.metric("Vol. Mín. Promedio", f"${vol_min_promedio:.2f}")
            else:
                st.metric("Vol. Mín. Promedio", "N/A")

st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
