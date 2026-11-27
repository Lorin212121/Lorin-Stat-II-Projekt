# %% [markdown]
# # Daten laden
# Lädt die Ist-Daten 2025 Monat für Monat aus dem Archiv von opentransportdata.swiss,
# filtert sie und speichert pro Monat ein kleines CSV in daten/gefiltert/.
# Ablauf pro Monat: ZIP herunterladen -> Tagesdateien filtern -> CSV speichern -> ZIP löschen.
#
# Die "# %%"-Zeilen sind Zellgrenzen. VS Code und Jupyter zeigen sie als einzelne Zellen an.

# %% Pakete
from pathlib import Path
from urllib.parse import urljoin
import re
import zipfile

import pandas as pd
import requests
from bs4 import BeautifulSoup  # falls es fehlt: pip install beautifulsoup4

# %% Einstellungen
ARCHIV_URL = "https://archive.opentransportdata.swiss/actual_data_archive.htm"
JAHR = "2025"
LINK_FILTER = "ist-daten-2025-"  # nur v1 (v1 hat alle 12 Monate, v2 erst ab Juli 2025)

ROH = Path("daten/roh")              # hier landen die ZIPs kurzzeitig
GEFILTERT = Path("daten/gefiltert")  # hier landen die kleinen Monats-CSVs
ROH.mkdir(parents=True, exist_ok=True)
GEFILTERT.mkdir(parents=True, exist_ok=True)

# Testmodus: zuerst klein anfangen! Für den vollen Lauf beide auf None setzen.
MAX_MONATE = None
MAX_TAGE = None
ZIP_LOESCHEN = True  

# Die 10 Bahnhöfe mit dem höchsten DTV 2025 (SBB Open Data, «Passagierfrequenz»).
# Gefiltert wird über die UIC-Nummer (Spalte BPUIC), so gibt es keine Probleme mit Schreibweisen.
# Der Name dient nur zur Kontrolle.
BAHNHOEFE = {
    "8503000": "Zürich HB",
    "8507000": "Bern",
    "8505000": "Luzern",
    "8506000": "Winterthur",
    "8500010": "Basel SBB",
    "8501120": "Lausanne",
    "8503006": "Zürich Oerlikon",
    "8501008": "Genève",
    "8500218": "Olten",
    "8503003": "Zürich Stadelhofen",
}

# Nur diese Spalten werden eingelesen (spart viel Zeit und Speicher).
SPALTEN = [
    "BETRIEBSTAG",
    "PRODUKT_ID",
    "LINIEN_TEXT",
    "VERKEHRSMITTEL_TEXT",
    "HALTESTELLEN_NAME",
    "BPUIC",
    "ABFAHRTSZEIT",
    "AB_PROGNOSE",
    "AB_PROGNOSE_STATUS",
    "FAELLT_AUS_TF",
    "DURCHFAHRT_TF",
]

# Diese Spalten braucht es nur zum Filtern, danach fliegen sie raus.
NUR_ZUM_FILTERN = ["PRODUKT_ID", "AB_PROGNOSE_STATUS", "FAELLT_AUS_TF", "DURCHFAHRT_TF"]


