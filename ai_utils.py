import os
import json
from datetime import date, datetime
from openai import OpenAI
import PyPDF2
from typing import List, Dict, Tuple
# Maak de OpenAI client aan met je API key uit de omgeving
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def test_ai():
    """
    Eenvoudige test of de AI-verbinding werkt.
    Deze functie wordt gebruikt door de /ai/test route.
    """
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=(
                "Geef één korte Nederlandse zin die bevestigt dat de AI "
                "van Study OS succesvol werkt. Maak het informeel en geruststellend."
            ),
        )
        text = resp.output_text.strip()
        return text
    except Exception as e:
        print("AI-fout in test_ai():", e)
        return f"Er ging iets mis bij het testen van de AI: {e}"


def generate_questions_for_course(course, max_questions=6):
    """
    Genereer oefenvragen voor een vak op basis van de course-data.
    Verwacht dat 'course' een dict is met minstens:
      - 'name': naam van het vak
      - 'topics': lijst van hoofstukken/onderwerpen (mag leeg zijn)

    Retourneert: (vragen_lijst, error_text)
      - vragen_lijst: list[dict] met keys 'question' en 'answer'
      - error_text: None als alles goed ging, anders een foutbericht (string)
    """

    course_name = course.get("name", "Onbekend vak")
    topics = course.get("topics") or []

    if topics:
        topics_text = "\n".join(f"- {t}" for t in topics)
    else:
        topics_text = (
            "- Geen specifieke topics opgegeven. "
            "Maak algemene, basisvragen over de belangrijkste kernbegrippen van dit vak."
        )

    prompt = f"""
Je bent een studie-assistent in een app genaamd Study OS.

Vaknaam: "{course_name}"

Topics / hoofstukken:
{topics_text}

Opdracht:
- Genereer maximaal {max_questions} goede oefenvragen voor dit vak.
- Gebruik verschillende vraagtypes:
  - definitievragen ("Wat is ..."),
  - begripsvragen ("Leg uit in eigen woorden ..."),
  - vergelijkingsvragen ("Wat is het verschil tussen ..."),
  - eenvoudige toepassingsvragen.

BELANGRIJK:
- Antwoord in ÉÉN geldig JSON-object.
- GEEN extra tekst, GEEN uitleg, GEEN markdown.
- Alleen pure JSON, in exact deze structuur:

{{
  "questions": [
    {{
      "question": "Schrijf hier de vraag",
      "answer": "Schrijf hier het beknopte, duidelijke modelantwoord"
    }},
    {{
      "question": "Nog een vraag",
      "answer": "Het bijhorende modelantwoord"
    }}
  ]
}}

Let op:
- 'questions' moet altijd een lijst zijn.
- Elke vraag moet zowel 'question' als 'answer' bevatten.
- Gebruik gewone, dubbele aanhalingstekens in de JSON.
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor vragen:", raw)

        data = json.loads(raw)

        questions = data.get("questions", [])
        if not isinstance(questions, list):
            return [], "AI antwoordde geen lijst onder 'questions'."

        cleaned = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            vraag = q.get("question", "").strip()
            antwoord = q.get("answer", "").strip()
            if vraag and antwoord:
                cleaned.append({"question": vraag, "answer": antwoord})

        if not cleaned:
            return [], "AI gaf geen bruikbare vragen terug."

        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON parse fout bij AI-vragen:", e)
        return [], f"JSON-fout bij het verwerken van het AI-antwoord: {e}"

    except Exception as e:
        print("AI-fout bij vragen genereren:", e)
        return [], f"Er ging iets mis bij het genereren van vragen: {e}"

def generate_questions_from_note(course_name: str, note_title: str, note_content: str, max_questions: int = 6):
    """
    Genereer oefenvragen op basis van de inhoud van één notitie.

    Input:
      - course_name: naam van het vak
      - note_title: titel van de notitie
      - note_content: volledige tekst van de notitie
    Output:
      - (vragen_lijst, error_text)
        vragen_lijst = list[dict] met 'question' en 'answer'
        error_text = None als alles ok, anders foutstring
    """

    note_content = (note_content or "").strip()
    if not note_content:
        return [], "Notitie is leeg; geen vragen gegenereerd."

    title_text = (note_title or "Ongetitelde notitie").strip()

    prompt = f"""
