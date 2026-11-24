import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from supabase import create_client
import pandas as pd
import io
import time

# ==============================================================================
# CONFIGURACIÓN GENERAL Y CONSTANTES DE LA TIENDA
# ==============================================================================

# Zona horaria oficial para registrar fechas de pedidos en hora local de Bolivia
ZONA_BOLIVIA = ZoneInfo("America/La_Paz")

# Datos de identidad y contacto de la tienda
NOMBRE_TIENDA = "MIMUNDOMICASA"
WHATSAPP_TIENDA = "59170730777"

# Credenciales y bucket de almacenamiento en Supabase
SUPABASE_URL = "https://ytwnelevkiggsodsinaf.supabase.co"
SUPABASE_KEY = "sb_publishable_R21i4vgb0lI50KYpL3_q_A_lW9ED3n2"
BUCKET_FOTOS = "fotos_productos"

# Líneas principales del negocio (permanentes y de temporada)
LINEAS_BASE = [
    "ACCESORIOS PARA EL CABELLO",
    "ACCESORIOS PARA EL HOGAR (NAVIDAD)",
    "ACCESORIOS PARA EL HOGAR (TEMPORADA)",
]

# Tipos de producto base que se muestran como mosaicos en el catálogo
TIPOS_PRODUCTO_BASE = [
    "COQUET",
    "FLOR",
    "POMPÓN",
    "SCRUNCHIES",
    "MARIPOSAS",
    "WINCHAS",
    "PULSERAS",
    "ALMOHADONES NAVIDEÑOS",
]

# Diccionario para corregir ortografía común y unificar nombres en mayúsculas
CORRECCIONES_ORTOGRAFIA = {
    "COQUET EN TELA": "COQUET EN TELA",
    "COQUET EN CINTA": "COQUET EN CINTA",
    "FLOR GOGO": "FLOR",
    "POMPON": "POMPÓN",
    "POMPÓN EN CINTA": "POMPÓN",
    "MARIPOSAS EN TELA": "MARIPOSAS",
    "ALAMOHADONES NAVIDEÑOS": "ALMOHADONES NAVIDEÑOS",
    "ALOHADONES NAVIDEÑOS": "ALMOHADONES NAVIDEÑOS",
    "ALOMOHADONES NAVIDEÑOS": "ALMOHADONES NAVIDEÑOS",
    "ACCESORIOS PARA EL CABELLO": "ACCESORIOS PARA EL CABELLO",
    "ACCESORIOS PARA EL HOGAR (NAVIDAD)": "ACCESORIOS PARA EL HOGAR (NAVIDAD)",
    "ACCESORIOS PARA EL HOGAR (TEMPORADA)": "ACCESORIOS PARA EL HOGAR (TEMPORADA)",
    "ESTANDAR": "ESTÁNDAR",
    "ESTÁNDAR": "ESTÁNDAR",
    "UNICO": "ÚNICO",
    "ÚNICO": "ÚNICO",
    "CAFE": "CAFÉ",
    "CAFÉ": "CAFÉ",
    "MARRON": "MARRÓN",
    "MARRÓN": "MARRÓN",
}

# Colores visuales (HEX) para mostrar muestras junto a los botones de color
MAPA_COLORES_CSS = {
    "ROJO": "#e53935",
    "AZUL": "#1e88e5",
    "CELESTE": "#4fc3f7",
    "ROSADO": "#ec407a",
    "ROSA": "#ec407a",
    "FUCSIA": "#d81b60",
    "NEGRO": "#212121",
    "BLANCO": "#f5f5f5",
    "VERDE": "#43a047",
    "AMARILLO": "#fdd835",
    "MORADO": "#8e24aa",
    "LILA": "#ab47bc",
    "NARANJA": "#fb8c00",
    "CAFÉ": "#6d4c41",
    "MARRÓN": "#6d4c41",
    "DORADO": "#fbc02d",
    "PLATEADO": "#90a4ae",
    "GRIS": "#757575",
    "BEIGE": "#d7ccc8",
    "CREMA": "#fff8e1",
    "NAVIDEÑO": "#c62828",
    "ÚNICO": "#546e7a",
}


# ==============================================================================
# FUNCIONES AUXILIARES (FECHAS, ORTOGRAFÍA, COLORES Y CONEXIÓN)
# ==============================================================================

def ahora_bolivia():
    """
    Cabecera:
    Obtiene la fecha y hora actual en la zona horaria de Bolivia (America/La_Paz).
    - Parámetros: ninguno.
    - Retorna: objeto datetime con zona horaria configurada.
    """
    return datetime.now(ZONA_BOLIVIA)  # Devuelve el instante actual en hora local de Bolivia


def normalizar_texto(texto, default="GENERAL"):
    """
    Cabecera:
    Limpia espacios sobrantes, convierte un texto a MAYÚSCULAS y aplica correcciones
    ortográficas predefinidas para mantener consistencia en el catálogo.
    - Parámetros:
        texto (str | None): texto de entrada a normalizar.
        default (str): valor en mayúsculas si el texto está vacío.
    - Retorna: str normalizado en mayúsculas.
    """
    limpio = " ".join(str(texto or "").strip().split()).upper()  # Quita espacios extra y pasa a mayúsculas
    if not limpio:
        return default.upper()  # Usa el valor por defecto si quedó vacío
    return CORRECCIONES_ORTOGRAFIA.get(limpio, limpio)  # Aplica corrección ortográfica si existe


def parsear_colores_stock(texto_colores):
    """
    Cabecera:
    Convierte una cadena de texto con formato 'COLOR:CANTIDAD, COLOR2:CANTIDAD2'
    en una lista de tuplas [(COLOR_MAYUS, STOCK_ENTERO), ...].
    - Parámetros:
        texto_colores (str | None): cadena con colores y cantidades separadas por coma.
    - Retorna: list[tuple[str, int]] con colores normalizados y cantidades >= 0.
    """
    resultado = []
    if not texto_colores or not str(texto_colores).strip():
        return [("ÚNICO", 0)]  # Valor seguro si no hay colores cargados
    for parte in str(texto_colores).split(","):
        parte = parte.strip()
        if not parte:
            continue  # Omite segmentos vacíos por comas dobles o finales
        if ":" in parte:
            nombre_c, cant_s = parte.split(":", 1)  # Separa nombre del color y cantidad
            nombre_c = normalizar_texto(nombre_c, "ÚNICO")  # Normaliza ortografía y mayúsculas del color
            try:
                cant_i = max(0, int(float(cant_s.strip())))  # Convierte stock a entero no negativo
            except ValueError:
                cant_i = 0  # Evita fallos si escriben un texto no numérico en stock
            resultado.append((nombre_c, cant_i))
        else:
            resultado.append((normalizar_texto(parte, "ÚNICO"), 1))  # Si solo indica color, asume 1 unidad
    return resultado if resultado else [("ÚNICO", 0)]


