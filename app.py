import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from supabase import create_client
import pandas as pd
import io
import time

# --- ZONA HORARIA LOCAL (COCHABAMBA / BOLIVIA) ---
ZONA_BOLIVIA = ZoneInfo("America/La_Paz")

def ahora_bolivia():
    return datetime.now(ZONA_BOLIVIA)

# --- CONFIGURACIÓN DE LA TIENDA ---
NOMBRE_TIENDA = "MiMundoMiCasa"
WHATSAPP_TIENDA = "59170730777"

SUPABASE_URL = "https://ytwnelevkiggsodsinaf.supabase.co"
SUPABASE_KEY = "sb_publishable_R21i4vgb0lI50KYpL3_q_A_lW9ED3n2"
BUCKET_FOTOS = "fotos_productos"

MAPA_COLORES_CSS = {
    "rojo": "#e53935",
    "azul": "#1e88e5",
    "celeste": "#4fc3f7",
    "rosado": "#ec407a",
    "rosa": "#ec407a",
    "fucsia": "#d81b60",
    "negro": "#212121",
    "blanco": "#f5f5f5",
    "verde": "#43a047",
    "amarillo": "#fdd835",
    "morado": "#8e24aa",
    "lila": "#ab47bc",
    "naranja": "#fb8c00",
    "cafe": "#6d4c41",
    "café": "#6d4c41",
    "marron": "#6d4c41",
    "marrón": "#6d4c41",
    "dorado": "#fbc02d",
    "plateado": "#90a4ae",
    "gris": "#757575",
    "beige": "#d7ccc8",
    "crema": "#fff8e1",
    "navideño": "#c62828",
    "unico": "#546e7a",
    "único": "#546e7a",
}

def parsear_colores_stock(texto_colores):
    """Convierte 'Rojo:4, Azul:2' en [('Rojo', 4), ('Azul', 2)]."""
    resultado = []
    if not texto_colores or not str(texto_colores).strip():
        return [("Único", 0)]
    partes = str(texto_colores).split(",")
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if ":" in parte:
            nombre_c, cant_s = parte.split(":", 1)
            nombre_c = nombre_c.strip().title()
            try:
                cant_i = max(0, int(float(cant_s.strip())))
            except ValueError:
                cant_i = 0
            resultado.append((nombre_c, cant_i))
        else:
            resultado.append((parte.title(), 1))
    return resultado if resultado else [("Único", 0)]

def serializar_colores_stock(lista_tuplas):
    return ", ".join([f"{c}:{max(0, int(s))}" for c, s in lista_tuplas])

def color_hex(nombre_color):
    clave = (nombre_color or "").strip().lower()
    for k, v in MAPA_COLORES_CSS.items():
        if k in clave:
            return v
    return "#546e7a"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