Je bent een studie-assistent in een app genaamd Study OS.

Vak: "{course_name}"
Notitie-titel: "{title_text}"

Hieronder staat de volledige tekst van de notitie van de student.
Gebruik ALLEEN informatie uit deze notitie om vragen te maken.

----------------- BEGIN NOTITIE -----------------
{note_content}
----------------- EINDE NOTITIE -----------------

Opdracht:
- Genereer maximaal {max_questions} goede oefenvragen op basis van deze notitie.
- Gebruik verschillende vraagtypes:
  - definitievragen ("Wat is ..."),
  - begripsvragen ("Leg uit in eigen woorden ..."),
  - vergelijkingsvragen,
  - kleine toepassingsvragen.

BELANGRIJK:
- Antwoord in ÉÉN geldig JSON-object.
- GEEN extra tekst, GEEN uitleg, GEEN markdown.
- Alleen pure JSON, in exact deze structuur:

{{
  "questions": [
    {{
      "question": "Schrijf hier de vraag",
      "answer": "Schrijf hier het beknopte, duidelijke modelantwoord"
    }},
    {{
      "question": "Nog een vraag",
      "answer": "Het bijhorende modelantwoord"
    }}
  ]
}}

Regels:
- 'questions' moet altijd een lijst zijn.
- Elke vraag heeft zowel 'question' als 'answer'.
- Gebruik gewone dubbele aanhalingstekens in de JSON.
- Gebruik geen kennis buiten de notitie (blijf bij de inhoud van de tekst).
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor vragen uit notitie:", raw)

        data = json.loads(raw)
        questions = data.get("questions", [])

        if not isinstance(questions, list):
            return [], "AI antwoordde geen lijst onder 'questions'."

        cleaned = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            vraag = (q.get("question") or "").strip()
            antwoord = (q.get("answer") or "").strip()
            if vraag and antwoord:
                cleaned.append({"question": vraag, "answer": antwoord})

        if not cleaned:
            return [], "AI gaf geen bruikbare vragen terug uit de notitie."

        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON parse fout bij AI-vragen uit notitie:", e)
        return [], f"JSON-fout bij het verwerken van het AI-antwoord: {e}"

    except Exception as e:
        print("AI-fout bij vragen uit notitie genereren:", e)
        return [], f"Er ging iets mis bij het genereren van vragen uit de notitie: {e}"

def generate_summary_from_note(course_name: str, note_title: str, note_content: str) -> Tuple[str, str]:
    """
    Genereer een korte, duidelijke samenvatting op basis van één notitie.

    Input:
      - course_name: naam van het vak
      - note_title: titel van de notitie
      - note_content: volledige tekst van de notitie

    Output:
      - (summary_text, error_text)
        summary_text = samenvatting (string) of "" als mislukking
        error_text = None als ok, anders foutstring
    """
    note_content = (note_content or "").strip()
    if not note_content:
        return "", "Notitie is leeg; geen samenvatting gegenereerd."

    title_text = (note_title or "Ongetitelde notitie").strip()

    prompt = f"""
Je bent een studie-assistent in de app Study OS.

Vak: "{course_name}"
Notitie-titel: "{title_text}"

Hieronder staat de volledige tekst van de notitie van de student:

----------------- BEGIN NOTITIE -----------------
{note_content}
----------------- EINDE NOTITIE -----------------

Opdracht:
- Maak een duidelijke, overzichtelijke samenvatting in het Nederlands.
- Schrijf in 3 tot 8 korte alinea's of bullets.
- Focus op de kernbegrippen, definities en verbanden.
- Schrijf alsof je het uitlegt aan je toekomstige zelf vlak voor het examen.
- Vermijd irrelevante details en herhaling.

BELANGRIJK:
- GEEN JSON, GEEN markdown codeblokken.
- Gewoon normale, lopende tekst (je mag wel korte lijstjes gebruiken).
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        text = resp.output_text.strip()
        if not text:
            return "", "AI gaf een leeg antwoord bij samenvatting."
        return text, None
    except Exception as e:
        print("AI-fout bij samenvatting uit notitie:", e)
        return "", f"Er ging iets mis bij het genereren van een samenvatting: {e}"


def generate_topics_from_text(text, max_topics=12):
    """
    Neemt pure text als input en laat AI een lijst van topics/hoofdstukken genereren.
    Retourneert: (topics_list, error_text)
    """

    prompt = f"""
