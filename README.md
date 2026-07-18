# Janelas da Barra — Porto de Lisboa

Painel informal de janelas de manobra: cruza as chegadas/partidas da APL com
previsão de swell, vento e nível do mar, e classifica cada hora como
verde / âmbar / vermelho segundo regras editáveis em `regras.toml`.

> ⚠ **Ferramenta informativa.** Não substitui JUP, VTS-Lisboa, Capitania,
> tabelas do Instituto Hidrográfico nem o juízo profissional do piloto.
> Os limiares marcados PLACEHOLDER estão por validar.

## Correr no PC

Basta Python 3.11+ — sem dependências externas:

```bash
python janelas_barra.py
```

Abre o `index.html` gerado. Opções: `--sem-apl` (só meteo-mar, teste rápido),
`--horas 96` (horizonte alargado).

## Publicar para o telemóvel (GitHub Pages, grátis)

1. Criar um repositório no GitHub e enviar esta pasta completa.
2. No repositório: **Settings → Pages → Source: GitHub Actions**.
3. Separador **Actions** → workflow "Atualizar Janelas da Barra" →
   **Run workflow** (primeira execução manual).
4. O painel fica em `https://<utilizador>.github.io/<repositório>/` e
   atualiza-se sozinho a cada 30 minutos. No Android/iPhone: abrir o link →
   menu do browser → **Adicionar ao ecrã principal**.

No painel, toca numa hora da timeline para veres os motivos e valores
(swell, nível, vento); a hora atual aparece contornada a magenta.

## Afinar as regras

Tudo em `regras.toml` — cada limiar tem um campo `fonte`. Os valores
PLACEHOLDER aparecem a magenta no painel até serem validados por quem
conhece a barra. Editar o número **e** a fonte.

## Documentação técnica

Ver `CLAUDE.md` (arquitetura, convenções, dívidas conhecidas e roadmap).
