
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

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

    with conectar_banco() as conexao:
        atividades = conexao.execute("""
            SELECT * FROM atividades
            ORDER BY prazo ASC, id DESC
        """).fetchall()

    return render_template("index.html", atividades=atividades)


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