Je bent een studie-assistent in Study OS.

Hieronder staat de tekst van een cursus. 
Genereer een duidelijke, gestructureerde lijst van maximaal {max_topics} hoofdstukken of topics.

Regels:
- Hou het kort maar duidelijk.
- Geen sub-substructuur nodig (1 niveau is genoeg).
- Antwoord in ÉÉN geldig JSON-object, zonder extra tekst, zonder markdown.

Structuur:
{{
  "topics": [
    "Hoofdstuk 1 titel",
    "Hoofdstuk 2 titel",
    "Hoofdstuk 3 titel"
  ]
}}

Hier is de text:
--------------------
{text}
--------------------
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor topics:", raw)

        data = json.loads(raw)
        topics = data.get("topics", [])

        if not isinstance(topics, list):
            return [], "AI gaf geen lijst bij 'topics'."

        cleaned = [t.strip() for t in topics if isinstance(t, str) and t.strip()]

        if not cleaned:
            return [], "AI gaf geen bruikbare topics terug."

        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON-fout bij AI topics:", e)
        return [], f"JSON-fout: {e}"

    except Exception as e:
        print("AI-fout bij topic generation:", e)
        return [], f"Fout bij AI topic generation: {e}"


from typing import List, Dict, Tuple

# ==== AI-coach helpers voor notitieblok ====


def _build_course_context(course: dict, notes_data: dict, max_chars: int = 9000) -> str:
    """
    Bouw een compacte context-string met info over:
    - vaknaam, tag, examendatum
    - topics, oefenvragen, blokken
    - notitiemappen + (bijna) volledige inhoud
    - lijst van geüploade bestanden
    """
    parts = []

    name = course.get("name", "Onbekend vak")
    tag = course.get("tag", "")
    exam_date = course.get("exam_date") or "Onbekend"
    parts.append(f"Vak: {name} ({tag}) – Examen: {exam_date}")

    # Geüploade bestanden (alleen namen, geen content)
    files = course.get("files") or []
    if files:
        parts.append("Geüploade bestanden: " + ", ".join(files))

    # Topics
    topics = course.get("topics") or []
    if topics:
        topics_str = "; ".join(topics[:30])
        parts.append(f"Topics/hoofdstukken: {topics_str}")

    # Oefenvragen (alleen de vraag-tekst)
    qa = course.get("qa") or []
    if qa:
        q_lines = []
        for item in qa[:40]:
            q_lines.append(f"- Vraag: {item.get('question')}")
        parts.append("Oefenvragen (alleen de vragen):\n" + "\n".join(q_lines))

    # Blokplanning
    blocks = course.get("blocks") or []
    if blocks:
        b_lines = []
        for b in blocks[:25]:
            b_lines.append(f"- {b.get('title')} ({b.get('when','?')} · {b.get('duration','?')})")
        parts.append("Blokplanning:\n" + "\n".join(b_lines))

    # Notities: map + titel + vrij lange inhoud
    if isinstance(notes_data, dict):
        folders = notes_data.get("folders") or []
        note_blocks = []
        for f in folders:
            fname = f.get("name", "Map")
            for n in (f.get("notes") or []):
                title = n.get("title", "Notitie")
                content = (n.get("content") or "").replace("\r", " ")
                # per notitie best wat meer tekst, maar niet oneindig
                if len(content) > 700:
                    content = content[:700] + "..."
                note_blocks.append(
                    f"[MAP: {fname}] TITEL: {title}\nINHOUD:\n{content}"
                )
        if note_blocks:
            parts.append("Notities van de student (per map en document):\n\n" + "\n\n---\n\n".join(note_blocks))

    context = "\n\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n(… context ingekort …)"
    return context


