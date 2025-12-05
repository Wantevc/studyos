from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
import json
import random
from datetime import date, datetime
import ai_utils

app = Flask(__name__)

# === Paden & configuratie ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATA_FILE = os.path.join(BASE_DIR, "courses_data.json")
PROJECTS_FILE = os.path.join(BASE_DIR, "projects_data.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # zorg dat map bestaat

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # max 25 MB per upload
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "txt"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# === Data laden & opslaan ===

def load_courses():
    """Laad cursussen uit JSON-bestand, of gebruik startdata als het niet bestaat."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # als het bestand corrupt is, vallen we terug op defaults
            pass

    # Startdata: dit zie je de eerste keer
    # Examendatums in vorm YYYY-MM-DD
    return [
        {
            "name": "Anatomie I",
            "chapters": "8/12 hoofdstukken gescand",
            "questions": "34 vragen gemaakt",
            "tag": "Medisch · Bachelor",
            "exam_date": "2026-01-25",
            "progress": "mid",
            "files": [],
            "topics": [
                "Hoofdstuk 1 – Beenderstelsel",
                "Hoofdstuk 2 – Spierstelsel",
                "Hoofdstuk 3 – Zenuwstelsel",
            ],
            "qa": [
                {
                    "question": "Noem de drie hoofdtypes spierweefsel.",
                    "answer": "Skeletspier, hartspier, glad spierweefsel.",
                },
            ],
            "blocks": [
                {"title": "Hoofdstuk 3 lezen", "duration": "30 min", "when": "Vandaag"},
                {"title": "Flashcards zenuwstelsel", "duration": "20 min", "when": "Morgen"},
            ],
        },
        {
            "name": "Biofysica",
            "chapters": "5/9 hoofdstukken",
            "questions": "22 vragen",
            "tag": "Wetenschap",
            "exam_date": "2026-01-28",
            "progress": "high",
            "files": [],
            "topics": [
                "Kracht en beweging",
                "Elektriciteit in biologisch weefsel",
            ],
            "qa": [],
            "blocks": [],
        },
        {
            "name": "Neurobiologie",
            "chapters": "Nieuw vak",
            "questions": "Nog geen vragen",
            "tag": "Focusvak",
            "exam_date": "2026-02-02",
            "progress": "low",
            "files": [],
            "topics": [],
            "qa": [],
            "blocks": [],
        },
    ]


def save_courses():
    """Schrijf huidige data naar JSON-bestand."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(courses_data, f, ensure_ascii=False, indent=2)


# Globale 'database' in geheugen, geladen bij start
courses_data = load_courses()

def load_projects():
    """Laad projecten uit JSON-bestand, of geef lege lijst als het niet bestaat."""
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_projects():
    """Schrijf projecten naar JSON-bestand."""
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects_data, f, ensure_ascii=False, indent=2)


# Globale projecten-lijst
projects_data = load_projects()

@app.route("/projects")
def projects_overview():
    """
    Overzicht van alle projecten (thesis, eindwerk, papers, ...).
    """
    attach_project_deadlines()
    return render_template("projects.html", projects=projects_data)


@app.route("/projects/new", methods=["POST"])
def new_project():
    """
    Nieuw project toevoegen.
    """
    title = (request.form.get("title") or "").strip()
    tag = (request.form.get("tag") or "").strip()
    deadline = (request.form.get("deadline") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not title:
        return redirect(url_for("projects_overview"))

    project = {
        "title": title,
        "tag": tag or "Project",
        "deadline": deadline,          # YYYY-MM-DD of ""
        "description": description,
        "progress_pct": 0,
        "tasks": [],
        "notes": "",
    }
    projects_data.append(project)
    save_projects()
    attach_project_deadlines()

    project_id = len(projects_data) - 1
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>")
def project_detail(project_id: int):
    if not (0 <= project_id < len(projects_data)):
        return redirect(url_for("projects_overview"))

    attach_project_deadlines()
    project = projects_data[project_id]
    return render_template(
        "project_detail.html",
        project=project,
        project_id=project_id,
    )


@app.route("/projects/<int:project_id>/tasks/add", methods=["POST"])
def add_project_task(project_id: int):
    if not (0 <= project_id < len(projects_data)):
        return redirect(url_for("projects_overview"))

    project = projects_data[project_id]
    title = (request.form.get("task_title") or "").strip()
    if title:
        project.setdefault("tasks", [])
        project["tasks"].append({"title": title, "done": False})
        save_projects()
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>/tasks/toggle/<int:task_index>", methods=["POST"])
def toggle_project_task(project_id: int, task_index: int):
    if not (0 <= project_id < len(projects_data)):
        return redirect(url_for("projects_overview"))

    project = projects_data[project_id]
    tasks = project.get("tasks") or []
    if 0 <= task_index < len(tasks):
        tasks[task_index]["done"] = not tasks[task_index].get("done", False)
        # optioneel: progress updaten als je wil
        done_count = sum(1 for t in tasks if t.get("done"))
        if tasks:
            project["progress_pct"] = int(round((done_count / len(tasks)) * 100))
        save_projects()

    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>/notes", methods=["POST"])
def update_project_notes(project_id: int):
    if not (0 <= project_id < len(projects_data)):
        return redirect(url_for("projects_overview"))

    project = projects_data[project_id]
    notes = (request.form.get("notes") or "").strip()
    project["notes"] = notes
    save_projects()
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id: int):
    """
    Verwijder een project volledig.
    """
    global projects_data
    if not (0 <= project_id < len(projects_data)):
        return redirect(url_for("projects_overview"))

    del projects_data[project_id]
    save_projects()
    return redirect(url_for("projects_overview"))


