
import sqlite3
import calendar

from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta

app = Flask(__name__)

BANCO = "academico.db"


def conectar_banco():
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabela():
    with conectar_banco() as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS atividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                disciplina TEXT NOT NULL,
                tipo TEXT NOT NULL,
                prazo TEXT NOT NULL,
                prioridade TEXT NOT NULL,
                concluida INTEGER NOT NULL DEFAULT 0
            )
        """)


    # Adiciona os campos de nota caso ainda não existam.
    with conectar_banco() as conexao:
        colunas = [
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(atividades)"
            ).fetchall()
        ]

        if "nota_obtida" not in colunas:
            conexao.execute("""
                ALTER TABLE atividades
                ADD COLUMN nota_obtida REAL
            """)

        if "nota_maxima" not in colunas:
            conexao.execute("""
                ALTER TABLE atividades
                ADD COLUMN nota_maxima REAL
            """)



@app.route("/", methods=["GET", "POST"])
def inicio():
    if request.method == "POST":
        titulo = request.form["titulo"].strip()
        disciplina = request.form["disciplina"].strip()
        tipo = request.form["tipo"]
        prazo = request.form["prazo"]
        prioridade = request.form["prioridade"]

        if titulo and disciplina and tipo and prazo and prioridade:
            with conectar_banco() as conexao:
                conexao.execute("""
                    INSERT INTO atividades
                    (titulo, disciplina, tipo, prazo, prioridade)
                    VALUES (?, ?, ?, ?, ?)
                """, (titulo, disciplina, tipo, prazo, prioridade))

        return redirect(url_for("inicio"))

    situacao = request.args.get("situacao", "todas")
    disciplina_filtro = request.args.get("disciplina", "").strip()
    busca = request.args.get("busca", "").strip()
    ordenacao = request.args.get("ordenacao", "prazo")

    if situacao not in ("todas", "pendentes", "concluidas"):
        situacao = "todas"

    if ordenacao not in ("prazo", "prioridade", "recentes"):
        ordenacao = "prazo"

    consulta = "SELECT * FROM atividades WHERE 1=1"
    parametros = []

    if situacao == "pendentes":
        consulta += " AND concluida = 0"
    elif situacao == "concluidas":
        consulta += " AND concluida = 1"

    if disciplina_filtro:
        consulta += " AND disciplina = ?"
        parametros.append(disciplina_filtro)

    if busca:
        consulta += " AND (titulo LIKE ? OR disciplina LIKE ?)"
        termo_busca = f"%{busca}%"
        parametros.extend([termo_busca, termo_busca])

    if ordenacao == "prazo":
        consulta += " ORDER BY prazo ASC, id DESC"
    elif ordenacao == "prioridade":
        consulta += """
            ORDER BY
            CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                WHEN 'Baixa' THEN 3
                ELSE 4
            END,
            prazo ASC
        """
    else:
        consulta += " ORDER BY id DESC"

    with conectar_banco() as conexao:
        atividades = conexao.execute(
            consulta, parametros
        ).fetchall()

        disciplinas = conexao.execute("""
            SELECT DISTINCT disciplina
            FROM atividades
            ORDER BY disciplina ASC
        """).fetchall()


        desempenho_disciplinas = conexao.execute("""
            SELECT
                disciplina,
                COUNT(*) AS total,
                SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas,
                SUM(CASE WHEN concluida = 0 THEN 1 ELSE 0 END) AS pendentes
            FROM atividades
            GROUP BY disciplina
            ORDER BY disciplina ASC
        """).fetchall()

        desempenho_disciplinas = [
            dict(item) for item in desempenho_disciplinas
        ]

        total_atividades = conexao.execute(
            "SELECT COUNT(*) FROM atividades"
        ).fetchone()[0]

        pendentes = conexao.execute(
            "SELECT COUNT(*) FROM atividades WHERE concluida = 0"
        ).fetchone()[0]

        concluidas = conexao.execute(
            "SELECT COUNT(*) FROM atividades WHERE concluida = 1"
        ).fetchone()[0]

        atrasadas = conexao.execute("""
            SELECT COUNT(*) FROM atividades
            WHERE concluida = 0 AND prazo < ?
        """, (date.today().isoformat(),)).fetchone()[0]

        data_limite = (date.today() + timedelta(days=7)).isoformat()

        proximas = conexao.execute("""
            SELECT COUNT(*) FROM atividades
            WHERE concluida = 0
              AND prazo >= ?
              AND prazo <= ?
        """, (date.today().isoformat(), data_limite)).fetchone()[0]


        # Busca atividades pendentes com prazo nas próximas quatro semanas.
        hoje_carga = date.today()
        limite_carga = hoje_carga + timedelta(days=28)

        atividades_carga = conexao.execute("""
            SELECT prazo, COUNT(*) AS quantidade
            FROM atividades
            WHERE concluida = 0
              AND prazo >= ?
              AND prazo <= ?
            GROUP BY prazo
            ORDER BY prazo ASC
        """, (
            hoje_carga.isoformat(),
            limite_carga.isoformat()
        )).fetchall()


        # Busca atividades pendentes vencidas ou com prazo nos próximos 7 dias.
        hoje_iso = date.today().isoformat()
        limite_prioridades = (
            date.today() + timedelta(days=7)
        ).isoformat()

        prioridades = conexao.execute("""
            SELECT *
            FROM atividades
            WHERE concluida = 0
              AND prazo <= ?
            ORDER BY
                CASE
                    WHEN prazo < ? THEN 1
                    WHEN prazo = ? THEN 2
                    ELSE 3
                END,
                prazo ASC,
                CASE prioridade
                    WHEN 'Alta' THEN 1
                    WHEN 'Média' THEN 2
                    WHEN 'Baixa' THEN 3
                    ELSE 4
                END
        """, (
            limite_prioridades,
            hoje_iso,
            hoje_iso
        )).fetchall()


    atividades = [dict(atividade) for atividade in atividades]

    # Agrupa a quantidade de atividades por semana.
    carga_semanal = {}

    for item in atividades_carga:
        prazo = date.fromisoformat(item["prazo"])

        # A semana começa na segunda-feira.
        inicio_semana = prazo - timedelta(days=prazo.weekday())
        fim_semana = inicio_semana + timedelta(days=6)

        chave_semana = inicio_semana.isoformat()

        if chave_semana not in carga_semanal:
            carga_semanal[chave_semana] = {
                "inicio": inicio_semana.strftime("%d/%m"),
                "fim": fim_semana.strftime("%d/%m"),
                "quantidade": 0
            }

        carga_semanal[chave_semana]["quantidade"] += item["quantidade"]

    # Transforma os dados em uma lista para o template.
    carga_semanal = list(carga_semanal.values())

    # Classifica o volume de atividades de cada semana.
    for semana in carga_semanal:
        quantidade = semana["quantidade"]

        if quantidade >= 7:
            semana["classificacao"] = "Sobrecarga"
            semana["classe"] = "carga-alta"
            semana["mensagem"] = "Muitas atividades nesta semana"
        elif quantidade >= 4:
            semana["classificacao"] = "Atenção"
            semana["classe"] = "carga-moderada"
            semana["mensagem"] = "Organize seus estudos com antecedência"
        else:
            semana["classificacao"] = "Normal"
            semana["classe"] = "carga-baixa"
            semana["mensagem"] = "Carga de atividades administrável"


    prioridades = [dict(atividade) for atividade in prioridades]

    for atividade in prioridades:
        prazo = date.fromisoformat(atividade["prazo"])
        dias_restantes = (prazo - date.today()).days

        if dias_restantes < 0:
            atividade["mensagem_prioridade"] = (
                f"Atrasada há {abs(dias_restantes)} dia(s)"
            )
            atividade["classe_prioridade"] = "prioridade-atrasada"

        elif dias_restantes == 0:
            atividade["mensagem_prioridade"] = "Vence hoje"
            atividade["classe_prioridade"] = "prioridade-hoje"

        elif dias_restantes == 1:
            atividade["mensagem_prioridade"] = "Vence amanhã"
            atividade["classe_prioridade"] = "prioridade-proxima"

        else:
            atividade["mensagem_prioridade"] = (
                f"Vence em {dias_restantes} dias"
            )
            atividade["classe_prioridade"] = "prioridade-proxima"

    percentual_conclusao = (
        round((concluidas / total_atividades) * 100)
        if total_atividades > 0
        else 0
    )

    hoje = date.today()

    for atividade in atividades:
        prazo = date.fromisoformat(atividade["prazo"])
        dias_restantes = (prazo - hoje).days

        if atividade["concluida"]:
            atividade["status_prazo"] = "concluida"
            atividade["mensagem_prazo"] = "Atividade concluída"

        elif dias_restantes < 0:
            atividade["status_prazo"] = "atrasada"
            atividade["mensagem_prazo"] = (
                f"Atrasada há {abs(dias_restantes)} dia(s)"
            )

        elif dias_restantes <= 3:
            atividade["status_prazo"] = "proxima"

            if dias_restantes == 1:
                atividade["mensagem_prazo"] = "Prazo vence amanhã"
            else:
                atividade["mensagem_prazo"] = (
                    f"Prazo em {dias_restantes} dias"
                )

        else:
            atividade["status_prazo"] = "normal"
            atividade["mensagem_prazo"] = ""



    # Calcula o desempenho acadêmico por disciplina.
    with conectar_banco() as conexao:
        resultados_desempenho = conexao.execute("""
            SELECT
                disciplina,
                COUNT(*) AS total_notas,
                ROUND(
                    AVG(
                        (nota_obtida * 100.0) / nota_maxima
                    ),
                    1
                ) AS media_aproveitamento
            FROM atividades
            WHERE nota_obtida IS NOT NULL
              AND nota_maxima IS NOT NULL
              AND nota_maxima > 0
            GROUP BY disciplina
            ORDER BY media_aproveitamento DESC
        """).fetchall()

    desempenho_disciplinas = [
        dict(item) for item in resultados_desempenho
    ]

    print("DEBUG DESEMPENHO:", desempenho_disciplinas)

    # Calcula o desempenho acadêmico por disciplina.
    with conectar_banco() as conexao:
        resultados_carga = conexao.execute("""
            SELECT
                disciplina,
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN concluida = 0 THEN 1
                        ELSE 0
                    END
                ) AS pendentes
            FROM atividades
            GROUP BY disciplina
            ORDER BY pendentes DESC
        """).fetchall()

    carga_disciplinas = [
        dict(item) for item in resultados_carga
    ]

    return render_template(
        "index.html",
        atividades=atividades,
        carga_semanal=carga_semanal,
        carga_disciplinas=carga_disciplinas,
        prioridades=prioridades,
        total_atividades=total_atividades,
        pendentes=pendentes,
        concluidas=concluidas,
        percentual_conclusao=percentual_conclusao,
        atrasadas=atrasadas,
        proximas=proximas,
        disciplinas=disciplinas,
        desempenho_disciplinas=desempenho_disciplinas,
        situacao=situacao,
        disciplina_filtro=disciplina_filtro,
        busca=busca,
        ordenacao=ordenacao,
        prazo_predefinido=request.args.get("prazo", ""),        
        dados_grafico={
            "concluidas": concluidas,
            "pendentes": pendentes - atrasadas,
            "atrasadas": atrasadas
        }

    )


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    with conectar_banco() as conexao:
        atividade = conexao.execute(
            "SELECT * FROM atividades WHERE id = ?", (id,)
        ).fetchone()

        if atividade is None:
            return redirect(url_for("inicio"))

        if request.method == "POST":
            titulo = request.form["titulo"].strip()
            disciplina = request.form["disciplina"].strip()
            tipo = request.form["tipo"]
            prazo = request.form["prazo"]
            prioridade = request.form["prioridade"]

            if titulo and disciplina and tipo and prazo and prioridade:
                conexao.execute("""
                    UPDATE atividades
                    SET titulo = ?, disciplina = ?, tipo = ?,
                        prazo = ?, prioridade = ?
                    WHERE id = ?
                """, (
                    titulo, disciplina, tipo, prazo, prioridade, id
                ))

                return redirect(url_for("inicio"))

        # Busca os prazos de todas as atividades ainda pendentes.
        prazos_pendentes = conexao.execute("""
            SELECT prazo
            FROM atividades
            WHERE concluida = 0
        """).fetchall()

    return render_template("editar.html", atividade=atividade)

    # Calcula a carga acadêmica das próximas quatro semanas.
    hoje = date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    carga_semanal = []

    for numero_semana in range(4):
        inicio = inicio_semana + timedelta(weeks=numero_semana)
        fim = inicio + timedelta(days=6)

        quantidade = 0

        for registro in prazos_pendentes:
            prazo = date.fromisoformat(registro["prazo"])

            if hoje <= prazo and inicio <= prazo <= fim:
                quantidade += 1

        if quantidade >= 7:
            nivel = "alta"
            mensagem = "Semana sobrecarregada"
        elif quantidade >= 4:
            nivel = "moderada"
            mensagem = "Semana movimentada"
        else:
            nivel = "baixa"
            mensagem = "Semana tranquila"

        carga_semanal.append({
            "inicio": max(inicio, hoje).strftime("%d/%m/%Y"),
            "fim": fim.strftime("%d/%m/%Y"),
            "quantidade": quantidade,
            "nivel": nivel,
            "mensagem": mensagem
        })


@app.route("/concluir/<int:id>", methods=["POST"])
def concluir(id):
    with conectar_banco() as conexao:
        atividade = conexao.execute(
            "SELECT concluida FROM atividades WHERE id = ?",
            (id,)
        ).fetchone()

        if atividade:
            novo_status = 0 if atividade["concluida"] else 1

            conexao.execute(
                "UPDATE atividades SET concluida = ? WHERE id = ?",
                (novo_status, id)
            )

    return redirect(url_for("inicio"))


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    with conectar_banco() as conexao:
        conexao.execute(
            "DELETE FROM atividades WHERE id = ?",
            (id,)
        )

    return redirect(url_for("inicio"))


@app.route("/calendario")
def calendario_academico():
    hoje = date.today()

    ano = request.args.get("ano", hoje.year, type=int)
    mes = request.args.get("mes", hoje.month, type=int)

    # Impede meses inválidos e anos fora do intervalo esperado.
    if mes < 1 or mes > 12 or ano < 2000 or ano > 2100:
        ano = hoje.year
        mes = hoje.month

    # Organiza o calendário começando na segunda-feira.
    semanas = calendar.monthcalendar(ano, mes)

    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril",
        "Maio", "Junho", "Julho", "Agosto",
        "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    # Calcula o mês anterior.
    if mes == 1:
        ano_anterior = ano - 1
        mes_anterior = 12
    else:
        ano_anterior = ano
        mes_anterior = mes - 1

    # Calcula o próximo mês.
    if mes == 12:
        ano_proximo = ano + 1
        mes_proximo = 1
    else:
        ano_proximo = ano
        mes_proximo = mes + 1

    # Busca as atividades que vencem no mês selecionado.
    inicio_mes = f"{ano:04d}-{mes:02d}-01"

    if mes == 12:
        inicio_proximo_mes = f"{ano + 1:04d}-01-01"
    else:
        inicio_proximo_mes = f"{ano:04d}-{mes + 1:02d}-01"

    with conectar_banco() as conexao:
        atividades = conexao.execute("""
            SELECT *
            FROM atividades
            WHERE prazo >= ? AND prazo < ?
            ORDER BY prazo ASC, prioridade ASC
        """, (inicio_mes, inicio_proximo_mes)).fetchall()

    # Agrupa as atividades pelo dia do mês.
    atividades_por_dia = {}

    for registro in atividades:
        atividade = dict(registro)
        prazo = date.fromisoformat(atividade["prazo"])
        dia = prazo.day

        dias_restantes = (prazo - hoje).days

        if atividade["concluida"]:
            atividade["status_prazo"] = "concluida"
            atividade["mensagem_prazo"] = "Concluída"
        elif dias_restantes < 0:
            atividade["status_prazo"] = "atrasada"
            atividade["mensagem_prazo"] = "Atrasada"
        elif dias_restantes <= 3:
            atividade["status_prazo"] = "proxima"
            atividade["mensagem_prazo"] = "Prazo próximo"
        else:
            atividade["status_prazo"] = "normal"
            atividade["mensagem_prazo"] = ""

        atividades_por_dia.setdefault(dia, []).append(atividade)

    return render_template(
        "calendario.html",
        ano=ano,
        mes=mes,
        nome_mes=meses[mes - 1],
        semanas=semanas,
        atividades_por_dia=atividades_por_dia,
        ano_anterior=ano_anterior,
        mes_anterior=mes_anterior,
        ano_proximo=ano_proximo,
        mes_proximo=mes_proximo,
        hoje=hoje
    )


@app.route("/nota/<int:id>", methods=["POST"])
def registrar_nota(id):
    nota_obtida_texto = request.form.get("nota_obtida", "").strip()
    nota_maxima_texto = request.form.get("nota_maxima", "").strip()

    try:
        nota_obtida = float(nota_obtida_texto.replace(",", "."))
        nota_maxima = float(nota_maxima_texto.replace(",", "."))

        if nota_maxima <= 0:
            raise ValueError

        if nota_obtida < 0 or nota_obtida > nota_maxima:
            raise ValueError

    except ValueError:
        return (
            "Notas inválidas. Informe valores numéricos, "
            "com nota máxima maior que zero e nota obtida "
            "entre zero e a nota máxima.",
            400
        )

    with conectar_banco() as conexao:
        atividade = conexao.execute(
            "SELECT id FROM atividades WHERE id = ?",
            (id,)
        ).fetchone()

        if atividade is None:
            return "Atividade não encontrada.", 404

        conexao.execute("""
            UPDATE atividades
            SET nota_obtida = ?, nota_maxima = ?
            WHERE id = ?
        """, (nota_obtida, nota_maxima, id))

    return redirect(url_for("inicio"))


if __name__ == "__main__":
    criar_tabela()
    app.run(debug=True)

