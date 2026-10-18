
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

    
    from datetime import date, timedelta

    with conectar_banco() as conexao:
        atividades = conexao.execute("""
            SELECT * FROM atividades
            ORDER BY prazo ASC, id DESC
        """).fetchall()

        total_atividades = conexao.execute("""
            SELECT COUNT(*) FROM atividades
        """).fetchone()[0]

        pendentes = conexao.execute("""
            SELECT COUNT(*) FROM atividades
            WHERE concluida = 0
        """).fetchone()[0]

        concluidas = conexao.execute("""
            SELECT COUNT(*) FROM atividades
            WHERE concluida = 1
        """).fetchone()[0]

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

    return render_template(
        "index.html",
        atividades=atividades,
        total_atividades=total_atividades,
        pendentes=pendentes,
        concluidas=concluidas,
        atrasadas=atrasadas,
        proximas=proximas
    )


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