@app.route("/exams")
def exams_overview():
    """
    Overzichtspagina met alle vakken gesorteerd op examendatum + status.
    """
    attach_exam_countdown()  # zorgt voor days_to_exam, progress en risk_status

    upcoming = []
    past = []
    no_date = []

    for c in courses_data:
        d = c.get("days_to_exam")
        if d is None:
            no_date.append(c)
        elif d < 0:
            past.append(c)
        else:
            upcoming.append(c)

    # Sorteer upcoming op dichtstbijzijnde examen eerst
    upcoming.sort(key=lambda x: x.get("days_to_exam", 9999))
    # Sorteer past op meest recent voorbij eerst
    past.sort(key=lambda x: x.get("days_to_exam", 0), reverse=True)
    # No_date sorteren op naam
    no_date.sort(key=lambda x: x.get("name", "").lower())

    return render_template(
        "exams.html",
        upcoming=upcoming,
        past=past,
        no_date=no_date,
    )

def ensure_notes_structure(course: dict):
    """
    Zorgt ervoor dat course['notes'] een geldige structuur heeft:
    {
      "folders": [
        {
          "name": "...",
          "notes": [
            {"title": "...", "content": "..."}
          ]
        }
      ]
    }
    """
    notes = course.get("notes")
    if not isinstance(notes, dict):
        notes = {"folders": []}
        course["notes"] = notes

    if "folders" not in notes or not isinstance(notes["folders"], list):
        notes["folders"] = []

    return notes
def ensure_ai_history(course: dict):
    """
    Zorgt ervoor dat course['ai_chat_history'] een lijst is.
    Structuur: [{"role": "user"|"assistant", "content": "..."}]
    """
    history = course.get("ai_chat_history")
    if not isinstance(history, list):
        history = []
        course["ai_chat_history"] = history
    return history

def attach_project_deadlines():
    """
    Voeg days_to_deadline + simpele status toe aan elk project.
    deadline: YYYY-MM-DD of leeg.
    """
    today = date.today()
    for p in projects_data:
        deadline_str = p.get("deadline") or ""
        p["days_to_deadline"] = None

        if deadline_str:
            try:
                d = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                p["days_to_deadline"] = (d - today).days
            except ValueError:
                p["days_to_deadline"] = None

        # Kleine statuslogica
        progress = int(p.get("progress_pct", 0) or 0)
        days = p["days_to_deadline"]

        if days is None:
            status = "Geen deadline"
        elif days < 0:
            status = "Deadline voorbij"
        elif days <= 7:
            if progress >= 70:
                status = "Laatste sprint"
            else:
                status = "Deadline alarm"
        elif days <= 21:
            if progress >= 50:
                status = "Op schema"
            else:
                status = "Extra focus nodig"
        else:
            if progress >= 30:
                status = "Rustige opbouw"
            else:
                status = "Opstart"

        p["status"] = status

# === Helpers voor AI-demo functies ===

AUTO_QUESTION_TEMPLATES = [
    "Leg uit wat wordt bedoeld met: {topic}.",
    "Waarom is {topic} belangrijk in dit vak?",
    "Noem de belangrijkste onderdelen van {topic}.",
    "Geef een concreet voorbeeld dat {topic} illustreert.",
    "Welke fouten worden vaak gemaakt bij {topic}?",
]

AUTO_PLAN_PATTERNS = [
    "Lezen: {topic}",
    "Samenvatten & kernbegrippen: {topic}",
    "Oefenvragen maken over {topic}",
    "Herhaling en flashcards: {topic}",
]


def generate_auto_questions_for_course(course: dict, max_questions: int = 6):
    """Simpele 'AI-demo' vragen op basis van topics of cursusnaam."""
    topics = course.get("topics") or []
    if not topics:
        topics = [course.get("name", "deze cursus")]

    existing = {item.get("question", "") for item in course.get("qa", [])}
    course.setdefault("qa", [])

    random_topics = topics[:]
    random.shuffle(random_topics)
    random_templates = AUTO_QUESTION_TEMPLATES[:]
    random.shuffle(random_templates)

    created = 0
    for topic in random_topics:
        for template in random_templates:
            if created >= max_questions:
                return
            q = template.format(topic=topic)
            if q in existing:
                continue
            course["qa"].append({"question": q, "answer": "—"})
            existing.add(q)
            created += 1


def generate_auto_plan_for_course(course: dict, max_blocks: int = 6):
    """Simpele 'AI-demo' blokplanning op basis van topics of cursusnaam."""
    topics = course.get("topics") or []
    if not topics:
        topics = [course.get("name", "deze cursus")]

    course.setdefault("blocks", [])
    existing_titles = {b.get("title", "") for b in course["blocks"]}

    durations = ["25 min", "30 min", "40 min"]
    moments = ["Vandaag", "Morgen", "Deze week", "Volgend weekend"]

    random_topics = topics[:]
    random.shuffle(random_topics)

    created = 0
    for topic in random_topics:
        random_patterns = AUTO_PLAN_PATTERNS[:]
        random.shuffle(random_patterns)

        for pattern in random_patterns:
            if created >= max_blocks:
                return

            title = pattern.format(topic=topic)
            if title in existing_titles:
                continue

            block = {
                "title": title,
                "duration": random.choice(durations),
                "when": random.choice(moments),
            }
            course["blocks"].append(block)
            existing_titles.add(title)
            created += 1


