# Comparador de ofertas de GPU

A página do GitHub Pages lista as 48 GPUs de desktop em um único catálogo. Selecione 4K, 1440p ou 1080p para recalcular o custo por FPS. O destaque considera a meta de FPS e o teto de preço. A seção **Minhas ofertas manuais** mantém os preços cadastrados neste navegador.

- **Desempenho** — média de FPS nativos da tabela de rasterização do Tom’s Hardware de 2026, em catalogo.json.
- **Preços** — menor valor à vista publicado na tabela brasileira do [Hardware Barato](https://www.hardwarebarato.com/produtos/placas-de-video), conforme a versão da GPU e a VRAM. A página identifica a origem e abre a oferta na fonte.
- **Atualização** — o workflow Atualizar preços e publicar roda diariamente às 10h17 UTC (07h17 em Brasília) e também pode ser iniciado manualmente. Ele gera o precos.json deste repositório e publica a página.

A lista inclui placas sem cotação na fonte. Falhas de consulta são registradas no precos.json e mostradas na página. A coleta usa dados públicos, respeita o robots.txt e não tenta contornar bloqueios. Os preços publicados pela fonte variam conforme disponibilidade e condições da loja.

## Rodar localmente

    python -m pip install -r requirements.txt
    python atualizar_precos.py
    python -m http.server 8000

Abra http://localhost:8000. Para incluir uma fonte de produto, edite fontes.json com uma URL HTTPS pública do anúncio, o nome exato do modelo e a loja. O leitor de páginas individuais exige oferta em BRL e disponibilidade em JSON-LD.