def serializar_colores_stock(lista_tuplas):
    """
    Cabecera:
    Convierte una lista de tuplas [(COLOR, STOCK), ...] en un texto limpio
    con formato 'COLOR:STOCK, COLOR2:STOCK2'.
    - Parámetros:
        lista_tuplas (list[tuple[str, int]]): pares color y cantidad.
    - Retorna: str formateado en mayúsculas.
    """
    return ", ".join([f"{normalizar_texto(c, 'ÚNICO')}:{max(0, int(s))}" for c, s in lista_tuplas])


def color_hex(nombre_color):
    """
    Cabecera:
    Busca un código hexadecimal de color CSS acorde al nombre del color en mayúsculas.
    - Parámetros:
        nombre_color (str): nombre del color (ej. 'ROJO', 'ROSADO', 'AZUL').
    - Retorna: str con código hexadecimal de color.
    """
    clave = normalizar_texto(nombre_color, "ÚNICO")  # Normaliza el nombre del color
    for k, v in MAPA_COLORES_CSS.items():
        if k in clave:
            return v  # Devuelve el primer color coincidente del diccionario
    return "#546e7a"  # Color gris azulado neutro por defecto


@st.cache_resource
def init_connection():
    """
    Cabecera:
    Crea y cachea el cliente oficial de Supabase para reutilizar la conexión
    entre recargas de la interfaz de Streamlit.
    - Parámetros: ninguno.
    - Retorna: cliente de Supabase inicializado.
    """
    return create_client(SUPABASE_URL, SUPABASE_KEY)  # Conecta con URL y clave pública de Supabase


# Cliente global de Supabase disponible para todas las funciones de datos e interfaz
supabase = init_connection()