st.set_page_config(
    page_title=f"{NOMBRE_TIENDA} | Tienda Virtual",
    page_icon="🎀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

# --- ESTADO DE SESIÓN ---
# carrito guarda {(id_producto, color): cantidad}
if "carrito" not in st.session_state:
    st.session_state["carrito"] = {}
if "linea_activa" not in st.session_state:
    st.session_state["linea_activa"] = "TODAS"
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False
if "admin_usuario" not in st.session_state:
    st.session_state["admin_usuario"] = ""
if "ultimo_pedido_wp" not in st.session_state:
    st.session_state["ultimo_pedido_wp"] = None

def cargar_productos(solo_activos=True):
    try:
        query = supabase.table("productos").select("*").order("id", desc=False)
        if solo_activos:
            query = query.eq("activo", True)
        resp = query.execute()
        return resp.data if resp.data else []
    except Exception as e:
        st.error(f"Error al cargar productos: {e}")
        return []

def subir_imagen_storage(archivo_subido):
    if archivo_subido is None:
        return ""
    try:
        extension = archivo_subido.name.split(".")[-1].lower()
        nombre_archivo = f"prod_{int(time.time() * 1000)}.{extension}"
        bytes_imagen = archivo_subido.getvalue()
        supabase.storage.from_(BUCKET_FOTOS).upload(
            path=nombre_archivo,
            file=bytes_imagen,
            file_options={"content-type": archivo_subido.type}
        )
        return supabase.storage.from_(BUCKET_FOTOS).get_public_url(nombre_archivo)
    except Exception as e:
        st.error(f"No se pudo subir la imagen: {e}")
        return ""

# --- CABECERA ---
total_items_carrito = sum(st.session_state["carrito"].values())
etiqueta_carrito = f"🛒 Carrito ({total_items_carrito} art.)" if total_items_carrito > 0 else "🛒 Carrito (0 art.)"

st.markdown(f"""
    <div class="kiosco-header">
        <div class="kiosco-titulo">🎀 {NOMBRE_TIENDA} · CATÁLOGO</div>
        <div class="kiosco-sub">Accesorios para el cabello y detalles para el hogar · Precios de lista en Bs.</div>
    </div>
""", unsafe_allow_html=True)

tab_catalogo, tab_carrito, tab_admin = st.tabs([
    "🛍️ Catálogo",
    etiqueta_carrito,
    "🔐 Administración"
])

# ==========================================
# PESTAÑA 1: CATÁLOGO CON BOTONES DE COLOR
# ==========================================
with tab_catalogo:
    productos = cargar_productos(solo_activos=True)

    if not productos:
        st.info("Aún no hay productos activos en el catálogo.")
    else:
        busqueda = st.text_input(
            "🔍 Buscar por producto, subproducto, línea o color",
            placeholder="Ej. Coquet, Scrunchies, Winchas, Almohadones Navideños, Rojo..."
        )

        lineas = []
        for p in productos:
            cat = (p.get("categoria") or "General").strip()
            if cat not in lineas:
                lineas.append(cat)

        botones_linea = [("TODAS", len(productos))] + [
            (cat, sum(1 for x in productos if (x.get("categoria") or "General").strip() == cat))
            for cat in lineas
        ]

        cols_lineas = st.columns(len(botones_linea))
        for idx_l, (nombre_l, cant_l) in enumerate(botones_linea):
            etiqueta_l = f"INICIO ({cant_l})" if nombre_l == "TODAS" else f"{nombre_l} ({cant_l})"
            es_actual = (st.session_state["linea_activa"] == nombre_l)
            with cols_lineas[idx_l]:
                if st.button(
                    etiqueta_l,
                    key=f"btn_linea_{idx_l}",
                    type="primary" if es_actual else "secondary",
                    use_container_width=True
                ):
                    st.session_state["linea_activa"] = nombre_l
                    st.rerun()

        linea_sel = st.session_state["linea_activa"]
        filtrados = productos
        if linea_sel != "TODAS":
            filtrados = [p for p in filtrados if (p.get("categoria") or "General").strip() == linea_sel]

        if busqueda.strip():
            term = busqueda.strip().lower()
            filtrados = [
                p for p in filtrados
                if term in (p.get("nombre") or "").lower()
                or term in (p.get("subproducto") or "").lower()
                or term in (p.get("categoria") or "").lower()
                or term in (p.get("colores_stock") or "").lower()
            ]

        st.divider()

        if not filtrados:
            st.warning("No se encontraron productos con ese filtro.")
        else:
            cols_prod = st.columns(3)
            for idx_p, prod in enumerate(filtrados):
                with cols_prod[idx_p % 3]:
                    with st.container(border=True):
                        img_url = (prod.get("imagen_url") or "").strip()
                        if img_url:
                            st.image(img_url, use_container_width=True)
                        else:
                            st.markdown(
                                "<div style='height:140px;background:#f8fafc;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-weight:600;'>🎀 Sin imagen</div>",
                                unsafe_allow_html=True
                            )

                        subp = (prod.get("subproducto") or "Estándar").strip()
                        precio = float(prod.get("precio") or 0)
                        colores_lista = parsear_colores_stock(prod.get("colores_stock"))
                        colores_disp = [(c, s) for c, s in colores_lista if s > 0]
                        stock_total = sum(s for _, s in colores_lista)

                        st.caption(f"{prod.get('categoria') or 'General'}")
                        st.markdown(f"**{prod['nombre']}** · *{subp}*")
                        st.markdown(f"<div class='precio-lista'>{precio:.2f} Bs</div>", unsafe_allow_html=True)

                        if stock_total > 0 and precio > 0:
                            st.markdown(f"<div class='badge-stock'>Stock total: {stock_total} unid.</div>", unsafe_allow_html=True)
                            st.caption("Colores disponibles en stock (haz clic para elegir):")

                            # Botones de color con muestra visual y stock
                            key_color_sel = f"color_sel_{prod['id']}"
                            nombres_disp = [c for c, _ in colores_disp]
                            if key_color_sel not in st.session_state or st.session_state[key_color_sel] not in nombres_disp:
                                st.session_state[key_color_sel] = nombres_disp[0]

                            color_actual = st.session_state[key_color_sel]

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
                                        "Elegido ✓" if es_sel else f"Color {nom_c}",
                                        key=f"btn_c_{prod['id']}_{nom_c}",
                                        use_container_width=True
                                    ):
                                        st.session_state[key_color_sel] = nom_c
                                        st.rerun()

                            stock_color_actual = dict(colores_disp).get(color_actual, 0)
                            en_carrito_color = st.session_state["carrito"].get((prod["id"], color_actual), 0)

                            if st.button(
                                f"🛒 Agregar ({color_actual}) al Carrito",
                                key=f"add_cart_{prod['id']}",
                                type="primary",
                                use_container_width=True
                            ):
                                if en_carrito_color < stock_color_actual:
                                    st.session_state["carrito"][(prod["id"], color_actual)] = en_carrito_color + 1
                                    st.toast(f"✅ Agregado: {prod['nombre']} [{color_actual}]")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ No hay más unidades en color {color_actual}.")
                        else:
                            st.markdown("<div class='badge-agotado'>❌ AGOTADO</div>", unsafe_allow_html=True)
                            st.button("Sin stock disponible", key=f"no_stk_{prod['id']}", disabled=True, use_container_width=True)