def compute_course_progress(course: dict):
    """
    Bereken een voortgangsscore (0–100%) voor een vak op basis van:
    - hoeveelheid structuur (topics, vragen, blokken, summaries)
    - hoe goed je de vragen al kent (flashcard stats: correct/wrong)
    - en leid een eenvoudige exam-status af (risk_status).
    """

    topics = course.get("topics") or []
    qa = course.get("qa") or []
    blocks = course.get("blocks") or []
    summaries = course.get("summaries")
    if isinstance(summaries, dict):
        summaries_count = len(summaries)
    else:
        summaries_count = 0

    topics_count = len(topics)
    qa_count = len(qa)
    blocks_count = len(blocks)

    # 1) Structuur-scores (hoeveel er al bestaat)
    topics_score = min(topics_count / 8.0, 1.0)       # 8 topics ≈ “vol”
    qa_score = min(qa_count / 30.0, 1.0)              # 30 vragen ≈ “vol”
    blocks_score = min(blocks_count / 10.0, 1.0)      # 10 blokken ≈ “vol”

    if topics_count > 0:
        summaries_ratio = summaries_count / max(topics_count, 1)
        summaries_score = min(summaries_ratio, 1.0)   # 1 summary per topic = vol
    else:
        summaries_score = 0.0

    # 2) Mastery-score (hoeveel vragen je echt al "kent")
    mastered = 0
    for item in qa:
        correct = int(item.get("correct", 0) or 0)
        wrong = int(item.get("wrong", 0) or 0)
        # simpele regel: minstens 1x "Ik wist deze" en niet vaker fout dan juist
        if correct > 0 and correct >= wrong:
            mastered += 1

    if qa_count > 0:
        mastery_ratio = mastered / float(qa_count)
        mastery_score = min(mastery_ratio, 1.0)
    else:
        mastery_score = 0.0

    # 3) Alles samenvoegen (structuur + mastery)
    scores = [topics_score, qa_score, blocks_score, summaries_score, mastery_score]
    total_score = sum(scores) / len(scores)
    pct = int(round(total_score * 100))

    # 4) Label op basis van progress
    if pct < 25:
        label = "Opstart"
    elif pct < 60:
        label = "Bezig"
    elif pct < 85:
        label = "Goed op weg"
    else:
        label = "Bijna examen-klaar"

    course["progress_pct"] = pct
    course["progress_label"] = label
    course["mastered_questions"] = mastered
    course["total_questions"] = qa_count

    # 5) Exam-status (risk_status) op basis van progress + days_to_exam
    days_to_exam = course.get("days_to_exam")

    if days_to_exam is None:
        risk_status = "Geen examendatum"
    elif days_to_exam < 0:
        risk_status = "Examen voorbij"
    elif days_to_exam > 21:
        # Examen ver weg
        if pct >= 40:
            risk_status = "Ruime marge"
        else:
            risk_status = "Rustig opstarten"
    elif days_to_exam > 7:
        # 1–3 weken
        if pct >= 60:
            risk_status = "Op schema"
        else:
            risk_status = "Extra focus nodig"
    else:
        # Laatste week (0–7 dagen)
        if pct >= 75:
            risk_status = "Ready voor examen"
        elif pct >= 50:
            risk_status = "Nog even doorduwen"
        else:
            risk_status = "Examen alarm"

    course["risk_status"] = risk_status


def attach_exam_countdown():
    """
    Voeg 'days_to_exam' toe aan elk vak op basis van exam_date (YYYY-MM-DD).
    En bereken ook automatisch een voortgangsscore + status per vak.
    """
    today = date.today()
    for course in courses_data:
        exam_str = course.get("exam_date")
        course["days_to_exam"] = None

        if exam_str:
            try:
                exam_date = datetime.strptime(exam_str, "%Y-%m-%d").date()
                course["days_to_exam"] = (exam_date - today).days
            except ValueError:
                course["days_to_exam"] = None

        # Na het updaten van days_to_exam ook progress + risk_status berekenen
        compute_course_progress(course)


# === Routes ===