def chat_with_course_assistant(
    course: dict,
    notes_data: dict,
    history: List[Dict[str, str]],
    user_message: str,
    max_history: int = 10,
) -> Tuple[str, List[Dict[str, str]], str]:
    """
    Eén chat-turn met de vak-coach.

    LET OP:
    - In app.py voegen we het nieuwste user-bericht al toe aan history.
    - Hier nemen we die history enkel tekstueel mee en voegen we ALLEEN
      het assistant-antwoord toe aan de nieuwe history.
    """
    # 1) Context over het vak + notities
    context = _build_course_context(course, notes_data)

    # 2) Geschiedenis als tekst (laatste N berichten)
    trimmed_history = history[-(max_history * 2):]
    history_lines = []
    for msg in trimmed_history:
        role = msg.get("role", "user")
        prefix = "Student" if role == "user" else "Coach"
        history_lines.append(f"{prefix}: {msg.get('content','')}")

    history_text = "\n".join(history_lines) if history_lines else "(nog geen vorig gesprek)"

    # 3) Systeem-instructie
    name = course.get("name", "dit vak")
    system_text = (
        "Je bent een rustige, duidelijke AI-study coach voor het vak "
        f"'{name}'. Je helpt de student dit vak te begrijpen, legt dingen "
        "uit in eenvoudige taal en verwijst naar hun eigen topics, vragen, "
        "blokplanning en notities waar relevant.\n\n"
        "Belangrijke richtlijnen:\n"
        "- Geef concrete inhoudelijke uitleg, geen vage motivatiespeeches.\n"
        "- Verwijs naar het examen en planning als dat helpt.\n"
        "- Als iets niet in de context zit, zeg dat eerlijk en antwoord dan met algemene kennis.\n"
        "- Antwoord in het Nederlands, tenzij de vraag duidelijk in een andere taal is.\n"
        "- Houd antwoorden compact maar duidelijk."
    )

    # 4) Prompt opbouwen als ÉÉN tekst (zoals je andere werkende functies)
    prompt = (
        system_text
        + "\n\n--- CONTEXT OVER DIT VAK ---\n"
        + context
        + "\n\n--- VORIG GESPREK ---\n"
        + history_text
        + "\n\n--- NIEUWE VRAAG VAN DE STUDENT ---\n"
        + user_message
        + "\n\nGeef nu één duidelijk, beknopt antwoord als de vak-coach."
    )

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",   # zelfde model als in je andere functies
            input=prompt,
        )
        # Zelfde manier als generate_questions / test_ai
        reply_text = resp.output_text.strip()
        error_text = ""
    except Exception as e:
        reply_text = "Er ging iets mis bij het genereren van een antwoord."
        error_text = str(e)
        print("AI CHAT ERROR:", e)  # => zie je in de terminal

    # 5) History: we gaan ervan uit dat history het user-bericht al bevat.
    # We voegen dus alleen het assistant-antwoord toe.
    new_history = trimmed_history + [
        {"role": "assistant", "content": reply_text},
    ]

    return reply_text, new_history, error_text
