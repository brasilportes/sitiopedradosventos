"""Lê a agenda do sítio (link iCal secreto) e gera data.json para a página de reservas.

Roda no GitHub Actions. O link fica no segredo ICAL_URL do repositório e nunca
é gravado em arquivo. Só datas ocupadas vão para data.json — nada de nomes.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("America/Sao_Paulo")


def carregar_config():
    p = RAIZ / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def pascoa(ano):
    a = ano % 19; b, c = divmod(ano, 100); d, e = divmod(b, 4)
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(ano, mes, dia)


def feriados(ano):
    fixos = {
        "01-01": "Ano Novo", "04-21": "Tiradentes", "05-01": "Dia do Trabalho",
        "09-07": "Independência", "10-12": "N. Sra. Aparecida", "11-02": "Finados",
        "11-15": "Proclamação da República", "11-20": "Consciência Negra",
        "12-24": "Véspera de Natal", "12-25": "Natal", "12-31": "Véspera de Ano Novo",
    }
    r = {f"{ano}-{k}": v for k, v in fixos.items()}
    p = pascoa(ano)
    moveis = {
        -51: "Carnaval", -50: "Carnaval", -49: "Carnaval", -48: "Carnaval", -47: "Carnaval",
        -46: "Quarta de Cinzas", -2: "Paixão de Cristo", -1: "Semana Santa", 0: "Páscoa",
        8: "N. Sra. da Penha (ES)", 60: "Corpus Christi",
    }
    for delta, nome in moveis.items():
        r[(p + dt.timedelta(days=delta)).isoformat()] = nome
    return r


def desdobrar(texto):
    linhas = []
    for linha in texto.splitlines():
        if linha[:1] in (" ", "\t") and linhas:
            linhas[-1] += linha[1:]
        else:
            linhas.append(linha)
    return linhas


def ler_valor(linha):
    """'DTSTART;TZID=America/Sao_Paulo:20261103T150000' -> (params, valor)"""
    chave, _, valor = linha.partition(":")
    params = {}
    for parte in chave.split(";")[1:]:
        k, _, v = parte.partition("=")
        params[k.upper()] = v
    return params, valor.strip()


def para_local(params, valor):
    """Devolve (data_local, hora_local_ou_None)."""
    if params.get("VALUE") == "DATE" or len(valor) == 8:
        return dt.date(int(valor[:4]), int(valor[4:6]), int(valor[6:8])), None
    base = dt.datetime.strptime(valor[:15], "%Y%m%dT%H%M%S")
    if valor.endswith("Z"):
        base = base.replace(tzinfo=dt.timezone.utc)
    else:
        base = base.replace(tzinfo=ZoneInfo(params.get("TZID", "America/Sao_Paulo")))
    loc = base.astimezone(TZ)
    return loc.date(), loc.time()


def dias_ocupados(ics):
    ocupados = set()
    ev = None
    for linha in desdobrar(ics):
        if linha == "BEGIN:VEVENT":
            ev = {}
        elif linha == "END:VEVENT" and ev is not None:
            if ev.get("status") != "CANCELLED" and "ini" in ev:
                ini, hini = ev["ini"]
                fim, hfim = ev.get("fim", (ini + dt.timedelta(days=1), None) if hini is None else ev["ini"])
                if hini is None:  # dia inteiro: fim é exclusivo
                    ultimo = fim - dt.timedelta(days=1)
                else:  # com horário: saída até meio-dia libera o dia da saída
                    ultimo = fim - dt.timedelta(days=1) if (hfim is not None and fim > ini and hfim <= dt.time(12, 0)) else fim
                d = ini
                while d <= ultimo:
                    ocupados.add(d)
                    d += dt.timedelta(days=1)
            ev = None
        elif ev is not None:
            nome = linha.split(":", 1)[0].split(";", 1)[0].upper()
            if nome == "DTSTART":
                ev["ini"] = para_local(*ler_valor(linha))
            elif nome == "DTEND":
                ev["fim"] = para_local(*ler_valor(linha))
            elif nome == "STATUS":
                ev["status"] = ler_valor(linha)[1].upper()
    return ocupados


def main():
    cfg = carregar_config()
    hoje = dt.datetime.now(TZ).date()
    destino = RAIZ / "data.json"
    atual = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}

    url = os.environ.get("ICAL_URL", "").strip()
    if url:
        req = urllib.request.Request(url, headers={"User-Agent": "agenda-pedradosventos"})
        with urllib.request.urlopen(req, timeout=60) as r:
            ics = r.read().decode("utf-8", errors="replace")
        if "BEGIN:VCALENDAR" not in ics:
            sys.exit("O link ICAL_URL não devolveu uma agenda válida.")
        ocupados = dias_ocupados(ics)
    else:
        print("Aviso: segredo ICAL_URL não configurado; mantendo as datas atuais.")
        ocupados = {dt.date.fromisoformat(x) for x in atual.get("busy", [])}

    for x in cfg.get("bloqueios_manuais", []):
        ocupados.add(dt.date.fromisoformat(x))

    desde = hoje - dt.timedelta(days=int(cfg.get("manter_passado_dias", 7)))
    fim_ano = dt.date(hoje.year + 1, 12, 31)
    busy = sorted(d.isoformat() for d in ocupados if desde <= d <= fim_ano + dt.timedelta(days=7))

    hol = {}
    for ano in (hoje.year, hoje.year + 1):
        hol.update(feriados(ano))
    hol.update(cfg.get("feriados_extras", {}))

    dados = {
        "updated": hoje.isoformat(),
        "start": f"{hoje.year}-{hoje.month:02d}",
        "end": f"{hoje.year + 1}-12",
        "busy": busy,
        "holidays": dict(sorted(hol.items())),
    }
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(busy)} dias ocupados gravados (de {desde} até {fim_ano}).")


if __name__ == "__main__":
    main()