# ==========================================
# PESTAÑA 2: CARRITO DE COMPRAS — PEDIDO
# ==========================================
with tab_carrito:
    st.subheader("🛒 Carrito de Compras")
    st.write("Revise los artículos en su carrito. Al confirmar, se registrará el pedido, se descontará el stock y podrá enviarlo por WhatsApp.")

    st.markdown(
        "<div class='aviso-envio'>🚚 Nota: El costo de envío es adicional al precio del producto según el destino.</div>",
        unsafe_allow_html=True
    )

    if st.session_state.get("ultimo_pedido_wp"):
        info_wp = st.session_state["ultimo_pedido_wp"]
        st.success(f"🎉 ¡Pedido #{info_wp['id']} registrado con éxito y stock actualizado!")
        st.markdown(
            f"<a href='{info_wp['url']}' target='_blank' class='btn-whatsapp'>📲 Enviar Pedido por WhatsApp a {NOMBRE_TIENDA}</a>",
            unsafe_allow_html=True
        )
        st.write("")
        if st.button("🛍️ Seguir comprando"):
            st.session_state["ultimo_pedido_wp"] = None
            st.rerun()
        st.divider()

    productos_map = {p["id"]: p for p in cargar_productos(solo_activos=True)}
    carrito = st.session_state["carrito"]

    # Validar ítems del carrito contra stock de color actual
    for clave_item in list(carrito.keys()):
        pid, col_item = clave_item
        if pid not in productos_map:
            del carrito[clave_item]
            continue
        colores_dict = dict(parsear_colores_stock(productos_map[pid].get("colores_stock")))
        if colores_dict.get(col_item, 0) <= 0:
            del carrito[clave_item]

    if not carrito:
        st.info("Tu carrito está vacío. Selecciona un producto y su color en la pestaña **🛍️ Catálogo**.")
    else:
        # Encabezado tipo tabla
        h1, h2, h3, h4 = st.columns([4.5, 1.8, 2.2, 1.8])
        h1.markdown("**Descripción**")
        h2.markdown("**Precio Unitario**")
        h3.markdown("**Cant.**")
        h4.markdown("**Importe**")
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
                carrito[clave_item] = cant

            precio_u = float(prod.get("precio") or 0)
            importe = precio_u * cant
            total_productos += importe
            subp = (prod.get("subproducto") or "Estándar").strip()
            lineas_detalle.append(f"• {cant}x {prod['nombre']} ({subp}) - Color: {col_item} [{precio_u:.2f} Bs] = {importe:.2f} Bs")

            r1, r2, r3, r4 = st.columns([4.5, 1.8, 2.2, 1.8], vertical_alignment="center")
            with r1:
                st.markdown(f"**{prod['nombre']}** · *{subp}*")
                st.caption(f"Color: **{col_item}** · Stock color: {max_col}")
            with r2:
                st.write(f"{precio_u:.2f} Bs")
            with r3:
                c_men, c_num, c_mas = st.columns([1, 1, 1], vertical_alignment="center")
                with c_men:
                    if st.button("➖", key=f"dec_{pid}_{col_item}"):
                        if cant > 1:
                            carrito[clave_item] = cant - 1
                        else:
                            del carrito[clave_item]
                        st.rerun()
                with c_num:
                    st.markdown(f"<div style='text-align:center;font-weight:700;'>{cant}</div>", unsafe_allow_html=True)
                with c_mas:
                    if st.button("➕", key=f"inc_{pid}_{col_item}"):
                        if cant < max_col:
                            carrito[clave_item] = cant + 1
                            st.rerun()
                        else:
                            st.warning("Stock máximo en este color.")
            with r4:
                st.markdown(f"**{importe:.2f} Bs**")

        st.divider()
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;'>"
            f"<span style='font-size:17px;font-weight:700;'>Subtotal Productos (Bs.):</span>"
            f"<span style='font-size:22px;font-weight:800;color:#1565c0;'>{total_productos:.2f} Bs</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.caption("*El costo de envío es adicional al precio del producto según el destino y se coordina al enviar el pedido.")

        st.divider()
        st.subheader("📋 Datos del Cliente y Envío")

        with st.form("form_datos_cliente_carrito"):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                cliente_nombre = st.text_input("Nombre Completo *", placeholder="Ej. María Pérez")
                cliente_email = st.text_input("Correo Electrónico (opcional)", placeholder="Ej. correo@ejemplo.com")
            with col_d2:
                cliente_telefono = st.text_input("Teléfono / Celular WhatsApp *", placeholder="Ej. 70712345")
                ubicacion_envio = st.text_input("Ubicación / Dirección para el envío *", placeholder="Ej. Zona Norte, Av. América / Recojo")

            observacion = st.text_input("Observación (opcional)", placeholder="Ej. Envolver para regalo, horario de entrega...")

            col_b1, col_b2 = st.columns([1, 2])
            with col_b1:
                limpiar_btn = st.form_submit_button("🗑️ Vaciar Carrito")
            with col_b2:
                confirmar_btn = st.form_submit_button("✅ Confirmar Pedido y Enviar por WhatsApp", type="primary")

            if limpiar_btn:
                st.session_state["carrito"] = {}
                st.rerun()

            if confirmar_btn:
                if not cliente_nombre.strip() or not cliente_telefono.strip() or not ubicacion_envio.strip():
                    st.warning("⚠️ Completa tu Nombre Completo, Teléfono/WhatsApp y Ubicación para el envío.")
                else:
                    prod_frescos = {p["id"]: p for p in cargar_productos(solo_activos=True)}
                    errores_stock = []

                    for (pid, col_item), cant in carrito.items():
                        if pid not in prod_frescos:
                            errores_stock.append(f"Producto ID {pid}")
                            continue
                        col_map = dict(parsear_colores_stock(prod_frescos[pid].get("colores_stock")))
                        if col_map.get(col_item, 0) < cant:
                            errores_stock.append(f"{prod_frescos[pid]['nombre']} ({col_item})")

                    if errores_stock:
                        st.error(f"⚠️ Stock insuficiente para: {', '.join(errores_stock)}. Actualiza las cantidades.")
                    else:
                        try:
                            detalle_txt = "\n".join(lineas_detalle)
                            obs_txt = f"\n📝 *Observación:* {observacion.strip()}" if observacion.strip() else ""
                            email_txt = f"\n✉️ *Correo:* {cliente_email.strip()}" if cliente_email.strip() else ""

                            resp_ped = supabase.table("pedidos").insert({
                                "fecha": ahora_bolivia().isoformat(),
                                "cliente_nombre": cliente_nombre.strip(),
                                "cliente_telefono": cliente_telefono.strip(),
                                "cliente_email": cliente_email.strip(),
                                "direccion": ubicacion_envio.strip(),
                                "detalle": detalle_txt + (f"\nObs: {observacion.strip()}" if observacion.strip() else ""),
                                "total": float(total_productos),
                                "estado": "Pendiente"
                            }).execute()
                            pedido_id = resp_ped.data[0]["id"] if resp_ped.data else "NUEVO"

                            # Descontar stock del color específico y actualizar stock total
                            for (pid, col_item), cant in carrito.items():
                                colores_act = parsear_colores_stock(prod_frescos[pid].get("colores_stock"))
                                nuevos_colores = []
                                for c_nom, c_stk in colores_act:
                                    if c_nom == col_item:
                                        nuevos_colores.append((c_nom, max(0, c_stk - cant)))
                                    else:
                                        nuevos_colores.append((c_nom, c_stk))
                                nuevo_stock_total = sum(s for _, s in nuevos_colores)
                                supabase.table("productos").update({
                                    "colores_stock": serializar_colores_stock(nuevos_colores),
                                    "stock": nuevo_stock_total
                                }).eq("id", pid).execute()

                            msg_wp = (
                                f"🎀 *NUEVO PEDIDO - {NOMBRE_TIENDA}*\n"
                                f"🧾 *Pedido N°:* #{pedido_id}\n"
                                f"👤 *Cliente:* {cliente_nombre.strip()}\n"
                                f"📱 *WhatsApp:* {cliente_telefono.strip()}"
                                f"{email_txt}\n"
                                f"📍 *Ubicación de envío:* {ubicacion_envio.strip()}"
                                f"{obs_txt}\n\n"
                                f"🛍️ *Productos:*\n{detalle_txt}\n\n"
                                f"💰 *SUBTOTAL PRODUCTOS: {total_productos:.2f} Bs*\n"
                                f"🚚 _El costo de envío es adicional al precio del producto según el destino._"
                            )
                            url_wp = f"https://wa.me/{WHATSAPP_TIENDA}?text={quote(msg_wp)}"

                            st.session_state["carrito"] = {}
                            st.session_state["ultimo_pedido_wp"] = {"id": pedido_id, "url": url_wp}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar el pedido: {e}")

