# Sítio Pedra dos Ventos · Reservas

Página de disponibilidade e reservas do Sítio Pedra dos Ventos (Domingos Martins, ES).

- **Site:** https://sitiopedradosventos.com.br/ (`index.html`, fotos em `img/`)
- **Calendário de reservas:** https://sitiopedradosventos.com.br/reservas/ (`reservas/index.html`)
- O hóspede escolhe entrada e saída, vê o valor na hora e reserva pelo WhatsApp.

## Como funciona

| Arquivo | Para que serve |
|---|---|
| `index.html` | O site do sítio |
| `reservas/index.html` | O calendário de reservas (preços e regras) |
| `img/` | Fotos do site: `nome.jpg` na resolução original e `nome-p.jpg` menor, para a grade |
| `data.json` | Datas ocupadas e feriados. **Gerado sozinho**, não editar à mão |
| `config.json` | Bloqueios manuais de datas e feriados extras |
| `scripts/atualizar_agenda.py` | Lê a agenda e gera o `data.json` |
| `.github/workflows/agenda.yml` | Roda a atualização a cada hora e publica a página |

A agenda é lida pelo link iCal secreto guardado no segredo **ICAL_URL**
(Settings → Secrets and variables → Actions). O link nunca fica nos arquivos,
e a página mostra só as datas, sem nomes de hóspedes.

Para bloquear uma data sem reserva na agenda, inclua em `config.json`
(`"bloqueios_manuais": ["2027-01-14"]`).