def inicializar_estado_sesion():
    """
    Cabecera:
    Inicializa en st.session_state las variables necesarias para el carrito,
    navegación por línea y tipo de producto, sesión del administrador y enlace de WhatsApp.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    if "carrito" not in st.session_state:
        st.session_state["carrito"] = {}  # Estructura: {(id_producto, color): cantidad}
    if "linea_activa" not in st.session_state:
        st.session_state["linea_activa"] = "TODAS"  # Línea seleccionada en el catálogo
    if "tipo_activo" not in st.session_state:
        st.session_state["tipo_activo"] = None  # None = muestra mosaicos; str = muestra modelos del mosaico
    if "admin_autenticado" not in st.session_state:
        st.session_state["admin_autenticado"] = False  # Control de acceso al panel administrativo
    if "admin_usuario" not in st.session_state:
        st.session_state["admin_usuario"] = ""  # Nombre del usuario administrador autenticado
    if "ultimo_pedido_wp" not in st.session_state:
        st.session_state["ultimo_pedido_wp"] = None  # Guarda el último pedido confirmado para mostrar botón WP


# ==============================================================================
# FUNCIONES DE ACCESO A DATOS (SUPABASE DB Y STORAGE)
# ==============================================================================

def cargar_productos(solo_activos=True):
    """
    Cabecera:
    Consulta la tabla 'productos' en Supabase ordenada por ID ascendente.
    - Parámetros:
        solo_activos (bool): si es True, filtra únicamente productos con activo=True.
    - Retorna: list[dict] con los registros de productos.
    """
    try:
        query = supabase.table("productos").select("*").order("id", desc=False)  # Ordena por ID
        if solo_activos:
            query = query.eq("activo", True)  # Filtra solo productos visibles en catálogo público
        resp = query.execute()
        return resp.data if resp.data else []
    except Exception as e:
        st.error(f"ERROR AL CARGAR PRODUCTOS: {e}")
        return []


def subir_imagen_storage(archivo_subido):
    """
    Cabecera:
    Sube una imagen cargada por el usuario al bucket público 'fotos_productos' en Supabase
    y devuelve su URL pública.
    - Parámetros:
        archivo_subido (UploadedFile | None): archivo de imagen desde st.file_uploader.
    - Retorna: str con la URL pública de la imagen o cadena vacía si falla/no hay archivo.
    """
    if archivo_subido is None:
        return ""  # No sube nada si no se seleccionó imagen
    try:
        extension = archivo_subido.name.split(".")[-1].lower()  # Obtiene extensión (jpg, png, webp)
        nombre_archivo = f"prod_{int(time.time() * 1000)}.{extension}"  # Genera nombre único con timestamp
        bytes_imagen = archivo_subido.getvalue()  # Lee los bytes del archivo subido
        supabase.storage.from_(BUCKET_FOTOS).upload(
            path=nombre_archivo,
            file=bytes_imagen,
            file_options={"content-type": archivo_subido.type}
        )  # Sube el archivo al bucket de Supabase Storage
        return supabase.storage.from_(BUCKET_FOTOS).get_public_url(nombre_archivo)  # Retorna URL pública
    except Exception as e:
        st.error(f"NO SE PUDO SUBIR LA IMAGEN: {e}")
        return ""


def eliminar_producto_db(producto_id):
    """
    Cabecera:
    Elimina permanentemente un producto o modelo de la tabla 'productos' en Supabase
    según su identificador único (id).
    - Parámetros:
        producto_id (int): ID del registro a eliminar.
    - Retorna: None.
    """
    supabase.table("productos").delete().eq("id", int(producto_id)).execute()  # Borra la fila en Supabase por ID


def descontar_stock_pedido(carrito_dict, productos_frescos):
    """
    Cabecera:
    Descuenta en Supabase las cantidades compradas de cada color seleccionado
    y recalcula el stock total de cada producto afectado.
    - Parámetros:
        carrito_dict (dict): {(id_producto, color): cantidad}.
        productos_frescos (dict): {id_producto: registro_producto} actualizados.
    - Retorna: None.
    """
    for (pid, col_item), cant in carrito_dict.items():
        colores_act = parsear_colores_stock(productos_frescos[pid].get("colores_stock"))  # Lee stock actual por color
        nuevos_colores = []
        for c_nom, c_stk in colores_act:
            if c_nom == col_item:
                nuevos_colores.append((c_nom, max(0, c_stk - cant)))  # Descuenta unidades del color elegido
            else:
                nuevos_colores.append((c_nom, c_stk))  # Mantiene intactos los demás colores
        nuevo_stock_total = sum(s for _, s in nuevos_colores)  # Suma el stock de todos los colores
        supabase.table("productos").update({
            "colores_stock": serializar_colores_stock(nuevos_colores),
            "stock": nuevo_stock_total
        }).eq("id", pid).execute()  # Persiste el nuevo stock en Supabase


def generar_mensaje_whatsapp(pedido_id, nom_cli, tel_cli, mail_cli, ubi_cli, obs_cli, detalle_txt, total_productos):
    """
    Cabecera:
    Construye el mensaje formateado para WhatsApp y su enlace 'https://wa.me/...'
    incluyendo datos del cliente, ubicación de envío, detalle de productos y aviso de envío adicional.
    - Parámetros:
        pedido_id (int | str): identificador del pedido guardado.
        nom_cli (str): nombre del cliente en mayúsculas.
        tel_cli (str): teléfono/WhatsApp del cliente.
        mail_cli (str): correo electrónico opcional.
        ubi_cli (str): ubicación o dirección de envío.
        obs_cli (str): observación opcional.
        detalle_txt (str): líneas con productos, modelos, colores y subtotales.
        total_productos (float): subtotal de productos en Bs.
    - Retorna: str con la URL lista para abrir en WhatsApp.
    """
    obs_txt = f"\n📝 *OBSERVACIÓN:* {obs_cli}" if obs_cli else ""  # Añade observación solo si existe
    email_txt = f"\n✉️ *CORREO:* {mail_cli}" if mail_cli else ""  # Añade correo solo si fue ingresado
    msg_wp = (
        f"🎀 *NUEVO PEDIDO - {NOMBRE_TIENDA}*\n"
        f"🧾 *PEDIDO N°:* #{pedido_id}\n"
        f"👤 *CLIENTE:* {nom_cli}\n"
        f"📱 *WHATSAPP:* {tel_cli}"
        f"{email_txt}\n"
        f"📍 *UBICACIÓN DE ENVÍO:* {ubi_cli}"
        f"{obs_txt}\n\n"
        f"🛍️ *PRODUCTOS:*\n{detalle_txt}\n\n"
        f"💰 *SUBTOTAL PRODUCTOS: {total_productos:.2f} BS*\n"
        f"🚚 _EL COSTO DE ENVÍO ES ADICIONAL AL PRECIO DEL PRODUCTO SEGÚN EL DESTINO._"
    )  # Arma el cuerpo del mensaje para WhatsApp
    return f"https://wa.me/{WHATSAPP_TIENDA}?text={quote(msg_wp)}"  # Codifica el texto para URL de WhatsApp


# ==============================================================================
# FUNCIONES DE INTERFAZ (CATÁLOGO, CARRITO Y ADMINISTRACIÓN)
# ==============================================================================

def configurar_pagina_y_estilos():
    """
    Cabecera:
    Configura los parámetros generales de la página en Streamlit e inyecta
    los estilos CSS personalizados para el catálogo, tarjetas de color, aviso de envío y botón de WhatsApp.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    st.set_page_config(
        page_title=f"{NOMBRE_TIENDA} | CATÁLOGO",
        page_icon="🎀",
        layout="wide",
        initial_sidebar_state="collapsed"
    )  # Configura título, ícono y ancho de la app web

    st.markdown("""
        <style>
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        .kiosco-header {
            background: linear-gradient(90deg, #1565c0 0%, #1976d2 100%);
            color: white;
            padding: 16px 22px;
            border-radius: 12px;
            margin-bottom: 14px;
            box-shadow: 0 3px 10px rgba(21, 101, 192, 0.2);
        }
        .kiosco-titulo {
            font-size: 24px;
            font-weight: 800;
            margin: 0;
        }
        .kiosco-sub {
            font-size: 13px;
            opacity: 0.92;
            margin-top: 2px;
        }
        .seccion-banner {
            text-align: center;
            font-size: 22px;
            font-weight: 700;
            color: #1e293b;
            margin: 8px 0 4px 0;
        }
        .seccion-subrayado {
            width: 90px;
            height: 4px;
            background-color: #1976d2;
            margin: 0 auto 18px auto;
            border-radius: 2px;
        }
        .precio-lista {
            font-size: 20px;
            font-weight: 800;
            color: #1565c0;
            margin: 6px 0;
        }
        .badge-stock {
            display: inline-block;
            background-color: #e8f5e9;
            color: #1b5e20;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            margin-bottom: 6px;
        }
        .badge-agotado {
            display: inline-block;
            background-color: #ffebee;
            color: #c62828;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            margin-bottom: 6px;
        }
        .aviso-envio {
            background-color: #fff8e1;
            border-left: 4px solid #f59e0b;
            padding: 10px 14px;
            border-radius: 6px;
            color: #78350f;
            font-size: 14px;
            font-weight: 600;
            margin: 10px 0 14px 0;
        }
        .btn-whatsapp {
            display: inline-block;
            width: 100%;
            text-align: center;
            background-color: #25D366;
            color: white !important;
            font-size: 18px;
            font-weight: bold;
            padding: 14px 20px;
            border-radius: 10px;
            text-decoration: none;
            margin-top: 10px;
            box-shadow: 0 4px 10px rgba(37, 211, 102, 0.35);
        }
        .btn-whatsapp:hover {
            background-color: #1ebe5d;
            color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)


def render_catalogo(productos):
    """
    Cabecera:
    Renderiza el catálogo público con buscador, filtros por línea/temporada,
    mosaicos por tipo de producto (COQUET, FLOR, POMPÓN, SCRUNCHIES, MARIPOSAS,
    WINCHAS, PULSERAS, ALMOHADONES NAVIDEÑOS), filtro rápido de COQUET EN TELA
    y COQUET EN CINTA, y tarjetas de modelos con botones de color en stock.
    - Parámetros:
        productos (list[dict]): lista de productos activos desde Supabase.
    - Retorna: None.
    """
    if not productos:
        st.info("AÚN NO HAY PRODUCTOS ACTIVOS EN EL CATÁLOGO.")
        return  # Sale temprano si no hay productos publicados

    busqueda = st.text_input(
        "🔍 BUSCAR POR TIPO, MODELO O COLOR",
        placeholder="EJ. COQUET EN TELA, COQUET EN CINTA, COLA REDONDA, COLA LARGA, DELGADA, GRUESA..."
    )  # Barra de búsqueda en tiempo real

    # Extrae las líneas únicas preservando el orden de aparición
    lineas = []
    for p in productos:
        cat = normalizar_texto(p.get("categoria"), "ACCESORIOS PARA EL CABELLO")
        if cat not in lineas:
            lineas.append(cat)

    # Construye botones de línea con contador de artículos
    botones_linea = [("TODAS", len(productos))] + [
        (cat, sum(1 for x in productos if normalizar_texto(x.get("categoria"), "ACCESORIOS PARA EL CABELLO") == cat))
        for cat in lineas
    ]

    cols_lineas = st.columns(len(botones_linea))
    for idx_l, (nombre_l, cant_l) in enumerate(botones_linea):
        etiqueta_l = f"INICIO ({cant_l})" if nombre_l == "TODAS" else f"{nombre_l} ({cant_l})"
        es_actual = (st.session_state["linea_activa"] == nombre_l and st.session_state["tipo_activo"] is None)
        with cols_lineas[idx_l]:
            if st.button(
                etiqueta_l,
                key=f"btn_linea_{idx_l}",
                type="primary" if es_actual else "secondary",
                use_container_width=True
            ):
                st.session_state["linea_activa"] = nombre_l  # Cambia la línea activa
                st.session_state["tipo_activo"] = None  # Regresa a los mosaicos de tipos de producto
                st.rerun()

    st.divider()

    linea_sel = st.session_state["linea_activa"]
    tipo_sel = st.session_state["tipo_activo"]

    # Filtra productos según la línea seleccionada
    productos_linea = productos
    if linea_sel != "TODAS":
        productos_linea = [
            p for p in productos_linea
            if normalizar_texto(p.get("categoria"), "ACCESORIOS PARA EL CABELLO") == linea_sel
        ]

    # Nivel 2: Muestra mosaicos de Tipos de Producto cuando no hay tipo seleccionado ni búsqueda
    if tipo_sel is None and not busqueda.strip():
        st.markdown("<div class='seccion-banner'>SELECCIONA UN TIPO DE PRODUCTO</div><div class='seccion-subrayado'></div>", unsafe_allow_html=True)

        tipos_disponibles = []
        for p in productos_linea:
            tp = normalizar_texto(p.get("tipo_producto") or p.get("nombre"), "GENERAL")
            if tp not in tipos_disponibles:
                tipos_disponibles.append(tp)  # Obtiene cada tipo de producto único en mayúsculas

        cols_mosaico = st.columns(4)
        for idx_t, tp_nombre in enumerate(tipos_disponibles):
            items_tp = [
                x for x in productos_linea
                if normalizar_texto(x.get("tipo_producto") or x.get("nombre"), "GENERAL") == tp_nombre
            ]  # Modelos pertenecientes a este mosaico
            foto_tp = next((x.get("imagen_url") for x in items_tp if (x.get("imagen_url") or "").strip()), "")
            subproductos_preview = ", ".join(
                dict.fromkeys([
                    normalizar_texto(x.get("subproducto") or x.get("nombre"), "")
                    for x in items_tp if (x.get("subproducto") or "").strip()
                ])
            )  # Vista previa de modelos dentro del mosaico

            with cols_mosaico[idx_t % 4]:
                with st.container(border=True):
                    if foto_tp:
                        st.image(foto_tp, use_container_width=True)  # Muestra foto representativa del mosaico
                    else:
                        st.markdown(
                            f"<div style='height:145px;background:#f1f5f9;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#475569;font-weight:800;font-size:16px;text-align:center;padding:8px;'>🎀 {tp_nombre}</div>",
                            unsafe_allow_html=True
                        )  # Placeholder visual si aún no tiene foto
                    st.markdown(f"### {tp_nombre}")
                    if tp_nombre == "COQUET":
                        st.caption("INCLUYE: COQUET EN TELA Y COQUET EN CINTA")  # Destaca ambas líneas dentro de COQUET
                    elif subproductos_preview:
                        st.caption(f"MODELOS: {subproductos_preview}")
                    st.write(f"**{len(items_tp)}** MODELOS DISPONIBLES")
                    if st.button(f"VER MODELOS →", key=f"open_tipo_{idx_t}", type="primary", use_container_width=True):
                        st.session_state["tipo_activo"] = tp_nombre  # Abre los modelos de este tipo de producto
                        st.rerun()

    # Nivel 3: Muestra subproductos/modelos del tipo elegido o resultados de búsqueda
    else:
        filtro_coquet = "TODOS"
        if tipo_sel is not None:
            col_back, col_tit = st.columns([1.3, 4], vertical_alignment="center")
            with col_back:
                if st.button("⬅️ VOLVER A LOS PRODUCTOS", use_container_width=True):
                    st.session_state["tipo_activo"] = None  # Regresa al mosaico general de tipos
                    st.rerun()
            with col_tit:
                st.markdown(f"<div class='seccion-banner' style='text-align:left;margin:0;'>{tipo_sel}</div>", unsafe_allow_html=True)

            # Si el usuario entra a COQUET, permite filtrar entre COQUET EN TELA y COQUET EN CINTA
            if tipo_sel == "COQUET":
                filtro_coquet = st.radio(
                    "FILTRAR COQUET POR TIPO:",
                    ["TODOS", "COQUET EN TELA", "COQUET EN CINTA"],
                    horizontal=True,
                    key="filtro_estilo_coquet"
                )  # Selector rápido entre COQUET EN TELA y COQUET EN CINTA
            st.divider()

        filtrados = productos_linea
        if tipo_sel is not None:
            filtrados = [
                p for p in filtrados
                if normalizar_texto(p.get("tipo_producto") or p.get("nombre"), "GENERAL") == tipo_sel
            ]

        if tipo_sel == "COQUET" and filtro_coquet != "TODOS":
            filtrados = [
                p for p in filtrados
                if filtro_coquet in normalizar_texto(p.get("subproducto"), "")
                or filtro_coquet in normalizar_texto(p.get("nombre"), "")
                or filtro_coquet in normalizar_texto(p.get("descripcion"), "")
            ]  # Filtra los modelos que corresponden a COQUET EN TELA o COQUET EN CINTA

        if busqueda.strip():
            term = normalizar_texto(busqueda, "")
            filtrados = [
                p for p in filtrados
                if term in normalizar_texto(p.get("tipo_producto"), "")
                or term in normalizar_texto(p.get("nombre"), "")
                or term in normalizar_texto(p.get("subproducto"), "")
                or term in normalizar_texto(p.get("categoria"), "")
                or term in normalizar_texto(p.get("colores_stock"), "")
            ]

        if not filtrados:
            st.warning("NO SE ENCONTRARON MODELOS CON ESE CRITERIO.")
            return

        cols_prod = st.columns(3)
        for idx_p, prod in enumerate(filtrados):
            with cols_prod[idx_p % 3]:
                with st.container(border=True):
                    img_url = (prod.get("imagen_url") or "").strip()
                    if img_url:
                        st.image(img_url, use_container_width=True)  # Muestra foto del modelo
                    else:
                        st.markdown(
                            "<div style='height:150px;background:#f8fafc;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-weight:600;'>🎀 SIN IMAGEN</div>",
                            unsafe_allow_html=True
                        )

                    tp_prod = normalizar_texto(prod.get("tipo_producto") or prod.get("nombre"), "GENERAL")
                    subp = normalizar_texto(prod.get("subproducto") or prod.get("nombre"), "ESTÁNDAR")
                    precio = float(prod.get("precio") or 0)
                    colores_lista = parsear_colores_stock(prod.get("colores_stock"))
                    colores_disp = [(c, s) for c, s in colores_lista if s > 0]  # Solo colores con stock disponible
                    stock_total = sum(s for _, s in colores_lista)

                    st.caption(f"{normalizar_texto(prod.get('categoria'), 'GENERAL')} · {tp_prod}")
                    st.markdown(f"### {subp}")
                    if prod.get("descripcion"):
                        st.write(normalizar_texto(prod["descripcion"], ""))
                    st.markdown(f"<div class='precio-lista'>{precio:.2f} BS</div>", unsafe_allow_html=True)

                    if stock_total > 0 and precio > 0:
                        st.markdown(f"<div class='badge-stock'>STOCK DISPONIBLE: {stock_total} UNID.</div>", unsafe_allow_html=True)
                        st.caption("COLORES DISPONIBLES EN STOCK:")

                        key_color_sel = f"color_sel_{prod['id']}"
                        nombres_disp = [c for c, _ in colores_disp]
                        if key_color_sel not in st.session_state or st.session_state[key_color_sel] not in nombres_disp:
                            st.session_state[key_color_sel] = nombres_disp[0]  # Selecciona el primer color disponible

                        color_actual = st.session_state[key_color_sel]

                        # Botones visuales por cada color disponible en stock
                        cols_colores = st.columns(min(len(colores_disp), 3))
                        for idx_c, (nom_c, stk_c) in enumerate(colores_disp):
                            hex_c = color_hex(nom_c)
                            es_sel = (nom_c == color_actual)
                            borde = "3px solid #1565c0" if es_sel else "1px solid #cbd5e1"
                            with cols_colores[idx_c % len(cols_colores)]:
                                st.markdown(
                                    f"<div style='display:flex;align-items:center;gap:6px;padding:4px 6px;border:{borde};border-radius:6px;margin-bottom:4px;background:#fff;'>"
                                    f"<span style='display:inline-block;width:14px;height:14px;border-radius:50%;background:{hex_c};border:1px solid #999;'></span>"
                                    f"<span style='font-size:12px;font-weight:700;'>{nom_c} ({stk_c})</span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                                if st.button(
                                    "ELEGIDO ✓" if es_sel else f"{nom_c}",
                                    key=f"btn_c_{prod['id']}_{nom_c}",
                                    use_container_width=True
                                ):
                                    st.session_state[key_color_sel] = nom_c  # Actualiza color seleccionado
                                    st.rerun()

                        stock_color_actual = dict(colores_disp).get(color_actual, 0)
                        en_carrito_color = st.session_state["carrito"].get((prod["id"], color_actual), 0)

                        if st.button(
                            f"🛒 AGREGAR ({color_actual}) AL CARRITO",
                            key=f"add_cart_{prod['id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            if en_carrito_color < stock_color_actual:
                                st.session_state["carrito"][(prod["id"], color_actual)] = en_carrito_color + 1  # Agrega unidad al carrito
                                st.toast(f"✅ AGREGADO: {tp_prod} - {subp} [{color_actual}]")
                                st.rerun()
                            else:
                                st.warning(f"⚠️ NO HAY MÁS UNIDADES EN COLOR {color_actual}.")
                    else:
                        st.markdown("<div class='badge-agotado'>❌ AGOTADO</div>", unsafe_allow_html=True)
                        st.button("SIN STOCK DISPONIBLE", key=f"no_stk_{prod['id']}", disabled=True, use_container_width=True)


def render_carrito(productos):
    """
    Cabecera:
    Renderiza el carrito de compras con tabla de artículos (descripción, precio unitario,
    cantidad con botones +/- e importe), subtotal, aviso de costo de envío adicional
    según destino, formulario de datos del cliente/ubicación y confirmación a WhatsApp.
    - Parámetros:
        productos (list[dict]): lista de productos activos desde Supabase.
    - Retorna: None.
    """
    st.subheader("🛒 CARRITO DE COMPRAS")
    st.write("REVISE LOS ARTÍCULOS EN SU CARRITO. AL CONFIRMAR, SE REGISTRARÁ EL PEDIDO, SE DESCONTARÁ EL STOCK Y PODRÁ ENVIARLO POR WHATSAPP.")

    # Aviso obligatorio sobre el costo de envío adicional según destino
    st.markdown(
        "<div class='aviso-envio'>🚚 NOTA: EL COSTO DE ENVÍO ES ADICIONAL AL PRECIO DEL PRODUCTO SEGÚN EL DESTINO.</div>",
        unsafe_allow_html=True
    )

    # Muestra botón verde directo a WhatsApp si el pedido acaba de confirmarse
    if st.session_state.get("ultimo_pedido_wp"):
        info_wp = st.session_state["ultimo_pedido_wp"]
        st.success(f"🎉 ¡PEDIDO #{info_wp['id']} REGISTRADO CON ÉXITO Y STOCK ACTUALIZADO!")
        st.markdown(
            f"<a href='{info_wp['url']}' target='_blank' class='btn-whatsapp'>📲 ENVIAR PEDIDO POR WHATSAPP A {NOMBRE_TIENDA}</a>",
            unsafe_allow_html=True
        )
        st.write("")
        if st.button("🛍️ SEGUIR COMPRANDO"):
            st.session_state["ultimo_pedido_wp"] = None
            st.rerun()
        st.divider()

    productos_map = {p["id"]: p for p in productos}
    carrito = st.session_state["carrito"]

    # Limpia ítems del carrito que ya no tengan stock en su color elegido
    for clave_item in list(carrito.keys()):
        pid, col_item = clave_item
        if pid not in productos_map:
            del carrito[clave_item]
            continue
        colores_dict = dict(parsear_colores_stock(productos_map[pid].get("colores_stock")))
        if colores_dict.get(col_item, 0) <= 0:
            del carrito[clave_item]

    if not carrito:
        st.info("TU CARRITO ESTÁ VACÍO. SELECCIONA UN TIPO DE PRODUCTO, SU MODELO Y COLOR EN LA PESTAÑA **🛍️ CATÁLOGO**.")
        return

    # Encabezados de la tabla del carrito
    h1, h2, h3, h4 = st.columns([4.5, 1.8, 2.2, 1.8])
    h1.markdown("**DESCRIPCIÓN**")
    h2.markdown("**PRECIO UNITARIO**")
    h3.markdown("**CANT.**")
    h4.markdown("**IMPORTE**")
    st.divider()

    total_productos = 0.0
    lineas_detalle = []

    for clave_item, cant in list(carrito.items()):
        pid, col_item = clave_item
        prod = productos_map[pid]
        colores_dict = dict(parsear_colores_stock(prod.get("colores_stock")))
        max_col = colores_dict.get(col_item, 0)

        if cant > max_col:
            cant = max_col
            carrito[clave_item] = cant  # Ajusta si el stock bajó mientras navegaba

        precio_u = float(prod.get("precio") or 0)
        importe = precio_u * cant
        total_productos += importe
        tp_prod = normalizar_texto(prod.get("tipo_producto") or prod.get("nombre"), "GENERAL")
        subp = normalizar_texto(prod.get("subproducto"), "ESTÁNDAR")
        col_norm = normalizar_texto(col_item, "ÚNICO")
        lineas_detalle.append(f"• {cant}X {tp_prod} - {subp} (COLOR: {col_norm}) [{precio_u:.2f} BS] = {importe:.2f} BS")

        r1, r2, r3, r4 = st.columns([4.5, 1.8, 2.2, 1.8], vertical_alignment="center")
        with r1:
            st.markdown(f"**{tp_prod}** · *{subp}*")
            st.caption(f"COLOR: **{col_norm}** · STOCK COLOR: {max_col}")
        with r2:
            st.write(f"{precio_u:.2f} BS")
        with r3:
            c_men, c_num, c_mas = st.columns([1, 1, 1], vertical_alignment="center")
            with c_men:
                if st.button("➖", key=f"dec_{pid}_{col_item}"):
                    if cant > 1:
                        carrito[clave_item] = cant - 1  # Decrementa cantidad en 1
                    else:
                        del carrito[clave_item]  # Elimina el ítem si llega a 0
                    st.rerun()
            with c_num:
                st.markdown(f"<div style='text-align:center;font-weight:700;'>{cant}</div>", unsafe_allow_html=True)
            with c_mas:
                if st.button("➕", key=f"inc_{pid}_{col_item}"):
                    if cant < max_col:
                        carrito[clave_item] = cant + 1  # Incrementa cantidad si hay stock
                        st.rerun()
                    else:
                        st.warning("STOCK MÁXIMO EN ESTE COLOR.")
        with r4:
            st.markdown(f"**{importe:.2f} BS**")

    st.divider()
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;'>"
        f"<span style='font-size:17px;font-weight:700;'>SUBTOTAL PRODUCTOS (BS.):</span>"
        f"<span style='font-size:22px;font-weight:800;color:#1565c0;'>{total_productos:.2f} BS</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.caption("*EL COSTO DE ENVÍO ES ADICIONAL AL PRECIO DEL PRODUCTO SEGÚN EL DESTINO Y SE COORDINA AL ENVIAR EL PEDIDO.")

    st.divider()
    st.subheader("📋 DATOS DEL CLIENTE Y ENVÍO")

    with st.form("form_datos_cliente_carrito"):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            cliente_nombre = st.text_input("NOMBRE COMPLETO *", placeholder="EJ. MARÍA PÉREZ")
            cliente_email = st.text_input("CORREO ELECTRÓNICO (OPCIONAL)", placeholder="EJ. CORREO@EJEMPLO.COM")
        with col_d2:
            cliente_telefono = st.text_input("TELÉFONO / CELULAR WHATSAPP *", placeholder="EJ. 70712345")
            ubicacion_envio = st.text_input("UBICACIÓN / DIRECCIÓN PARA EL ENVÍO *", placeholder="EJ. ZONA NORTE, AV. AMÉRICA / RECOJO")

        observacion = st.text_input("OBSERVACIÓN (OPCIONAL)", placeholder="EJ. ENVOLVER PARA REGALO, HORARIO DE ENTREGA...")

        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
            limpiar_btn = st.form_submit_button("🗑️ VACIAR CARRITO")
        with col_b2:
            confirmar_btn = st.form_submit_button("✅ CONFIRMAR PEDIDO Y ENVIAR POR WHATSAPP", type="primary")

        if limpiar_btn:
            st.session_state["carrito"] = {}  # Vacía todo el carrito
            st.rerun()

        if confirmar_btn:
            if not cliente_nombre.strip() or not cliente_telefono.strip() or not ubicacion_envio.strip():
                st.warning("⚠️ COMPLETA TU NOMBRE COMPLETO, TELÉFONO/WHATSAPP Y UBICACIÓN PARA EL ENVÍO.")
                return

            prod_frescos = {p["id"]: p for p in cargar_productos(solo_activos=True)}
            errores_stock = []

            # Verifica disponibilidad de stock por color justo antes de guardar el pedido
            for (pid, col_item), cant in carrito.items():
                if pid not in prod_frescos:
                    errores_stock.append(f"PRODUCTO ID {pid}")
                    continue
                col_map = dict(parsear_colores_stock(prod_frescos[pid].get("colores_stock")))
                if col_map.get(col_item, 0) < cant:
                    errores_stock.append(
                        f"{normalizar_texto(prod_frescos[pid].get('tipo_producto'), 'PRODUCTO')} - "
                        f"{normalizar_texto(prod_frescos[pid].get('subproducto'), 'MODELO')} ({normalizar_texto(col_item, 'COLOR')})"
                    )

            if errores_stock:
                st.error(f"⚠️ STOCK INSUFICIENTE PARA: {', '.join(errores_stock)}. ACTUALIZA LAS CANTIDADES.")
                return

            try:
                nom_cli = normalizar_texto(cliente_nombre, "")
                tel_cli = normalizar_texto(cliente_telefono, "")
                mail_cli = cliente_email.strip().lower()
                ubi_cli = normalizar_texto(ubicacion_envio, "")
                obs_cli = normalizar_texto(observacion, "")
                detalle_txt = "\n".join(lineas_detalle)

                # Inserta el pedido en la tabla 'pedidos' de Supabase
                resp_ped = supabase.table("pedidos").insert({
                    "fecha": ahora_bolivia().isoformat(),
                    "cliente_nombre": nom_cli,
                    "cliente_telefono": tel_cli,
                    "cliente_email": mail_cli,
                    "direccion": ubi_cli,
                    "detalle": detalle_txt + (f"\nOBS: {obs_cli}" if obs_cli else ""),
                    "total": float(total_productos),
                    "estado": "PENDIENTE"
                }).execute()
                pedido_id = resp_ped.data[0]["id"] if resp_ped.data else "NUEVO"

                # Descuenta el stock de cada color vendido en Supabase
                descontar_stock_pedido(carrito, prod_frescos)

                # Genera el enlace de WhatsApp y limpia el carrito
                url_wp = generar_mensaje_whatsapp(
                    pedido_id, nom_cli, tel_cli, mail_cli, ubi_cli, obs_cli, detalle_txt, total_productos
                )
                st.session_state["carrito"] = {}
                st.session_state["ultimo_pedido_wp"] = {"id": pedido_id, "url": url_wp}
                st.rerun()
            except Exception as e:
                st.error(f"ERROR AL PROCESAR EL PEDIDO: {e}")


def render_login_admin():
    """
    Cabecera:
    Muestra el formulario de inicio de sesión para el panel administrativo
    y valida credenciales contra la tabla 'admin_tienda' de Supabase.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    st.subheader("🔐 ACCESO ADMINISTRADOR")
    with st.form("form_login_tienda"):
        u_in = st.text_input("USUARIO").strip().lower()
        p_in = st.text_input("CONTRASEÑA", type="password")
        if st.form_submit_button("INGRESAR"):
            try:
                r = supabase.table("admin_tienda").select("*").eq("usuario", u_in).eq("password", p_in).execute()
                if r.data:
                    st.session_state["admin_autenticado"] = True
                    st.session_state["admin_usuario"] = u_in.upper()
                    st.rerun()
                else:
                    st.error("USUARIO O CONTRASEÑA INCORRECTOS.")
            except Exception:
                # Respaldo local en caso de falla temporal al consultar la tabla de admin
                if u_in == "admin" and p_in == "12345":
                    st.session_state["admin_autenticado"] = True
                    st.session_state["admin_usuario"] = "ADMIN"
                    st.rerun()
                else:
                    st.error("USUARIO O CONTRASEÑA INCORRECTOS.")


def render_subtab_crear_producto():
    """
    Cabecera:
    Renderiza el formulario para crear un nuevo tipo de producto (mosaico),
    un subtipo/variante opcional (ej. COQUET EN TELA, COQUET EN CINTA) y su
    subproducto/modelo (ej. COLA REDONDA, COLA LARGA, DELGADA, GRUESA) con precio,
    colores en stock y foto.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    st.write("CREA UN **TIPO DE PRODUCTO** (EJ. *COQUET*, *FLOR*, *POMPÓN*, *SCRUNCHIES*, *MARIPOSAS*, *WINCHAS*, *PULSERAS*), SU SUBTIPO OPCIONAL (EJ. *COQUET EN TELA*, *COQUET EN CINTA*) Y SU **SUBPRODUCTO / MODELO** (EJ. *COLA REDONDA*, *COLA LARGA*, *DELGADA*, *GRUESA*):")
    todos_existentes = cargar_productos(solo_activos=False)
    tipos_guardados = sorted(list(set(
        [normalizar_texto(t, "") for t in TIPOS_PRODUCTO_BASE] + [
            normalizar_texto(p.get("tipo_producto") or p.get("nombre"), "")
            for p in todos_existentes if normalizar_texto(p.get("tipo_producto") or p.get("nombre"), "")
        ]
    )))  # Lista unificada y ordenada de tipos de producto en mayúsculas

    with st.form("form_nuevo_tipo_subproducto", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            cat_sel = st.selectbox("1. LÍNEA / TEMPORADA", LINEAS_BASE)
            cat_nueva = st.text_input("O ESCRIBE NUEVA LÍNEA (OPCIONAL)")
        with c2:
            tipo_sel_form = st.selectbox("2. TIPO DE PRODUCTO (MOSAICO) *", tipos_guardados)
            subtipo_opcional = st.text_input(
                "SUBTIPO / DETALLE OPCIONAL (EJ. COQUET EN TELA, COQUET EN CINTA)",
                placeholder="DEJAR VACÍO SI NO APLICA"
            )  # Permite indicar COQUET EN TELA / COQUET EN CINTA o dejarlo vacío
            sub_p = st.text_input(
                "3. SUBPRODUCTO / MODELO * (EJ. COLA REDONDA, COLA LARGA, DELGADA, GRUESA)",
                placeholder="EJ. COLA REDONDA, COLA LARGA, DELGADA, GRUESA"
            )
        with c3:
            prec_p = st.number_input("4. PRECIO DE LISTA (BS.) *", min_value=0.0, step=1.0, format="%.2f")
            col_stk_p = st.text_input("5. COLORES Y STOCK * (EJ. ROJO:4, ROSA:6, AZUL:2)", value="ROJO:5, ROSA:5")
            desc_p = st.text_input("DESCRIPCIÓN CORTA (OPCIONAL)")

        foto_p = st.file_uploader("FOTO DEL MODELO (OPCIONAL)", type=["jpg", "jpeg", "png", "webp"])

        if st.form_submit_button("💾 GUARDAR TIPO Y SUBPRODUCTO", type="primary"):
            cat_f = normalizar_texto(cat_nueva if cat_nueva.strip() else cat_sel, "ACCESORIOS PARA EL CABELLO")
            tipo_f = normalizar_texto(tipo_sel_form, "")
            subtipo_f = normalizar_texto(subtipo_opcional, "") if subtipo_opcional.strip() else ""
            modelo_f = normalizar_texto(sub_p, "")
            desc_f = normalizar_texto(desc_p, "")

            if not tipo_f or not modelo_f:
                st.warning("⚠️ COMPLETA EL TIPO DE PRODUCTO Y EL SUBPRODUCTO / MODELO.")
                return

            # Si se indicó subtipo (ej. COQUET EN TELA) y no se repitió dentro del modelo, los une cleanly
            if subtipo_f and subtipo_f not in modelo_f:
                subproducto_final = f"{subtipo_f} - {modelo_f}"
            else:
                subproducto_final = modelo_f

            col_tuplas = parsear_colores_stock(col_stk_p)
            stk_tot = sum(s for _, s in col_tuplas)
            url_img = subir_imagen_storage(foto_p) if foto_p else ""

            try:
                supabase.table("productos").insert({
                    "categoria": cat_f,
                    "tipo_producto": tipo_f,
                    "nombre": f"{tipo_f} - {subproducto_final}",
                    "subproducto": subproducto_final,
                    "descripcion": desc_f,
                    "precio": float(prec_p),
                    "colores_stock": serializar_colores_stock(col_tuplas),
                    "stock": int(stk_tot),
                    "imagen_url": url_img,
                    "activo": True
                }).execute()  # Inserta el nuevo modelo en Supabase
                st.success(f"✅ CREADO EN MOSAICO **{tipo_f}** → **{subproducto_final}**.")
                st.rerun()
            except Exception as e:
                st.error(f"ERROR AL CREAR PRODUCTO: {e}")


def render_subtab_lista_precios():
    """
    Cabecera:
    Renderiza la tabla editable para configurar y actualizar en lote los precios de lista,
    colores en stock, tipos de producto, modelos y visibilidad de cada ítem,
    e incluye una herramienta para eliminar un producto/modelo específico.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    st.write("EDITA DIRECTAMENTE LOS TIPOS DE PRODUCTO, MODELOS, PRECIOS DE LISTA, COLORES EN STOCK O VISIBILIDAD:")
    todos_p = cargar_productos(solo_activos=False)
    if not todos_p:
        st.info("NO HAY PRODUCTOS REGISTRADOS TODAVÍA.")
        return

    df_lista = pd.DataFrame([
        {
            "id": p["id"],
            "LÍNEA": normalizar_texto(p.get("categoria"), "ACCESORIOS PARA EL CABELLO"),
            "TIPO PRODUCTO (MOSAICO)": normalizar_texto(p.get("tipo_producto") or p.get("nombre"), "GENERAL"),
            "SUBPRODUCTO / MODELO": normalizar_texto(p.get("subproducto"), "ESTÁNDAR"),
            "PRECIO LISTA (BS.)": float(p.get("precio") or 0),
            "COLORES EN STOCK (COLOR:CANT)": serializar_colores_stock(parsear_colores_stock(p.get("colores_stock"))),
            "ACTIVO": bool(p.get("activo", True))
        }
        for p in todos_p
    ])  # Construye DataFrame con valores normalizados en mayúsculas

    df_editado = st.data_editor(
        df_lista,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "PRECIO LISTA (BS.)": st.column_config.NumberColumn(
                "PRECIO LISTA (BS.)",
                min_value=0.0,
                step=1.0,
                format="%.2f"
            ),
            "COLORES EN STOCK (COLOR:CANT)": st.column_config.TextColumn(
                "COLORES EN STOCK (EJ. ROJO:5, AZUL:3)"
            ),
            "ACTIVO": st.column_config.CheckboxColumn("VISIBLE")
        },
        use_container_width=True,
        hide_index=True,
        key="editor_lista_precios"
    )  # Tabla editable interactiva

    if st.button("💾 GUARDAR TODOS LOS CAMBIOS DE PRECIOS Y STOCK", type="primary"):
        try:
            for _, fila in df_editado.iterrows():
                col_list = parsear_colores_stock(fila["COLORES EN STOCK (COLOR:CANT)"])
                stock_sum = sum(s for _, s in col_list)
                cat_val = normalizar_texto(fila["LÍNEA"], "ACCESORIOS PARA EL CABELLO")
                tp_val = normalizar_texto(fila["TIPO PRODUCTO (MOSAICO)"], "GENERAL")
                sub_val = normalizar_texto(fila["SUBPRODUCTO / MODELO"], "ESTÁNDAR")
                supabase.table("productos").update({
                    "categoria": cat_val,
                    "tipo_producto": tp_val,
                    "nombre": f"{tp_val} - {sub_val}",
                    "subproducto": sub_val,
                    "precio": float(fila["PRECIO LISTA (BS.)"]),
                    "colores_stock": serializar_colores_stock(col_list),
                    "stock": int(stock_sum),
                    "activo": bool(fila["ACTIVO"])
                }).eq("id", int(fila["id"])).execute()  # Guarda cada fila editada en Supabase
            st.success("✅ ¡LISTA DE PRECIOS, MOSAICOS Y STOCK ACTUALIZADOS!")
            st.rerun()
        except Exception as e:
            st.error(f"ERROR AL ACTUALIZAR TABLA: {e}")

    st.divider()
    st.subheader("🗑️ ELIMINAR UN PRODUCTO / MODELO ESPECÍFICO")  # Sección para borrar un registro individual

    # Construye etiquetas descriptivas en mayúsculas para elegir el modelo a eliminar
    opciones_borrar = {
        f"#{p['id']} | {normalizar_texto(p.get('tipo_producto') or p.get('nombre'), 'GENERAL')} - "
        f"{normalizar_texto(p.get('subproducto'), 'ESTÁNDAR')} ({float(p.get('precio') or 0):.2f} BS)": p["id"]
        for p in todos_p
    }
    sel_borrar = st.selectbox("SELECCIONA EL REGISTRO A ELIMINAR", list(opciones_borrar.keys()))

    if st.button("🗑️ ELIMINAR PRODUCTO SELECCIONADO"):
        try:
            eliminar_producto_db(opciones_borrar[sel_borrar])  # Ejecuta el borrado en Supabase
            st.success("✅ PRODUCTO ELIMINADO CORRECTAMENTE.")
            st.rerun()
        except Exception as e:
            st.error(f"ERROR AL ELIMINAR PRODUCTO: {e}")