def generate_exam_for_course(
    course: dict,
    notes_data: dict,
    num_questions: int = 10
) -> Tuple[List[Dict], str]:
    """
    Genereer een examenset (mix van multiple choice + open vragen)
    op basis van:
      - course (topics, qa, blocks, summaries...)
      - notes_data (notitie-mappen + inhoud)

    Output:
      - (questions_list, error_text)
      - questions_list is een lijst van dicts met structuur:

        {
          "type": "mc" of "open",
          "question": "vraagtekst",
          "options": ["optie A", "optie B", ...],      # alleen bij type == "mc"
          "correct_option_index": 1,                   # index in 'options'
          "model_answer": "modelantwoord / oplossing",
          "explanation": "korte uitleg"
        }
    """

    # Bouw compacte context over het vak (hergebruik helper)
    try:
        context = _build_course_context(course, notes_data, max_chars=6000)
    except Exception:
        context = ""

    course_name = course.get("name", "Onbekend vak")
    exam_date = course.get("exam_date") or "Onbekend"

    prompt = f"""
Je bent een docent aan een hogeschool. Je maakt examen-vragen voor het vak "{course_name}".

Hieronder heb je context over het vak, inclusief topics, oefenvragen, blokplanning en notities:

---------------- CONTEXT ----------------
{context}
-----------------------------------------

Opdracht:
- Genereer een examen met in totaal {num_questions} vragen.
- Mix:
  - multiple choice vragen (minstens de helft)
  - open vragen (kort open antwoord)
- Niveau: realistisch hogeschool-examen (niet kinderachtig, maar ook niet onhaalbaar).
- Zorg dat de vragen netjes de leerstof dekken die in de context staat.

BELANGRIJK:
- Geef je antwoord in ÉÉN geldig JSON-object, zonder extra tekst, zonder markdown.
- Structuur EXACT als volgt:

{{
  "questions": [
    {{
      "type": "mc",
      "question": "Volledige vraagtekst hier",
      "options": [
        "Antwoordoptie A",
        "Antwoordoptie B",
        "Antwoordoptie C",
        "Antwoordoptie D"
      ],
      "correct_option_index": 1,
      "model_answer": "Korte uitleg waarom dit het juiste antwoord is.",
      "explanation": "Extra toelichting (optioneel, mag gelijk zijn aan model_answer)."
    }},
    {{
      "type": "open",
      "question": "Open vraag hier",
      "options": [],
      "correct_option_index": -1,
      "model_answer": "Kort modelantwoord of kernpunten die verwacht worden.",
      "explanation": "Korte uitleg van de oplossing."
    }}
  ]
}}

Regels:
- 'questions' is altijd een lijst.
- 'type' is ALTIJD ofwel "mc" ofwel "open".
- Bij type "mc":
  - 'options' moet minstens 3 en maximaal 6 opties bevatten.
  - 'correct_option_index' is de 0-based index van het juiste antwoord in 'options'.
- Bij type "open":
  - 'options' is een lege lijst [].
  - 'correct_option_index' = -1.
- 'model_answer' is wat de docent ongeveer zou verwachten.
- Gebruik gewone dubbele aanhalingstekens in de JSON.
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        raw = resp.output_text.strip()
        print("AI raw JSON voor examen:", raw)

        data = json.loads(raw)
        questions = data.get("questions", [])
        if not isinstance(questions, list):
            return [], "AI antwoordde geen lijst onder 'questions'."

        cleaned: List[Dict] = []
        for q in questions:
            if not isinstance(q, dict):
                continue

            qtype = (q.get("type") or "").strip().lower()
            question_text = (q.get("question") or "").strip()
            model_answer = (q.get("model_answer") or "").strip()
            explanation = (q.get("explanation") or "").strip()

            if not question_text:
                continue

            if qtype == "mc":
                options = q.get("options") or []
                if not isinstance(options, list) or len(options) < 2:
                    continue
                options = [str(o).strip() for o in options if str(o).strip()]
                if not options:
                    continue
                try:
                    ci = int(q.get("correct_option_index", 0))
                except Exception:
                    ci = 0
                if ci < 0 or ci >= len(options):
                    ci = 0

                cleaned.append({
                    "type": "mc",
                    "question": question_text,
                    "options": options,
                    "correct_option_index": ci,
                    "model_answer": model_answer or f"Correct antwoord: {options[ci]}",
                    "explanation": explanation or model_answer or ""
                })

            else:
                # open vraag (fallback als type onbekend)
                cleaned.append({
                    "type": "open",
                    "question": question_text,
                    "options": [],
                    "correct_option_index": -1,
                    "model_answer": model_answer or "",
                    "explanation": explanation or ""
                })

        if not cleaned:
            return [], "AI gaf geen bruikbare examenvragen terug."

        # trim op max num_questions
        cleaned = cleaned[:num_questions]
        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON-fout bij AI examen:", e)
        return [], f"JSON-fout bij het parsen van het examen: {e}"

    except Exception as e:
        print("AI-fout bij examen genereren:", e)
        return [], f"Er ging iets mis bij het genereren van het examen: {e}"

def extract_text_from_pdf(filepath):
    """
    Leest simpele tekst uit een PDF bestand via PyPDF2.
    (Niet perfect, maar genoeg voor onze MVP.)
    """
    try:
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    text += "\n" + txt
        return text
    except Exception as e:
        print("PDF extract error:", e)
        return ""


def generate_study_blocks_for_course(course, max_blocks=8):
    """
    Laat de AI een studieplanning maken (studieblokken) voor één vak.

    Input: course = dict met minstens:
      - "name"
      - "topics" (lijst, mag leeg zijn)
      - "exam_date" (YYYY-MM-DD, mag leeg zijn)

    Retourneert: (blocks_list, error_text)
      - blocks_list = lijst van dicts met keys: 'title', 'duration', 'when'
      - error_text = None als ok, anders foutstring
    """

    course_name = course.get("name", "dit vak")
    topics = course.get("topics") or []
    exam_date_str = course.get("exam_date", "").strip()

    if topics:
        topics_text = "\n".join(f"- {t}" for t in topics)
    else:
        topics_text = "- Geen specifieke topics. Verdeel de leerstof in logische blokken."

    days_left = None
    if exam_date_str:
        try:
            exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
            days_left = (exam_date - date.today()).days
        except Exception:
            pass

    if days_left is None:
        days_info = "Er is geen geldige examendatum ingesteld."
    else:
        days_info = f"Er zijn nog ongeveer {days_left} dagen tot het examen."

    prompt = f"""
