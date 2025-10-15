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
COMISION_PORCENTAJE = 0.01  # 1%
COMISION_ENVIO_USDT = 1  # 1 USDT
VOLUMEN_MINIMO_DEFAULT = 1000  # USD por defecto

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

def calcular_arbitraje_mep(dolar_oficial_compra, mep_venta, volumen_usd):
    """
    Calcula el resultado de vender dólar oficial en el mercado MEP.
    
    Flujo:
    1. Comprar USD en oficial con ARS
    2. Vender USD en MEP por ARS
    3. La diferencia es la ganancia/pérdida (sin comisiones de crypto)
    """
    # Costo inicial en ARS para comprar USD oficiales
    costo_inicial_ars = volumen_usd * dolar_oficial_compra
    
    # Ingresos por vender en MEP
    ingresos_ars = volumen_usd * mep_venta
    
    # Ganancia/Pérdida
    ganancia_ars = ingresos_ars - costo_inicial_ars
    ganancia_usd = ganancia_ars / dolar_oficial_compra if dolar_oficial_compra > 0 else 0
    roi_porcentaje = (ganancia_ars / costo_inicial_ars) * 100 if costo_inicial_ars > 0 else 0
    
    return {
        'costo_inicial_ars': costo_inicial_ars,
        'ingresos_ars': ingresos_ars,
        'ganancia_ars': ganancia_ars,
        'ganancia_usd': ganancia_usd,
        'roi_porcentaje': roi_porcentaje,
        'viable': ganancia_ars > 0
    }

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Configuración")
    
    st.subheader("💰 Parámetros de Operación")
    volumen_usd = st.number_input(
        "Volumen a operar (USD)",
        min_value=1.0,
        value=float(VOLUMEN_MINIMO_DEFAULT),
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
st.title("💱 Arbitraje: Dólar Oficial → Crypto vs MEP")
st.markdown(
    """
    Esta herramienta compara dos estrategias de arbitraje con dólar oficial:
    
    **Estrategia 1: Oficial → Crypto (USDT)**
    - Comprar USD oficiales
    - Convertir a USDT y vender en exchanges crypto
    - ⚠️ Incluye comisiones de transferencia y exchange
    
    **Estrategia 2: Oficial → MEP**
    - Comprar USD oficiales
    - Vender en el mercado MEP
    - ✅ Sin comisiones de crypto (solo spread MEP)
    """
)

st.warning(
    """
    ⚠️ **IMPORTANTE - Dólar Matrimonio:**
    
    Una misma persona **NO puede operar dólar oficial y MEP simultáneamente** por restricciones del BCRA.
    
    La estrategia recomendada es **"Dólar Matrimonio"**: una persona compra dólar oficial y otra compra MEP, 
    luego intercambian entre sí para acceder a ambos mercados y maximizar oportunidades.
    
    📺 Para más información sobre esta estrategia:
    - [El Minero Sudaka](https://www.youtube.com/c/ElMineroSudaka) - Explicación detallada del dólar matrimonio
    - [Rulo](https://www.youtube.com/@rulo_ok) - Mi canal con más estrategias de arbitraje
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
    
    # Extraer datos del dólar oficial (Usuario compra al precio de VENTA del broker)
    if dolar_data:
        dolar_compra_usuario = dolar_data['venta']  # El usuario compra al precio de venta del broker
        dolar_venta_broker = dolar_data['compra']
        fecha_actualizacion_oficial = datetime.fromisoformat(dolar_data['fechaActualizacion'].replace('Z', '+00:00'))
    else:
        dolar_compra_usuario = None
        dolar_venta_broker = None
        fecha_actualizacion_oficial = None
    
    # Extraer datos del MEP (Usuario vende al precio de COMPRA del broker)
    if mep_data:
        mep_compra_broker = mep_data['compra']  # Precio al que el broker compra (el usuario vende)
        mep_venta_usuario = mep_data['venta']
        fecha_actualizacion_mep = datetime.fromisoformat(mep_data['fechaActualizacion'].replace('Z', '+00:00'))
    else:
        mep_compra_broker = None
        mep_venta_usuario = None
        fecha_actualizacion_mep = None
    
    # Mostrar cotizaciones
    st.header("📌 Cotizaciones de Dólar")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💵 Dólar Oficial")
        if dolar_compra_usuario:
            subcol1, subcol2 = st.columns(2)
            with subcol1:
                st.metric("Compras a", f"${dolar_compra_usuario:,.2f}")
                st.caption("(Precio venta del broker)")
            with subcol2:
                st.metric("Vendes a", f"${dolar_venta_broker:,.2f}")
                st.caption("(Precio compra del broker)")
            st.caption(f"🕐 Actualizado: {fecha_actualizacion_oficial.strftime('%H:%M:%S')}")
        else:
            st.error("No disponible")
    
    with col2:
        st.subheader("📈 Dólar MEP")
        if mep_venta_usuario:
            subcol1, subcol2 = st.columns(2)
            with subcol1:
                st.metric("Compras a", f"${mep_venta_usuario:,.2f}")
                st.caption("(Precio venta del broker)")
            with subcol2:
                st.metric("Vendes a", f"${mep_compra_broker:,.2f}")
                st.caption("(Precio compra del broker)")
            st.caption(f"🕐 Actualizado: {fecha_actualizacion_mep.strftime('%H:%M:%S')}")
        else:
            st.error("No disponible")
    
    # Comparación y cálculo de arbitraje MEP
    if dolar_compra_usuario and mep_compra_broker:
        st.markdown("---")
        st.subheader("📊 Estrategia 2: Oficial → MEP (Sin comisiones crypto)")
        
        resultado_mep = calcular_arbitraje_mep(dolar_compra_usuario, mep_compra_broker, volumen_usd)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            spread_mep = mep_compra_broker - dolar_compra_usuario
            spread_pct = (spread_mep / dolar_compra_usuario) * 100
            st.metric("Spread MEP", f"${spread_mep:,.2f}", f"{spread_pct:+.2f}%")
        with col2:
            st.metric("Ganancia ARS", f"${resultado_mep['ganancia_ars']:,.2f}")
        with col3:
            st.metric("Ganancia USD", f"${resultado_mep['ganancia_usd']:.2f}")
        with col4:
            st.metric("ROI", f"{resultado_mep['roi_porcentaje']:.2f}%")
        
        if resultado_mep['viable']:
            st.success("✅ Operación rentable: Comprar oficial y vender en MEP genera ganancia")
        else:
            st.error("❌ Operación NO rentable: El MEP está por debajo del oficial")
        
        with st.expander("Ver detalle de operación Oficial → MEP"):
            st.markdown(f"""
            1. 💵 **Comprar USD oficiales**: ${volumen_usd:,.2f} USD × ${dolar_compra_usuario:,.2f} = **${resultado_mep['costo_inicial_ars']:,.2f} ARS**
            2. 📈 **Vender en MEP**: ${volumen_usd:,.2f} USD × ${mep_compra_broker:,.2f} = **${resultado_mep['ingresos_ars']:,.2f} ARS**
            3. 📊 **Resultado final**: **${resultado_mep['ganancia_ars']:,.2f} ARS** (${resultado_mep['ganancia_usd']:.2f} USD)
            
            ✨ **Sin comisiones de transferencia ni exchange**
            """)
    
    st.markdown("---")
    
    # Obtener precios crypto
    st.header("💎 Estrategia 1: Oficial → Crypto (Con comisiones)")
    st.caption("Comparación con exchanges crypto considerando comisiones de transferencia y exchange")
    
    if not exchanges_seleccionados:
        st.warning("Por favor, selecciona al menos un exchange en la barra lateral.")
        st.stop()
    
    resultados_crypto = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, exchange in enumerate(exchanges_seleccionados):
        status_text.text(f"Consultando {exchange}...")
        crypto_data = get_crypto_price(exchange)
        
        if crypto_data and 'totalBid' in crypto_data:
            crypto_venta = crypto_data['totalBid']  # Precio al que vendemos USDT
            
            # Calcular arbitraje con OFICIAL → CRYPTO
            if dolar_compra_usuario:
                resultado_crypto = calcular_arbitraje(
                    dolar_compra_usuario, 
                    crypto_venta, 
                    volumen_usd,
                    comision_pct,
                    comision_usdt
                )
                
                vol_min_crypto = calcular_volumen_minimo(
                    dolar_compra_usuario,
                    crypto_venta,
                    comision_pct,
                    comision_usdt
                )
                
                resultados_crypto.append({
                    'Exchange': exchange.upper(),
                    'Precio USDT': crypto_venta,
                    'Spread vs Oficial (%)': ((crypto_venta - dolar_compra_usuario) / dolar_compra_usuario) * 100,
                    'Ganancia ARS': resultado_crypto['ganancia_ars'],
                    'Ganancia USD': resultado_crypto['ganancia_usd'],
                    'ROI (%)': resultado_crypto['roi_porcentaje'],
                    'Viable': resultado_crypto['viable'],
                    'Vol. Mínimo (USD)': vol_min_crypto,
                    'Detalles': resultado_crypto
                })
        
        progress_bar.progress((idx + 1) / len(exchanges_seleccionados))
    
    progress_bar.empty()
    status_text.empty()
    
    if not resultados_crypto:
        st.error("No se pudieron obtener cotizaciones de ningún exchange. Por favor, verifica tu conexión.")
        st.stop()
    
    # Crear DataFrame
    df_crypto = pd.DataFrame(resultados_crypto).sort_values('Ganancia ARS', ascending=False) if resultados_crypto else None
    
    if df_crypto is None:
        st.error("No hay datos disponibles")
        st.stop()
    
    # --- COMPARACIÓN PRINCIPAL ---
    st.header("🏆 ¿Qué conviene más?")
    
    mejor_crypto = None
    if not df_crypto[df_crypto['Viable']].empty:
        mejor_crypto = df_crypto[df_crypto['Viable']].iloc[0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Estrategia MEP")
        st.info("Comprar Oficial → Vender MEP")
        if resultado_mep and resultado_mep['viable']:
            st.success(f"✅ RENTABLE")
            st.metric("Ganancia", f"${resultado_mep['ganancia_usd']:.2f} USD", f"{resultado_mep['roi_porcentaje']:.2f}% ROI")
            st.metric("En ARS", f"${resultado_mep['ganancia_ars']:,.2f}")
            st.caption("Sin comisiones de crypto")
        else:
            st.error("❌ NO RENTABLE")
            if resultado_mep:
                st.metric("Pérdida", f"${resultado_mep['ganancia_usd']:.2f} USD")
    
    with col2:
        st.subheader("💎 Mejor Estrategia Crypto")
        st.info("Comprar Oficial → Vender USDT")
        if mejor_crypto is not None:
            st.success(f"✅ {mejor_crypto['Exchange']}")
            st.metric("Ganancia", f"${mejor_crypto['Ganancia USD']:.2f} USD", f"{mejor_crypto['ROI (%)']:.2f}% ROI")
            st.metric("En ARS", f"${mejor_crypto['Ganancia ARS']:,.2f}")
            st.caption(f"Vol. mínimo: ${mejor_crypto['Vol. Mínimo (USD)']:,.2f} USD")
        else:
            st.error("❌ NO HAY OPCIONES RENTABLES")
            st.caption("Aumenta el volumen de operación")
    
    # Recomendación final
    st.markdown("---")
    
    if resultado_mep and resultado_mep['viable'] and mejor_crypto is not None:
        if resultado_mep['ganancia_usd'] > mejor_crypto['Ganancia USD']:
            diferencia = resultado_mep['ganancia_usd'] - mejor_crypto['Ganancia USD']
            st.success(
                f"""
                ### 🎯 RECOMENDACIÓN: Estrategia MEP
                
                La estrategia **Oficial → MEP** es **${diferencia:.2f} USD más rentable** que el mejor exchange crypto ({mejor_crypto['Exchange']}).
                
                - ✅ Sin comisiones de transferencia
                - ✅ Sin comisiones de exchange
                - ✅ Operación más simple y rápida
                """
            )
        else:
            diferencia = mejor_crypto['Ganancia USD'] - resultado_mep['ganancia_usd']
            st.success(
                f"""
                ### 🎯 RECOMENDACIÓN: Estrategia Crypto
                
                La estrategia **Oficial → {mejor_crypto['Exchange']}** es **${diferencia:.2f} USD más rentable** que vender en MEP.
                
                - Exchange: {mejor_crypto['Exchange']}
                - Precio USDT: ${mejor_crypto['Precio USDT']:,.2f}
                - Volumen mínimo: ${mejor_crypto['Vol. Mínimo (USD)']:,.2f} USD
                """
            )
    elif resultado_mep and resultado_mep['viable']:
        st.success(
            """
            ### 🎯 RECOMENDACIÓN: Estrategia MEP
            
            La estrategia **Oficial → MEP** es rentable mientras que ningún exchange crypto lo es con el volumen actual.
            """
        )
    elif mejor_crypto is not None:
        st.success(
            f"""
            ### 🎯 RECOMENDACIÓN: Estrategia Crypto
            
            La estrategia **Oficial → {mejor_crypto['Exchange']}** es rentable mientras que MEP no lo es actualmente.
            """
        )
    else:
        st.error(
            """
            ### ⚠️ NINGUNA ESTRATEGIA ES RENTABLE
            
            Ni la venta en MEP ni en exchanges crypto son rentables con el volumen actual.
            
            **Sugerencias:**
            - Aumenta el volumen de operación
            - Espera mejores condiciones de mercado
            - Revisa los volúmenes mínimos en la tabla inferior
            """
        )
    
    st.markdown("---")
    
    # --- DETALLES DE CRYPTO EXCHANGES ---
    st.header("💎 Detalle de Exchanges Crypto")
    
    mejores_crypto = df_crypto[df_crypto['Viable']].head(5)
    
    if not mejores_crypto.empty:
        st.subheader("🏆 Top 5 Exchanges Rentables")
        for idx, row in mejores_crypto.iterrows():
            with st.expander(
                f"**{row['Exchange']}** - Ganancia: ${row['Ganancia ARS']:,.2f} ARS ({row['ROI (%)']:.2f}% ROI)", 
                expanded=idx==mejores_crypto.index[0]
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
                1. 💵 **Comprar USD oficiales**: ${volumen_usd:,.2f} USD × ${dolar_compra_usuario:,.2f} = **${detalles['costo_inicial_ars']:,.2f} ARS**
                2. 🔄 **Transferir a USDT**: ${volumen_usd:,.2f} USDT - ${comision_usdt} USDT (comisión) = **{detalles['usdt_netos']:.2f} USDT**
                3. 💎 **Vender USDT**: {detalles['usdt_netos']:.2f} USDT × ${row['Precio USDT']:,.2f} = **${detalles['ingresos_brutos_ars']:,.2f} ARS**
                4. 💸 **Comisión exchange** ({comision_pct*100:.1f}%): **${detalles['comision_ars']:,.2f} ARS**
                5. ✅ **Ingresos netos**: **${detalles['ingresos_netos_ars']:,.2f} ARS**
                6. 📊 **Resultado final**: **${detalles['ganancia_ars']:,.2f} ARS** (${detalles['ganancia_usd']:.2f} USD)
                """)
    else:
        st.warning(
            f"⚠️ **No hay exchanges crypto rentables con el volumen actual (${volumen_usd:,.2f} USD)**\n\n"
            "Revisa los volúmenes mínimos en la tabla inferior o considera la estrategia MEP."
        )
    
    st.markdown("---")
    
    # Gráfico comparativo
    st.subheader("📊 Gráfico de Rentabilidad por Exchange")
    
    df_plot_crypto = df_crypto.sort_values('Ganancia USD')
    colors_crypto = ['green' if viable else 'red' for viable in df_plot_crypto['Viable']]
    
    fig_crypto = go.Figure()
    
    # Barra para MEP
    if resultado_mep:
        fig_crypto.add_trace(go.Scatter(
            x=[resultado_mep['ganancia_usd']],
            y=['MEP'],
            mode='markers+text',
            marker=dict(size=15, color='cyan', symbol='star'),
            text=[f"MEP: ${resultado_mep['ganancia_usd']:.2f}"],
            textposition='middle right',
            name='Estrategia MEP',
            hovertemplate='<b>MEP</b><br>Ganancia: $%{x:.2f} USD<extra></extra>'
        ))
    
    # Barras para exchanges
    fig_crypto.add_trace(go.Bar(
        x=df_plot_crypto['Ganancia USD'],
        y=df_plot_crypto['Exchange'],
        orientation='h',
        marker=dict(color=colors_crypto),
        text=[f"${val:.2f}" for val in df_plot_crypto['Ganancia USD']],
        textposition='outside',
        name='Exchanges Crypto',
        hovertemplate='<b>%{y}</b><br>Ganancia: $%{x:.2f} USD<br>ROI: %{customdata:.2f}%<extra></extra>',
        customdata=df_plot_crypto['ROI (%)']
    ))
    
    fig_crypto.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
    
    fig_crypto.update_layout(
        template='plotly_dark',
        title=f'Comparación: MEP vs Crypto Exchanges (Volumen: ${volumen_usd:,.2f} USD)',
        xaxis_title='Ganancia (USD)',
        yaxis_title='Opción',
        height=max(500, len(df_plot_crypto) * 30 + 100),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_crypto, use_container_width=True)
    
    # Tabla completa
    st.subheader("📋 Tabla Completa de Exchanges")
    
    df_display_crypto = df_crypto[['Exchange', 'Precio USDT', 'Spread vs Oficial (%)', 
                                    'Ganancia ARS', 'Ganancia USD', 'ROI (%)', 
                                    'Vol. Mínimo (USD)', 'Viable']].copy()
    
    def highlight_viable(row):
        if row['Viable']:
            return ['background-color: rgba(0, 255, 0, 0.1)'] * len(row)
        else:
            return ['background-color: rgba(255, 0, 0, 0.1)'] * len(row)
    
    st.dataframe(
        df_display_crypto.style
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
    
    # --- INFORMACIÓN ADICIONAL ---
    st.markdown("---")
    st.header("💡 Información Importante")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(
            """
            **Estrategia 1 - Oficial → Crypto:**
            1. Comprar dólares oficiales
            2. Convertir a USDT (1:1)
            3. Pagar comisión de transferencia (${:.2f} USDT)
            4. Vender USDT en exchange crypto
            5. Pagar comisión del exchange ({:.1f}%)
            
            **Estrategia 2 - Oficial → MEP:**
            1. Comprar dólares oficiales
            2. Vender en el mercado MEP
            3. Sin comisiones adicionales
            """.format(comision_usdt, comision_pct * 100)
        )
    
    with col2:
        st.warning(
            """
            **⚠️ Consideraciones:**
            - Los precios fluctúan constantemente
            - Límites de compra diaria de dólares oficiales
            - Verifica requisitos KYC de exchanges
            - Esta es una simulación, no asesoramiento financiero
            - **No puedes operar oficial y MEP simultáneamente**
            - Considera el "Dólar Matrimonio" para maximizar oportunidades
            """
        )
    
    # Estadísticas generales
    st.markdown("---")
    st.header("📈 Estadísticas Generales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Exchanges Consultados", len(resultados_crypto))
    
    with col2:
        viables_crypto = len(df_crypto[df_crypto['Viable']])
        st.metric("Exchanges Rentables", viables_crypto)
    
    with col3:
        if df_crypto['ROI (%)'].max() > 0:
            mejor_roi_crypto = df_crypto['ROI (%)'].max()
            st.metric("Mejor ROI Crypto", f"{mejor_roi_crypto:.2f}%")
        if resultado_mep and resultado_mep['viable']:
            st.metric("ROI MEP", f"{resultado_mep['roi_porcentaje']:.2f}%")
    
    with col4:
        vol_min_crypto = df_crypto[df_crypto['Vol. Mínimo (USD)'] < float('inf')]['Vol. Mínimo (USD)'].mean()
        if pd.notna(vol_min_crypto):
            st.metric("Vol. Mín. Promedio", f"${vol_min_crypto:.2f}")
        else:
            st.metric("Vol. Mín. Promedio", "N/A")

st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