def render_subtab_pedidos():
    """
    Cabecera:
    Muestra los pedidos recibidos desde la tienda, permite cambiar su estado
    y ofrece la descarga del reporte en formato Excel (.xlsx).
    - Parámetros: ninguno.
    - Retorna: None.
    """
    try:
        resp_ped = supabase.table("pedidos").select("*").order("id", desc=True).execute()
        ped_rows = resp_ped.data if resp_ped.data else []
        if not ped_rows:
            st.info("AÚN NO HAY PEDIDOS REGISTRADOS.")
            return

        df_ped = pd.DataFrame(ped_rows)
        st.dataframe(df_ped, use_container_width=True)

        ops = {
            f"#{r['id']} - {normalizar_texto(r['cliente_nombre'], 'CLIENTE')} ({r['total']} BS) [{normalizar_texto(r['estado'], 'PENDIENTE')}]": r["id"]
            for _, r in df_ped.iterrows()
        }
        sel_o = st.selectbox("SELECCIONAR PEDIDO", list(ops.keys()))
        est_o = st.selectbox("ESTADO", ["PENDIENTE", "PAGADO / EN CAMINO", "ENTREGADO", "CANCELADO"])
        if st.button("ACTUALIZAR ESTADO DE PEDIDO"):
            supabase.table("pedidos").update({"estado": est_o}).eq("id", ops[sel_o]).execute()  # Actualiza estado en DB
            st.success("✅ ESTADO ACTUALIZADO.")
            st.rerun()

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_ped.to_excel(w, index=False, sheet_name="Pedidos")  # Genera archivo Excel en memoria
        st.download_button(
            "📥 EXPORTAR PEDIDOS (.XLSX)",
            data=buf.getvalue(),
            file_name=f"pedidos_{NOMBRE_TIENDA}_{ahora_bolivia().date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"ERROR AL CARGAR PEDIDOS: {e}")


def render_admin():
    """
    Cabecera:
    Controla el acceso al panel de administración y muestra las subpestañas para crear
    tipos/modelos, editar la tabla de precios/colores y administrar pedidos.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    if not st.session_state["admin_autenticado"]:
        render_login_admin()  # Muestra login si aún no inició sesión
        return

    col_at, col_as = st.columns([4, 1], vertical_alignment="center")
    with col_at:
        st.subheader(f"⚙️ PANEL DE ADMINISTRACIÓN · {NOMBRE_TIENDA}")
    with col_as:
        if st.button("🚪 SALIR"):
            st.session_state["admin_autenticado"] = False  # Cierra sesión administrativa
            st.session_state["admin_usuario"] = ""
            st.rerun()

    sub_crear, sub_precios, sub_pedidos = st.tabs([
        "➕ CREAR TIPO DE PRODUCTO Y MODELO",
        "💲 LISTA DE PRECIOS Y COLORES (TABLA)",
        "📦 PEDIDOS RECIBIDOS"
    ])

    with sub_crear:
        render_subtab_crear_producto()

    with sub_precios:
        render_subtab_lista_precios()

    with sub_pedidos:
        render_subtab_pedidos()


def main():
    """
    Cabecera:
    Función principal que orquesta la inicialización de la página, estado de sesión,
    encabezado superior y pestañas principales de MIMUNDOMICASA.
    - Parámetros: ninguno.
    - Retorna: None.
    """
    configurar_pagina_y_estilos()  # Aplica configuración y estilos visuales
    inicializar_estado_sesion()  # Prepara variables de sesión

    total_items_carrito = sum(st.session_state["carrito"].values())
    etiqueta_carrito = f"🛒 CARRITO ({total_items_carrito} ART.)" if total_items_carrito > 0 else "🛒 CARRITO (0 ART.)"

    st.markdown(f"""
        <div class="kiosco-header">
            <div class="kiosco-titulo">🎀 {NOMBRE_TIENDA} · CATÁLOGO</div>
            <div class="kiosco-sub">ACCESORIOS PARA EL CABELLO Y DETALLES PARA EL HOGAR · PRECIOS DE LISTA EN BS.</div>
        </div>
    """, unsafe_allow_html=True)

    tab_catalogo, tab_carrito, tab_admin = st.tabs([
        "🛍️ CATÁLOGO",
        etiqueta_carrito,
        "🔐 ADMINISTRACIÓN"
    ])

    productos_activos = cargar_productos(solo_activos=True)

    with tab_catalogo:
        render_catalogo(productos_activos)

    with tab_carrito:
        render_carrito(productos_activos)

    with tab_admin:
        render_admin()


if __name__ == "__main__":
    main()  # Punto de entrada de la aplicación Streamlit