Je bent een studieplanner in de app Study OS.

Vak: "{course_name}"

Topics / hoofdstukken:
{topics_text}

Info over examen:
- {days_info}

Opdracht:
- Maak een eenvoudige maar realistische studieplanning in maximaal {max_blocks} blokken.
- Elk blok is een concreet stukje werk (bijv. "Hoofdstuk 3 lezen", "Oefenvragen zenuwstelsel").
- Verdeel de blokken verspreid in de tijd (bijv. vandaag, morgen, later deze week, enz.).
- Houd de duur tussen 20 en 60 minuten.

BELANGRIJK:
- Antwoord in ÉÉN geldig JSON-object, zonder extra uitleg, zonder markdown.
- Structuur van de JSON is precies:

{{
  "blocks": [
    {{
      "title": "Korte titel van het studieblok",
      "duration": "30 min",
      "when": "Vandaag"
    }},
    {{
      "title": "Volgend blok",
      "duration": "40 min",
      "when": "Morgen"
    }}
  ]
}}

Regels voor 'when':
- Gebruik korte Nederlandse labels zoals "Vandaag", "Morgen", "Binnen 2 dagen",
  "Volgende week", "Laatste herhaling", ...
- Schrijf GEEN exacte datums, alleen woorden/labels.
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor study blocks:", raw)

        data = json.loads(raw)
        blocks = data.get("blocks", [])

        if not isinstance(blocks, list):
            return [], "AI gaf geen lijst bij 'blocks'."

        cleaned = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            title = (b.get("title") or "").strip()
            duration = (b.get("duration") or "").strip()
            when = (b.get("when") or "").strip()
            if title:
                cleaned.append(
                    {
                        "title": title,
                        "duration": duration or "30 min",
                        "when": when or "Ongepland",
                    }
                )

        if not cleaned:
            return [], "AI gaf geen bruikbare blokken terug."

        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON-fout bij AI study blocks:", e)
        return [], f"JSON-fout: {e}"

    except Exception as e:
        print("AI-fout bij study blocks:", e)
        return [], f"Fout bij AI study blocks: {e}"


