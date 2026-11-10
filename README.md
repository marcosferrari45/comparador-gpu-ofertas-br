# Comparador automático de ofertas de GPU

## Uso local

1. Edite `fontes.json`, troque as URLs de exemplo por páginas reais de produtos e marque `ativo` como `true`.
2. Respeite os termos de uso e o `robots.txt` de cada loja. Prefira APIs ou feeds oficiais quando existirem.
3. Rode:

```bash
python -m pip install -r requirements.txt
python atualizar_precos.py
python -m http.server 8000
```

Abra `http://localhost:8000`. Abrir o HTML diretamente por `file://` pode impedir o `fetch` de `precos.json`.

## GitHub Actions + Pages

1. Envie todos os arquivos para a raiz de um repositório no GitHub.
2. Em **Settings > Pages > Source**, escolha **GitHub Actions**.
3. Edite `fontes.json`, ative as fontes e execute manualmente o workflow uma vez em **Actions**.
4. O workflow roda diariamente às 10:17 UTC, atualiza `precos.json`, salva a alteração e publica a página.

## Limitações

O robô procura dados estruturados JSON-LD do tipo `Product`/`Offer`. Sites com proteção antibot, conteúdo renderizado apenas por JavaScript ou marcação diferente podem falhar. Nesses casos, use uma API/feed oficial ou crie um adaptador específico. Erros ficam registrados em `precos.json`, e o último preço válido é preservado quando possível.
