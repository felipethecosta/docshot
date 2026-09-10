---
titulo: Clientes
subtitulo: Manual de Operação
versao: 1.0.0
data: Janeiro/2026
---

# OBJETIVO

Descrever a operação do módulo de Clientes: cadastro, consulta, edição e o
histórico de cada cliente.

# ESCOPO

Este manual aplica-se à equipe que opera o sistema no dia a dia.

# CADASTRO

![Lista de clientes](clientes-01-lista.png)

A lista abre com todos os clientes da conta ativa. A busca filtra por nome e por
documento.

- **Novo cliente** abre o formulário de cadastro
- O documento é validado no envio e não pode se repetir

![Formulário de cadastro](clientes-02-cadastro.png)

| Campo | Obrigatório | Observação |
| ----- | ----------- | ---------- |
| Nome | Sim | Como aparece nas listas |
| Documento | Sim | Único por conta |
| Responsável | Não | Quem atende esse cliente |

# AÇÕES DA LINHA

![Menu de ações](clientes-04-acoes-da-linha.png)

O menu de cada linha reúne as ações que não cabem na tabela: editar, arquivar e
exportar.

{{include: tecnico}}
