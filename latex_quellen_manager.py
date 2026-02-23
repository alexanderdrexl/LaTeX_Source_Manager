"""
LaTeX Quellen Manager - Web Edition
Erstellt von: Alex Drexl
Version: 4.1

Startet einen lokalen Flask-Webserver und öffnet den Browser automatisch.
"""

import os
import sys
import re
import json
import unicodedata
import threading
import subprocess
import webbrowser
import datetime
import pathlib
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response

# ---------------------------------------------------------------------------
# Pfad-Konfiguration
# ---------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).parent.resolve()
SETTINGS_FILE = BASE_DIR / "bibtex_generator_settings.json"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR))

# ---------------------------------------------------------------------------
# Standard-Einstellungen
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "target_directory": "",
    "latex_main_path": "",
    "last_entry_type": "online",
    "add_date_comment": True,
    "auto_open_browser": True,
    "port": 5000,
    "bib_placement_sections": [
        {"id": "s1", "label": "Bücher", "search_text": "% Bücher", "active": False},
        {"id": "s2", "label": "Online-Quellen", "search_text": "% Online-Quellen", "active": False},
        {"id": "s3", "label": "Artikel & Zeitschriften", "search_text": "% Artikel", "active": False},
        {"id": "s4", "label": "Berichte & Normen", "search_text": "% Berichte", "active": False},
        {"id": "s5", "label": "Sonstiges", "search_text": "% Sonstiges", "active": False},
    ],
    "default_section_id": "",
    "addbibresource_placement": {
        "enabled": False,
        "search_text": "% Literaturverzeichnis",
        "after_last_existing": True,
    },
}