# ==========================================
# PESTAÑA 3: ADMINISTRACIÓN Y LISTA DE PRECIOS
# ==========================================
with tab_admin:
    if not st.session_state["admin_autenticado"]:
        st.subheader("🔐 Acceso Administrador")
        with st.form("form_login_tienda"):
            u_in = st.text_input("Usuario").strip().lower()
            p_in = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar"):
                try:
                    r = supabase.table("admin_tienda").select("*").eq("usuario", u_in).eq("password", p_in).execute()
                    if r.data:
                        st.session_state["admin_autenticado"] = True
                        st.session_state["admin_usuario"] = u_in.upper()
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception:
                    if u_in == "admin" and p_in == "12345":
                        st.session_state["admin_autenticado"] = True
                        st.session_state["admin_usuario"] = "ADMIN"
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
    else:
        col_at, col_as = st.columns([4, 1], vertical_alignment="center")
        with col_at:
            st.subheader(f"⚙️ Panel de Administración · {NOMBRE_TIENDA}")
        with col_as:
            if st.button("🚪 Salir"):
                st.session_state["admin_autenticado"] = False
                st.session_state["admin_usuario"] = ""
                st.rerun()

        sub_precios, sub_crear, sub_pedidos = st.tabs([
            "💲 Lista de Precios y Colores (Tabla)",
            "➕ Nuevo Producto / Variante",
            "📦 Pedidos Recibidos"
        ])

        # --- TABLA EDITABLE DE PRECIOS Y STOCK POR COLOR ---
        with sub_precios:
            st.write("Configura y actualiza los precios de lista, colores en stock y visibilidad directamente en la tabla:")
            todos_p = cargar_productos(solo_activos=False)
            if not todos_p:
                st.info("No hay productos registrados todavía.")
            else:
                df_lista = pd.DataFrame([
                    {
                        "id": p["id"],
                        "Línea": p.get("categoria") or "General",
                        "Producto": p["nombre"],
                        "Subproducto": p.get("subproducto") or "Estándar",
                        "Precio Lista (Bs.)": float(p.get("precio") or 0),
                        "Colores en Stock (Color:Cant)": p.get("colores_stock") or "Único:0",
                        "Activo": bool(p.get("activo", True))
                    }
                    for p in todos_p
                ])

                df_editado = st.data_editor(
                    df_lista,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "Precio Lista (Bs.)": st.column_config.NumberColumn(
                            "Precio Lista (Bs.)",
                            min_value=0.0,
                            step=1.0,
                            format="%.2f"
                        ),
                        "Colores en Stock (Color:Cant)": st.column_config.TextColumn(
                            "Colores en Stock (Ej. Rojo:5, Azul:3)"
                        ),
                        "Activo": st.column_config.CheckboxColumn("Visible")
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="editor_lista_precios"
                )

                if st.button("💾 Guardar Todos los Cambios de Precios y Stock", type="primary"):
                    try:
                        for _, fila in df_editado.iterrows():
                            col_list = parsear_colores_stock(fila["Colores en Stock (Color:Cant)"])
                            stock_sum = sum(s for _, s in col_list)
                            supabase.table("productos").update({
                                "categoria": str(fila["Línea"]).strip(),
                                "nombre": str(fila["Producto"]).strip(),
                                "subproducto": str(fila["Subproducto"]).strip(),
                                "precio": float(fila["Precio Lista (Bs.)"]),
                                "colores_stock": serializar_colores_stock(col_list),
                                "stock": int(stock_sum),
                                "activo": bool(fila["Activo"])
                            }).eq("id", int(fila["id"])).execute()
                        st.success("✅ ¡Lista de precios y stock de colores actualizada en Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar tabla de precios: {e}")

        # --- CREAR NUEVO PRODUCTO CON COLORES Y FOTO ---
        with sub_crear:
            st.write("Registra un nuevo producto o variante con sus colores disponibles y foto:")
            with st.form("form_nuevo_prod_colores", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    cat_sel = st.selectbox(
                        "Línea / Temporada",
                        [
                            "Accesorios para el Cabello",
                            "Accesorios para el Hogar (Navidad)",
                            "Accesorios para el Hogar (Temporada)"
                        ]
                    )
                    cat_nueva = st.text_input("O escribe nueva línea (Opcional)")
                with c2:
                    nom_p = st.text_input("Producto * (Ej. Scrunchies, Almohadones Navideños)")
                    sub_p = st.text_input("Subproducto * (Ej. Grande, Cola Redonda)", value="Estándar")
                with c3:
                    prec_p = st.number_input("Precio de Lista (Bs.) *", min_value=0.0, step=1.0, format="%.2f")
                    col_stk_p = st.text_input("Colores y Stock * (Ej. Rojo:4, Rosa:6, Azul:2)", value="Rojo:5, Rosa:5")

                foto_p = st.file_uploader("Foto del producto (Opcional)", type=["jpg", "jpeg", "png", "webp"])

                if st.form_submit_button("➕ Guardar Producto"):
                    cat_f = cat_nueva.strip() if cat_nueva.strip() else cat_sel
                    if not nom_p.strip() or not sub_p.strip():
                        st.warning("⚠️ Completa el nombre del producto y del subproducto.")
                    else:
                        col_tuplas = parsear_colores_stock(col_stk_p)
                        stk_tot = sum(s for _, s in col_tuplas)
                        url_img = subir_imagen_storage(foto_p) if foto_p else ""
                        try:
                            supabase.table("productos").insert({
                                "categoria": cat_f,
                                "nombre": nom_p.strip(),
                                "subproducto": sub_p.strip(),
                                "precio": float(prec_p),
                                "colores_stock": serializar_colores_stock(col_tuplas),
                                "stock": int(stk_tot),
                                "imagen_url": url_img,
                                "activo": True
                            }).execute()
                            st.success(f"✅ Producto '{nom_p.strip()} - {sub_p.strip()}' guardado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al crear producto: {e}")

        # --- PEDIDOS RECIBIDOS ---
        with sub_pedidos:
            try:
                resp_ped = supabase.table("pedidos").select("*").order("id", desc=True).execute()
                ped_rows = resp_ped.data if resp_ped.data else []
                if not ped_rows:
                    st.info("Aún no hay pedidos registrados.")
                else:
                    df_ped = pd.DataFrame(ped_rows)
                    st.dataframe(df_ped, use_container_width=True)

                    ops = {f"#{r['id']} - {r['cliente_nombre']} ({r['total']} Bs) [{r['estado']}]": r["id"] for _, r in df_ped.iterrows()}
                    sel_o = st.selectbox("Seleccionar pedido", list(ops.keys()))
                    est_o = st.selectbox("Estado", ["Pendiente", "Pagado / En camino", "Entregado", "Cancelado"])
                    if st.button("Actualizar Estado de Pedido"):
                        supabase.table("pedidos").update({"estado": est_o}).eq("id", ops[sel_o]).execute()
                        st.success("✅ Estado actualizado.")
                        st.rerun()

                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        df_ped.to_excel(w, index=False, sheet_name="Pedidos")
                    st.download_button(
                        "📥 Exportar Pedidos (.xlsx)",
                        data=buf.getvalue(),
                        file_name=f"pedidos_{NOMBRE_TIENDA}_{ahora_bolivia().date()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"Error al cargar pedidos: {e}")