@app.route("/")
def home():
    attach_exam_countdown()

    # Verzamel alle blokken die voor "Vandaag" gepland staan
    today_blocks = []
    for idx, course in enumerate(courses_data):
        for block in course.get("blocks", []):
            when_text = (block.get("when") or "").lower()
            if "vandaag" in when_text:
                today_blocks.append(
                    {
                        "course_id": idx,
                        "course_name": course.get("name", "Onbekend vak"),
                        "title": block.get("title", ""),
                        "duration": block.get("duration", ""),
                        "when": block.get("when", ""),
                    }
                )

    # Focus-vakken bepalen (meest dringend t.o.v. examen)
    focus_candidates = []
    for idx, course in enumerate(courses_data):
        days = course.get("days_to_exam")
        status = (course.get("risk_status") or "").lower()

        if days is None or days < 0:
            continue  # geen datum of al voorbij

        # welke status telt als "dringend"?
        if any(key in status for key in ["alarm", "extra focus", "nog even doorduwen"]):
            focus_candidates.append((idx, course))

    # sorteer: eerst dichtstbijzijnde examen
    focus_candidates.sort(key=lambda pair: pair[1].get("days_to_exam", 9999))

    # neem max 3
    focus_courses = []
    for idx, course in focus_candidates[:3]:
        focus_courses.append(
            {
                "index": idx,
                "name": course.get("name", "Onbekend vak"),
                "tag": course.get("tag", ""),
                "days_to_exam": course.get("days_to_exam"),
                "risk_status": course.get("risk_status"),
                "progress_pct": course.get("progress_pct", 0),
                "progress_label": course.get("progress_label", "Opstart"),
            }
        )

    return render_template(
        "index.html",
        courses=courses_data,
        today_blocks=today_blocks,
        focus_courses=focus_courses,
    )
@app.route("/courses")
def courses():
    attach_exam_countdown()
    return render_template("courses.html", courses=courses_data)


@app.route("/courses/new", methods=["GET", "POST"])
def new_course():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        tag = request.form.get("tag", "").strip()
        exam_date = request.form.get("exam_date", "").strip()  # verwacht YYYY-MM-DD
        chapters = request.form.get("chapters", "").strip()
        questions = request.form.get("questions", "").strip()

        if name:
            courses_data.append(
                {
                    "name": name,
                    "chapters": chapters or "Nog geen hoofdstukken",
                    "questions": questions or "Nog geen vragen",
                    "tag": tag or "Nieuw vak",
                    "exam_date": exam_date or "",
                    "progress": "low",
                    "files": [],
                    "topics": [],
                    "qa": [],
                    "blocks": [],
                }
            )
            save_courses()

        return redirect(url_for("courses"))

    return render_template("new_course.html")


