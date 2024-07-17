
import streamlit as st
import ee
import geemap
import folium
from folium import WmsTileLayer
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import json

# Autenticação e inicialização do Google Earth Engine
ee.Authenticate()
ee.Initialize(project='ee-marceloclaro')

st.markdown(
"""
<style>
    /* Cabeçalho */
    .st-emotion-cache-1avcm0n{
        height: 1rem;
    }
    /* Rolagem suave */
    .main {
        scroll-behavior: smooth;
    }
    /* corpo principal do app com menos padding */
    .st-emotion-cache-z5fcl4 {
        padding-block: 0;
    }

    /* Barra lateral */
    .st-emotion-cache-10oheav {
        padding: 0 1rem;
    }

    /* Barra lateral: contêiner interno */
    .css-ge7e53 {
        width: fit-content;
    }

    /* Barra lateral: imagem */
    .css-1kyxreq {
        display: block !important;
    }

    /* Barra lateral: lista de navegação */
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li {
        padding: 0;
        margin: 0;
        padding: 0;
        font-weight: 600;
    }
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li > a {
        text-decoration: none;
        transition: 0.2s ease-in-out;
        padding-inline: 10px;
    }
    
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li > a:hover {
        color: rgb(46, 206, 255);
        transition: 0.2s ease-in-out;
        background: #131720;
        border-radius: 4px;
    }
    
    /* Barra lateral: sociais */
    div.css-rklnmr:nth-child(6) > div:nth-child(1) > div:nth-child(1) > p {
        display: flex;
        flex-direction: row;
        gap: 1rem;
    }

    /* Caixa de informações de upload */
    /* Botão de upload: tema escuro */
    .st-emotion-cache-1erivf3 {
        display: flex;
        flex-direction: column;
        align-items: inherit;
        font-size: 14px;
    }
    .css-u8hs99.eqdbnj014 {
        display: flex;
        flex-direction: row;
        margin-inline: 0;
    }
    /* Botão de upload: tema claro */
    .st-emotion-cache-1gulkj5 {
        display: flex;
        flex-direction: column;
        align-items: inherit;
        font-size: 14px;
    }

    .st-emotion-cache-u8hs99 {
        display: flex;
        flex-direction: row;
        margin-inline: 0;
    }
    /* Estilo da legenda */

    .ndvilegend {
        transition: 0.2s ease-in-out;
        border-radius: 5px;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
        background: rgba(0, 0, 0, 0.05);
    }
    .ndvilegend:hover {
        transition: 0.3s ease-in-out;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.8);
        background: rgba(0, 0, 0, 0.12);
        cursor: pointer;
    }
    .reclassifiedndvi {
        transition: 0.2s ease-in-out;
        border-radius: 5px;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
        background: rgba(0, 0, 0, 0.05);
    }
    .reclassifiedndvi:hover {
        transition: 0.3s ease-in-out;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.8);
        background: rgba(0, 0, 0, 0.12);
        cursor: pointer;
    }
    
    /* Botão de envio de formulário: gerar mapa */
    button.st-emotion-cache-19rxjzo:nth-child(1) {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    layer = folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Dados do mapa &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=name,
        overlay=True,
        control=True
    )
    layer.add_to(self)
    return layer

folium.Map.add_ee_layer = add_ee_layer

def satCollection(cloudRate, initialDate, updatedDate, aoi):
    collection = ee.ImageCollection('COPERNICUS/S2_SR') \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloudRate)) \
        .filterDate(initialDate, updatedDate) \
        .filterBounds(aoi)
    
    def clipCollection(image):
        return image.clip(aoi).divide(10000)
    collection = collection.map(clipCollection)
    return collection

last_uploaded_centroid = None
def upload_files_proc(upload_files):
    global last_uploaded_centroid
    geometry_aoi_list = []

    for upload_file in upload_files:
        bytes_data = upload_file.read()
        geojson_data = json.loads(bytes_data)

        if 'features' in geojson_data and isinstance(geojson_data['features'], list):
            features = geojson_data['features']
        elif 'geometries' in geojson_data and isinstance(geojson_data['geometries'], list):
            features = [{'geometry': geo} for geo in geojson_data['geometries']]
        else:
            continue

        for feature in features:
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coordinates = feature['geometry']['coordinates']
                geometry = ee.Geometry.Polygon(coordinates) if feature['geometry']['type'] == 'Polygon' else ee.Geometry.MultiPolygon(coordinates)
                geometry_aoi_list.append(geometry)
                last_uploaded_centroid = geometry.centroid(maxError=1).getInfo()['coordinates']

    if geometry_aoi_list:
        geometry_aoi = ee.Geometry.MultiPolygon(geometry_aoi_list)
    else:
        geometry_aoi = ee.Geometry.Point([27.98, 36.13])

    return geometry_aoi

def date_input_proc(input_date, time_range):
    end_date = input_date
    start_date = input_date - timedelta(days=time_range)
    
    str_start_date = start_date.strftime('%Y-%m-%d')
    str_end_date = end_date.strftime('%Y-%m-%d')
    return str_start_date, str_end_date

def main():
    with st.sidebar:
        st.title("Aplicativo Visualizador NDVI")
        st.image("https://cdn-icons-png.flaticon.com/512/2516/2516640.png", width=90)
        st.subheader("Navegação:")
        st.markdown("""
            - [Mapa NDVI](#visualizador-ndvi)
            - [Legenda do Mapa](#map-legend)
            - [Fluxo de trabalho do processo](#process-workflow-aoi-date-range-and-classification)
            - [Interpretando os Resultados](#interpreting-the-results)
            - [Índice Ambiental](#using-an-environmental-index-ndvi)
            - [Dados](#data-sentinel-2-imagery-and-l2a-product)
            - [Contribuição](#contribute-to-the-app)
            - [Sobre](#about)
            - [Crédito](#credit)
        """)
        st.subheader("Contato:")
        st.markdown("""
            [![Instagram](https://cdn-icons-png.flaticon.com/512/2111/2111463.png)](https://www.instagram.com/marceloclaro.geomaker/)
            Projeto Geomaker + IA
            - Professor: Marcelo Claro.
        """)

    with st.container():
        st.title("Visualizador NDVI")
        st.markdown("**Monitore a saúde da vegetação visualizando e comparando valores de NDVI ao longo do tempo e da localização com imagens de satélite Sentinel-2 em tempo real!**")

    with st.form("input_form"):
        c1, c2 = st.columns([3, 1])
        
        with st.container():
            with c2:
                st.info("Cobertura de Nuvens 🌥️")
                cloud_pixel_percentage = st.slider(label="taxa de pixel de nuvem", min_value=5, max_value=100, step=5, value=85 , label_visibility="collapsed")
                st.info("Carregar arquivo de Área de Interesse:")
                upload_files = st.file_uploader("Crie um arquivo GeoJSON em: [geojson.io](https://geojson.io/)", accept_multiple_files=True)
                geometry_aoi = upload_files_proc(upload_files)
                st.info("Paletas de Cores Personalizadas")
                accessibility = st.selectbox("Acessibilidade: Paletas amigáveis para daltônicos", ["Normal", "Deuteranopia", "Protanopia", "Tritanopia", "Acromatopsia"])
                default_ndvi_palette = ["#ffffe5", "#f7fcb9", "#78c679", "#41ab5d", "#238443", "#005a32"]
                default_reclassified_ndvi_palette = ["#a50026","#ed5e3d","#f9f7ae","#f4ff78","#9ed569","#229b51","#006837"]
                ndvi_palette = default_ndvi_palette.copy()
                reclassified_ndvi_palette = default_reclassified_ndvi_palette.copy()

                if accessibility == "Deuteranopia":
                    ndvi_palette = ["#fffaa1","#f4ef8e","#9a5d67","#573f73","#372851","#191135"]
                    reclassified_ndvi_palette = ["#95a600","#92ed3e","#affac5","#78ffb0","#69d6c6","#22459c","#000e69"]
                elif accessibility == "Protanopia":
                    ndvi_palette = ["#a6f697","#7def75","#2dcebb","#1597ab","#0c677e","#002c47"]
                    reclassified_ndvi_palette = ["#95a600","#92ed3e","#affac5","#78ffb0","#69d6c6","#22459c","#000e69"]
                elif accessibility == "Tritanopia":
                    ndvi_palette = ["#cdffd7","#a1fbb6","#6cb5c6","#3a77a5","#205080","#001752"]
                    reclassified_ndvi_palette = ["#ed4700","#ed8a00","#e1fabe","#99ff94","#87bede","#2e40cf","#0600bc"]
                elif accessibility == "Acromatopsia":
                    ndvi_palette = ["#407de0", "#2763da", "#394388", "#272c66", "#16194f", "#010034"]
                    reclassified_ndvi_palette = ["#004f3d", "#338796", "#66a4f5", "#3683ff", "#3d50ca", "#421c7f", "#290058"]

        with st.container():
            with c1:
                col1, col2 = st.columns(2)
                today = datetime.today()
                delay = today - timedelta(days=2)
                col1.warning("Data Inicial NDVI 📅")
                initial_date = col1.date_input("inicial", value=delay, label_visibility="collapsed")
                col2.success("Data Atualizada NDVI 📅")
                updated_date = col2.date_input("atualizada", value=delay, label_visibility="collapsed")
                time_range = 7
                str_initial_start_date, str_initial_end_date = date_input_proc(initial_date, time_range)
                str_updated_start_date, str_updated_end_date = date_input_proc(updated_date, time_range)

            global last_uploaded_centroid

            if last_uploaded_centroid is not None:
                latitude = last_uploaded_centroid[1]
                longitude = last_uploaded_centroid[0]
                m = folium.Map(location=[latitude, longitude], tiles=None, zoom_start=12, control_scale=True)
            else:
                m = folium.Map(location=[36.45, 10.85], tiles=None, zoom_start=4, control_scale=True)

            b0 = folium.TileLayer('Open Street Map', name="Open Street Map")
            b0.add_to(m)
            b1 = folium.TileLayer('cartodbdark_matter', name='Dark Basemap')
            b1.add_to(m)

            initial_collection = satCollection(cloud_pixel_percentage, str_initial_start_date, str_initial_end_date, geometry_aoi)
            updated_collection = satCollection(cloud_pixel_percentage, str_updated_start_date, str_updated_end_date, geometry_aoi)
            initial_sat_imagery = initial_collection.median()
            updated_sat_imagery = updated_collection.median()
            initial_tci_image = initial_sat_imagery
            updated_tci_image = updated_sat_imagery

            tci_params = {
                'bands': ['B4', 'B3', 'B2'],
                'min': 0,
                'max': 1,
                'gamma': 1
            }

            def getNDVI(collection):
                return collection.normalizedDifference(['B8', 'B4'])

            initial_ndvi = getNDVI(initial_sat_imagery)
            updated_ndvi = getNDVI(updated_sat_imagery)

            ndvi_params = {
                'min': 0,
                'max': 1,
                'palette': ndvi_palette
            }

            def satImageMask(sat_image):
                masked_image = sat_image.updateMask(sat_image.gte(0))
                return masked_image

            initial_ndvi = satImageMask(initial_ndvi)
            updated_ndvi = satImageMask(updated_ndvi)

            def classify_ndvi(masked_image):
                ndvi_classified = ee.Image(masked_image) \
                .where(masked_image.gte(0).And(masked_image.lt(0.15)), 1) \
                .where(masked_image.gte(0.15).And(masked_image.lt(0.25)), 2) \
                .where(masked_image.gte(0.25).And(masked_image.lt(0.35)), 3) \
                .where(masked_image.gte(0.35).And(masked_image.lt(0.45)), 4) \
                .where(masked_image.gte(0.45).And(masked_image.lt(0.65)), 5) \
                .where(masked_image.gte(0.65).And(masked_image.lt(0.75)), 6) \
                .where(masked_image.gte(0.75), 7)
                return ndvi_classified

            initial_ndvi_classified = classify_ndvi(initial_ndvi)
            updated_ndvi_classified = classify_ndvi(updated_ndvi)

            ndvi_classified_params = {
                'min': 1,
                'max': 7,
                'palette': reclassified_ndvi_palette
            }

            if initial_date == updated_date:
                m.add_ee_layer(updated_tci_image, tci_params, 'Imagens de Satélite')
                m.add_ee_layer(updated_ndvi, ndvi_params, 'NDVI Bruto')
                m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, 'NDVI Reclassificado')
            else:
                m.add_ee_layer(initial_tci_image, tci_params, f'Imagens de Satélite Iniciais: {initial_date}')
                m.add_ee_layer(updated_tci_image, tci_params, f'Imagens de Satélite Atualizadas: {updated_date}')
                m.add_ee_layer(initial_ndvi, ndvi_params, f'NDVI Bruto Inicial: {initial_date}')
                m.add_ee_layer(updated_ndvi, ndvi_params, f'NDVI Bruto Atualizado: {updated_date}')
                m.add_ee_layer(initial_ndvi_classified, ndvi_classified_params, f'NDVI Reclassificado Inicial: {initial_date}')
                m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, f'NDVI Reclassificado Atualizado: {updated_date}')

            folium.LayerControl(collapsed=True).add_to(m)

        submitted = c2.form_submit_button("Gerar mapa")
        if submitted:
            with c1:
                folium_static(m)
        else:
            with c1:
                folium_static(m)

    with st.container():
        st.subheader("Legenda do Mapa:")
        col3, col4, col5 = st.columns([1,2,1])

        with col3:            
            ndvi_legend_html = """
                <div class="ndvilegend">
                    <h5>NDVI Bruto</h5>
                    <div style="display: flex; flex-direction: row; align-items: flex-start; gap: 1rem; width: 100%;">
                        <div style="width: 30px; height: 200px; background: linear-gradient({0},{1},{2},{3},{4},{5});"></div>
                        <div style="display: flex; flex-direction: column; justify-content: space-between; height: 200px;">
                            <span>-1</span>
                            <span style="align-self: flex-end;">1</span>
                        </div>
                    </div>
                </div>
            """.format(*ndvi_palette)

            st.markdown(ndvi_legend_html, unsafe_allow_html=True)

        with col4:            
            reclassified_ndvi_legend_html = """
                <div class="reclassifiedndvi">
                    <h5>Classes de NDVI</h5>
                    <ul style="list-style-type: none; padding: 0;">
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {0};">&#9632;</span> Vegetação Ausente. (Água/Nuvens/Construído/Rochas/Areias..)</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {1};">&#9632;</span> Solo Exposto.</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {2};">&#9632;</span> Vegetação Baixa.</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {3};">&#9632;</span> Vegetação Leve.</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {4};">&#9632;</span> Vegetação Moderada.</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {5};">&#9632;</span> Vegetação Forte.</li>
                        <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {6};">&#9632;</span> Vegetação Densa.</li>
                    </ul>
                </div>
            """.format(*reclassified_ndvi_palette)

            st.markdown(reclassified_ndvi_legend_html, unsafe_allow_html=True)

    with st.container():
        st.subheader("Informações")

        st.write("#### Fluxo de trabalho do processo: AOI, Intervalo de Datas e Classificação")
        st.write("Este aplicativo fornece uma interface simples para explorar as mudanças do NDVI ao longo do tempo para uma Área de Interesse (AOI) especificada. Veja como funciona:")

        st.write("1. **Carregar arquivo GeoJSON AOI:** Comece carregando um arquivo GeoJSON que delineia sua Área de Interesse. Isso define a região onde a análise de NDVI será realizada. Você pode criar qualquer área de interesse em forma de polígono em [geojson.io](https://geojson.io).")
        st.write("2. **Selecionar Intervalo de Datas:** Escolha uma data, este input faz com que o aplicativo reúna imagens de um **período de 7 dias** até essa data. Essas imagens se fundem em um mosaico que destaca os padrões de vegetação, minimizando interrupções como nuvens.")
        st.write("3. **Selecionar Taxa de Cobertura de Nuvens:** Escolha um valor para a cobertura de nuvens, este input faz com que o aplicativo reúna imagens com o valor relevante de nuvens cobrindo as imagens. Um valor mais alto reunirá mais imagens, mas pode ser de baixa qualidade, um valor mais baixo de cobertura de nuvens reúne imagens mais claras, mas pode ter menos imagens na coleção.")
        st.write("4. **Coleta e Processamento de Imagens:** Uma vez estabelecido o intervalo de datas, o aplicativo coleta imagens de satélite que abrangem esse período. Essas imagens são então recortadas para sua Área de Interesse (AOI) escolhida e passam por processamento para derivar valores brutos de NDVI usando cálculos de comprimento de onda. Esse método garante que o mapa de NDVI resultante reflita com precisão o estado da vegetação dentro de sua região específica de interesse.")
        st.write("5. **Classificação do NDVI:** Os resultados brutos do NDVI são classificados em classes distintas de vegetação. Essa classificação fornece uma visualização simplificada da densidade da vegetação, auxiliando na interpretação.")
        st.write("6. **Visualização do Mapa:** Os resultados são exibidos em um mapa interativo, permitindo que você explore os padrões e mudanças do NDVI dentro de sua AOI.")

        st.write("Este aplicativo foi projetado para fornecer uma ferramenta acessível para usuários técnicos e não técnicos explorarem e interpretarem mudanças na saúde e densidade da vegetação.")
        st.write("Lembre-se de que, embora o mapa de NDVI seja uma ferramenta valiosa, sua interpretação requer a consideração de vários fatores. Aproveite para explorar o mundo da saúde e densidade da vegetação!")

        st.write("#### Interpretando os Resultados")
        st.write("Ao explorar o mapa NDVI, lembre-se de que:")

        st.write("- Nuvens, condições atmosféricas e corpos d'água podem afetar a aparência do mapa.")
        st.write("- Os sensores de satélite têm limitações para distinguir tipos de superfícies, levando a variações de cor.")
        st.write("- Os valores de NDVI variam com as estações, estágios de crescimento e mudanças na cobertura do solo.")
        st.write("- O mapa fornece insights visuais em vez de representações precisas.")

        st.write("Compreender esses fatores ajudará você a interpretar os resultados de forma mais eficaz. Este aplicativo tem como objetivo fornecer uma ajuda visual informativa para a análise da vegetação.")

        st.write("#### Usando um Índice Ambiental - NDVI:")
        st.write("O [Índice de Vegetação por Diferença Normalizada (NDVI)](https://eos.com/make-an-analysis/ndvi/) é um índice ambiental essencial que fornece insights sobre a saúde e densidade da vegetação. É amplamente utilizado em sensoriamento remoto e análise geoespacial para monitorar mudanças na cobertura do solo, crescimento da vegetação e condições ambientais.")

        st.write("O NDVI é calculado usando imagens de satélite que capturam comprimentos de onda tanto no Infravermelho Próximo **(NIR)** quanto no Vermelho **(R)**. A fórmula é:")
        st.latex(r'''
        \text{NDVI} = \frac{\text{NIR} - \text{R}}{\text{NIR} + \text{R}}
        ''')

        st.write("Os valores de NDVI variam de **[-1** a **1]**, com valores mais altos indicando vegetação mais densa e saudável. Valores mais baixos representam superfícies não vegetadas, como corpos d'água, solo exposto ou áreas construídas.")

        st.write("#### Dados: Imagens Sentinel-2 e Produto L2A")
        st.write("Este aplicativo utiliza **imagens de Reflectância de Superfície corrigida atmosfericamente do Sentinel-2 Nível-2A**. A [constelação de satélites Sentinel-2](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/applications) consiste em satélites gêmeos (Sentinel-2A e Sentinel-2B) que capturam imagens multiespectrais de alta resolução da superfície da Terra.")

        st.write("Os [produtos Nível-2A](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/product-types/level-2a) passaram por correção atmosférica, aumentando a precisão dos valores de reflectância da superfície. Essas imagens são adequadas para várias análises de cobertura do solo e vegetação, incluindo cálculos de NDVI.")

    st.header("Contribua para o Aplicativo")
    con1, con2 = st.columns(2)
    con1.image("https://www.pixenli.com/image/SoL3iZMG")
    con2.markdown("""
        Contribuições são bem-vindas da comunidade para ajudar a melhorar este aplicativo! Se você está interessado em corrigir bugs 🐞, implementar um novo recurso 🌟 ou melhorar a experiência do usuário 🪄, suas contribuições são valiosas.

        O projeto está listado sob o rótulo **Hacktoberfest** para aqueles entusiastas do [Hacktoberfest](https://hacktoberfest.com/)! Já que a recompensa por contribuir com 4 PRs é ter uma árvore plantada em seu nome através da [TreeNation](https://tree-nation.com/), vejo que isso se encaixa no tema deste projeto.
    """)

    st.markdown("""
        #### Maneiras de Contribuir

        - **Relatar Problemas**: Se você encontrar algum bug, problema ou comportamento inesperado, por favor, relate-os no [Rastreador de Problemas do GitHub](https://github.com/IndigoWizard/NDVI-Viewer/issues).

        - **Sugerir Melhorias**: Tem uma ideia para melhorar o aplicativo? Compartilhe suas sugestões no [Rastreador de Problemas do GitHub](https://github.com/IndigoWizard/NDVI-Viewer/issues).

        - **Contribuições de Código**: Se você se sente confortável com a codificação, pode contribuir enviando pull requests contra a branch `dev` do [repositório GitHub do Projeto](https://github.com/IndigoWizard/NDVI-Viewer/).
    """)

    st.subheader("Sobre:")
    st.markdown("Este projeto foi desenvolvido inicialmente por [IndigoWizard](https://github.com/IndigoWizard) e [Emmarie-Ahtunan](https://github.com/Emmarie-Ahtunan) como uma submissão para o **Desafio de Dados Ambientais** do [Global Hack Week: Data](https://ghw.mlh.io/) pela [Major League Hacking](https://mlh.io/).<br> Eu continuei desenvolvendo o projeto base para torná-lo um aplicativo completo. Confira o repositório GitHub do projeto aqui: [IndigoWizard/NDVI-Viewer](https://github.com/IndigoWizard/NDVI-Viewer)", unsafe_allow_html=True)
    st.image("https://www.pixenli.com/image/Hn1xkB-6")

    st.subheader("Crédito:")
    st.markdown("""O aplicativo foi desenvolvido por [IndigoWizard](https://github.com/IndigoWizard) usando; [Streamlit](https://streamlit.io/), [Google Earth Engine](https://github.com/google/earthengine-api) API Python, [geemap](https://github.com/gee-community/geemap), [Folium](https://github.com/python-visualization/folium). Ícones de agricultura criados por <a href="https://www.flaticon.com/free-icons/agriculture" title="ícones de agricultura">dreamicons - Flaticon</a>""", unsafe_allow_html=True)

    st.markdown(
    """
    <style>
        /*Map iframe*/
        iframe {
            width: 100%;
        }
        .css-1o9kxky.e1f1d6gn0 {
            border: 2px solid #ffffff4d;
            border-radius: 4px;
            padding: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
 

if __name__ == "__main__":
    main()