def generate_summaries_for_topics(course, max_topics=8):
    """
    Genereer korte samenvattingen per topic voor één vak.

    Input: course = dict met minstens:
      - "name"
      - "topics" (lijst van strings)

    Retourneert: (summaries_list, error_text)
      - summaries_list = lijst van dicts: {"topic": "...", "summary": "..."}
      - error_text = None als ok, anders foutstring
    """

    course_name = course.get("name", "dit vak")
    topics = course.get("topics") or []

    if not topics:
        return [], "Geen topics beschikbaar om samen te vatten."

    topics = topics[:max_topics]
    topics_text = "\n".join(f"- {t}" for t in topics)

    prompt = f"""
Je bent een studie-assistent in Study OS.

Vak: "{course_name}"

Hier zijn de topics/hoofdstukken:
{topics_text}

Opdracht:
- Maak voor elk topic een korte, duidelijke samenvatting in het Nederlands.
- Schrijf in begrijpelijke taal (niveau eerstejaars student).
- Focus op de kern: wat moet je zeker begrijpen/onthouden per topic?

BELANGRIJK:
- Antwoord in ÉÉN geldig JSON-object, zonder extra tekst, zonder markdown.
- Structuur exact als:

{{
  "summaries": [
    {{
      "topic": "Naam van het topic 1 (exact of bijna exact zoals hierboven)",
      "summary": "Korte, duidelijke samenvatting van topic 1 in 2–4 zinnen."
    }},
    {{
      "topic": "Naam van topic 2",
      "summary": "Samenvatting van topic 2"
    }}
  ]
}}
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor topic-summaries:", raw)

        data = json.loads(raw)
        items = data.get("summaries", [])

        if not isinstance(items, list):
            return [], "AI gaf geen lijst bij 'summaries'."

        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            topic = (item.get("topic") or "").strip()
            summary = (item.get("summary") or "").strip()
            if topic and summary:
                cleaned.append({"topic": topic, "summary": summary})

        if not cleaned:
            return [], "AI gaf geen bruikbare samenvattingen terug."

        return cleaned, None

    except json.JSONDecodeError as e:
        print("JSON-fout bij AI topic-summaries:", e)
        return [], f"JSON-fout: {e}"

    except Exception as e:
        print("AI-fout bij topic-summaries:", e)
        return [], f"Fout bij AI topic-summaries: {e}"


def generate_answer_feedback(question_text: str, model_answer: str, user_answer: str) -> str:
    """
    Geef vriendelijke, duidelijke feedback op het antwoord van de student.

    Input:
      - question_text: de oefenvraag
      - model_answer: het beoogde modelantwoord
      - user_answer: wat de student heeft ingevuld

    Output:
      - Een tekst (Nederlands) met feedback en tips.
    """

    prompt = f"""
Je bent een vriendelijke studiecoach in de app Study OS.

Dit is de vraag:
"{question_text}"

Modelantwoord (referentie):
"{model_answer}"

Antwoord van de student:
"{user_answer}"

Opdracht:
- Vergelijk het antwoord van de student met het modelantwoord.
- Geef korte, duidelijke feedback in het Nederlands.
- Structuur:
  1. Korte beoordeling (klopt grotendeels / deels / mist belangrijke zaken)
  2. Waar het antwoord goed is
  3. Wat er nog ontbreekt of fout is
  4. Eventueel een verbeterde voorbeeldformulering (1–3 zinnen)

Schrijf in informele maar respectvolle toon, alsof je een medestudent bent die goed kan uitleggen.
Geen JSON, geen lijst met bulletpoints, gewoon normale lopende tekst.
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        text = resp.output_text.strip()
        return text
    except Exception as e:
        print("AI-fout bij answer feedback:", e)
        return f"Er ging iets mis bij het genereren van feedback: {e}"

def generate_structured_data_from_pdf(course_name: str, extracted_text: str, max_topics: int = 12):
    """
    Neemt pure tekst van een PDF en genereert:
    - topics
    - samenvatting
    - kernbegrippen (key concepts)

    Retourneert: (topics_list, summary_text, concepts_list, error)
    """

    if not extracted_text.strip():
        return [], "", [], "Geen tekst gevonden in PDF."

    prompt = f"""
Je bent een AI-studieassistent in Study OS.

Vak: "{course_name}"

Hieronder staat de volledige tekst van een geüploade cursus (PDF):

----------------------  
{extracted_text[:6000]}  
----------------------

Genereer de volgende elementen:

1. Een lijst met maximaal {max_topics} topics / hoofdstukken.
2. Een korte samenvatting van maximaal 6 alinea's.
3. Een lijst van 10-20 kernbegrippen (key concepts) die centraal staan in dit vak.

BELANGRIJK:
- Antwoord in ÉÉN geldig JSON-object, zonder extra tekst.
- Structuur EXACT zo:

{{
  "topics": ["...", "..."],
  "summary": "Korte samenvatting hier...",
  "concepts": ["...", "..."]
}}
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        raw = resp.output_text.strip()
        print("AI raw JSON voor PDF:", raw)

        data = json.loads(raw)

        topics = data.get("topics", [])
        summary = data.get("summary", "")
        concepts = data.get("concepts", [])

        return topics, summary, concepts, None

    except Exception as e:
        print("AI-fout PDF:", e)
        return [], "", [], f"AI-fout: {e}"