@app.route("/courses/<int:course_id>/notes")
def course_notes(course_id: int):
    """
    Notitieblok voor één vak: mappen + notities + editor + AI-chat.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    folders = notes["folders"]
    history = ensure_ai_history(course)

    from flask import request

    # Welke folder/nota is actief?
    try:
        folder_index = int(request.args.get("folder", "0"))
    except ValueError:
        folder_index = 0

    try:
        note_index = int(request.args.get("note", "0"))
    except ValueError:
        note_index = 0

    if not folders:
        active_folder = None
        active_note = None
    else:
        if folder_index < 0:
            folder_index = 0
        if folder_index >= len(folders):
            folder_index = len(folders) - 1

        active_folder = folders[folder_index]
        notes_list = active_folder.get("notes") or []
        if notes_list:
            if note_index < 0:
                note_index = 0
            if note_index >= len(notes_list):
                note_index = len(notes_list) - 1
            active_note = notes_list[note_index]
        else:
            active_note = None
            note_index = 0

    save_courses()  # structuur bewaren als hij net aangemaakt is

    # AI-botnaam
    assistant_name = f"{course.get('name', 'Vak')} Coach"

    return render_template(
        "course_notes.html",
        course=course,
        course_id=course_id,
        folders=folders,
        folder_index=folder_index,
        note_index=note_index,
        active_folder=active_folder,
        active_note=active_note,
        ai_history=history,
        assistant_name=assistant_name,
    )

@app.route("/courses/<int:course_id>/notes/folders/add", methods=["POST"])
def add_notes_folder(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    from flask import request

    name = (request.form.get("folder_name") or "").strip()
    if name:
        notes["folders"].append({"name": name, "notes": []})
        save_courses()

    folder_index = max(0, len(notes["folders"]) - 1)
    return redirect(url_for("course_notes", course_id=course_id, folder=folder_index))


@app.route("/courses/<int:course_id>/notes/folders/<int:folder_index>/delete", methods=["POST"])
def delete_notes_folder(course_id: int, folder_index: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    folders = notes["folders"]

    if 0 <= folder_index < len(folders):
        del folders[folder_index]
        save_courses()

    return redirect(url_for("course_notes", course_id=course_id))


@app.route("/courses/<int:course_id>/notes/<int:folder_index>/notes/add", methods=["POST"])
def add_note(course_id: int, folder_index: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    folders = notes["folders"]

    if not (0 <= folder_index < len(folders)):
        return redirect(url_for("course_notes", course_id=course_id))

    from flask import request
    title = (request.form.get("note_title") or "").strip()
    if title:
        folder = folders[folder_index]
        folder.setdefault("notes", [])
        folder["notes"].append({"title": title, "content": ""})
        save_courses()
        note_index = len(folder["notes"]) - 1
        return redirect(url_for("course_notes", course_id=course_id, folder=folder_index, note=note_index))

    return redirect(url_for("course_notes", course_id=course_id, folder=folder_index))


@app.route("/courses/<int:course_id>/notes/<int:folder_index>/notes/<int:note_index>/save", methods=["POST"])
def save_note(course_id: int, folder_index: int, note_index: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    folders = notes["folders"]

    if not (0 <= folder_index < len(folders)):
        return redirect(url_for("course_notes", course_id=course_id))

    folder = folders[folder_index]
    notes_list = folder.get("notes") or []
    if not (0 <= note_index < len(notes_list)):
        return redirect(url_for("course_notes", course_id=course_id, folder=folder_index))

    from flask import request
    title = (request.form.get("note_title") or "").strip()
    content = (request.form.get("note_content") or "")

    note = notes_list[note_index]
    if title:
        note["title"] = title
    note["content"] = content

    save_courses()
    return redirect(url_for("course_notes", course_id=course_id, folder=folder_index, note=note_index))


@app.route("/courses/<int:course_id>/notes/<int:folder_index>/notes/<int:note_index>/delete", methods=["POST"])
def delete_note(course_id: int, folder_index: int, note_index: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    notes = ensure_notes_structure(course)
    folders = notes["folders"]

    if not (0 <= folder_index < len(folders)):
        return redirect(url_for("course_notes", course_id=course_id))

    folder = folders[folder_index]
    notes_list = folder.get("notes") or []

    if 0 <= note_index < len(notes_list):
        del notes_list[note_index]
        save_courses()

    return redirect(url_for("course_notes", course_id=course_id, folder=folder_index))


    ...
    return redirect(url_for("course_notes", course_id=course_id, folder=folder_index))

@app.route("/courses/<int:course_id>/notes/ai_chat", methods=["POST"])
def course_notes_ai_chat(course_id: int):
    """
    Ontvangt een bericht uit de UI, voegt het toe aan de history,
    roept ai_utils aan en stuurt een JSON-antwoord terug.
    """
    if not (0 <= course_id < len(courses_data)):
        return jsonify({"error": "Onbekend vak"}), 400

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Leeg bericht"}), 400

    course = courses_data[course_id]
    notes_data = ensure_notes_structure(course)
    history = ensure_ai_history(course)

    # user-bericht eerst zelf toevoegen aan de geschiedenis
    history.append({"role": "user", "content": user_message})

    try:
        reply_text, new_history, error_text = ai_utils.chat_with_course_assistant(
            course=course,
            notes_data=notes_data,
            history=history,
            user_message=user_message,
        )
    except Exception as e:
        reply_text = "Er ging iets mis bij de AI-koppeling."
        new_history = history
        error_text = str(e)

    course["ai_chat_history"] = new_history
    save_courses()

    return jsonify({
        "reply": reply_text,
        "error": error_text,
    })

@app.route("/courses/<int:course_id>/notes/ai_chat/clear", methods=["POST"])
def course_notes_ai_clear(course_id: int):
    """
    Wis de chatgeschiedenis voor dit vak.
    """
    if not (0 <= course_id < len(courses_data)):
        return jsonify({"error": "Onbekend vak"}), 400

    course = courses_data[course_id]
    course["ai_chat_history"] = []
    save_courses()

    return jsonify({"ok": True})

@app.route("/courses/<int:course_id>")
def course_detail(course_id: int):
    if 0 <= course_id < len(courses_data):
        attach_exam_countdown()
        course = courses_data[course_id]
    else:
        return redirect(url_for("courses"))

    return render_template("course_detail.html", course=course, course_id=course_id)

@app.route("/courses/<int:course_id>/delete", methods=["POST"])
def delete_course(course_id: int):
    """
    Verwijder een vak volledig uit courses_data + JSON.
    """
    global courses_data

    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    # Optioneel: hier zouden we ook geüploade bestanden van dit vak kunnen verwijderen.
    # Voor nu laten we de files fysiek staan om risico op verkeerde delete te vermijden.

    # Vak verwijderen uit de lijst
    del courses_data[course_id]
    save_courses()

    return redirect(url_for("courses"))


@app.route("/courses/<int:course_id>/meta", methods=["POST"])
def edit_course_meta(course_id: int):
    """
    Bewerk basisgegevens van een vak: naam, tag, examendatum, hoofdstuk-/vragen-tekst.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    name = (request.form.get("name") or "").strip()
    tag = (request.form.get("tag") or "").strip()
    exam_date = (request.form.get("exam_date") or "").strip()
    chapters = (request.form.get("chapters") or "").strip()
    questions = (request.form.get("questions") or "").strip()

    # Alleen overschrijven als er iets is ingevuld, behalve exam_date:
    # exam_date mag leeg zijn om te verwijderen.
    if name:
        course["name"] = name
    if tag:
        course["tag"] = tag
    if chapters:
        course["chapters"] = chapters
    if questions:
        course["questions"] = questions

    # Examendatum: zelfs lege string is toegestaan => verwijdert datum
    course["exam_date"] = exam_date

    # Na wijzigingen: opnieuw countdown + progress berekenen
    save_courses()
    attach_exam_countdown()

    return redirect(url_for("course_detail", course_id=course_id))