# ---------------------------------------------------------------------------
# Alle BibTeX-Eintragstypen (Deutsch) mit ihren Feldern
# ---------------------------------------------------------------------------
ENTRY_TYPES = {
    "online": {
        "label": "Online-Quelle / Website",
        "icon": "bi-globe",
        "fields": [
            {"key": "author",       "label": "Autor(en)",              "required": True,  "placeholder": "Nachname, Vorname and Nachname2, Vorname2"},
            {"key": "title",        "label": "Titel",                  "required": True,  "placeholder": "Titel der Webseite"},
            {"key": "url",          "label": "URL",                    "required": True,  "placeholder": "https://..."},
            {"key": "urldate",      "label": "Abrufdatum",             "required": True,  "placeholder": "JJJJ-MM-TT", "type": "date"},
            {"key": "date",         "label": "Veröffentlichungsdatum", "required": False, "placeholder": "JJJJ oder JJJJ-MM-TT", "type": "date"},
            {"key": "organization", "label": "Organisation / Betreiber","required": False, "placeholder": "Name der Organisation"},
            {"key": "subtitle",     "label": "Untertitel",             "required": False, "placeholder": "Optionaler Untertitel"},
            {"key": "note",         "label": "Anmerkung",              "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "book": {
        "label": "Buch (Monographie)",
        "icon": "bi-book",
        "fields": [
            {"key": "author",    "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",     "label": "Titel",              "required": True,  "placeholder": "Buchtitel"},
            {"key": "publisher", "label": "Verlag",             "required": True,  "placeholder": "Verlagsname"},
            {"key": "date",      "label": "Erscheinungsjahr",   "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "location",  "label": "Erscheinungsort",    "required": False, "placeholder": "Stadt"},
            {"key": "edition",   "label": "Auflage",            "required": False, "placeholder": "z.B. 3 oder Dritte"},
            {"key": "isbn",      "label": "ISBN",               "required": False, "placeholder": "978-3-..."},
            {"key": "series",    "label": "Schriftenreihe",     "required": False, "placeholder": "Name der Reihe"},
            {"key": "volume",    "label": "Band",               "required": False, "placeholder": "Bandnummer"},
            {"key": "subtitle",  "label": "Untertitel",         "required": False, "placeholder": "Optionaler Untertitel"},
            {"key": "editor",    "label": "Herausgeber",        "required": False, "placeholder": "Nur wenn kein Autor"},
            {"key": "note",      "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "article": {
        "label": "Zeitschriftenartikel",
        "icon": "bi-journal-text",
        "fields": [
            {"key": "author",   "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",    "label": "Titel des Artikels", "required": True,  "placeholder": "Artikeltitel"},
            {"key": "journal",  "label": "Zeitschrift",        "required": True,  "placeholder": "Name der Zeitschrift"},
            {"key": "date",     "label": "Erscheinungsjahr",   "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "volume",   "label": "Jahrgang / Band",    "required": False, "placeholder": "z.B. 42"},
            {"key": "number",   "label": "Heft / Ausgabe",     "required": False, "placeholder": "z.B. 3"},
            {"key": "pages",    "label": "Seiten",             "required": False, "placeholder": "z.B. 123--145"},
            {"key": "doi",      "label": "DOI",                "required": False, "placeholder": "10.xxxx/xxxxx"},
            {"key": "issn",     "label": "ISSN",               "required": False, "placeholder": "XXXX-XXXX"},
            {"key": "url",      "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "subtitle", "label": "Untertitel",         "required": False, "placeholder": "Optionaler Untertitel"},
            {"key": "note",     "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "inbook": {
        "label": "Buchkapitel",
        "icon": "bi-bookmark",
        "fields": [
            {"key": "author",    "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",     "label": "Titel des Kapitels", "required": True,  "placeholder": "Kapiteltitel"},
            {"key": "booktitle", "label": "Buchtitel",          "required": True,  "placeholder": "Titel des Gesamtwerks"},
            {"key": "publisher", "label": "Verlag",             "required": True,  "placeholder": "Verlagsname"},
            {"key": "date",      "label": "Erscheinungsjahr",   "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "pages",     "label": "Seiten",             "required": False, "placeholder": "z.B. 123--145"},
            {"key": "chapter",   "label": "Kapitel-Nr.",        "required": False, "placeholder": "z.B. 5"},
            {"key": "editor",    "label": "Herausgeber",        "required": False, "placeholder": "Nachname, Vorname"},
            {"key": "location",  "label": "Erscheinungsort",    "required": False, "placeholder": "Stadt"},
            {"key": "edition",   "label": "Auflage",            "required": False, "placeholder": "z.B. 2"},
            {"key": "isbn",      "label": "ISBN",               "required": False, "placeholder": "978-3-..."},
            {"key": "note",      "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "incollection": {
        "label": "Beitrag in Sammelwerk",
        "icon": "bi-collection",
        "fields": [
            {"key": "author",    "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",     "label": "Titel des Beitrags","required": True,  "placeholder": "Beitragstitel"},
            {"key": "booktitle", "label": "Titel des Sammelwerks","required": True,"placeholder": "Sammelwerkstitel"},
            {"key": "editor",    "label": "Herausgeber",        "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "publisher", "label": "Verlag",             "required": True,  "placeholder": "Verlagsname"},
            {"key": "date",      "label": "Erscheinungsjahr",   "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "pages",     "label": "Seiten",             "required": False, "placeholder": "z.B. 45--67"},
            {"key": "location",  "label": "Erscheinungsort",    "required": False, "placeholder": "Stadt"},
            {"key": "isbn",      "label": "ISBN",               "required": False, "placeholder": "978-3-..."},
            {"key": "note",      "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "inproceedings": {
        "label": "Konferenzbeitrag",
        "icon": "bi-people",
        "fields": [
            {"key": "author",       "label": "Autor(en)",           "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",        "label": "Titel des Beitrags",  "required": True,  "placeholder": "Vortragstitel"},
            {"key": "booktitle",    "label": "Name der Konferenz",  "required": True,  "placeholder": "Proceedings of ..."},
            {"key": "date",         "label": "Jahr",                "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "pages",        "label": "Seiten",              "required": False, "placeholder": "z.B. 10--18"},
            {"key": "editor",       "label": "Herausgeber",         "required": False, "placeholder": "Nachname, Vorname"},
            {"key": "publisher",    "label": "Verlag",              "required": False, "placeholder": "Verlagsname"},
            {"key": "location",     "label": "Veranstaltungsort",   "required": False, "placeholder": "Stadt, Land"},
            {"key": "organization", "label": "Veranstalter",        "required": False, "placeholder": "Name der Organisation"},
            {"key": "doi",          "label": "DOI",                 "required": False, "placeholder": "10.xxxx/xxxxx"},
            {"key": "isbn",         "label": "ISBN",                "required": False, "placeholder": "978-3-..."},
            {"key": "note",         "label": "Anmerkung",           "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "proceedings": {
        "label": "Konferenzband",
        "icon": "bi-journals",
        "fields": [
            {"key": "title",        "label": "Titel des Tagungsbands","required": True,  "placeholder": "Proceedings of ..."},
            {"key": "editor",       "label": "Herausgeber",           "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "date",         "label": "Jahr",                  "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "publisher",    "label": "Verlag",                "required": False, "placeholder": "Verlagsname"},
            {"key": "location",     "label": "Erscheinungsort",       "required": False, "placeholder": "Stadt"},
            {"key": "organization", "label": "Veranstalter",          "required": False, "placeholder": "Name der Organisation"},
            {"key": "isbn",         "label": "ISBN",                  "required": False, "placeholder": "978-3-..."},
            {"key": "note",         "label": "Anmerkung",             "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "techreport": {
        "label": "Technischer Bericht",
        "icon": "bi-file-earmark-text",
        "fields": [
            {"key": "author",      "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel",              "required": True,  "placeholder": "Berichtstitel"},
            {"key": "institution", "label": "Institution",        "required": True,  "placeholder": "Name der Institution"},
            {"key": "date",        "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "type",        "label": "Berichtstyp",        "required": False, "placeholder": "z.B. Technical Report"},
            {"key": "number",      "label": "Berichtsnummer",     "required": False, "placeholder": "z.B. TR-2024-001"},
            {"key": "location",    "label": "Ort",                "required": False, "placeholder": "Stadt"},
            {"key": "url",         "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",        "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "report": {
        "label": "Bericht / Forschungsbericht",
        "icon": "bi-clipboard-data",
        "fields": [
            {"key": "author",      "label": "Autor(en)",          "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel",              "required": True,  "placeholder": "Berichtstitel"},
            {"key": "institution", "label": "Institution",        "required": True,  "placeholder": "Name der Institution"},
            {"key": "date",        "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "type",        "label": "Berichtsart",        "required": False, "placeholder": "z.B. Forschungsbericht"},
            {"key": "number",      "label": "Berichtsnummer",     "required": False, "placeholder": "z.B. 2024/01"},
            {"key": "location",    "label": "Ort",                "required": False, "placeholder": "Stadt"},
            {"key": "url",         "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",        "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "mastersthesis": {
        "label": "Masterarbeit",
        "icon": "bi-mortarboard",
        "fields": [
            {"key": "author",      "label": "Autor",              "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel",              "required": True,  "placeholder": "Titel der Masterarbeit"},
            {"key": "institution", "label": "Hochschule",         "required": True,  "placeholder": "Name der Hochschule"},
            {"key": "date",        "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "location",    "label": "Ort",                "required": False, "placeholder": "Ort der Hochschule"},
            {"key": "type",        "label": "Typ",                "required": False, "placeholder": "Masterarbeit"},
            {"key": "url",         "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",        "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "phdthesis": {
        "label": "Dissertation / Doktorarbeit",
        "icon": "bi-award",
        "fields": [
            {"key": "author",      "label": "Autor",              "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel",              "required": True,  "placeholder": "Titel der Dissertation"},
            {"key": "institution", "label": "Universität",        "required": True,  "placeholder": "Name der Universität"},
            {"key": "date",        "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "location",    "label": "Ort",                "required": False, "placeholder": "Ort der Universität"},
            {"key": "url",         "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "doi",         "label": "DOI",                "required": False, "placeholder": "10.xxxx/xxxxx"},
            {"key": "note",        "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "thesis": {
        "label": "Abschlussarbeit (allgemein)",
        "icon": "bi-file-earmark-ruled",
        "fields": [
            {"key": "author",      "label": "Autor",              "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel",              "required": True,  "placeholder": "Titel der Arbeit"},
            {"key": "institution", "label": "Hochschule",         "required": True,  "placeholder": "Name der Hochschule"},
            {"key": "date",        "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "type",        "label": "Typ der Arbeit",     "required": True,  "placeholder": "z.B. Bachelorarbeit, Seminararbeit"},
            {"key": "location",    "label": "Ort",                "required": False, "placeholder": "Ort der Hochschule"},
            {"key": "url",         "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",        "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "manual": {
        "label": "Handbuch / Dokumentation",
        "icon": "bi-tools",
        "fields": [
            {"key": "title",        "label": "Titel",              "required": True,  "placeholder": "Name des Handbuchs"},
            {"key": "author",       "label": "Autor(en)",          "required": False, "placeholder": "Nachname, Vorname (optional)"},
            {"key": "organization", "label": "Organisation",       "required": False, "placeholder": "Hersteller / Verlag"},
            {"key": "date",         "label": "Jahr",               "required": False, "placeholder": "JJJJ", "type": "year"},
            {"key": "edition",      "label": "Version / Auflage",  "required": False, "placeholder": "z.B. 2.1"},
            {"key": "location",     "label": "Ort",                "required": False, "placeholder": "Stadt"},
            {"key": "url",          "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",         "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "standard": {
        "label": "Norm / Standard",
        "icon": "bi-patch-check",
        "fields": [
            {"key": "title",        "label": "Bezeichnung / Titel","required": True,  "placeholder": "z.B. DIN EN ISO 9001:2015"},
            {"key": "number",       "label": "Norm-Nummer",        "required": True,  "placeholder": "z.B. DIN EN ISO 9001"},
            {"key": "organization", "label": "Normungsgremium",    "required": True,  "placeholder": "z.B. DIN, ISO, IEEE"},
            {"key": "date",         "label": "Jahr",               "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "type",         "label": "Typ",                "required": False, "placeholder": "z.B. Norm, Richtlinie"},
            {"key": "location",     "label": "Erscheinungsort",    "required": False, "placeholder": "z.B. Berlin"},
            {"key": "url",          "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",         "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "patent": {
        "label": "Patent",
        "icon": "bi-lightbulb",
        "fields": [
            {"key": "author",    "label": "Erfinder",           "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",     "label": "Titel der Erfindung","required": True,  "placeholder": "Patentbezeichnung"},
            {"key": "number",    "label": "Patentnummer",       "required": True,  "placeholder": "z.B. EP1234567"},
            {"key": "date",      "label": "Anmeldedatum",       "required": True,  "placeholder": "JJJJ-MM-TT", "type": "date"},
            {"key": "location",  "label": "Land",               "required": False, "placeholder": "z.B. Deutschland"},
            {"key": "holder",    "label": "Patentinhaber",      "required": False, "placeholder": "Firma / Person"},
            {"key": "url",       "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",      "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "dataset": {
        "label": "Datensatz / Datenbank",
        "icon": "bi-database",
        "fields": [
            {"key": "author",      "label": "Autor(en) / Ersteller","required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",       "label": "Titel des Datensatzes","required": True,  "placeholder": "Datensatzbezeichnung"},
            {"key": "date",        "label": "Erscheinungsjahr",     "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "institution", "label": "Herausgebende Stelle", "required": False, "placeholder": "Organisation / Institut"},
            {"key": "url",         "label": "URL / DOI-Link",       "required": False, "placeholder": "https://..."},
            {"key": "doi",         "label": "DOI",                  "required": False, "placeholder": "10.xxxx/xxxxx"},
            {"key": "version",     "label": "Version",              "required": False, "placeholder": "z.B. 1.2"},
            {"key": "note",        "label": "Anmerkung",            "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "software": {
        "label": "Software / Programm",
        "icon": "bi-code-square",
        "fields": [
            {"key": "author",       "label": "Entwickler / Autor",  "required": True,  "placeholder": "Nachname, Vorname oder Org."},
            {"key": "title",        "label": "Programmname",        "required": True,  "placeholder": "Name der Software"},
            {"key": "date",         "label": "Jahr",                "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "version",      "label": "Version",             "required": False, "placeholder": "z.B. 3.4.1"},
            {"key": "organization", "label": "Unternehmen",         "required": False, "placeholder": "Herstellerfirma"},
            {"key": "url",          "label": "URL",                 "required": False, "placeholder": "https://..."},
            {"key": "howpublished", "label": "Vertrieb",            "required": False, "placeholder": "z.B. Open Source, Commercial"},
            {"key": "note",         "label": "Anmerkung",           "required": False, "placeholder": "Lizenz etc."},
        ]
    },
    "misc": {
        "label": "Sonstiges",
        "icon": "bi-three-dots",
        "fields": [
            {"key": "author",       "label": "Autor(en)",          "required": False, "placeholder": "Nachname, Vorname"},
            {"key": "title",        "label": "Titel",              "required": True,  "placeholder": "Bezeichnung"},
            {"key": "date",         "label": "Jahr",               "required": False, "placeholder": "JJJJ", "type": "year"},
            {"key": "howpublished", "label": "Veröffentlichungsart","required": False, "placeholder": "z.B. Broschüre, Poster"},
            {"key": "organization", "label": "Organisation",       "required": False, "placeholder": "Name der Organisation"},
            {"key": "url",          "label": "URL",                "required": False, "placeholder": "https://..."},
            {"key": "note",         "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "unpublished": {
        "label": "Unveröffentlichtes Werk",
        "icon": "bi-file-lock",
        "fields": [
            {"key": "author",  "label": "Autor(en)",   "required": True,  "placeholder": "Nachname, Vorname"},
            {"key": "title",   "label": "Titel",       "required": True,  "placeholder": "Titel des Werks"},
            {"key": "note",    "label": "Anmerkung",   "required": True,  "placeholder": "Pflichtfeld: Erläuterung (z.B. eingereicht bei ...)"},
            {"key": "date",    "label": "Jahr",        "required": False, "placeholder": "JJJJ", "type": "year"},
            {"key": "url",     "label": "URL",         "required": False, "placeholder": "https://..."},
        ]
    },
    "booklet": {
        "label": "Broschüre / Flugblatt",
        "icon": "bi-newspaper",
        "fields": [
            {"key": "title",        "label": "Titel",              "required": True,  "placeholder": "Titel der Broschüre"},
            {"key": "author",       "label": "Autor(en)",          "required": False, "placeholder": "Nachname, Vorname"},
            {"key": "howpublished", "label": "Veröffentlichungsart","required": False, "placeholder": "z.B. Flugblatt, Broschüre"},
            {"key": "date",         "label": "Jahr",               "required": False, "placeholder": "JJJJ", "type": "year"},
            {"key": "organization", "label": "Herausgeber",        "required": False, "placeholder": "Organisation"},
            {"key": "location",     "label": "Ort",                "required": False, "placeholder": "Stadt"},
            {"key": "note",         "label": "Anmerkung",          "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
    "periodical": {
        "label": "Periodikum / Zeitschrift (gesamte Ausgabe)",
        "icon": "bi-calendar3",
        "fields": [
            {"key": "title",   "label": "Titel der Zeitschrift", "required": True,  "placeholder": "Zeitschriftenname"},
            {"key": "editor",  "label": "Herausgeber",           "required": False, "placeholder": "Nachname, Vorname"},
            {"key": "date",    "label": "Jahr",                  "required": True,  "placeholder": "JJJJ", "type": "year"},
            {"key": "volume",  "label": "Jahrgang",              "required": False, "placeholder": "z.B. 12"},
            {"key": "number",  "label": "Ausgabe",               "required": False, "placeholder": "z.B. 4"},
            {"key": "issn",    "label": "ISSN",                  "required": False, "placeholder": "XXXX-XXXX"},
            {"key": "note",    "label": "Anmerkung",             "required": False, "placeholder": "Zusätzliche Hinweise"},
        ]
    },
}

# ---------------------------------------------------------------------------
# Einstellungsverwaltung
# ---------------------------------------------------------------------------
class SettingsManager:
    def __init__(self):
        self._data = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Deep merge: top level only für einfache Werte, sections ersetzen
                for k, v in stored.items():
                    self._data[k] = v
                # Fehlende Keys aus Defaults nachfüllen
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in self._data:
                        self._data[k] = v
            except Exception:
                pass

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def all(self):
        return dict(self._data)

    def update(self, data: dict):
        self._data.update(data)
        self.save()


settings = SettingsManager()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def normalize_string(text: str) -> str:
    """Normalisiert Text für Dateinamen & Zitierschlüssel."""
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue") \
               .replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue").replace("ß", "ss")
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def generate_cite_key(title: str, author: str = "", year: str = "") -> str:
    """Erzeugt einen BibTeX-Zitierschlüssel."""
    if not title and not author:
        return "quelle_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    base = normalize_string(title or author)
    key = re.sub(r"[^a-zA-Z0-9_]", "", base.replace(" ", "_"))
    key = re.sub(r"_+", "_", key).strip("_").lower()

    if year:
        yr = re.sub(r"[^0-9]", "", year)[:4]
        if yr:
            key = f"{key}_{yr}"

    return key[:60] if len(key) > 60 else key


def generate_filename(cite_key: str) -> str:
    """Erzeugt einen sauberen Dateinamen aus dem Zitierschlüssel."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "", cite_key) + ".bib"


def generate_bibtex(entry_type: str, fields: dict, cite_key: str) -> str:
    """Baut den vollständigen BibTeX-Eintrag als String zusammen."""
    lines = [f"@{entry_type}{{{cite_key},"]
    for k, v in fields.items():
        v = v.strip()
        if v:
            escaped = v.replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  {k:<14} = {{{escaped}}},")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flask-Routen
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/entry-types")
def get_entry_types():
    result = {}
    for key, val in ENTRY_TYPES.items():
        result[key] = {
            "label": val["label"],
            "icon": val["icon"],
            "fields": val["fields"],
        }
    return jsonify(result)


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(settings.all())


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(force=True)
    settings.update(data)
    return jsonify({"ok": True, "settings": settings.all()})


@app.route("/api/cite-key", methods=["POST"])
def api_cite_key():
    body = request.get_json(force=True)
    key = generate_cite_key(
        body.get("title", ""),
        body.get("author", ""),
        body.get("date", ""),
    )
    return jsonify({"cite_key": key, "filename": generate_filename(key)})


@app.route("/api/preview", methods=["POST"])
def api_preview():
    body = request.get_json(force=True)
    entry_type = body.get("entry_type", "misc")
    fields = body.get("fields", {})
    cite_key = body.get("cite_key", "")
    if not cite_key:
        cite_key = generate_cite_key(
            fields.get("title", ""),
            fields.get("author", ""),
            fields.get("date", ""),
        )
    bibtex = generate_bibtex(entry_type, fields, cite_key)
    return jsonify({"bibtex": bibtex, "cite_key": cite_key})


@app.route("/api/save", methods=["POST"])
def api_save():
    """Speichert die BibTeX-Datei und aktualisiert optional die LaTeX-Hauptdatei."""
    body = request.get_json(force=True)
    entry_type = body.get("entry_type", "misc")
    fields = body.get("fields", {})
    cite_key = body.get("cite_key", "")
    filename = body.get("filename", "")
    section_id = body.get("section_id", "")

    if not cite_key:
        cite_key = generate_cite_key(
            fields.get("title", ""),
            fields.get("author", ""),
            fields.get("date", ""),
        )
    if not filename:
        filename = generate_filename(cite_key)
    if not filename.endswith(".bib"):
        filename += ".bib"

    target_dir = pathlib.Path(settings.get("target_directory", ""))
    if not target_dir or not str(target_dir).strip():
        return jsonify({"ok": False, "error": "Kein Zielverzeichnis konfiguriert. Bitte in den Einstellungen festlegen."}), 400

    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / filename

    # BibTeX-Inhalt erzeugen
    bibtex = generate_bibtex(entry_type, fields, cite_key)

    # Datumskommentar
    add_date = settings.get("add_date_comment", True)
    if add_date:
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        comment = f"% Hinzugefügt am: {now_str}\n"

        # Abschnittskommentar
        if section_id:
            sections = settings.get("bib_placement_sections", [])
            sec = next((s for s in sections if s["id"] == section_id), None)
            if sec:
                comment += f"% Abschnitt: {sec['label']}\n"

        bibtex = comment + bibtex

    # Datei schreiben
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(bibtex)

    # LaTeX-Hauptdatei aktualisieren
    latex_updated = False
    latex_error = None
    latex_main = settings.get("latex_main_path", "")
    if latex_main and pathlib.Path(latex_main).exists():
        try:
            latex_updated, latex_error = update_latex_main(filepath, pathlib.Path(latex_main), section_id)
        except Exception as e:
            latex_error = str(e)

    return jsonify({
        "ok": True,
        "filepath": str(filepath),
        "cite_key": cite_key,
        "filename": filename,
        "latex_updated": latex_updated,
        "latex_error": latex_error,
    })


@app.route("/api/browse-directory", methods=["POST"])
def api_browse_directory():
    """Öffnet einen Systemdialog zur Verzeichnisauswahl (Windows)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Zielverzeichnis auswählen")
        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as e:
        return jsonify({"path": "", "error": str(e)})


@app.route("/api/browse-file", methods=["POST"])
def api_browse_file():
    """Öffnet einen Systemdialog zur Dateiauswahl (Windows)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="LaTeX-Hauptdatei auswählen",
            filetypes=[("LaTeX-Dateien", "*.tex"), ("Alle Dateien", "*.*")]
        )
        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as e:
        return jsonify({"path": "", "error": str(e)})


@app.route("/api/check-latex-sections", methods=["POST"])
def api_check_latex_sections():
    """Liest die Kommentar-Überschriften aus der LaTeX-Datei."""
    latex_main = settings.get("latex_main_path", "")
    if not latex_main or not pathlib.Path(latex_main).exists():
        return jsonify({"sections": [], "error": "LaTeX-Datei nicht gefunden"})
    try:
        with open(latex_main, "r", encoding="utf-8") as f:
            content = f.read()
        found = re.findall(r"^(%[^\n]+)", content, re.MULTILINE)
        return jsonify({"sections": found[:30]})
    except Exception as e:
        return jsonify({"sections": [], "error": str(e)})


@app.route("/api/history", methods=["GET"])
def api_history():
    """Gibt eine Liste aller .bib-Dateien im Zielverzeichnis zurück."""
    target_dir = pathlib.Path(settings.get("target_directory", ""))
    if not target_dir or not target_dir.exists():
        return jsonify({"files": []})
    files = []
    for f in sorted(target_dir.glob("*.bib"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                "size": stat.st_size,
            })
        except Exception:
            pass
    return jsonify({"files": files[:50]})


@app.route("/api/file-content", methods=["POST"])
def api_file_content():
    """Gibt den Inhalt einer .bib-Datei zurück."""
    body = request.get_json(force=True)
    filepath = body.get("path", "")
    try:
        p = pathlib.Path(filepath)
        # Sicherheitscheck: nur innerhalb des Zielverzeichnisses
        target_dir = pathlib.Path(settings.get("target_directory", ""))
        if target_dir and target_dir.exists():
            p.relative_to(target_dir)
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"content": "", "error": str(e)})


# ---------------------------------------------------------------------------
# BibTeX-Parser (für Bibliotheks-Ansicht)
# ---------------------------------------------------------------------------
def parse_bib_entry(content: str) -> dict:
    """Parsed den ersten @type{key,...} Block aus einem BibTeX-String."""
    entry = {"type": "", "key": "", "title": "", "author": "", "year": "",
             "publisher": "", "isbn": "", "url": "", "doi": "", "journal": "", "fields": {}}
    m = re.search(r"@(\w+)\s*\{([^,]+),", content)
    if m:
        entry["type"] = m.group(1).lower()
        entry["key"]  = m.group(2).strip()

    for field_m in re.finditer(r"^\s*(\w+)\s*=\s*\{([^}]*)\}", content, re.MULTILINE):
        k = field_m.group(1).lower()
        v = field_m.group(2).strip()
        entry["fields"][k] = v
        if k in ("title", "author", "date", "year", "publisher", "isbn", "url", "doi", "journal"):
            entry[k] = v

    # Jahr aus date extrahieren wenn nötig
    if not entry["year"] and entry.get("date"):
        yr = re.match(r"(\d{4})", entry["date"])
        if yr:
            entry["year"] = yr.group(1)

    return entry


@app.route("/api/library", methods=["GET"])
def api_library():
    """Gibt alle .bib-Dateien mit geparsten Metadaten zurück."""
    target_dir = pathlib.Path(settings.get("target_directory", ""))
    if not target_dir or not target_dir.exists():
        return jsonify({"files": []})

    files = []
    for f in sorted(target_dir.glob("*.bib"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            stat = f.stat()
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            entry = parse_bib_entry(content)
            files.append({
                "name":     f.name,
                "path":     str(f),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                "size":     stat.st_size,
                "type":     entry["type"],
                "key":      entry["key"],
                "title":    entry["title"],
                "author":   entry["author"],
                "year":     entry["year"],
                "publisher":entry["publisher"],
                "isbn":     entry["isbn"],
                "url":      entry["url"],
                "doi":      entry["doi"],
                "journal":  entry["journal"],
            })
        except Exception:
            pass

    return jsonify({"files": files})


@app.route("/api/bib/save-edit", methods=["POST"])
def api_bib_save_edit():
    """Speichert den bearbeiteten Inhalt einer .bib-Datei."""
    body = request.get_json(force=True)
    filepath = body.get("path", "")
    content  = body.get("content", "")
    try:
        p = pathlib.Path(filepath)
        target_dir = pathlib.Path(settings.get("target_directory", ""))
        if target_dir and target_dir.exists():
            p.relative_to(target_dir)  # Sicherheitscheck
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/bib/delete", methods=["POST"])
def api_bib_delete():
    """Löscht eine .bib-Datei und entfernt \\addbibresource aus der .tex-Datei."""
    body = request.get_json(force=True)
    filepath = body.get("path", "")
    try:
        p = pathlib.Path(filepath)
        target_dir = pathlib.Path(settings.get("target_directory", ""))
        if target_dir and target_dir.exists():
            p.relative_to(target_dir)  # Sicherheitscheck
        bib_filename = p.name
        p.unlink()

        # Automatisch aus LaTeX-Hauptdatei entfernen
        tex_removed = False
        tex_error   = None
        latex_main  = settings.get("latex_main_path", "")
        if latex_main and pathlib.Path(latex_main).exists():
            tex_removed, tex_error = remove_from_latex_main(
                bib_filename, pathlib.Path(latex_main)
            )

        return jsonify({"ok": True, "tex_removed": tex_removed, "tex_error": tex_error})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/bib/rename", methods=["POST"])
def api_bib_rename():
    """Benennt eine .bib-Datei um."""
    body = request.get_json(force=True)
    filepath = body.get("path", "")
    new_name = body.get("new_name", "").strip()
    try:
        if not new_name:
            return jsonify({"ok": False, "error": "Kein neuer Name angegeben."})
        if not new_name.endswith(".bib"):
            new_name += ".bib"
        # Nur erlaubte Zeichen
        if re.search(r'[<>:"/\\|?*]', new_name):
            return jsonify({"ok": False, "error": "Ungültige Zeichen im Dateinamen."})
        p = pathlib.Path(filepath)
        target_dir = pathlib.Path(settings.get("target_directory", ""))
        if target_dir and target_dir.exists():
            p.relative_to(target_dir)  # Sicherheitscheck
        new_path = p.parent / new_name
        if new_path.exists():
            return jsonify({"ok": False, "error": f"Datei '{new_name}' existiert bereits."})
        p.rename(new_path)
        return jsonify({"ok": True, "new_path": str(new_path), "new_name": new_name})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ---------------------------------------------------------------------------
# LaTeX-Datei-Integration
# ---------------------------------------------------------------------------
def remove_from_latex_main(bib_filename: str, latex_path: pathlib.Path) -> tuple:
    """
    Entfernt die \\addbibresource{...filename.bib}-Zeile sauber aus der .tex-Datei.
    Gibt (True, None) bei Erfolg oder (False, Fehlermeldung) zurück.
    """
    try:
        with open(latex_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        for line in lines:
            # Entfernen wenn die Zeile \addbibresource enthält UND den Dateinamen
            if r"\addbibresource" in line and bib_filename in line:
                found = True
                # Zeile überspringen (nicht in new_lines aufnehmen)
            else:
                new_lines.append(line)

        if not found:
            return False, f"'{bib_filename}' nicht in LaTeX-Datei gefunden."

        # Mehr als 2 aufeinanderfolgende Leerzeilen → maximal 1 Leerzeile
        cleaned = []
        blank_count = 0
        for line in new_lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 1:
                    cleaned.append(line)
            else:
                blank_count = 0
                cleaned.append(line)

        with open(latex_path, "w", encoding="utf-8") as f:
            f.writelines(cleaned)

        return True, None
    except Exception as e:
        return False, str(e)


def update_latex_main(bib_filepath: pathlib.Path, latex_path: pathlib.Path, section_id: str = "") -> tuple:
    """
    Fügt \\addbibresource{...} in die LaTeX-Hauptdatei ein.
    Gibt (True, None) bei Erfolg oder (False, Fehlermeldung) zurück.
    """
    with open(latex_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Relativen Pfad berechnen
    try:
        rel = bib_filepath.relative_to(latex_path.parent)
        rel_str = str(rel).replace("\\", "/")
    except ValueError:
        rel_str = str(bib_filepath).replace("\\", "/")

    new_line = f"\\addbibresource{{{rel_str}}}"

    # Duplikat-Check
    if new_line in content:
        return False, f"Eintrag '{rel_str}' ist bereits in der LaTeX-Datei vorhanden."

    placement_cfg = settings.get("addbibresource_placement", {})
    search_text = ""

    # Abschnitts-Suchtext ermitteln
    if section_id:
        sections = settings.get("bib_placement_sections", [])
        sec = next((s for s in sections if s["id"] == section_id), None)
        if sec and sec.get("search_text"):
            search_text = sec["search_text"]

    if not search_text and placement_cfg.get("enabled") and placement_cfg.get("search_text"):
        search_text = placement_cfg["search_text"]

    if search_text and search_text in content:
        # Nach dem Suchtext einfügen
        idx = content.find(search_text)
        end_of_line = content.find("\n", idx)
        if end_of_line == -1:
            end_of_line = len(content)
        # Alle bestehenden \addbibresource nach dem Suchtext überspringen
        insert_pos = end_of_line + 1
        lines_after = content[insert_pos:].split("\n")
        offset = 0
        for line in lines_after:
            if line.strip().startswith("\\addbibresource"):
                offset += len(line) + 1
            else:
                break
        insert_pos += offset
        new_content = content[:insert_pos] + new_line + "\n" + content[insert_pos:]
    elif placement_cfg.get("after_last_existing", True):
        # Nach dem letzten vorhandenen \addbibresource einfügen
        matches = list(re.finditer(r"\\addbibresource\{[^}]+\}", content))
        if matches:
            last = matches[-1]
            end_of_last = content.find("\n", last.end())
            if end_of_last == -1:
                end_of_last = len(content)
            new_content = content[:end_of_last + 1] + new_line + "\n" + content[end_of_last + 1:]
        else:
            # Kein vorhandener Eintrag – ans Ende des Präambels
            begin_doc = content.find("\\begin{document}")
            if begin_doc != -1:
                new_content = content[:begin_doc] + new_line + "\n" + content[begin_doc:]
            else:
                new_content = content + "\n" + new_line + "\n"
    else:
        new_content = content + "\n" + new_line + "\n"

    with open(latex_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True, None


# ---------------------------------------------------------------------------
# Browser starten
# ---------------------------------------------------------------------------
def open_browser(port: int):
    """Öffnet Chrome bevorzugt, fallback auf Standard-Browser."""
    url = f"http://127.0.0.1:{port}"
    chrome_paths_windows = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Chromium\Application\chrome.exe",
    ]

    # Chrome versuchen
    for chrome_path in chrome_paths_windows:
        if os.path.exists(chrome_path):
            try:
                subprocess.Popen([chrome_path, f"--app={url}", "--window-size=1280,860"])
                return
            except Exception:
                pass

    # Chromium via webbrowser-Modul
    try:
        chrome = webbrowser.get("chrome")
        chrome.open(url)
        return
    except Exception:
        pass

    # Standard-Browser als Fallback
    webbrowser.open(url)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------
def main():
    port = settings.get("port", 5000)

    # Abhängigkeits-Check
    try:
        import flask  # noqa
    except ImportError:
        print("FEHLER: Flask ist nicht installiert.")
        print("Bitte ausführen: pip install flask")
        input("Drücken Sie Enter zum Beenden...")
        sys.exit(1)

    print("=" * 55)
    print("  LaTeX Quellen Manager v4.1")
    print(f"  Weboberfläche: http://127.0.0.1:{port}")
    print("  Zum Beenden: Strg+C drücken")
    print("=" * 55)

    # Browser nach einer kurzen Verzögerung öffnen
    if settings.get("auto_open_browser", True):
        t = threading.Timer(1.2, open_browser, args=[port])
        t.daemon = True
        t.start()

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
