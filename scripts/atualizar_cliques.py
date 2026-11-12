"""Busca as visitas do site no Cloudflare Web Analytics e salva em estatisticas/cliques.json.

Precisa dos segredos CF_API_TOKEN (permissão "Account Analytics: Read") e CF_ACCOUNT_ID.
Guarda o histórico dia a dia: os dias antigos ficam no arquivo mesmo depois que a
Cloudflare deixa de mostrá-los.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

ARQ = os.path.join(os.path.dirname(__file__), "..", "estatisticas", "cliques.json")
API = "https://api.cloudflare.com/client/v4/graphql"
DIAS = 30  # janela consultada a cada execução

# Cada consulta agrupa por dia + uma dimensão
DIMENSOES = {
    "origem": "refererHost",
    "pagina": "requestPath",
    "pais": "countryName",
    "aparelho": "deviceType",
}


def consultar(token, conta, dim, inicio, fim):
    q = """query($conta: string!, $ini: Date!, $fim: Date!) {
      viewer { accounts(filter: {accountTag: $conta}) {
        rumPageloadEventsAdaptiveGroups(limit: 5000,
          filter: {date_geq: $ini, date_leq: $fim}) {
          count
          sum { visits }
          dimensions { date requestHost %s }
        }
      } }
    }""" % dim
    corpo = json.dumps({"query": q, "variables": {"conta": conta, "ini": inicio, "fim": fim}}).encode()
    req = urllib.request.Request(API, data=corpo, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    if res.get("errors"):
        raise RuntimeError(json.dumps(res["errors"], ensure_ascii=False))
    contas = res["data"]["viewer"]["accounts"]
    return contas[0]["rumPageloadEventsAdaptiveGroups"] if contas else []


def main():
    token, conta = os.environ.get("CF_API_TOKEN"), os.environ.get("CF_ACCOUNT_ID")
    if not token or not conta:
        print("Faltam os segredos CF_API_TOKEN e/ou CF_ACCOUNT_ID — nada a fazer.")
        return 0

    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    inicio = (hoje - timedelta(days=DIAS)).isoformat()
    fim = hoje.isoformat()

    try:
        with open(ARQ, encoding="utf-8") as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dados = {}
    dias = dados.get("dias", {})

    novos, falhas = {}, []
    for chave, dim in DIMENSOES.items():
        try:
            linhas = consultar(token, conta, dim, inicio, fim)
        except Exception as e:  # uma dimensão com erro não derruba as outras
            falhas.append(f"{chave}: {e}")
            continue
        for l in linhas:
            d = l["dimensions"]
            host = (d.get("requestHost") or "").lower()
            if host and "sitiopedradosventos" not in host and "github.io" not in host:
                continue  # ignora outros sites da conta
            dia = novos.setdefault(d["date"], {"visitas": 0, "paginas_vistas": 0})
            nome = d.get(dim) or ("direto" if chave == "origem" else "?")
            grupo = dia.setdefault(chave, {})
            grupo[nome] = grupo.get(nome, 0) + l["sum"]["visits"]
            if chave == "pagina":  # totais do dia saem da consulta por página
                dia["visitas"] += l["sum"]["visits"]
                dia["paginas_vistas"] += l["count"]

    for f in falhas:
        print("ERRO", f, file=sys.stderr)
    if not novos and falhas:
        return 1

    # substitui os dias da janela consultada, mantém o histórico mais antigo
    for d in list(dias):
        if inicio <= d <= fim:
            dias.pop(d)
    dias.update(novos)

    dados = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "dias": dict(sorted(dias.items())),
    }
    os.makedirs(os.path.dirname(ARQ), exist_ok=True)
    with open(ARQ, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    total = sum(v["visitas"] for v in novos.values())
    print(f"OK: {len(novos)} dias, {total} visitas nos últimos {DIAS} dias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
