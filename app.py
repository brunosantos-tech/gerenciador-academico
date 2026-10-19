
import sqlite3
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


    atividades = [dict(atividade) for atividade in atividades]

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

            if dias_restantes == 0:
                atividade["mensagem_prazo"] = "Prazo vence hoje"
            elif dias_restantes == 1:
                atividade["mensagem_prazo"] = "Prazo vence amanhã"
            else:
                atividade["mensagem_prazo"] = (
                    f"Prazo em {dias_restantes} dias"
                )

        else:
            atividade["status_prazo"] = "normal"
            atividade["mensagem_prazo"] = ""


    return render_template(
        "index.html",
        atividades=atividades,
        total_atividades=total_atividades,
        pendentes=pendentes,
        concluidas=concluidas,
        atrasadas=atrasadas,
        proximas=proximas,
        disciplinas=disciplinas,
        situacao=situacao,
        disciplina_filtro=disciplina_filtro,
        ordenacao=ordenacao
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

    return render_template("editar.html", atividade=atividade)


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


if __name__ == "__main__":
    criar_tabela()
    app.run(debug=True)