@app.route("/courses/<int:course_id>/export")
def export_course(course_id: int):
    """
    Toon een leesbaar overzicht van één vak:
    - basisinfo
    - topics + eventuele samenvattingen
    - oefenvragen
    - blokplanning
    Handig om te printen of te bewaren.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    attach_exam_countdown()
    course = courses_data[course_id]

    # summaries altijd als dict
    summaries = course.get("summaries")
    if not isinstance(summaries, dict):
        summaries = {}

    return render_template(
        "export_course.html",
        course=course,
        course_id=course_id,
        summaries=summaries,
    )

@app.route("/courses/<int:course_id>/upload", methods=["POST"])
def upload_course_file(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    file = request.files.get("course_file")
    if not file or file.filename == "":
        return redirect(url_for("course_detail", course_id=course_id))

    if not allowed_file(file.filename):
        return redirect(url_for("course_detail", course_id=course_id))

    original_name = file.filename
    safe_name = secure_filename(original_name)
    disk_name = f"course{course_id}_{safe_name}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], disk_name)

    file.save(save_path)

    # We slaan de BESTANDSNAAM OP DIE OP SCHIJF STAAT, zodat AI 'm kan vinden
    if "files" not in course:
        course["files"] = []
    course["files"].append(disk_name)
    save_courses()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/topics/add", methods=["POST"])
def add_topic(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    title = request.form.get("topic_title", "").strip()

    if title:
        if "topics" not in course:
            course["topics"] = []
        course["topics"].append(title)
        save_courses()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/questions/add", methods=["POST"])
def add_question(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    q = request.form.get("question", "").strip()
    a = request.form.get("answer", "").strip()

    if q:
        if "qa" not in course:
            course["qa"] = []
        course["qa"].append({"question": q, "answer": a or "—"})
        save_courses()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/questions/auto", methods=["POST"])
def auto_questions(course_id: int):
    """
    Deze endpoint gebruikt nu echte AI via ai_utils.generate_questions_for_course.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    new_questions, error_text = ai_utils.generate_questions_for_course(
        course,
        max_questions=6,
    )

    if new_questions:
        course.setdefault("qa", [])
        course["qa"].extend(new_questions)
        save_courses()

    if error_text:
        print(error_text)

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/plan/add", methods=["POST"])
def add_block(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    title = request.form.get("block_title", "").strip()
    duration = request.form.get("block_duration", "").strip()
    when = request.form.get("block_when", "").strip()

    if title:
        if "blocks" not in course:
            course["blocks"] = []
        course["blocks"].append(
            {
                "title": title,
                "duration": duration or "—",
                "when": when or "Ongepland",
            }
        )
        save_courses()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/topics/auto", methods=["POST"])
def auto_generate_topics(course_id: int):
    """
    AI: topics genereren op basis van geüploade PDF's.
    We werken rechtstreeks op de globale courses_data en gebruiken save_courses()
    zonder argument.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    # 1. Verzamel tekst uit alle geüploade files
    all_text = ""

    for filename in course.get("files", []):
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if filename.lower().endswith(".pdf"):
            extracted = ai_utils.extract_text_from_pdf(path)
            if extracted:
                all_text += "\n" + extracted

    if not all_text.strip():
        all_text = "Geen tekst gevonden. Genereer algemene topics voor dit vak."

    # 2. Laat AI topics genereren
    topics, error = ai_utils.generate_topics_from_text(all_text, max_topics=12)

    if topics:
        if "topics" not in course or not isinstance(course["topics"], list):
            course["topics"] = []

        for t in topics:
            if t not in course["topics"]:
                course["topics"].append(t)

        save_courses()

    if error:
        print("AI topic generation error:", error)

    return redirect(url_for("course_detail", course_id=course_id))

@app.route("/courses/<int:course_id>/summaries/auto", methods=["POST"])
def auto_generate_summaries(course_id: int):
    """
    AI: korte samenvattingen genereren per topic voor dit vak.
    Resultaat wordt opgeslagen in course["summaries"] als dict: {topic: summary}.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    summaries, error_text = ai_utils.generate_summaries_for_topics(
        course,
        max_topics=8,
    )

    if summaries:
        # we slaan samenvattingen op in een dict per topic
        existing = course.get("summaries")
        if not isinstance(existing, dict):
            existing = {}
        for item in summaries:
            topic = item["topic"]
            summary = item["summary"]
            # overschrijven mag; je zou hier ook kunnen checken of topic bestaat
            existing[topic] = summary
        course["summaries"] = existing
        save_courses()

    if error_text:
        print(error_text)

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/plan/auto", methods=["POST"])
def auto_plan(course_id: int):
    """
    AI: echte studieplanning genereren voor dit vak.
    Gebruikt ai_utils.generate_study_blocks_for_course.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]

    blocks, error_text = ai_utils.generate_study_blocks_for_course(
        course,
        max_blocks=8,
    )

    if blocks:
        course.setdefault("blocks", [])
        course["blocks"].extend(blocks)
        save_courses()

    if error_text:
        print(error_text)

    return redirect(url_for("course_detail", course_id=course_id))

@app.route("/courses/<int:course_id>/topics/clear", methods=["POST"])
def clear_topics(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    course["topics"] = []
    save_courses()
    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/stats")
def stats_overview():
    """
    Globale statistieken over alle vakken:
    - aantal vakken
    - aantal (en beheersing van) oefenvragen
    - examengerelateerde info
    """
    attach_exam_countdown()  # zorgt dat days_to_exam, progress, risk_status up-to-date zijn

    total_courses = len(courses_data)

    total_questions = 0
    total_mastered = 0

    upcoming_exams = 0
    exams_without_date = 0
    exams_past = 0

    alarm_courses = 0
    focus_courses_count = 0

    # Voor “top courses” op basis van aantal vragen
    courses_with_counts = []

    for c in courses_data:
        q_total = int(c.get("total_questions", 0) or 0)
        q_mastered = int(c.get("mastered_questions", 0) or 0)

        total_questions += q_total
        total_mastered += q_mastered

        days = c.get("days_to_exam")
        if days is None:
            exams_without_date += 1
        elif days < 0:
            exams_past += 1
        else:
            upcoming_exams += 1

        status = (c.get("risk_status") or "").lower()
        if "alarm" in status:
            alarm_courses += 1
        if any(key in status for key in ["alarm", "extra focus", "nog even doorduwen"]):
            focus_courses_count += 1

        courses_with_counts.append({
            "name": c.get("name", "Onbekend vak"),
            "tag": c.get("tag", ""),
            "total_questions": q_total,
            "mastered_questions": q_mastered,
            "progress_pct": c.get("progress_pct", 0),
            "risk_status": c.get("risk_status", "Onbekend"),
        })

    mastery_pct_global = 0
    if total_questions > 0:
        mastery_pct_global = int(round((total_mastered / float(total_questions)) * 100))

    # Top 5 vakken op basis van aantal vragen
    courses_with_counts.sort(key=lambda x: x["total_questions"], reverse=True)
    top_courses = courses_with_counts[:5]

    return render_template(
        "stats.html",
        total_courses=total_courses,
        total_questions=total_questions,
        total_mastered=total_mastered,
        mastery_pct_global=mastery_pct_global,
        upcoming_exams=upcoming_exams,
        exams_without_date=exams_without_date,
        exams_past=exams_past,
        alarm_courses=alarm_courses,
        focus_courses_count=focus_courses_count,
        top_courses=top_courses,
    )

@app.route("/courses/<int:course_id>/questions/clear", methods=["POST"])
def clear_questions(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    course["qa"] = []
    save_courses()
    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/plan/clear", methods=["POST"])
def clear_plan(course_id: int):
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    course["blocks"] = []
    save_courses()
    return redirect(url_for("course_detail", course_id=course_id))

@app.route("/courses/<int:course_id>/practice")
def practice(course_id: int):
    """
    Oefenmodus: één vraag per keer met modelantwoord.
    Vragen komen uit course["qa"].
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    qa_list = course.get("qa") or []

    # Als er nog geen vragen zijn → terug naar detail met melding in template
    if not qa_list:
        # Je kunt er later een mooie melding voor maken in de template
        return redirect(url_for("course_detail", course_id=course_id))

    # Welke vraag tonen? via query parameter q (index)
    try:
        index = int(request.args.get("q", "0"))
    except ValueError:
        index = 0

    if index < 0:
        index = 0
    if index >= len(qa_list):
        index = len(qa_list) - 1

    question = qa_list[index]

    has_prev = index > 0
    has_next = index < len(qa_list) - 1

    return render_template(
        "practice.html",
        course=course,
        course_id=course_id,
        question=question,
        index=index,
        total=len(qa_list),
        has_prev=has_prev,
        has_next=has_next,
    )

@app.route("/courses/<int:course_id>/flashcards")
def flashcards(course_id: int):
    """
    Flashcards-modus met filters:
    - mode=all: alle kaarten
    - mode=weak: kaarten die je nog niet goed kent
    - mode=strong: kaarten die je meestal goed hebt
    Ondersteunt ook ?pos=... en ?random=1
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    qa_list = course.get("qa") or []

    if not qa_list:
        return redirect(url_for("course_detail", course_id=course_id))

    from flask import request

    mode = (request.args.get("mode") or "all").lower()

    indexed = list(enumerate(qa_list))

    def is_strong(card):
        correct = int(card.get("correct", 0) or 0)
        wrong = int(card.get("wrong", 0) or 0)
        return correct > 0 and correct >= wrong

    def is_weak(card):
        correct = int(card.get("correct", 0) or 0)
        wrong = int(card.get("wrong", 0) or 0)
        # "nog moeilijk": nooit juist OF vaker fout dan juist
        return correct == 0 or wrong > correct

    if mode == "strong":
        filtered = [(i, c) for i, c in indexed if is_strong(c)]
    elif mode == "weak":
        filtered = [(i, c) for i, c in indexed if is_weak(c)]
    else:
        filtered = indexed
        mode = "all"

    empty_filter = False
    if not filtered:
        # Geen kaarten in deze selectie -> fallback naar alles
        filtered = indexed
        empty_filter = True
        mode = "all"

    # Positie in de gefilterde deck
    try:
        pos = int(request.args.get("pos", "0"))
    except ValueError:
        pos = 0

    random_flag = request.args.get("random")
    if random_flag == "1" and filtered:
        pos = random.randint(0, len(filtered) - 1)

    if pos < 0:
        pos = 0
    if pos >= len(filtered):
        pos = len(filtered) - 1

    original_index, card = filtered[pos]

    has_prev = pos > 0
    has_next = pos < len(filtered) - 1

    return render_template(
        "flashcards.html",
        course=course,
        course_id=course_id,
        card=card,
        index=original_index,  # index in originele qa-lijst
        pos=pos,               # positie binnen gefilterde deck
        total=len(filtered),
        total_all=len(qa_list),
        has_prev=has_prev,
        has_next=has_next,
        mode=mode,
        empty_filter=empty_filter,
    )


@app.route("/courses/<int:course_id>/flashcards/rate", methods=["POST"])
def rate_flashcard(course_id: int):
    """
    'Ik wist deze' / 'Nog niet' verwerken en daarna
    naar de volgende kaart in de huidige filter springen.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    qa_list = course.get("qa") or []

    if not qa_list:
        return redirect(url_for("course_detail", course_id=course_id))

    from flask import request

    try:
        index = int(request.form.get("q_index", "0"))
    except ValueError:
        index = 0

    mode = (request.form.get("mode") or "all").lower()
    result = (request.form.get("result") or "").strip()

    if index < 0:
        index = 0
    if index >= len(qa_list):
        index = len(qa_list) - 1

    card = qa_list[index]

    # Tellingen bijhouden
    if result == "know":
        card["correct"] = card.get("correct", 0) + 1
    elif result == "dontknow":
        card["wrong"] = card.get("wrong", 0) + 1

    save_courses()

    # Zelfde filterlogica als in flashcards()
    indexed = list(enumerate(qa_list))

    def is_strong(card):
        correct = int(card.get("correct", 0) or 0)
        wrong = int(card.get("wrong", 0) or 0)
        return correct > 0 and correct >= wrong

    def is_weak(card):
        correct = int(card.get("correct", 0) or 0)
        wrong = int(card.get("wrong", 0) or 0)
        return correct == 0 or wrong > correct

    if mode == "strong":
        filtered = [(i, c) for i, c in indexed if is_strong(c)]
    elif mode == "weak":
        filtered = [(i, c) for i, c in indexed if is_weak(c)]
    else:
        filtered = indexed
        mode = "all"

    if not filtered:
        filtered = indexed
        mode = "all"

    # Huidige positie in gefilterde deck zoeken
    cur_pos = 0
    for p, (orig_i, _) in enumerate(filtered):
        if orig_i == index:
            cur_pos = p
            break

    next_pos = cur_pos
    if cur_pos < len(filtered) - 1:
        next_pos = cur_pos + 1

    return redirect(url_for("flashcards", course_id=course_id, mode=mode, pos=next_pos))

@app.route("/courses/<int:course_id>/practice/feedback", methods=["POST"])
def practice_feedback(course_id: int):
    """
    Verwerk het antwoord van de student in oefenmodus en geef AI-feedback.
    """
    if not (0 <= course_id < len(courses_data)):
        return redirect(url_for("courses"))

    course = courses_data[course_id]
    qa_list = course.get("qa") or []

    if not qa_list:
        return redirect(url_for("course_detail", course_id=course_id))

    # Welke vraag?
    try:
        index = int(request.form.get("q_index", "0"))
    except ValueError:
        index = 0

    if index < 0:
        index = 0
    if index >= len(qa_list):
        index = len(qa_list) - 1

    question = qa_list[index]
    user_answer = (request.form.get("user_answer") or "").strip()

    feedback = ai_utils.generate_answer_feedback(
        question_text=question.get("question", ""),
        model_answer=question.get("answer", ""),
        user_answer=user_answer,
    )

    has_prev = index > 0
    has_next = index < len(qa_list) - 1

    # Hergebruik dezelfde template 'practice.html', maar nu met feedback + ingevuld antwoord
    return render_template(
        "practice.html",
        course=course,
        course_id=course_id,
        question=question,
        index=index,
        total=len(qa_list),
        has_prev=has_prev,
        has_next=has_next,
        user_answer=user_answer,
        feedback=feedback,
    )

@app.route("/ai/test")
def ai_test():
    """
    Eenvoudige route om te checken of de OpenAI-koppeling werkt.
    Surf naar /ai/test in je browser.
    """
    text = ai_utils.test_ai()
    return f"<pre>{text}</pre>"


@app.route("/demo")
def load_demo_course():
    """Voeg één demo-vak toe met voorbeeldtopics, vragen en blokken (met 'Vandaag')."""
    # Check of demo al bestaat
    for c in courses_data:
        if c.get("name") == "Study OS Demo":
            return redirect(url_for("home"))

    demo_course = {
        "name": "Study OS Demo",
        "chapters": "3/6 hoofdstukken gescand",
        "questions": "12 vragen gemaakt",
        "tag": "Demo · Medisch",
        "exam_date": "2026-02-10",
        "progress": "mid",
        "files": ["demo_cursus_neuro.pdf"],
        "topics": [
            "Hoofdstuk 1 – Overzicht zenuwstelsel",
            "Hoofdstuk 2 – Neuronen & synapsen",
            "Hoofdstuk 3 – Klinische casussen",
        ],
        "qa": [
            {
                "question": "Wat is het verschil tussen een sensorisch en een motorisch neuron?",
                "answer": "Sensorische neuronen brengen info naar het centrale zenuwstelsel; motorische neuronen sturen bevelen naar spieren/klieren.",
            },
            {
                "question": "Leg kort uit wat een synaps is.",
                "answer": "Contactpunt tussen twee neuronen waar signaaloverdracht via neurotransmitters gebeurt.",
            },
        ],
        "blocks": [
            {"title": "Hoofdstuk 1 – Leesronde", "duration": "30 min", "when": "Vandaag"},
            {"title": "Oefenvragen neuronen & synapsen", "duration": "25 min", "when": "Vandaag"},
            {"title": "Herhaling flashcards casussen", "duration": "20 min", "when": "Morgen"},
        ],
    }

    courses_data.append(demo_course)
    save_courses()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)