# %% Links finden
def finde_zip_links():
    """Holt die Liste der ZIP-Links für JAHR.

    Die Archivseite lädt ihre Dateiliste per JavaScript (list_dir.js) nach:
    Im HTML steht eine Variable dir = '...', und das Skript ruft dann dir + '.php' auf.
    Diese PHP-Adresse fragen wir hier direkt ab.
    """
    seite = requests.get(ARCHIV_URL, timeout=60)
    seite.raise_for_status()
    treffer = re.search(r"""dir\s*=\s*['"]([^'"]+)['"]""", seite.text)
    if not treffer:
        raise RuntimeError("Variable 'dir' nicht auf der Archivseite gefunden")
    liste_url = urljoin(ARCHIV_URL, treffer.group(1) + ".php")
    print(f"Dateiliste von: {liste_url}")

    liste = requests.get(liste_url, timeout=60)
    liste.raise_for_status()
    soup = BeautifulSoup(liste.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        url = urljoin(liste_url, a["href"])  # macht aus relativen Links ganze URLs
        if url.lower().endswith(".zip") and JAHR in url and LINK_FILTER in url:
            links.append(url)
    return sorted(set(links))


links = finde_zip_links()
print(f"{len(links)} Links gefunden:")
for link in links:
    print(link)
# Erwartet: 12 Links (einer pro Monat, Version 1).
# Sind es 0, schau dir die Adresse "Dateiliste von" im Browser an.


# %% Funktionen
def herunterladen(url, ziel):
    """Lädt eine grosse Datei Stück für Stück herunter."""
    if ziel.exists():
        print(f"  {ziel.name} ist schon da, Download übersprungen")
        return
    teil = ziel.with_suffix(".part")  # erst unter anderem Namen, damit ein Abbruch keine halbe ZIP hinterlässt
    with requests.get(url, stream=True, timeout=120) as antwort:
        antwort.raise_for_status()
        with open(teil, "wb") as f:
            for stueck in antwort.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(stueck)
    teil.rename(ziel)


def ist_wahr(spalte):
    """FAELLT_AUS_TF / DURCHFAHRT_TF enthalten 'true'/'false' als Text."""
    return spalte.fillna("").str.strip().str.lower().eq("true")


def filtere(df):
    """Behält nur die Zeilen, die wir für die Analyse brauchen."""
    df = df[df["BPUIC"].fillna("").str.strip().isin(BAHNHOEFE.keys())]
    df = df[df["PRODUKT_ID"].fillna("").str.strip().str.lower().eq("zug")]
    df = df[df["AB_PROGNOSE_STATUS"].fillna("").str.strip().str.upper().eq("REAL")]
    df = df[~ist_wahr(df["FAELLT_AUS_TF"])]
    df = df[~ist_wahr(df["DURCHFAHRT_TF"])]
    df = df[df["ABFAHRTSZEIT"].notna() & df["AB_PROGNOSE"].notna()]  # nur echte Abfahrten
    return df.drop(columns=NUR_ZUM_FILTERN)


def verarbeite_tagesdatei(z, name):
    """Liest eine Tagesdatei aus der offenen ZIP in Häppchen und filtert jedes Häppchen sofort."""
    teile = []
    with z.open(name) as f:
        for chunk in pd.read_csv(f, sep=";", usecols=SPALTEN, dtype=str, chunksize=500_000):
            teile.append(filtere(chunk))
    return pd.concat(teile, ignore_index=True)


def verarbeite_monat(zip_pfad, ziel_csv):
    """Geht durch alle Tagesdateien einer Monats-ZIP und schreibt ein gefiltertes CSV."""
    tage = []
    with zipfile.ZipFile(zip_pfad) as z:  # "with" schliesst die ZIP am Ende automatisch
        namen = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))
        if MAX_TAGE:
            namen = namen[:MAX_TAGE]
        for name in namen:
            try:
                tag = verarbeite_tagesdatei(z, name)
                tage.append(tag)
                print(f"  {name}: {len(tag):,} Zeilen behalten")
            except Exception as fehler:
                print(f"  FEHLER bei {name}: {fehler}")  # eine kaputte Datei stoppt nicht alles
    monat = pd.concat(tage, ignore_index=True)
    temp = ziel_csv.with_suffix(".tmp")
    monat.to_csv(temp, index=False)
    temp.rename(ziel_csv)  # erst am Schluss umbenennen: existiert die Datei, ist sie vollständig
    return len(monat)


# %% Hauptschleife
for url in links[:MAX_MONATE]:
    zip_pfad = ROH / url.split("/")[-1]
    ziel_csv = GEFILTERT / (zip_pfad.stem + ".csv")

    if ziel_csv.exists():
        print(f"{ziel_csv.name} ist schon fertig, übersprungen")
        continue

    print(f"Monat {zip_pfad.name}")
    herunterladen(url, zip_pfad)
    anzahl = verarbeite_monat(zip_pfad, ziel_csv)
    print(f"  -> {ziel_csv.name} gespeichert ({anzahl:,} Zeilen)")

    if ZIP_LOESCHEN:
        zip_pfad.unlink()  # erst löschen, nachdem das CSV sicher geschrieben ist
        print(f"  {zip_pfad.name} gelöscht")

print("Fertig.")


# %% Bahnhöfe prüfen (einmal laufen lassen, nachdem die erste ZIP da ist)
def pruefe_bahnhoefe(zip_pfad):
    """Zeigt für jede UIC-Nummer, wie der Bahnhof in den Ist-Daten heisst und wie viele Zeilen es gibt."""
    with zipfile.ZipFile(zip_pfad) as z:
        name = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))[0]
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", usecols=["BPUIC", "HALTESTELLEN_NAME", "PRODUKT_ID"], dtype=str)
    df = df[df["PRODUKT_ID"].fillna("").str.strip().str.lower().eq("zug")]
    df["BPUIC"] = df["BPUIC"].fillna("").str.strip()
    for uic, erwartet in BAHNHOEFE.items():
        treffer = df[df["BPUIC"] == uic]
        namen = treffer["HALTESTELLEN_NAME"].unique().tolist()
        print(f"{uic} {erwartet:20} -> {len(treffer):6,} Zeilen, Name in den Daten: {namen}")
    # Steht bei einem Bahnhof 0 Zeilen, stimmt die Nummer nicht oder BPUIC ist anders formatiert.


# pruefe_bahnhoefe(next(ROH.glob("*.zip")))