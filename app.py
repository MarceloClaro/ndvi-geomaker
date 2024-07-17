import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import json

# Autenticação e inicialização do Google Earth Engine
ee.Authenticate()
ee.Initialize(project='ee-marceloclaro')

# Função para carregar arquivos GeoJSON e extrair a geometria
def carregar_geojson(upload_files):
    geometry_aoi_list = []
    for upload_file in upload_files:
        bytes_data = upload_file.read()
        geojson_data = json.loads(bytes_data)
        if 'features' in geojson_data:
            for feature in geojson_data['features']:
                if 'geometry' in feature:
                    coordinates = feature['geometry']['coordinates']
                    if feature['geometry']['type'] == 'Polygon':
                        geometry = ee.Geometry.Polygon(coordinates)
                    elif feature['geometry']['type'] == 'MultiPolygon':
                        geometry = ee.Geometry.MultiPolygon(coordinates)
                    geometry_aoi_list.append(geometry)
    if geometry_aoi_list:
        geometry_aoi = ee.Geometry.MultiPolygon(geometry_aoi_list)
    else:
        geometry_aoi = ee.Geometry.Point([0, 0])
    return geometry_aoi

# Função para processar a data de entrada e gerar intervalos de datas
def processar_datas(data_inicial, intervalo_dias):
    data_final = data_inicial
    data_inicial = data_final - timedelta(days=intervalo_dias)
    return data_inicial.strftime('%Y-%m-%d'), data_final.strftime('%Y-%m-%d')

# Função para criar uma coleção de imagens filtradas
def criar_colecao_imagens(cloud_coverage, data_inicial, data_final, aoi):
    colecao = ee.ImageCollection('COPERNICUS/S2_SR') \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_coverage)) \
        .filterDate(data_inicial, data_final) \
        .filterBounds(aoi) \
        .map(lambda img: img.clip(aoi).divide(10000))
    return colecao

# Função para calcular o NDVI
def calcular_ndvi(imagem):
    return imagem.normalizedDifference(['B8', 'B4'])

# Função para mascarar o NDVI para remover áreas com valor menor que zero
def mascarar_ndvi(ndvi):
    return ndvi.updateMask(ndvi.gte(0))

# Função para classificar o NDVI
def classificar_ndvi(ndvi):
    ndvi_classificado = ndvi \
        .where(ndvi.lt(0.15), 1) \
        .where(ndvi.gte(0.15).And(ndvi.lt(0.25)), 2) \
        .where(ndvi.gte(0.25).And(ndvi.lt(0.35)), 3) \
        .where(ndvi.gte(0.35).And(ndvi.lt(0.45)), 4) \
        .where(ndvi.gte(0.45).And(ndvi.lt(0.65)), 5) \
        .where(ndvi.gte(0.65).And(ndvi.lt(0.75)), 6) \
        .where(ndvi.gte(0.75), 7)
    return ndvi_classificado

# Função para adicionar camadas do Earth Engine ao mapa Folium
def adicionar_camada_ee(mapa, imagem, params_vis, nome):
    map_id_dict = ee.Image(imagem).getMapId(params_vis)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Map data © <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=nome,
        overlay=True,
        control=True
    ).add_to(mapa)

# Configuração do layout do Streamlit
st.set_page_config(page_title="Visualizador de NDVI", layout="wide")

# Título e descrição
st.title("Visualizador de NDVI")
st.markdown("""
    Este aplicativo permite explorar as mudanças no NDVI ao longo do tempo para uma Área de Interesse (AOI) especificada. 
    Carregue um arquivo GeoJSON com a AOI, selecione o intervalo de datas e a taxa de cobertura de nuvens, 
    e visualize os resultados em um mapa interativo.
""")

# Barra lateral para entrada de dados
with st.sidebar:
    st.header("Parâmetros de Entrada")
    st.subheader("Carregar GeoJSON AOI")
    arquivos_geojson = st.file_uploader("Selecione arquivos GeoJSON", type="geojson", accept_multiple_files=True)
    if arquivos_geojson:
        aoi = carregar_geojson(arquivos_geojson)

    st.subheader("Selecionar Intervalo de Datas")
    data_selecionada = st.date_input("Escolha uma data", value=datetime.today())
    intervalo_dias = st.slider("Intervalo de Dias", min_value=1, max_value=30, value=7)
    data_inicial, data_final = processar_datas(data_selecionada, intervalo_dias)

    st.subheader("Selecionar Taxa de Cobertura de Nuvens")
    taxa_cobertura_nuvens = st.slider("Cobertura de Nuvens (%)", min_value=0, max_value=100, value=20)

# Coletar e processar imagens
if arquivos_geojson:
    colecao_inicial = criar_colecao_imagens(taxa_cobertura_nuvens, data_inicial, data_final, aoi)
    imagem_median_inicial = colecao_inicial.median()
    ndvi_inicial = calcular_ndvi(imagem_median_inicial)
    ndvi_mascarado_inicial = mascarar_ndvi(ndvi_inicial)
    ndvi_classificado_inicial = classificar_ndvi(ndvi_mascarado_inicial)

    # Configurações de visualização
    params_vis_tci = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 0.3, 'gamma': 1.4}
    params_vis_ndvi = {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}
    params_vis_ndvi_classificado = {'min': 1, 'max': 7, 'palette': ['a50026', 'ed5e3d', 'f9f7ae', 'f4ff78', '9ed569', '229b51', '006837']}

    # Criar o mapa
    centro = aoi.centroid().coordinates().getInfo()[::-1]
    mapa = folium.Map(location=centro, zoom_start=12)
    adicionar_camada_ee(mapa, imagem_median_inicial, params_vis_tci, "Imagem de Satélite")
    adicionar_camada_ee(mapa, ndvi_mascarado_inicial, params_vis_ndvi, "NDVI Bruto")
    adicionar_camada_ee(mapa, ndvi_classificado_inicial, params_vis_ndvi_classificado, "NDVI Classificado")

    folium.LayerControl().add_to(mapa)

    # Exibir o mapa no Streamlit
    st.subheader("Visualização do Mapa")
    folium_static(mapa)

    # Exibir a legenda
    st.subheader("Legenda do Mapa")
    st.markdown("""
        **NDVI Bruto**
        -1 (Vermelho) a 1 (Verde)

        **Classes de NDVI**
        1. Vegetação Ausente (Água/Nuvens/Construído/Rochas/Areias)
        2. Solo Exposto
        3. Vegetação Baixa
        4. Vegetação Leve
        5. Vegetação Moderada
        6. Vegetação Forte
        7. Vegetação Densa
    """)

st.write("#### Informações Adicionais")
st.write("""
    Este aplicativo é projetado para fornecer uma ferramenta acessível para usuários técnicos e não técnicos para explorar e interpretar a saúde da vegetação e mudanças de densidade. 
    Tenha em mente que, embora o mapa NDVI seja uma ferramenta valiosa, sua interpretação requer consideração de vários fatores. Divirta-se explorando o mundo da saúde e densidade da vegetação!
""")
