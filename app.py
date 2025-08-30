from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import google.generativeai as genai
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"   
# SQL INFORMATION MY SQL WORK BENCH IKKADA PETTALI
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="********",   
    database="exam_ai"
)
cursor = db.cursor(dictionary=True)

# GEMINI KEY IKKADA PASTE CHEYALI 
genai.configure(api_key="AIzaSyCh5qtjAHDLzDkJgE26bCRlh8IFPVjAHqA")
model = genai.GenerativeModel("models/gemini-2.5-pro")


def build_style(level: str) -> str:
    """
    Returns a brief style instruction based on the chosen difficulty.
    """
    level = (level or "moderate").lower()
    if level == "easy":
        return (
            "Use very simple, beginner-friendly language. Avoid jargon. "
            "Keep sentences short. Add a very simple example or analogy."
        )
    if level == "advanced":
        return (
            "Provide an in-depth, technical, and rigorous explanation. "
            "Include precise terms, optional formulas or proofs if relevant, "
            "and real-world or industry applications and limitations."
        )
   
    return (
        "Explain clearly in a balanced, student-friendly way. "
        "Use short paragraphs, a concrete example, and avoid unnecessary jargon."
    )


def build_prompt(question: str, level: str) -> str:
    """
    Builds a strict formatting prompt so the model always returns the
    exact structure you want. We request HTML so it renders nicely in your UI.
    """
    style = build_style(level)
    return f"""
You are an AI tutor. Always follow these rules STRICTLY:

1) OUTPUT FORMAT: Return ONLY valid HTML (no markdown fences, no backticks).
2) Structure MUST be exactly:
   <h2> How to Understand: {question}</h2>
   <h3>🔑 Key Idea (1–2 lines)</h3>
   <p>…concise 1–2 line key idea…</p>

   <h3> Step-by-Step Process</h3>
   <ol>
     <li><strong>Step title</strong><br/>Short step description.</li>
     <li>…</li>
     <li>…</li>
   </ol>

   <h3>🌟 Final Summary</h3>
   <p>…short recap or tip…</p>

3) Tone/Detail style for this answer:
   {style}

4) Additional constraints:
   - Keep the structure EXACT (use the same headings/emojis).
   - Keep it clean and scannable. Avoid long walls of text.
   - If math is needed, write inline using plain text or simple HTML (no LaTeX delimiters).
   - Do NOT include any disclaimers or meta text.
   - Do NOT reference these instructions.

Question to answer: {question}
"""


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

# BACK END RGISTER PAGE ANTARUU 
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            username = data.get("username")
            email = data.get("email")
            password = data.get("password")
        else:
            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")

        if not username or not email or not password:
            return (jsonify({"status": "error", "message": "All fields are required"}), 400) if request.is_json else ("All fields are required", 400)

        hashed_pw = generate_password_hash(password)

        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_pw)
            )
            db.commit()

            if request.is_json:
                return jsonify({"status": "success", "message": "User registered!"})
            else:
                return redirect(url_for("login"))

        except mysql.connector.IntegrityError:
            if request.is_json:
                return jsonify({"status": "error", "message": "Username or email already exists"}), 400
            else:
                return "Username or email already exists", 400

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            email = data.get("email")
            password = data.get("password")
        else:
            email = request.form.get("email")
            password = request.form.get("password")

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            if request.is_json:
                return jsonify({"status": "success", "message": "Login successful!"})
            else:
                return redirect(url_for("index"))
        else:
            if request.is_json:
                return jsonify({"status": "error", "message": "Invalid credentials"}), 401
            else:
                return "Invalid email or password", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


@app.route("/ask", methods=["POST"])
def ask():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    question = (data.get("message") or "").strip()
    level = data.get("level", "moderate")

    if not question:
        return jsonify({"error": "Please provide a question"}), 400

    try:
        prompt = build_prompt(question, level)

        response = model.generate_content(prompt)
    
        answer_html = (response.text or "").strip()

        if not answer_html:
        
            answer_html = f"""
<h2> How to Understand: {question}</h2>
<h3>🔑 Key Idea (1–2 lines)</h3>
<p>A concise overview explaining the core idea.</p>

<h3>🥘 Step-by-Step Process</h3>
<ol>
  <li><strong>Identify the concept</strong><br/>Clarify terms and scope.</li>
  <li><strong>Explain the mechanism</strong><br/>Describe how it works with a simple example.</li>
  <li><strong>Apply it</strong><br/>Show a small use case to reinforce understanding.</li>
</ol>

<h3>🌟 Final Summary</h3>
<p>Quick recap of the concept and when to use it.</p>
""".strip()

        # Save chat history in DB (storing question+answer; if you later add a 'level' column, include it here)
        cursor.execute(
            "INSERT INTO history (user_id, question, answer) VALUES (%s, %s, %s)",
            (session["user_id"], question, answer_html),
        )
        db.commit()

        return jsonify({"response": answer_html})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history", methods=["GET"])
def get_history():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    cursor.execute(
        "SELECT id, question, answer, created_at FROM history WHERE user_id = %s ORDER BY created_at DESC",
        (session["user_id"],),
    )
    history = cursor.fetchall()
    short_history = [
        {
            "id": h["id"],
            "key": (h["answer"] or "").split("\n")[0][:60],
            "question": h["question"],
            "answer": h["answer"],
        }
        for h in history
    ]
    return jsonify(short_history)


@app.route("/delete/<int:id>", methods=["DELETE"])
def delete_history(id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    cursor.execute("DELETE FROM history WHERE id = %s AND user_id = %s", (id, session["user_id"]))
    db.commit()
    return jsonify({"status": "deleted"})


# ================= Run =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
